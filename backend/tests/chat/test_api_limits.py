import pytest
from fastapi.testclient import TestClient


def _oversize_content(n_chars: int) -> dict:
    return {"messages": [{"role": "user", "content": "x" * n_chars}]}


def test_too_many_messages_returns_413(app):
    test_app, _ = app
    client = TestClient(test_app)
    body = {"messages": [{"role": "user", "content": "x"} for _ in range(201)]}
    r = client.post("/api/chat", json=body)
    assert r.status_code == 413


def test_message_content_too_large_returns_413(app):
    test_app, _ = app
    client = TestClient(test_app)
    r = client.post("/api/chat", json=_oversize_content(33_000))
    assert r.status_code == 413


def test_total_token_estimate_too_large_returns_413(app):
    test_app, _ = app
    client = TestClient(test_app)
    # 201 * 2000 chars = 402_000 chars // 4 = 100_500 tokens (> 100k).
    body = {"messages": [{"role": "user", "content": "x" * 2000} for _ in range(201)]}
    r = client.post("/api/chat", json=body)
    assert r.status_code == 413


def test_malformed_body_returns_400(app):
    test_app, _ = app
    client = TestClient(test_app)
    r = client.post("/api/chat", json={"messages": "not-a-list"})
    assert r.status_code in (400, 422)


def test_unknown_role_returns_422(app):
    test_app, _ = app
    client = TestClient(test_app)
    r = client.post("/api/chat", json={"messages": [{"role": "wizard", "content": "x"}]})
    assert r.status_code == 422
