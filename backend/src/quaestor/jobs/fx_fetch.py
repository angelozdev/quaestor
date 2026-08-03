"""Daily USD->COP FX rate fetcher (ADR-011).

Provider-agnostic: expects a JSON response with `rates.COP`. Compatible with
Frankfurter (`https://api.frankfurter.app/latest?base=USD&symbols=COP`) and
similar free providers. The provider URL is fully configurable via
`FX_API_URL`; this module just extracts the rate.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

import httpx


class _HttpClient(Protocol):
    def get(self, url: str, params: dict | None = None, timeout: float | None = None): ...


def fetch_usd_cop(
    url: str,
    api_key: str | None = None,
    *,
    client: _HttpClient | None = None,
) -> Decimal:
    """Hit the FX provider and return USD->COP as a Decimal.

    Args:
        url: FX provider endpoint. Must return JSON with `rates.COP`.
        api_key: Optional API key. Sent as `?api_key=...` query param when set.
        client: Optional httpx-compatible client (used by tests for stubbing).

    Raises:
        httpx.HTTPStatusError: the provider returned 4xx/5xx.
        ValueError: response JSON does not contain `rates.COP`.
    """
    params: dict[str, str] = {}
    if api_key:
        params["api_key"] = api_key
    owns_client = client is None
    if owns_client:
        client = httpx.Client(timeout=10.0)
    try:
        response = client.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()
    finally:
        if owns_client:
            client.close()  # type: ignore[union-attr]
    try:
        rate = data["rates"]["COP"]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"FX response missing rates.COP: {data!r}") from exc
    return Decimal(str(rate))
