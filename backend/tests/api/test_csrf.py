"""CSRF defense (QUA-A01-01) — double-submit cookie pattern.

The middleware compares the `X-CSRF-Token` header against the
`quaestor_csrf` cookie in constant time on every state-changing request.
Login is exempt (no cookie to forge yet); safe HTTP methods are exempt
(they're required to be idempotent).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from quaestor.api.csrf import CSRF_COOKIE, CSRF_HEADER


def _set_csrf_cookie(client, value: str) -> None:
    client.cookies.set(CSRF_COOKIE, value)


def _post_without_csrf(client):
    client.cookies.clear()
    return client.post("/api/accounts", json={"name": "x", "type": "debit"})


def test_post_without_csrf_header_rejected(client):
    """Use a fresh TestClient with no priming so we exercise the bare
    rejection path: no CSRF cookie, no header."""
    fresh = TestClient(client.app)
    resp = fresh.post("/api/accounts", json={"name": "x", "type": "debit"})
    assert resp.status_code == 403
    assert resp.json()["error"] == "Forbidden"


def test_post_with_mismatched_csrf_header_rejected(client):
    _set_csrf_cookie(client, "cookie-value")
    resp = client.post(
        "/api/accounts",
        json={"name": "x", "type": "debit"},
        headers={CSRF_HEADER: "different-value"},
    )
    assert resp.status_code == 403


def test_post_with_matched_csrf_passes_csrf_check(client):
    """When cookie == header, CSRF middleware lets the request through.
    The route still requires auth so the status will be 401 here; we
    only assert that the request wasn't rejected as CSRF-violating."""
    token = "matching-token-value"
    _set_csrf_cookie(client, token)
    resp = client.post(
        "/api/accounts",
        json={"name": "x", "type": "debit"},
        headers={CSRF_HEADER: token},
    )
    assert resp.status_code == 401


def test_login_is_csrf_exempt(client):
    fresh = TestClient(client.app)
    resp = fresh.post("/api/auth/login", json={"password": "test-password"})
    assert resp.status_code == 200


def test_get_request_does_not_require_csrf(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200


def test_options_preflight_does_not_require_csrf(client):
    resp = client.options("/api/accounts")
    assert resp.status_code in (200, 405)


def test_login_sets_csrf_cookie(client):
    resp = client.post("/api/auth/login", json={"password": "test-password"})
    assert resp.status_code == 200
    assert CSRF_COOKIE in client.cookies
    assert len(client.cookies[CSRF_COOKIE]) >= 32


def test_me_refreshes_csrf_cookie_on_every_call(client):
    first = client.get("/api/auth/me")
    token_1 = client.cookies[CSRF_COOKIE]
    assert first.status_code == 200
    second = client.get("/api/auth/me")
    token_2 = client.cookies[CSRF_COOKIE]
    assert second.status_code == 200
    assert token_1 != token_2
