"""
Tests for backend/src/quaestor/__main__.py (container entrypoint).
Verifies: DB probing, wait_for_db retry logic, migration runner, and async uvicorn launch.
"""
from __future__ import annotations

import subprocess
import sys
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeExc(Exception):
    """Sentinel exception for mock probing failures."""


# ---------------------------------------------------------------------------
# Tests: _probe_sqlite
# ---------------------------------------------------------------------------

def test_probe_sqlite_success() -> None:
    """create_engine(url).connect().close() works for a SQLite URL."""
    from quaestor.__main__ import _probe_sqlite
    _probe_sqlite("sqlite:///:memory:")


def test_probe_postgres_success() -> None:
    """mocked psycopg.connect(url, connect_timeout=3).close() succeeds."""
    from quaestor.__main__ import _probe_postgres
    mock_conn = MagicMock()
    with patch("quaestor.__main__.psycopg") as mock_psycopg:
        mock_psycopg.connect.return_value = mock_conn
        _probe_postgres("postgresql://user:pass@localhost/db")
        mock_psycopg.connect.assert_called_once_with(
            "postgresql://user:pass@localhost/db", connect_timeout=3
        )
        mock_conn.close.assert_called_once()


def test_probe_postgres_failure() -> None:
    """mocked psycopg.connect raises; exception propagates."""
    from quaestor.__main__ import _probe_postgres
    with patch("quaestor.__main__.psycopg") as mock_psycopg:
        mock_psycopg.connect.side_effect = FakeExc("connection refused")
        with pytest.raises(FakeExc):
            _probe_postgres("postgresql://user:pass@localhost/db")


# ---------------------------------------------------------------------------
# Tests: wait_for_db
# ---------------------------------------------------------------------------

def test_wait_for_db_immediate_success_sqlite() -> None:
    """first attempt succeeds for SQLite URL → returns without sleeping."""
    from quaestor.__main__ import wait_for_db
    with patch("quaestor.__main__._probe_sqlite") as mock_probe:
        with patch("time.sleep") as mock_sleep:
            wait_for_db("sqlite:///:memory:")
            mock_probe.assert_called_once_with("sqlite:///:memory:")
            mock_sleep.assert_not_called()


def test_wait_for_db_eventual_success_postgres() -> None:
    """first 3 attempts raise, 4th succeeds → returns after 3 sleeps."""
    from quaestor.__main__ import wait_for_db
    mock_probe = MagicMock(
        side_effect=[FakeExc("fail 1"), FakeExc("fail 2"), FakeExc("fail 3"), None]
    )
    with patch.object(sys, "exit") as mock_exit:
        with patch("time.sleep") as mock_sleep:
            with patch("quaestor.__main__._probe_postgres", mock_probe):
                wait_for_db("postgresql://user:pass@localhost/db")
                assert mock_probe.call_count == 4
                assert mock_sleep.call_count == 3
                mock_exit.assert_not_called()


def test_wait_for_db_max_attempts_exits_1(capsys: pytest.CaptureFixture[str]) -> None:
    """every attempt fails → calls sys.exit(1); last exception logged."""
    from quaestor.__main__ import DB_WAIT_MAX_ATTEMPTS, wait_for_db
    mock_probe = MagicMock(side_effect=FakeExc("always fails"))
    with patch.object(sys, "exit") as mock_exit:
        with patch("time.sleep"):
            with patch("quaestor.__main__._probe_postgres", mock_probe):
                wait_for_db("postgresql://user:pass@localhost/db")
                mock_exit.assert_called_once_with(1)
                assert mock_probe.call_count == DB_WAIT_MAX_ATTEMPTS
    # last exception is printed to stdout
    captured = capsys.readouterr()
    assert "FakeExc" in captured.out or "always fails" in captured.out


# ---------------------------------------------------------------------------
# Tests: run_migrations
# ---------------------------------------------------------------------------

def test_run_migrations_success() -> None:
    """fresh DB path: alembic upgrade head returns rc=0; function returns."""
    from quaestor.__main__ import run_migrations
    mock_result = MagicMock(returncode=0)
    with patch("quaestor.__main__._alembic_version_empty", return_value=True):
        with patch("quaestor.__main__._db_has_any_table", return_value=False):
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                run_migrations()
                mock_run.assert_called_once()
                args = mock_run.call_args.args[0]
                assert "upgrade" in args and "head" in args
                assert "stamp" not in args
                # cwd should be /app
                assert mock_run.call_args.kwargs.get("cwd") == "/app"


def test_run_migrations_failure_exits() -> None:
    """existing-version path: alembic upgrade head returns rc=2 → sys.exit(2)."""
    from quaestor.__main__ import run_migrations
    mock_result = MagicMock(returncode=2)
    with patch("quaestor.__main__._alembic_version_empty", return_value=False):
        with patch.object(sys, "exit") as mock_exit:
            with patch("subprocess.run", return_value=mock_result):
                run_migrations()
                mock_exit.assert_called_once_with(2)


