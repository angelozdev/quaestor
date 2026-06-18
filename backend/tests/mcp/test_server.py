import pytest
from starlette.testclient import TestClient

from quaestor import db
from quaestor.mcp import server


@pytest.fixture
def app(monkeypatch, engine):
    monkeypatch.setenv("APP_TOKEN", "test-token")
    monkeypatch.setattr(db, "engine", engine)  # build_app() calls init_db(db.engine)
    return server.build_app()


def test_mcp_requires_bearer_token(app):
    with TestClient(app) as client:
        # No Authorization header → rejected by middleware before the transport.
        assert client.post("/mcp").status_code == 401


def test_mcp_rejects_wrong_token(app):
    with TestClient(app) as client:
        resp = client.post("/mcp", headers={"Authorization": "Bearer nope"})
        assert resp.status_code == 401


def test_mcp_valid_token_passes_auth_layer(app):
    with TestClient(app) as client:
        # A bare POST won't complete the MCP handshake, but it must clear auth:
        # any status other than 401 proves the bearer gate let it through.
        resp = client.post(
            "/mcp",
            headers={
                "Authorization": "Bearer test-token",
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
        )
        assert resp.status_code != 401


def test_build_mcp_registers_core_tools():
    import asyncio

    from quaestor.mcp.registry import CORE_TOOL_NAMES

    mcp = server.build_mcp()
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert set(CORE_TOOL_NAMES) <= names
