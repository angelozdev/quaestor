import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from quaestor.api import create_app
from quaestor.db import init_db, make_engine
from quaestor.services import accounts, categories


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
    account = accounts.create_account(
        session, "Bancolombia", "debit", "COP", balance=10_000_000
    )
    category = categories.create_category(session, "Groceries")
    return {"account": account, "category": category}


@pytest.fixture
def app(monkeypatch, engine):
    """A TestClient app bound to the in-memory engine and a stub LLM."""
    from collections.abc import AsyncIterator
    from typing import Any

    from quaestor.api.deps import require_auth
    from quaestor.chat.llm.provider import LLMEvent, LLMEventType, LLMProvider

    class StubProvider(LLMProvider):
        def __init__(self) -> None:
            self.events: list[LLMEvent] = []

        async def stream(
            self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
        ) -> AsyncIterator[LLMEvent]:
            for ev in self.events:
                yield ev

    stub = StubProvider()
    monkeypatch.setattr("quaestor.chat.llm.factory.build_llm_provider", lambda: stub)
    # The chat router imports `build_llm_provider` via `from ... import ...`,
    # which captures the function object in its own namespace at import time.
    # Patching the factory module attribute alone leaves the router holding
    # the original LiteLLM factory; patch the symbol on the router module too.
    monkeypatch.setattr("quaestor.api.chat.build_llm_provider", lambda: stub)
    app = create_app()
    # Default: bypass auth so validation/streaming tests can hit the route
    # without supplying headers. `test_chat_requires_auth` clears this.
    app.dependency_overrides[require_auth] = lambda: None
    yield app, stub


@pytest.fixture
def auth_headers(monkeypatch):
    """A bearer token + session cookie for require_auth."""
    monkeypatch.setenv("APP_TOKEN", "test-token-xyz")
    return {"Authorization": "Bearer test-token-xyz"}
