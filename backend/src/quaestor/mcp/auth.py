"""Bearer-token gate for the MCP transport (defense-in-depth behind Tailscale).

Mirrors the API's constant-time check but enforces it at the ASGI layer, so an
unauthenticated request is rejected before any MCP tool runs.
"""
from __future__ import annotations

import hmac
import os

from starlette.responses import JSONResponse
from starlette.types import Receive, Scope, Send


def token_ok(authorization: str | None) -> bool:
    """Constant-time check of an `Authorization: Bearer <APP_TOKEN>` header."""
    expected = os.environ.get("APP_TOKEN")
    if not expected or not authorization:
        return False
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return False
    return hmac.compare_digest(token, expected)


class BearerAuthMiddleware:
    """Reject any HTTP request whose bearer token != APP_TOKEN, before the app."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        raw = headers.get(b"authorization")
        authorization = raw.decode("latin-1") if raw else None
        if not token_ok(authorization):
            response = JSONResponse(
                {
                    "error": "Unauthorized",
                    "detail": "Authorization: Bearer <APP_TOKEN> requerido",
                },
                status_code=401,
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
