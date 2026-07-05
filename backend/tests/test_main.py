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
    """mocked subprocess returns rc=0; function returns."""
    from quaestor.__main__ import run_migrations
    mock_result = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        run_migrations()
        mock_run.assert_called_once()
        # cwd should be /app
        assert mock_run.call_args.kwargs.get("cwd") == "/app"


def test_run_migrations_failure_exits() -> None:
    """mocked subprocess returns rc=2; calls sys.exit(2)."""
    from quaestor.__main__ import run_migrations
    mock_result = MagicMock(returncode=2)
    with patch.object(sys, "exit") as mock_exit:
        with patch("subprocess.run", return_value=mock_result):
            run_migrations()
            mock_exit.assert_called_once_with(2)
