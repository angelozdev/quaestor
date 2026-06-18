"""Auth router: password login -> signed session cookie; logout; me probe."""
from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from .deps import _token_ok
from .errors import Unauthorized

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    password: str


@router.post("/login")
def login(body: LoginIn, request: Request) -> dict[str, bool]:
    expected = os.environ.get("APP_PASSWORD")
    if not expected or not hmac.compare_digest(body.password, expected):
        raise Unauthorized("contraseña inválida")
    request.session["authenticated"] = True
    return {"ok": True}


@router.post("/logout")
def logout(request: Request) -> dict[str, bool]:
    request.session.clear()
    return {"ok": True}


@router.get("/me")
def me(
    request: Request, authorization: str | None = Header(default=None)
) -> dict[str, bool]:
    authed = _token_ok(authorization) or request.session.get("authenticated") is True
    return {"authenticated": authed}
