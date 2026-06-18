import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from quaestor.mcp.auth import BearerAuthMiddleware, token_ok


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("APP_TOKEN", "secret-token")

    async def ok(request):
        return PlainTextResponse("ok")

    application = Starlette(routes=[Route("/mcp", ok, methods=["GET", "POST"])])
    application.add_middleware(BearerAuthMiddleware)
    return application


def test_token_ok_accepts_matching_bearer(monkeypatch):
    monkeypatch.setenv("APP_TOKEN", "secret-token")
    assert token_ok("Bearer secret-token") is True


def test_token_ok_rejects_missing_wrong_or_unset(monkeypatch):
    monkeypatch.setenv("APP_TOKEN", "secret-token")
    assert token_ok(None) is False
    assert token_ok("secret-token") is False  # no scheme
    assert token_ok("Bearer wrong") is False
    monkeypatch.delenv("APP_TOKEN", raising=False)
    assert token_ok("Bearer secret-token") is False  # server has no token configured


def test_request_without_token_is_401(app):
    client = TestClient(app)
    assert client.get("/mcp").status_code == 401


def test_request_with_wrong_token_is_401(app):
    client = TestClient(app)
    resp = client.get("/mcp", headers={"Authorization": "Bearer nope"})
    assert resp.status_code == 401
    assert resp.json()["error"] == "Unauthorized"


def test_request_with_valid_token_passes_through(app):
    client = TestClient(app)
    resp = client.get("/mcp", headers={"Authorization": "Bearer secret-token"})
    assert resp.status_code == 200
    assert resp.text == "ok"
