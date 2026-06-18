"""Behavior: a freshly-built app initializes its own schema on startup, so
`uvicorn quaestor.api:app` serves a fresh DB without a manual init_db step."""
from fastapi.testclient import TestClient

from quaestor import db
from quaestor.api import create_app
from quaestor.db import make_engine


def test_app_initializes_schema_on_startup(monkeypatch):
    # A fresh engine with NO tables created (init_db is NOT called here).
    fresh = make_engine(memory=True)
    monkeypatch.setattr(db, "engine", fresh)
    monkeypatch.setenv("APP_TOKEN", "test-token")
    monkeypatch.setenv("SESSION_SECRET", "test-secret")

    # Using TestClient as a context manager fires the lifespan, which must
    # create the schema. No dependency_overrides: the real get_session runs.
    with TestClient(create_app()) as client:
        resp = client.get(
            "/api/accounts", headers={"Authorization": "Bearer test-token"}
        )
        assert resp.status_code == 200
        assert resp.json() == []
