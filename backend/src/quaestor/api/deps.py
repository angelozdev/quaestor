"""Request-scoped dependencies for the API layer."""
from __future__ import annotations

import hmac
import os
from collections.abc import Generator

from fastapi import Header, Request
from sqlmodel import Session

from ..db import engine
from .errors import Unauthorized


def get_session() -> Generator[Session, None, None]:
    """Yield a Session bound to the process engine, closed when the request ends.

    Tests override this via app.dependency_overrides to bind an in-memory engine.
    """
    with Session(engine) as s:
        yield s


def _token_ok(authorization: str | None) -> bool:
    """Constant-time check of an `Authorization: Bearer <APP_TOKEN>` header."""
    expected = os.environ.get("APP_TOKEN")
    if not expected or not authorization:
        return False
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return False
    return hmac.compare_digest(token, expected)


def require_auth(
    request: Request, authorization: str | None = Header(default=None)
) -> None:
    """Authorize via bearer token OR a valid session cookie; else 401."""
    if _token_ok(authorization):
        return
    if request.session.get("authenticated") is True:
        return
    raise Unauthorized()
