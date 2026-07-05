"""FastAPI application factory. The single place where routers are registered."""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .. import db
from ..scheduler import run_forever
from .csrf import CSRFMiddleware
from .errors import register_exception_handlers

log = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Ensure the schema exists and spawn the daily scheduler task."""
    db.init_db(db.engine)
    log.info("api: lifespan startup")
    task = asyncio.create_task(run_forever(), name="daily-scheduler")
    try:
        yield
    finally:
        log.info("api: lifespan shutdown; cancelling scheduler")
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


_MIN_SESSION_SECRET_BYTES = 32


def _resolve_session_secret() -> str:
    """Read SESSION_SECRET from env. Fail-fast if missing or too short.

    Starlette signs the session cookie with `itsdangerous`; a short secret
    makes cookie forgery trivial. 32 bytes is the OWASP-recommended minimum
    for HMAC keys and matches `secrets.token_urlsafe(32)` output length.
    Raises at app construction so misconfiguration breaks the deploy
    instead of silently accepting attacker-forgeable cookies.
    """
    raw = os.environ.get("SESSION_SECRET", "").strip()
    size = len(raw.encode("utf-8"))
    if size < _MIN_SESSION_SECRET_BYTES:
        raise RuntimeError(
            "SESSION_SECRET must be set and ≥32 bytes "
            f"(got {size} bytes). Generate one with: "
            "`python -c \"import secrets; print(secrets.token_urlsafe(32))\"`."
        )
    return raw


def _configure_middleware(app: FastAPI) -> None:
    app.add_middleware(
        SessionMiddleware,
        secret_key=_resolve_session_secret(),
        session_cookie="quaestor_session",
        same_site="lax",
        https_only=os.environ.get("COOKIE_SECURE", "").lower() in ("1", "true"),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "X-CSRF-Token", "X-Request-ID"],
    )
    app.add_middleware(CSRFMiddleware)


def _include_routers(app: FastAPI) -> None:
    """Register routers. Resource routers are protected by require_auth."""
    from fastapi import Depends

    from . import auth, chat as chat_module
    from .deps import require_auth
    from .routers import (
        accounts,
        budgets,
        categories,
        category_groups,
        fx,
        goals,
        planned,
        recurring,
        reports,
        rollover,
        settings,
        tags,
        transactions,
    )

    app.include_router(auth.router, prefix="/api")

    protected = [Depends(require_auth)]
    app.include_router(accounts.router, prefix="/api", dependencies=protected)
    app.include_router(category_groups.router, prefix="/api", dependencies=protected)
    app.include_router(categories.router, prefix="/api", dependencies=protected)
    app.include_router(tags.router, prefix="/api", dependencies=protected)
    app.include_router(fx.router, prefix="/api", dependencies=protected)
    app.include_router(settings.router, prefix="/api", dependencies=protected)
    app.include_router(transactions.router, prefix="/api", dependencies=protected)
    app.include_router(recurring.router, prefix="/api", dependencies=protected)
    app.include_router(planned.router, prefix="/api", dependencies=protected)
    app.include_router(rollover.router, prefix="/api", dependencies=protected)
    app.include_router(budgets.router, prefix="/api", dependencies=protected)
    app.include_router(goals.router, prefix="/api", dependencies=protected)
    app.include_router(reports.router, prefix="/api", dependencies=protected)
    app.include_router(chat_module.router, prefix="/api", dependencies=protected)


def create_app() -> FastAPI:
    app = FastAPI(title="Quaestor API", lifespan=_lifespan)
    _configure_middleware(app)
    register_exception_handlers(app)
    _include_routers(app)
    return app


app = create_app()
