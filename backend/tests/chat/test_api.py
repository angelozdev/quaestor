"""End-to-end POST /api/chat via TestClient with a stub LLMProvider."""
from __future__ import annotations

from quaestor.chat.llm.provider import LLMEvent, LLMEventType


def test_happy_path_streams_text_and_done(app, auth_headers, client):
    _test_app, stub = app
    stub.events = [
        LLMEvent(type=LLMEventType.MESSAGE_START, message_id="m1", model="MiniMax-M3"),
        LLMEvent(type=LLMEventType.TEXT_START, content_index=0),
        LLMEvent(type=LLMEventType.TEXT_DELTA, delta="Hola"),
        LLMEvent(type=LLMEventType.TEXT_END, content_index=0),
        LLMEvent(type=LLMEventType.STEP_FINISH),
        LLMEvent(type=LLMEventType.MESSAGE_FINISH, stop_reason="stop", iterations=1),
    ]
    with client.stream(
        "POST",
        "/api/chat",
        json={"messages": [{"role": "user", "content": "hola"}]},
        headers=auth_headers,
    ) as r:
        assert r.status_code == 200
        assert r.headers["x-vercel-ai-ui-message-stream"] == "v1"
        assert r.headers["content-type"].startswith("text/event-stream")
        body = b"".join(r.iter_bytes())
    assert b"data: [DONE]" in body
    assert b'"type":"start"' in body
    assert b'"type":"text-delta"' in body and b'"delta":"Hola"' in body
    assert b'"type":"finish"' in body
