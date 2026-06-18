import os

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from quaestor.api import create_app
from quaestor.api.deps import get_session
from quaestor.db import init_db, make_engine


@pytest.fixture
def engine():
    eng = make_engine(memory=True)
    init_db(eng)
    return eng


@pytest.fixture
def client(engine, monkeypatch):
    monkeypatch.setenv("APP_TOKEN", "test-token")
    monkeypatch.setenv("APP_PASSWORD", "test-password")
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:3000")
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    app = create_app()

    def override_get_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app)


@pytest.fixture
def auth():
    return {"Authorization": "Bearer test-token"}
