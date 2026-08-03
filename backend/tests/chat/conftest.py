import pytest
from fastapi.testclient import TestClient
from quaestor.api import create_app
from quaestor.api.csrf import CSRF_COOKIE, CSRF_HEADER
from quaestor.db import init_db, make_engine
from quaestor.services import accounts, categories
from sqlmodel import Session

_STATE_CHANGING = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class CSRFTestClient(TestClient):
    """Mirrors the CSRF cookie into X-CSRF-Token, like the real browser.
    Patches both `request()` and `stream()` because httpx.Client.stream
    bypasses `request()` and goes straight to `send()`."""

    def _prime_and_inject(self, method: str, kwargs: dict) -> dict:
        if method.upper() in _STATE_CHANGING and not self.cookies.get(CSRF_COOKIE):
            TestClient.get(self, "/api/auth/me")
        if method.upper() in _STATE_CHANGING:
            token = self.cookies.get(CSRF_COOKIE)
            if token:
                headers = dict(kwargs.pop("headers", None) or {})
                headers.setdefault(CSRF_HEADER, token)
                kwargs["headers"] = headers
        return kwargs

    def request(self, method, url, **kwargs):  # type: ignore[override]
        kwargs = self._prime_and_inject(method, kwargs)
        return super().request(method, url, **kwargs)

    def stream(self, method, url, **kwargs):  # type: ignore[override]
        kwargs = self._prime_and_inject(method, kwargs)
        return super().stream(method, url, **kwargs)


@pytest.fixture
def engine():
    eng = make_engine(memory=True)
    init_db(eng)
    return eng


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s


@pytest.fixture
def seeded(session):
    account = accounts.create_account(session, "Bancolombia", "debit", "COP", balance=10_000_000)
    category = categories.create_category(session, "Groceries")
    return {"account": account, "category": category}


@pytest.fixture
def app(monkeypatch, engine):
    """A TestClient app bound to the in-memory engine and a stub LLM."""
    from collections.abc import AsyncIterator
    from typing import Any

    from quaestor.api.deps import require_auth
    from quaestor.chat.llm.provider import LLMEvent, LLMProvider

    class StubProvider(LLMProvider):
        def __init__(self) -> None:
            self.events: list[LLMEvent] = []

        async def stream(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> AsyncIterator[LLMEvent]:
            for ev in self.events:
                yield ev

    stub = StubProvider()
    monkeypatch.setenv("APP_TOKEN", "test-token")
    monkeypatch.setenv("SESSION_SECRET", "x" * 64)
    monkeypatch.setattr("quaestor.chat.llm.factory.build_llm_provider", lambda: stub)
    monkeypatch.setattr("quaestor.api.chat.build_llm_provider", lambda: stub)
    app = create_app()
    app.dependency_overrides[require_auth] = lambda: None
    yield app, stub


@pytest.fixture
def client(app):
    """A TestClient that auto-mirrors CSRF for state-changing requests."""
    test_app, _ = app
    return CSRFTestClient(test_app)


@pytest.fixture
def auth_headers(monkeypatch):
    """A bearer token + session cookie for require_auth."""
    monkeypatch.setenv("APP_TOKEN", "test-token-xyz")
    return {"Authorization": "Bearer test-token-xyz"}
