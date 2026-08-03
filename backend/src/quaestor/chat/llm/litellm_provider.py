"""LiteLLMProvider — concrete LLMProvider implementation.

Reads `chunk.choices[0].delta` (LiteLLM normalizes every provider into this
shape). Tool-call deltas are accumulated per `index` and emitted as
TOOL_INPUT_START → TOOL_INPUT_DELTA* → TOOL_INPUT_AVAILABLE once
`finish_reason` arrives.
"""
from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import litellm

from .provider import LLMEvent, LLMEventType, UpstreamLLMError

# Map LiteLLM raised exceptions to our UpstreamLLMError. Keep the original
# message verbatim for server-side logs.
_LITELLM_UPSTREAM_ERRORS: tuple[type[BaseException], ...] = (
    litellm.APIError,
    litellm.AuthenticationError,
    litellm.RateLimitError,
    litellm.Timeout,
    litellm.ServiceUnavailableError,
)


class LiteLLMProvider:
    """Streamed chat over LiteLLM. See module docstring."""

    def __init__(self, model: str, api_key: str | None, base_url: str | None) -> None:
        self._model = model
        self._api_key = api_key
        self._base_url = base_url

    async def stream(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AsyncIterator[LLMEvent]:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools
        if self._api_key:
            kwargs["api_key"] = self._api_key
        if self._base_url:
            kwargs["base_url"] = self._base_url

        # Track per-tool-call state across chunks.
        # accumulated[idx] = {"id": str|None, "name": str|None, "args_buf": str, "started": bool}
        accumulated: dict[int, dict[str, Any]] = {}
        text_started = False
        # Token usage, captured from the last chunk that carries `.usage`.
        # Normalized to Vercel wire keys. None = provider didn't report.
        last_usage: dict[str, int] | None = None

        # Vercel UI Message Stream spec: `messageId` is the opaque identifier
        # of the whole message. Generate it locally with uuid4 so the value
        # is uniform regardless of whether the upstream provider attaches
        # `.id` to chunks (OpenAI does, Anthropic native does not).
        message_id = f"msg-{uuid.uuid4().hex}"

        try:
            response = await litellm.acompletion(**kwargs)
        except _LITELLM_UPSTREAM_ERRORS as exc:
            raise UpstreamLLMError(str(exc)) from exc

        try:
            yield LLMEvent(
                type=LLMEventType.MESSAGE_START,
                message_id=message_id,
                model=self._model,
            )
            async for chunk in response:
                # Capture token usage from any chunk that carries it. LiteLLM
                # normalizes usage onto the final chunk for both OpenAI and
                # Anthropic, but we accept it from any chunk in case other
                # providers stream it earlier. Last write wins.
                chunk_usage = getattr(chunk, "usage", None)
                if chunk_usage is not None:
                    usage_payload: dict[str, int] = {}
                    prompt = getattr(chunk_usage, "prompt_tokens", None)
                    completion = getattr(chunk_usage, "completion_tokens", None)
                    total = getattr(chunk_usage, "total_tokens", None)
                    if prompt is not None:
                        usage_payload["promptTokens"] = prompt
                    if completion is not None:
                        usage_payload["completionTokens"] = completion
                    if total is not None:
                        usage_payload["totalTokens"] = total
                    if usage_payload:
                        last_usage = usage_payload

                choice = chunk.choices[0]
                delta = choice.delta

                # --- text streaming ---------------------------------------------
                content_piece: str | None = getattr(delta, "content", None)
                if content_piece:
                    if not text_started:
                        text_started = True
                        yield LLMEvent(type=LLMEventType.TEXT_START, content_index=0)
                    yield LLMEvent(type=LLMEventType.TEXT_DELTA, delta=content_piece)

                # --- tool-call streaming ----------------------------------------
                raw_tool_calls = getattr(delta, "tool_calls", None) or []
                for tc in raw_tool_calls:
                    idx = tc.index
                    slot = accumulated.setdefault(
                        idx,
                        {"id": None, "name": None, "args_buf": "", "started": False},
                    )
                    if tc.id and slot["id"] is None:
                        slot["id"] = tc.id
                    func = getattr(tc, "function", None)
                    if func is not None:
                        if func.name and slot["name"] is None:
                            slot["name"] = func.name
                            if not slot["started"]:
                                slot["started"] = True
                                yield LLMEvent(
                                    type=LLMEventType.TOOL_INPUT_START,
                                    tool_call_id=slot["id"],
                                    tool_name=slot["name"],
                                )
                        if func.arguments:
                            slot["args_buf"] += func.arguments
                            yield LLMEvent(
                                type=LLMEventType.TOOL_INPUT_DELTA,
                                tool_call_id=slot["id"],
                                arguments_delta=func.arguments,
                            )

                # --- finish reason: flush tool calls / close text ---------------
                if choice.finish_reason:
                    if text_started:
                        yield LLMEvent(type=LLMEventType.TEXT_END, content_index=0)
                    for idx, slot in sorted(accumulated.items()):
                        # Parse accumulated arguments; if it's malformed JSON,
                        # surface it as an error rather than dropping the call.
                        try:
                            args_obj: Any = (
                                json.loads(slot["args_buf"]) if slot["args_buf"].strip() else {}
                            )
                        except json.JSONDecodeError as exc:
                            raise UpstreamLLMError(
                                f"tool_call {slot['id']} arguments not valid JSON: {exc}"
                            ) from exc
                        if not isinstance(args_obj, dict):
                            args_obj = {"value": args_obj}
                        yield LLMEvent(
                            type=LLMEventType.TOOL_INPUT_AVAILABLE,
                            tool_call_id=slot["id"],
                            tool_name=slot["name"] or "",
                            arguments=args_obj,
                        )
                    yield LLMEvent(type=LLMEventType.STEP_FINISH)
                    yield LLMEvent(
                        type=LLMEventType.MESSAGE_FINISH,
                        stop_reason=_to_vercel_finish_reason(choice.finish_reason),
                        iterations=1,
                        usage=last_usage,
                    )
        except _LITELLM_UPSTREAM_ERRORS as exc:
            # Mid-stream upstream failure (e.g. SSE cut, 5xx mid-response).
            raise UpstreamLLMError(str(exc)) from exc


# Vercel AI SDK UI Message Stream `finishReason` enum (the SSE wire format
# the frontend's `useChat` validates against). See ai-sdk.dev/docs/ai-sdk-ui/
# stream-protocol#finish-event. The renderer (events.py) is dumb on purpose
# — all provider-specific values are normalized HERE, so the renderer can
# trust whatever stop_reason it receives.
_VERCEL_FINISH_REASON = "stop"


def _to_vercel_finish_reason(raw: Any) -> str:
    """Map a LiteLLM/OpenAI/Anthropic `finish_reason` to a Vercel-spec value.

    Vercel's enum: `stop | length | content-filter | tool-calls | error | other`.

    Common raw values we see in the wild:
      LiteLLM/OpenAI: `stop`, `length`, `tool_calls`, `content_filter`, `null`.
      Anthropic direct: `end_turn`, `max_tokens`, `tool_use`, `stop_sequence`.
    """
    if raw is None:
        return _VERCEL_FINISH_REASON
    s = str(raw)
    if s == "stop" or s == "end_turn" or s == "stop_sequence":
        return "stop"
    if s == "length" or s == "max_tokens":
        return "length"
    if s == "tool_calls" or s == "tool_use":
        return "tool-calls"
    if s == "content_filter":
        return "content-filter"
    if s == "error":
        return "error"
    return "other"
