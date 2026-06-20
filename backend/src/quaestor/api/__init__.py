"""FastAPI application factory. The single place where routers are registered."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .. import db
from .errors import register_exception_handlers


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Ensure the schema exists before serving (P0's idempotent init_db)."""
    db.init_db(db.engine)
    yield


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
    """Register routers. Resource routers are protected by require_auth."""
    from fastapi import Depends

    from . import auth
    from .deps import require_auth
    from .routers import (
        accounts,
        categories,
        category_groups,
        fx,
        planned,
        recurring,
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


def create_app() -> FastAPI:
    app = FastAPI(title="Quaestor API", lifespan=_lifespan)
    _configure_middleware(app)
    register_exception_handlers(app)
    _include_routers(app)
    return app


app = create_app()
