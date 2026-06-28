"""SSE wire format for the chat endpoint.

We emit the Vercel AI SDK UI Message Stream (verified against
`ai-sdk.dev/docs/ai-sdk-ui/stream-protocol`): a `text/event-stream` body
where each event's `data:` line is a JSON object with a `type` field whose
value identifies the part (`start`, `text-start`, `text-delta`,
`tool-input-start`, `tool-input-available`, `tool-output-available`,
`finish-step`, `finish`, `error`, …). Termination is the literal
`data: [DONE]\\n\\n`.

Each dataclass-style event is rendered as one `data:` line — the SSE `event:`
field is intentionally NOT used because the consumer identifies events by
the JSON `type`.
"""
from __future__ import annotations

import json
from typing import Any

from .llm.provider import LLMEvent, LLMEventType


def render_sse(payload: dict[str, Any]) -> bytes:
    """Render one SSE message: `data: <json>\\n\\n`."""
    return f"data: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n\n".encode("utf-8")


def done_bytes() -> bytes:
    """The literal `[DONE]` sentinel Vercel's parser uses to end a stream."""
    return b"data: [DONE]\n\n"


# Per the Vercel UI Message Stream spec, the `id` of a text-* event is a
# per-part content id (stable across text-start/text-delta/text-end of the
# same text part). It must NOT collide with `messageId`. We currently emit
# exactly one text part per turn, so a constant suffices; revisit when we
# add parallel parts (e.g. reasoning + answer).
TEXT_PART_ID = "text-1"


def serialize_event(event: LLMEvent, *, message_id: str) -> bytes:
    """Translate one LLMEvent to SSE bytes. Field names follow the Vercel
    UI Message Stream protocol exactly (`messageId`, `toolCallId`,
    `toolName`, `input`, `isError`, `finishReason`, `errorText`, `id`).
    """
    t = event.type
    if t == LLMEventType.MESSAGE_START:
        return render_sse({"type": "start", "messageId": message_id})

    if t == LLMEventType.TEXT_START:
        return render_sse({"type": "text-start", "id": TEXT_PART_ID})

    if t == LLMEventType.TEXT_DELTA:
        return render_sse({"type": "text-delta", "id": TEXT_PART_ID, "delta": event.delta or ""})

    if t == LLMEventType.TEXT_END:
        return render_sse({"type": "text-end", "id": TEXT_PART_ID})

    if t == LLMEventType.TOOL_INPUT_START:
        assert event.tool_call_id is not None
        assert event.tool_name is not None
        return render_sse(
            {
                "type": "tool-input-start",
                "toolCallId": event.tool_call_id,
                "toolName": event.tool_name,
            }
        )

    if t == LLMEventType.TOOL_INPUT_DELTA:
        assert event.tool_call_id is not None
        return render_sse(
            {
                "type": "tool-input-delta",
                "toolCallId": event.tool_call_id,
                "inputTextDelta": event.arguments_delta or "",
            }
        )

    if t == LLMEventType.TOOL_INPUT_AVAILABLE:
        assert event.tool_call_id is not None
        assert event.tool_name is not None
        return render_sse(
            {
                "type": "tool-input-available",
                "toolCallId": event.tool_call_id,
                "toolName": event.tool_name,
                "input": event.arguments or {},
            }
        )

    if t == LLMEventType.TOOL_OUTPUT_AVAILABLE:
        assert event.tool_call_id is not None
        # Success-only emit path. Tool failures route through
        # TOOL_OUTPUT_ERROR (ADR-0022). The `is_error` field on this
        # variant would be rejected by the AI SDK v3 React client's
        # strict `uiMessageChunkSchema` (see
        # `frontend/node_modules/ai/dist/index.mjs:5463-5472`).
        return render_sse(
            {
                "type": "tool-output-available",
                "toolCallId": event.tool_call_id,
                "output": event.output or "",
            }
        )

    if t == LLMEventType.TOOL_OUTPUT_ERROR:
        assert event.tool_call_id is not None
        assert event.error_text is not None
        return render_sse(
            {
                "type": "tool-output-error",
                "toolCallId": event.tool_call_id,
                "errorText": event.error_text,
            }
        )

    if t == LLMEventType.STEP_FINISH:
        return render_sse({"type": "finish-step"})

    if t == LLMEventType.MESSAGE_FINISH:
        # Renderer is dumb by design: the LLMProvider maps provider-specific
        # finish_reason to the Vercel spec enum (`stop | length | content-filter
        # | tool-calls | error | other`). Defaulting to "stop" covers the rare
        # case where a scripted test or stub provider doesn't set it.
        # `messageMetadata.usage` is omitted when the provider didn't report
        # usage (additive contract; never breaks older clients).
        payload: dict[str, Any] = {
            "type": "finish",
            "finishReason": event.stop_reason or "stop",
        }
        if event.usage:
            payload["messageMetadata"] = {"usage": event.usage}
        return render_sse(payload)

    if t == LLMEventType.ERROR:
        return render_sse({"type": "error", "errorText": event.message or "unknown error"})

    raise ValueError(f"unhandled LLMEventType: {t!r}")
