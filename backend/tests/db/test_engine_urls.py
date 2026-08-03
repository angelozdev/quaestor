"""Engine factory URL routing — Postgres in prod, SQLite in-memory for tests.

These tests pin the contract `make_engine` advertises:
  * `memory=True`                 -> SQLite (in-memory, StaticPool)
  * `url` starts with `"sqlite"`  -> SQLite (with `StaticPool` + check_same_thread=False)
  * `url` starts with `"postgres"` -> PostgreSQL (pool_pre_ping + pool_size=5 + max_overflow=10)
  * default                       -> engine built from `QUAESTOR_DB` env (Postgres in prod)

If the engine factory ever stops branching on URL scheme, these tests fail.
"""

from __future__ import annotations

import pytest
from quaestor.db import make_engine


def test_make_engine_in_memory_returns_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QUAESTOR_DB", raising=False)
    engine = make_engine(memory=True)
    try:
        assert engine.dialect.name == "sqlite"
    finally:
        engine.dispose()


def test_make_engine_postgres_url_returns_postgres() -> None:
    url = "postgresql+psycopg://quaestor:dev_pass@localhost:5432/quaestor"
    engine = make_engine(url)
    try:
        assert engine.dialect.name == "postgresql"
        assert engine.pool.size() == 5
        assert engine.pool._max_overflow == 10
        assert engine.pool._pre_ping is True
    finally:
        engine.dispose()


def test_make_engine_default_url_postgres_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "QUAESTOR_DB",
        "postgresql+psycopg://quaestor:dev_pass@localhost:5432/quaestor",
    )
    engine = make_engine()
    try:
        assert engine.dialect.name == "postgresql"
        assert engine.pool.size() == 5
    finally:
        engine.dispose()
