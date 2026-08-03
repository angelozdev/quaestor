"""Auth router: password login -> signed session cookie; logout; me probe."""

from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Header, Request, Response
from pydantic import BaseModel

from .csrf import issue_csrf_cookie
from .deps import _token_ok
from .errors import Unauthorized

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    password: str


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response) -> dict[str, bool]:
    expected = os.environ.get("APP_PASSWORD")
    if not expected or not hmac.compare_digest(body.password, expected):
        raise Unauthorized("invalid password")
    request.session["authenticated"] = True
    issue_csrf_cookie(response)
    return {"ok": True}


@router.post("/logout")
def logout(request: Request) -> dict[str, bool]:
    request.session.clear()
    return {"ok": True}


@router.get("/me")
def me(
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
) -> dict[str, bool]:
    authed = _token_ok(authorization) or request.session.get("authenticated") is True
    issue_csrf_cookie(response)
    return {"authenticated": authed}
