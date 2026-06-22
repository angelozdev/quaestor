"""LiteLLMProvider — concrete LLMProvider implementation.

Reads `chunk.choices[0].delta` (LiteLLM normalizes every provider into this
shape). Tool-call deltas are accumulated per `index` and emitted as
TOOL_INPUT_START → TOOL_INPUT_DELTA* → TOOL_INPUT_AVAILABLE once
`finish_reason` arrives.
"""
from __future__ import annotations

import json
import os
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
        message_id: str | None = None
        text_started = False

        try:
            response = await litellm.acompletion(**kwargs)
        except _LITELLM_UPSTREAM_ERRORS as exc:
            raise UpstreamLLMError(str(exc)) from exc

        try:
            async for chunk in response:
                if message_id is None:
                    message_id = getattr(chunk, "id", None) or "msg_unknown"
                    yield LLMEvent(
                        type=LLMEventType.MESSAGE_START,
                        message_id=message_id,
                        model=self._model,
                    )

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
                        stop_reason=str(choice.finish_reason),
                        iterations=1,
                    )
        except _LITELLM_UPSTREAM_ERRORS as exc:
            # Mid-stream upstream failure (e.g. SSE cut, 5xx mid-response).
            raise UpstreamLLMError(str(exc)) from exc
