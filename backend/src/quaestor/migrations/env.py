from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Importing domain models registers all SQLModel classes on SQLModel.metadata,
# which Alembic's autogenerate needs to diff against the live DB.
# Read the URL at migration time so tests that mutate `QUAESTOR_DB`
# after import are honoured (mirrors `quaestor.db.make_engine`'s
# lazy resolution).
import os

from sqlmodel import SQLModel

from quaestor.domain import models  # noqa: F401

_DEFAULT_DB_URL = "sqlite:///quaestor.db"

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = SQLModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url") or os.environ.get(
        "QUAESTOR_DB", _DEFAULT_DB_URL
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
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    A caller may pre-supply the engine via
    ``config.attributes["engine"]`` (e.g. for in-memory SQLite tests,
    where every separate engine gets its own empty in-memory database).
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
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
