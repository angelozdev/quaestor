"""Alembic migration environment for Quaestor.

`target_metadata` binds Alembic's autogenerate to `SQLModel.metadata`,
so `alembic revision --autogenerate` diffs the live DB against the
registered SQLModel classes in `quaestor.domain.models`.

In online mode, the connection can come from a pre-supplied engine
(via `config.attributes["engine"]`) — which the in-memory SQLite tests
use so all alembic-managed operations share one StaticPool DB.
Otherwise the URL is read from the `[alembic]` section of `alembic.ini`
with a fallback to `QUAESTOR_DB`.

In offline mode the URL is read from the same sources and migrations
are emitted as SQL.
"""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from quaestor.domain import models  # noqa: F401


_DEFAULT_DB_URL: str = "sqlite:///quaestor.db"

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Emit migrations as SQL using only a URL — no live DB connection."""
    url = (
        config.get_main_option("sqlalchemy.url")
        or os.environ.get("QUAESTOR_DB", _DEFAULT_DB_URL)
    )
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations against a live DB connection.

    If a caller pre-supplied an engine (e.g. an in-memory SQLite test
    engine via `config.attributes["engine"]`), use that engine's
    connection. Otherwise build a fresh engine from
    `[alembic].sqlalchemy.url` with a `QUAESTOR_DB` fallback.
    """
    connectable = config.attributes.get("engine")
    if connectable is None:
        section = config.get_section(config.config_ini_section, {})
        if "sqlalchemy.url" not in section:
            section["sqlalchemy.url"] = os.environ.get("QUAESTOR_DB", _DEFAULT_DB_URL)
        connectable = engine_from_config(
            section,
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()