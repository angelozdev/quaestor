"""Test-only SQL query counter via SQLAlchemy's before_cursor_execute event."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session


@dataclass
class _Counter:
    count: int = 0


@contextmanager
def count_queries(target: Engine | Session):
    """Count SQL statements executed on `target`'s engine within the block."""
    engine = target.get_bind() if isinstance(target, Session) else target
    counter = _Counter()

    def _before(conn, cursor, statement, parameters, context, executemany):
        counter.count += 1

    event.listen(engine, "before_cursor_execute", _before)
    try:
        yield counter
    finally:
        event.remove(engine, "before_cursor_execute", _before)
