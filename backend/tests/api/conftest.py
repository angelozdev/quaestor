import pytest
from fastapi.testclient import TestClient
from quaestor.api import create_app
from quaestor.api.csrf import CSRF_COOKIE, CSRF_HEADER
from quaestor.api.deps import get_session
from quaestor.db import init_db, make_engine
from quaestor.domain.models import TxType
from sqlmodel import Session

from tests.support.categories import a_category

_STATE_CHANGING = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class CSRFTestClient(TestClient):
    """TestClient that mirrors the CSRF cookie into the X-CSRF-Token header.

    The real browser does this in JavaScript on every state-changing
    request. Doing it in the test fixture keeps the existing test bodies
    focused on what they actually want to verify. Both `request()` and
    `stream()` are patched because `httpx.Client.stream` does NOT route
    through `request()` — it calls `send()` directly with a pre-built
    Request.
    """

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
def client(engine, monkeypatch):
    monkeypatch.setenv("APP_TOKEN", "test-token")
    monkeypatch.setenv("APP_PASSWORD", "test-password")
    monkeypatch.setenv("SESSION_SECRET", "x" * 64)
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:3000")
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    app = create_app()

    def override_get_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    return CSRFTestClient(app)


@pytest.fixture
def auth():
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def expense_category(engine):
    """Id of the category an API test files its outgoing money under.

    Mandatory since feature 008 (ADR-0042); a test about routing, auth or
    balances still has to say what its money was for.
    """
    with Session(engine) as session:
        return a_category(session, TxType.expense)


@pytest.fixture
def income_category(engine):
    """Id of the category an API test files its incoming money under."""
    with Session(engine) as session:
        return a_category(session, TxType.income)
