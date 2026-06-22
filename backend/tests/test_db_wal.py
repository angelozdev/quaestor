"""The SQLite engine must enable WAL and a busy_timeout on every connection."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from sqlalchemy import event, text

from quaestor import db


def _temp_db_url(path: Path) -> str:
    # SQLite URL: three slashes for relative, four for absolute.
    return f"sqlite:///{path}"


def test_wal_mode_is_set_on_connect(tmp_path: Path):
    db_file = tmp_path / "test.db"
    engine = db.make_engine(_temp_db_url(db_file))
    # Open one connection so the PRAGMA fires.
    with engine.connect() as conn:
        mode = conn.execute(text("PRAGMA journal_mode")).scalar_one()
        assert mode.lower() == "wal", f"expected WAL, got {mode!r}"


def test_busy_timeout_is_set_on_connect(tmp_path: Path):
    db_file = tmp_path / "test.db"
    engine = db.make_engine(_temp_db_url(db_file))
    with engine.connect() as conn:
        ms = conn.execute(text("PRAGMA busy_timeout")).scalar_one()
        assert int(ms) == 5000, f"expected 5000, got {ms!r}"


def test_wal_persists_across_connections(tmp_path: Path):
    """Two distinct connections to the same file both observe WAL."""
    db_file = tmp_path / "test.db"
    engine = db.make_engine(_temp_db_url(db_file))
    with engine.connect() as a:
        assert a.execute(text("PRAGMA journal_mode")).scalar_one().lower() == "wal"
    with engine.connect() as b:
        assert b.execute(text("PRAGMA journal_mode")).scalar_one().lower() == "wal"
