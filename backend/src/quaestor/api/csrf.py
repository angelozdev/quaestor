"""CSRF defense (double-submit cookie pattern) — QUA-A01-01.

The session cookie's `SameSite=Lax` already blocks most cross-site POSTs,
but does not cover every browser/context. We add a second barrier:

  1. On any "safe" handler (login, me) we set a non-HttpOnly `csrf_token`
     cookie containing a high-entropy random value.
  2. The client JavaScript mirrors the cookie value into the
     `X-CSRF-Token` request header on every state-changing request.
  3. `CSRFMiddleware` compares the two in constant time. Cross-origin
     attackers cannot read the cookie (Same-Origin Policy) so they cannot
     forge the header.

Login is exempted because there is no CSRF cookie yet to forge against —
the password itself is the auth check. Safe HTTP methods are exempted
because they are required to be idempotent.
"""
from __future__ import annotations

import hmac
import os
import secrets

from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

CSRF_COOKIE = "quaestor_csrf"
CSRF_HEADER = "x-csrf-token"

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

_EXEMPT_PATHS = frozenset({"/api/auth/login"})


def _cookie_secure() -> bool:
    return os.environ.get("COOKIE_SECURE", "").lower() in ("1", "true")


def issue_csrf_cookie(response: Response) -> str:
    """Set a fresh CSRF cookie on `response` and return the token value.

    Intended for handlers that already authenticate the caller (login, me).
    A new token is issued on every call so a stale value on a shared host
    does not stay valid forever; rotation cost is one extra cookie write.
    """
    token = secrets.token_urlsafe(32)
    response.set_cookie(
        key=CSRF_COOKIE,
        value=token,
        secure=_cookie_secure(),
        httponly=False,
        samesite="lax",
        path="/",
    )
    return token


def _extract_cookie(cookie_header: str, name: str) -> str:
    for part in cookie_header.split(";"):
        part = part.strip()
        if part.startswith(name + "="):
            return part[len(name) + 1 :]
    return ""


class CSRFMiddleware:
    """Reject mismatched/missing CSRF token on state-changing requests."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = (scope.get("method") or "").upper()
        path = scope.get("path") or ""
        if method in _SAFE_METHODS or path in _EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        headers: dict[str, str] = {}
        for raw_k, raw_v in scope.get("headers") or ():
            headers[raw_k.decode("latin-1").lower()] = raw_v.decode("latin-1")

        header_token = headers.get(CSRF_HEADER, "")
        cookie_token = _extract_cookie(headers.get("cookie", ""), CSRF_COOKIE)

        if not header_token or not cookie_token:
            response = JSONResponse(
                {"error": "Forbidden", "detail": "CSRF token missing"},
                status_code=403,
            )
            await response(scope, receive, send)
            return

        if not hmac.compare_digest(header_token, cookie_token):
            response = JSONResponse(
                {"error": "Forbidden", "detail": "CSRF token invalid"},
                status_code=403,
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
