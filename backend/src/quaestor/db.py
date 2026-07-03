"""Database engine factory: Postgres in prod, SQLite in-memory for tests.

`make_engine` branches on URL scheme so the test path can keep using SQLite
without losing the production Postgres configuration (pool_pre_ping +
sized pool). Alembic is the source of truth for the schema; `init_db()`
calls `alembic upgrade head` so the API lifespan and the MCP server can
keep the historical "init_db-on-boot" ergonomics without bypassing the
migration history.
"""
from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session

from .domain.models import Settings

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_ALEMBIC_INI = _BACKEND_ROOT / "alembic.ini"


def _default_url() -> str:
    """Resolve `QUAESTOR_DB` at call time so env mutations are honoured."""
    return os.environ.get("QUAESTOR_DB", "sqlite:///quaestor.db")


def make_engine(url: str | None = None, *, memory: bool = False) -> Engine:
    """Build an Engine for either Postgres (prod) or SQLite (tests).

    Branch on URL scheme (or `memory=True`). SQLite keeps `StaticPool` +
    `check_same_thread=False` so a single in-memory engine can serve a
    multi-threaded test session. Postgres gets `pool_pre_ping=True`,
    `pool_size=5`, `max_overflow=10` for connection drop detection and
    bounded concurrency. The default URL is resolved from `QUAESTOR_DB`
    on every call so test code (or operational scripts) that mutate the
    environment after import still gets the intended engine.
    """
    target_url = url if url is not None else _default_url()
    if memory or (target_url or "").startswith("sqlite"):
        return create_engine(
            "sqlite://" if memory else target_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    # Default the postgresql URL to the psycopg3 driver (only `psycopg[binary]`
    # is installed; psycopg2 is not). When the URL already carries a driver
    # (`postgresql+psycopg://...`, `postgresql+psycopg2://...`) SQLAlchemy
    # uses it verbatim — the substitution is a no-op.
    if target_url.startswith("postgresql://"):
        target_url = "postgresql+psycopg://" + target_url[len("postgresql://"):]
    return create_engine(
        target_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


engine = make_engine()


def init_db(target_engine: Engine = engine) -> None:
    """Apply migrations to `target_engine`, then register goal hooks.

    Replaces the legacy `SQLModel.metadata.create_all` path: the project's
    migrations are now the single source of truth. Idempotent — calling
    this twice is a no-op when the schema is already at `head`. We hand
    Alembic the same engine so SQLite in-memory tests share the
    StaticPool connection (otherwise each alembic-managed engine creates
    its own empty in-memory DB).
    """
    cfg = AlembicConfig(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", str(target_engine.url))
    cfg.attributes["engine"] = target_engine
    alembic_command.upgrade(cfg, "head")
    with Session(target_engine) as s:
        if s.get(Settings, 1) is None:
            s.add(Settings(id=1, base_currency="COP"))
            s.commit()
    from .services.bootstrap import register_goal_hooks
    register_goal_hooks()


@contextmanager
def get_session(target_engine: Engine = engine) -> Generator[Session, None, None]:
    with Session(target_engine) as s:
        yield s


@contextmanager
def atomic(session: Session) -> Generator[Session, None, None]:
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
