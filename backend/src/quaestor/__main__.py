"""
Quaestor container entrypoint: wait for DB → migrate → start uvicorn.
Runs as `python -m quaestor` from the container CMD (ADR-0026).
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from typing import Final

import psycopg
import uvicorn
from sqlalchemy import create_engine, text

LOG_PREFIX: Final = "[entrypoint]"
DB_WAIT_MAX_ATTEMPTS: Final = 30
DB_WAIT_INTERVAL_S: Final = 2.0


def log(msg: str) -> None:
    print(f"{LOG_PREFIX} {msg}", flush=True)


_POSTGRESQL_SCHEME = "postgresql://"
_PSYCOPG_SCHEME = "postgresql+psycopg://"


def _resolve_db_url(url: str) -> str:
    """Promote bare ``postgresql://`` to ``postgresql+psycopg://`` for SQLAlchemy.

    Mirrors ``_resolve_driver`` in db.py so the entrypoint's direct
    ``create_engine`` calls use the same driver as the application proper.
    """
    if url.startswith(_POSTGRESQL_SCHEME):
        return _PSYCOPG_SCHEME + url[len(_POSTGRESQL_SCHEME) :]
    return url


def _probe_postgres(url: str) -> None:
    # psycopg (v3) does not accept the ``+psycopg`` dialect prefix.
    probe_url = url.replace(_PSYCOPG_SCHEME, _POSTGRESQL_SCHEME)
    psycopg.connect(probe_url, connect_timeout=3).close()


def _probe_sqlite(url: str) -> None:
    create_engine(_resolve_db_url(url)).connect().close()


def wait_for_db(url: str) -> None:
    last_exc: Exception | None = None
    for attempt in range(1, DB_WAIT_MAX_ATTEMPTS + 1):
        try:
            if url.startswith("sqlite"):
                _probe_sqlite(url)
            else:
                _probe_postgres(url)
        except Exception as exc:
            last_exc = exc
            if attempt >= DB_WAIT_MAX_ATTEMPTS:
                break
            time.sleep(DB_WAIT_INTERVAL_S)
        else:
            log(f"DB reachable (attempt {attempt}/{DB_WAIT_MAX_ATTEMPTS})")
            return
    log(f"DB unreachable after {DB_WAIT_MAX_ATTEMPTS} attempts: {last_exc}")
    sys.exit(1)


def _alembic_version_empty(url: str) -> bool:
    """Return True if the alembic_version table is absent or has no rows.

    Catches the case where a DB has the head schema (e.g. created by a
    pre-Alembic ``init_db()``) but never recorded an alembic stamp — on first
    boot the entrypoint must ``stamp head`` rather than ``upgrade head``,
    which would error with ``table <X> already exists``.
    """
    eng = create_engine(_resolve_db_url(url))
    try:
        with eng.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).first()
            return row is None
    except Exception:
        return True  # table doesn't exist yet


def _db_has_any_table(url: str) -> bool:
    """Return True if the DB has at least one user table.

    Used to distinguish a fresh DB (no tables, no version → ``upgrade head``)
    from a pre-existing-schema DB (tables present, no version → ``stamp head``).
    """
    eng = create_engine(_resolve_db_url(url))
    try:
        with eng.connect() as conn:
            row = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")).first()
            return row is not None
    except Exception:
        return False


def run_migrations() -> None:
    url = os.environ.get("QUAESTOR_DB", "sqlite:///:memory:")
    if _alembic_version_empty(url):
        if _db_has_any_table(url):
            log("existing schema detected with no alembic_version row; stamping head (one-time)")
            subprocess.run(
                [sys.executable, "-m", "alembic", "stamp", "head"],
                check=True,
                cwd="/app",
            )
        else:
            log("fresh DB; running alembic upgrade head")
            subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                check=True,
                cwd="/app",
            )
    else:
        log("running alembic upgrade head")
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            check=False,
            cwd="/app",
        )
        if result.returncode != 0:
            log(f"alembic upgrade failed (rc={result.returncode}); aborting")
            sys.exit(result.returncode)


def _run_uvicorn() -> None:
    # basicConfig sets the root logger so alembic / uvicorn / library logs
    # reach stderr. Per-logger StreamHandlers in api/__init__.py keep
    # quaestor.scheduler + quaestor.api visible even if root handlers get
    # cleared (alembic's fileConfig and uvicorn's dictConfig both reset
    # the root logger).
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    uvicorn.run(
        "quaestor.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["/app/src"],
        log_level="info",
    )


def main() -> None:
    url = os.environ.get("QUAESTOR_DB", "sqlite:///:memory:")
    wait_for_db(url)
    run_migrations()
    log("starting uvicorn")
    _run_uvicorn()


if __name__ == "__main__":
    main()
