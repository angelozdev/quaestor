"""SQLite engine, session, and work-unit helpers."""
from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from .domain.models import Settings

DATABASE_URL = os.environ.get("QUAESTOR_DB", "sqlite:///quaestor.db")


def _set_sqlite_pragmas(dbapi_connection, connection_record):  # noqa: ARG001
    """Enable WAL + busy_timeout + FK on every new SQLite connection.

    WAL allows concurrent readers while a writer is active (api vs mcp).
    busy_timeout makes the second writer wait instead of failing with
    'database is locked'. foreign_keys is on-by-default-disabled in SQLite.
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def make_engine(url: str = DATABASE_URL, *, memory: bool = False) -> Engine:
    if memory or url == "sqlite://":
        return create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    engine = create_engine(url, connect_args={"check_same_thread": False})
    event.listens_for(engine, "connect")(_set_sqlite_pragmas)
    return engine


engine = make_engine()


def init_db(target_engine: Engine = engine) -> None:
    SQLModel.metadata.create_all(target_engine)
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