def test_run_migrations_stamps_when_schema_exists_no_version() -> None:
    """Pre-existing schema, no alembic_version row → calls ``alembic stamp head``
    (NOT ``upgrade head``); this avoids the ``table <X> already exists`` error
    that occurs when the head schema is already in place but unrecorded.
    """
    from quaestor.__main__ import run_migrations
    mock_result = MagicMock(returncode=0)
    with patch("quaestor.__main__._alembic_version_empty", return_value=True):
        with patch("quaestor.__main__._db_has_any_table", return_value=True):
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                run_migrations()
                mock_run.assert_called_once()
                args = mock_run.call_args.args[0]
                assert "stamp" in args and "head" in args
                assert "upgrade" not in args
                assert mock_run.call_args.kwargs.get("cwd") == "/app"


def test_run_migrations_upgrades_when_version_present() -> None:
    """Alembic version table has a row → calls ``alembic upgrade head`` to apply
    any pending migrations.
    """
    from quaestor.__main__ import run_migrations
    mock_result = MagicMock(returncode=0)
    with patch("quaestor.__main__._alembic_version_empty", return_value=False):
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            run_migrations()
            mock_run.assert_called_once()
            args = mock_run.call_args.args[0]
            assert "upgrade" in args and "head" in args
            assert "stamp" not in args
            assert mock_run.call_args.kwargs.get("cwd") == "/app"


def test_run_migrations_upgrades_when_empty_db() -> None:
    """Fresh DB: no tables, no alembic_version row → calls ``alembic upgrade head``
    to create the schema and stamp it.
    """
    from quaestor.__main__ import run_migrations
    mock_result = MagicMock(returncode=0)
    with patch("quaestor.__main__._alembic_version_empty", return_value=True):
        with patch("quaestor.__main__._db_has_any_table", return_value=False):
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                run_migrations()
                mock_run.assert_called_once()
                args = mock_run.call_args.args[0]
                assert "upgrade" in args and "head" in args
                assert "stamp" not in args
                assert mock_run.call_args.kwargs.get("cwd") == "/app"


# ---------------------------------------------------------------------------
# Tests: _alembic_version_empty / _db_has_any_table (probe helpers)
# ---------------------------------------------------------------------------

def test_alembic_version_empty_when_table_absent() -> None:
    """In-memory SQLite with no alembic_version table → helper returns True."""
    from quaestor.__main__ import _alembic_version_empty
    # Real call against a fresh in-memory DB: no alembic_version table exists,
    # so the helper hits its exception branch and returns True.
    assert _alembic_version_empty("sqlite:///:memory:") is True


def test_alembic_version_empty_when_table_present_no_rows() -> None:
    """alembic_version table exists but has zero rows → helper returns True."""
    from quaestor.__main__ import _alembic_version_empty
    import sqlite3
    import tempfile
    # File-backed URL is required: SQLAlchemy's ``sqlite:///:memory:`` gives a
    # per-connection in-memory DB that doesn't share schema across connections.
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        conn.commit()
        conn.close()
        assert _alembic_version_empty(f"sqlite:///{path}") is True
    finally:
        import os as _os
        _os.unlink(path)


def test_alembic_version_empty_when_row_present() -> None:
    """alembic_version table has a row → helper returns False."""
    from quaestor.__main__ import _alembic_version_empty
    import sqlite3
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        conn.execute("INSERT INTO alembic_version VALUES ('abc123')")
        conn.commit()
        conn.close()
        assert _alembic_version_empty(f"sqlite:///{path}") is False
    finally:
        import os as _os
        _os.unlink(path)


# ---------------------------------------------------------------------------
# Tests: _run_uvicorn / main (uvicorn reloader wiring)
# ---------------------------------------------------------------------------

def test_run_uvicorn_calls_uvicorn_run_with_reload() -> None:
    """``main()`` must call ``uvicorn.run`` with ``reload=True`` and
    ``reload_dirs=["/app/src"]`` so uvicorn's ``ChangeReload`` reloader is
    actually wired (uvicorn.Server(config).serve() silently no-ops reload).
    """
    from quaestor import __main__ as entrypoint

    with patch.object(entrypoint, "wait_for_db") as mock_wait:
        with patch.object(entrypoint, "run_migrations") as mock_migrate:
            with patch.object(entrypoint.uvicorn, "run") as mock_run:
                entrypoint.main()
                mock_wait.assert_called_once()
                mock_migrate.assert_called_once()
                mock_run.assert_called_once_with(
                    "quaestor.api:app",
                    host="0.0.0.0",
                    port=8000,
                    reload=True,
                    reload_dirs=["/app/src"],
                    log_level="info",
                )


def test_scheduler_and_api_loggers_have_handlers_at_import() -> None:
    """Both quaestor.scheduler and quaestor.api loggers must have StreamHandlers
    configured at module-import time (in api/__init__.py) so their INFO lines
    reach stderr and appear in docker compose logs. Handlers are attached at
    import time rather than in the lifespan because uvicorn's Server.start()
    calls logging.config.dictConfig which can clear lifespan-added handlers.
    """
    import logging as logging_module

    # Importing the api module triggers the module-level handler setup
    from quaestor.api import log as api_log  # noqa: F401

    sched = logging_module.getLogger("quaestor.scheduler")
    assert len(sched.handlers) >= 1, "scheduler logger has no handler"
    assert sched.level == logging_module.INFO

    api_logger = logging_module.getLogger("quaestor.api")
    assert len(api_logger.handlers) >= 1, "api logger has no handler"
    assert api_logger.level == logging_module.INFO
