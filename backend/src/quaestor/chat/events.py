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


def serialize_event(event: LLMEvent, *, message_id: str) -> bytes:
    """Translate one LLMEvent to SSE bytes. Field names follow the Vercel
    UI Message Stream protocol exactly (`messageId`, `toolCallId`,
    `toolName`, `input`, `isError`, `finishReason`, `errorText`, `id`).
    """
    t = event.type
    if t == LLMEventType.MESSAGE_START:
        return render_sse({"type": "start", "messageId": message_id})

    if t == LLMEventType.TEXT_START:
        return render_sse({"type": "text-start", "id": message_id})

    if t == LLMEventType.TEXT_DELTA:
        return render_sse({"type": "text-delta", "id": message_id, "delta": event.delta or ""})

    if t == LLMEventType.TEXT_END:
        return render_sse({"type": "text-end", "id": message_id})

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
        payload: dict[str, Any] = {
            "type": "tool-output-available",
            "toolCallId": event.tool_call_id,
            "output": event.output or "",
        }
        if event.is_error:
            payload["isError"] = True
        return render_sse(payload)

    if t == LLMEventType.STEP_FINISH:
        return render_sse({"type": "finish-step"})

    if t == LLMEventType.MESSAGE_FINISH:
        return render_sse({"type": "finish", "finishReason": event.stop_reason or "end_turn"})

    if t == LLMEventType.ERROR:
        return render_sse({"type": "error", "errorText": event.message or "unknown error"})

    raise ValueError(f"unhandled LLMEventType: {t!r}")
