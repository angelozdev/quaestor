"""FastAPI application factory. The single place where routers are registered."""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .errors import register_exception_handlers


def _configure_middleware(app: FastAPI) -> None:
    app.add_middleware(
        SessionMiddleware,
        secret_key=os.environ.get("SESSION_SECRET", "dev-insecure-secret"),
        session_cookie="quaestor_session",
        same_site="lax",
        https_only=os.environ.get("COOKIE_SECURE", "").lower() in ("1", "true"),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
    )


def _include_routers(app: FastAPI) -> None:
    """Register routers. Filled in by later tasks (auth + resource routers)."""
    return None


def create_app() -> FastAPI:
    app = FastAPI(title="Quaestor API")
    _configure_middleware(app)
    register_exception_handlers(app)
    _include_routers(app)
    return app


app = create_app()
