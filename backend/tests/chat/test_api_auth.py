from fastapi.testclient import TestClient

from quaestor.api.deps import require_auth


def test_chat_requires_auth(app):
    # `app` fixture bypasses require_auth by default; drop the override so the
    # real auth check runs (and rejects this unauthenticated request).
    test_app, _ = app
    test_app.dependency_overrides.pop(require_auth, None)
    client = TestClient(test_app)
    r = client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 401


def test_chat_accepts_valid_bearer(app, auth_headers):
    test_app, stub = app
    client = TestClient(test_app)
    r = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "hi"}]},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
