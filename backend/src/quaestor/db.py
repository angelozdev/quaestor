"""Database engine factory and bootstrap: Postgres in prod, SQLite in-memory for tests.

The factory branches on URL scheme. The test path passes `memory=True`
or a `sqlite://` URL and gets an in-memory SQLite engine on `StaticPool`.
Production gets a Postgres engine with `pool_pre_ping=True` and a sized
pool. The default URL is resolved from `QUAESTOR_DB` on every call so
test code (or operational scripts) that mutate the environment after
import still gets the intended engine.

Alembic is the source of truth for schema. `init_db()` runs
`alembic upgrade head` to the latest revision, seeds the canonical
`Settings(id=1)` row, then registers the cross-service hooks.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Final

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session

from .domain.models import Settings
from .services.bootstrap import register_recurring_hooks

_BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
_ALEMBIC_INI: Final[Path] = _BACKEND_ROOT / "alembic.ini"
_DEFAULT_DB_URL: Final[str] = "sqlite:///quaestor.db"
_IN_MEMORY_SQLITE_URL: Final[str] = "sqlite://"
_POSTGRESQL_SCHEME: Final[str] = "postgresql://"
_PSYCOG3_SCHEME: Final[str] = "postgresql+psycopg://"
_POOL_SIZE: Final[int] = 5
_MAX_OVERFLOW: Final[int] = 10
_POOL_PRE_PING: Final[bool] = True
_DEFAULT_SETTINGS_ID: Final[int] = 1
_DEFAULT_BASE_CURRENCY: Final[str] = "COP"


def _default_url() -> str:
    """Resolve `QUAESTOR_DB` at call time so env mutations are honoured."""
    return os.environ.get("QUAESTOR_DB", _DEFAULT_DB_URL)


def _resolve_driver(url: str) -> str:
    """Promote bare `postgresql://` URLs to the explicit `postgresql+psycopg` driver.

    SQLAlchemy picks a driver based on the scheme prefix. Without this
    rewrite, a `postgresql://` URL on a host that has only
    `psycopg[binary]` installed raises `ImportError: No driver specified`
    at first connect. URLs that already carry a driver
    (`postgresql+psycopg://...`, `postgresql+psycopg2://...`) pass
    through untouched.
    """
    if url.startswith(_POSTGRESQL_SCHEME):
        return _PSYCOG3_SCHEME + url[len(_POSTGRESQL_SCHEME) :]
    return url


def _sqlite_engine(url: str) -> Engine:
    """Build a SQLite engine — used by tests with `memory=True` or a `sqlite://` URL."""
    return create_engine(
        url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def _postgres_engine(url: str) -> Engine:
    """Build the production Postgres engine — sized pool + pre-ping connection check."""
    return create_engine(
        _resolve_driver(url),
        pool_pre_ping=_POOL_PRE_PING,
        pool_size=_POOL_SIZE,
        max_overflow=_MAX_OVERFLOW,
    )


def make_engine(url: str | None = None, *, memory: bool = False) -> Engine:
    """Build an Engine for either Postgres (prod) or SQLite (tests).

    Branches on URL scheme (or `memory=True`). SQLite keeps `StaticPool`
    so a single in-memory engine can serve a multi-threaded test session;
    Postgres gets the sized pool + pre-ping for connection-drop detection.
    The default URL is resolved from `QUAESTOR_DB` on every call.
    """
    target_url = url if url is not None else _default_url()
    if memory:
        return _sqlite_engine(_IN_MEMORY_SQLITE_URL)
    if target_url.startswith("sqlite"):
        return _sqlite_engine(target_url)
    return _postgres_engine(target_url)


engine: Final[Engine] = make_engine()


def _apply_migrations(target_engine: Engine) -> None:
    """Apply Alembic migrations to `target_engine` to the latest revision.

    The AlembicConfig is built per call with `cfg.attributes["engine"]`
    so the in-memory SQLite test path can pre-supply its StaticPool engine
    and avoid creating a fresh empty in-memory DB.
    """
    cfg = AlembicConfig(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", str(target_engine.url))
    cfg.attributes["engine"] = target_engine
    alembic_command.upgrade(cfg, "head")


def _seed_default_settings(target_engine: Engine) -> None:
    """Insert the canonical `Settings(id=1)` row if it is missing."""
    with Session(target_engine) as session:
        if session.get(Settings, _DEFAULT_SETTINGS_ID) is None:
            session.add(Settings(id=_DEFAULT_SETTINGS_ID, base_currency=_DEFAULT_BASE_CURRENCY))
            session.commit()


def init_db(target_engine: Engine = engine) -> None:
    """Bootstrap a fresh database: migrations, defaults, then handler hooks.

    Replaces the legacy `SQLModel.metadata.create_all` path — the project's
    migrations are now the single source of truth. Idempotent: calling
    twice is a no-op when the schema is already at `head`.
    """
    _apply_migrations(target_engine)
    _seed_default_settings(target_engine)
    register_recurring_hooks()


@contextmanager
def get_session(target_engine: Engine = engine) -> Generator[Session, None, None]:
    """Yield a Session for the given engine — auto-closed on context exit."""
    with Session(target_engine) as session:
        yield session


@contextmanager
def atomic(session: Session) -> Generator[Session, None, None]:
    """Wrap a Session block in a transaction; rollback on any error.

    Catches `Exception` (broader than `SQLAlchemyError`) because the
    existing test contract in
    `tests/test_db.py::test_atomic_rolls_back_on_error` and the
    rollover test inject `RuntimeError` mid-block and assert the
    transaction is rolled back. Narrowing to `SQLAlchemyError` only
    would let dirty state leak into the caller's next query against
    the same session.
    """
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
