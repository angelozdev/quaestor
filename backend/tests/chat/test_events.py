import json

from quaestor.chat.events import done_bytes, render_sse, serialize_event
from quaestor.chat.llm.provider import LLMEvent, LLMEventType


def _data(text: bytes) -> dict:
    # Strip "data: " prefix and trailing "\n\n"
    assert text.startswith(b"data: "), text
    return json.loads(text.removeprefix(b"data: ").rstrip(b"\n").decode("utf-8"))


def test_serialize_message_start():
    ev = LLMEvent(type=LLMEventType.MESSAGE_START, message_id="msg_1", model="MiniMax-M3")
    out = _data(serialize_event(ev, message_id="msg_1"))
    assert out == {"type": "start", "messageId": "msg_1"}


def test_serialize_text_delta_uses_text_part_id_not_message_id():
    """The `id` of a text-* event is the per-part content id (`text-1`),
    NOT the message id. Per the Vercel UI Message Stream spec, useChat()
    matches deltas to a part by id."""
    ev = LLMEvent(type=LLMEventType.TEXT_DELTA, delta="hola")
    out = _data(serialize_event(ev, message_id="msg_abc"))
    assert out == {"type": "text-delta", "id": "text-1", "delta": "hola"}
    assert out["id"] != out["messageId"] if "messageId" in out else True
    # The "id" must NOT equal the message id we passed in.
    assert out["id"] != "msg_abc"


def test_serialize_text_start_and_end_share_text_part_id():
    start = _data(serialize_event(LLMEvent(type=LLMEventType.TEXT_START, content_index=0), message_id="msg_abc"))
    delta = _data(
        serialize_event(LLMEvent(type=LLMEventType.TEXT_DELTA, content_index=0, delta="x"), message_id="msg_abc")
    )
    end = _data(serialize_event(LLMEvent(type=LLMEventType.TEXT_END, content_index=0), message_id="msg_abc"))
    assert start == {"type": "text-start", "id": "text-1"}
    assert delta["id"] == "text-1"
    assert end == {"type": "text-end", "id": "text-1"}
    # None of them carry the message id.
    for ev in (start, delta, end):
        assert ev["id"] != "msg_abc"


def test_serialize_tool_input_start():
    ev = LLMEvent(type=LLMEventType.TOOL_INPUT_START, tool_call_id="tc_1", tool_name="list_transactions")
    out = _data(serialize_event(ev, message_id="m"))
    assert out == {"type": "tool-input-start", "toolCallId": "tc_1", "toolName": "list_transactions"}


def test_serialize_tool_input_available():
    ev = LLMEvent(
        type=LLMEventType.TOOL_INPUT_AVAILABLE,
        tool_call_id="tc_1",
        tool_name="list_transactions",
        arguments={"date_from": "2026-06-01"},
    )
    out = _data(serialize_event(ev, message_id="m"))
    assert out == {
        "type": "tool-input-available",
        "toolCallId": "tc_1",
        "toolName": "list_transactions",
        "input": {"date_from": "2026-06-01"},
    }


def test_serialize_tool_output_available_strips_is_error():
    """`tool-output-available` is success-only (ADR-0022). The renderer must
    never inject an `isError` field — if the upstream `LLMEvent` carries
    `is_error=True`, the renderer ignores it and emits the strict success
    shape `{type, toolCallId, output}`."""
    ev = LLMEvent(
        type=LLMEventType.TOOL_OUTPUT_AVAILABLE,
        tool_call_id="tc_1",
        output="account not found",
        is_error=True,
    )
    out = _data(serialize_event(ev, message_id="m"))
    assert out == {"type": "tool-output-available", "toolCallId": "tc_1", "output": "account not found"}
    assert "isError" not in out


def test_serialize_tool_output_error_emits_error_text():
    """Tool failures use the dedicated `tool-output-error` chunk
    (ADR-0022). The renderer carries `errorText` (camelCase) on the
    wire — NOT `isError` on `tool-output-available`."""
    ev = LLMEvent(
        type=LLMEventType.TOOL_OUTPUT_ERROR,
        tool_call_id="tc_1",
        error_text="account not found",
    )
    out = _data(serialize_event(ev, message_id="m"))
    assert out == {
        "type": "tool-output-error",
        "toolCallId": "tc_1",
        "errorText": "account not found",
    }


def test_serialize_step_finish_and_message_finish():
    step = _data(serialize_event(LLMEvent(type=LLMEventType.STEP_FINISH), message_id="m"))
    assert step == {"type": "finish-step"}
    msg = _data(
        serialize_event(
            LLMEvent(type=LLMEventType.MESSAGE_FINISH, stop_reason="stop", iterations=2),
            message_id="m",
        )
    )
    assert msg == {"type": "finish", "finishReason": "stop"}


def test_serialize_message_finish_defaults_to_stop():
    """Renderer default fallback must be a Vercel-spec value, not `end_turn`."""
    msg = _data(
        serialize_event(
            LLMEvent(type=LLMEventType.MESSAGE_FINISH, iterations=1),
            message_id="m",
        )
    )
    assert msg == {"type": "finish", "finishReason": "stop"}


def test_serialize_error_event():
    ev = LLMEvent(type=LLMEventType.ERROR, code="upstream", message="boom", retryable=True)
    out = _data(serialize_event(ev, message_id="m"))
    assert out == {"type": "error", "errorText": "boom"}


def test_render_sse_wraps_payload_with_data_prefix():
    out = render_sse({"type": "ping"})
    assert out.startswith(b"data: ")
    assert out.endswith(b"\n\n")
    assert json.loads(out.removeprefix(b"data: ").rstrip(b"\n")) == {"type": "ping"}


def test_done_bytes_literal():
    assert done_bytes() == b"data: [DONE]\n\n"


def test_serialize_message_finish_with_usage_includes_message_metadata():
    """When usage is present, emit messageMetadata.usage on the finish event
    so the frontend can display token counts and ops can reconcile billing."""
    ev = LLMEvent(
        type=LLMEventType.MESSAGE_FINISH,
        stop_reason="stop",
        iterations=1,
        usage={"promptTokens": 10, "completionTokens": 5, "totalTokens": 15},
    )
    out = _data(serialize_event(ev, message_id="m"))
    assert out == {
        "type": "finish",
        "finishReason": "stop",
        "messageMetadata": {"usage": {"promptTokens": 10, "completionTokens": 5, "totalTokens": 15}},
    }


def test_serialize_message_finish_without_usage_omits_message_metadata():
    """When usage is None (provider didn't report), the wire shape is unchanged
    from before this fix — additive, not breaking."""
    ev = LLMEvent(type=LLMEventType.MESSAGE_FINISH, stop_reason="stop", iterations=1)
    out = _data(serialize_event(ev, message_id="m"))
    assert out == {"type": "finish", "finishReason": "stop"}
    assert "messageMetadata" not in out
