import json

from quaestor.chat.events import done_bytes, render_sse, serialize_event
from quaestor.chat.llm.provider import LLMEvent, LLMEventType


def _data(text: bytes) -> dict:
    # Strip "data: " prefix and trailing "\n\n"
    assert text.startswith(b"data: "), text
    return json.loads(text.removeprefix(b"data: ").rstrip(b"\n").decode("utf-8"))


def test_serialize_message_start():
    ev = LLMEvent(
        type=LLMEventType.MESSAGE_START, message_id="msg_1", model="MiniMax-M3"
    )
    out = _data(serialize_event(ev, message_id="msg_1"))
    assert out == {"type": "start", "messageId": "msg_1"}


def test_serialize_text_delta():
    ev = LLMEvent(type=LLMEventType.TEXT_DELTA, delta="hola")
    out = _data(serialize_event(ev, message_id="m"))
    assert out == {"type": "text-delta", "id": "m", "delta": "hola"}


def test_serialize_text_start_and_end_share_content_index():
    start = _data(serialize_event(LLMEvent(type=LLMEventType.TEXT_START, content_index=0), message_id="m"))
    end = _data(serialize_event(LLMEvent(type=LLMEventType.TEXT_END, content_index=0), message_id="m"))
    assert start == {"type": "text-start", "id": "m"}
    assert end == {"type": "text-end", "id": "m"}


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


def test_serialize_tool_output_available_with_error():
    ev = LLMEvent(
        type=LLMEventType.TOOL_OUTPUT_AVAILABLE,
        tool_call_id="tc_1",
        output="account not found",
        is_error=True,
    )
    out = _data(serialize_event(ev, message_id="m"))
    assert out["type"] == "tool-output-available"
    assert out["toolCallId"] == "tc_1"
    assert out["output"] == "account not found"
    assert out["isError"] is True


def test_serialize_step_finish_and_message_finish():
    step = _data(serialize_event(LLMEvent(type=LLMEventType.STEP_FINISH), message_id="m"))
    assert step == {"type": "finish-step"}
    msg = _data(
        serialize_event(
            LLMEvent(type=LLMEventType.MESSAGE_FINISH, stop_reason="end_turn", iterations=2),
            message_id="m",
        )
    )
    assert msg == {"type": "finish", "finishReason": "end_turn"}


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
