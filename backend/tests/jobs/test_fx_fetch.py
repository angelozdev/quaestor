"""FX fetch job — provider-agnostic USD->COP rate extraction."""

from __future__ import annotations

from decimal import Decimal

import httpx
import pytest
from quaestor.jobs.fx_fetch import fetch_usd_cop


class _StubResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(f"{self.status_code}", request=None, response=None)


class _StubClient:
    def __init__(
        self,
        payload: dict | None = None,
        exc: Exception | None = None,
        status_code: int = 200,
    ):
        self.payload = payload
        self.exc = exc
        self.status_code = status_code
        self.last_url: str | None = None
        self.last_params: dict | None = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url: str, params: dict | None = None, timeout=None):
        self.last_url = url
        self.last_params = params or {}
        if self.exc:
            raise self.exc
        return _StubResponse(self.payload or {}, self.status_code)


def test_returns_decimal_from_rates_cop():
    client = _StubClient({"rates": {"COP": 4200.50}})
    rate = fetch_usd_cop("https://api.example.com/latest", client=client)
    assert rate == Decimal("4200.50")


def test_sends_api_key_as_query_param():
    client = _StubClient({"rates": {"COP": 4100}})
    fetch_usd_cop("https://api.example.com/latest", api_key="secret", client=client)
    assert client.last_params == {"api_key": "secret"}


def test_no_api_key_sends_no_query_params():
    client = _StubClient({"rates": {"COP": 4100}})
    fetch_usd_cop("https://api.example.com/latest", client=client)
    assert client.last_params == {}


def test_missing_rates_cop_raises():
    client = _StubClient({"foo": "bar"})
    with pytest.raises(ValueError, match=r"rates\.COP"):
        fetch_usd_cop("https://api.example.com/latest", client=client)


def test_http_error_propagates():
    bad = _StubClient(status_code=503)
    bad.payload = {}
    with pytest.raises(httpx.HTTPStatusError):
        fetch_usd_cop("https://api.example.com/latest", client=bad)
