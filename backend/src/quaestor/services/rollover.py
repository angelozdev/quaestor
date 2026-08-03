"""Monthly close (ADR-017/022): an atomic, idempotent run of rollover hooks.

P3 registers no hooks of its own (its temporal work is the daily materialize_due).
It leaves the seam ready and empty; P4 registers propose_goal_contributions via
register_rollover_hook without touching close_month. Each hook is
(period, session) -> None, runs in the same transaction, must be idempotent on
its own, and a failure in any hook aborts the whole close.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import date as Date

from sqlmodel import Session

from ..db import atomic

ROLLOVER_HOOKS: list[Callable[[str, Session], None]] = []


def register_rollover_hook(fn: Callable[[str, Session], None]) -> None:
    """Register a hook fired by close_month, in registration order."""
    ROLLOVER_HOOKS.append(fn)


def close_month(session: Session, period: str) -> None:
    """Close the calendar month `period` ("YYYY-MM"): run all rollover hooks atomically.

    Runs hooks in registration order inside one transaction. Any hook failure
    rolls back the entire close. Idempotency is each hook's own responsibility
    (keyed by its (..., period)); re-running close_month must not duplicate.
    """
    with atomic(session):
        for hook in ROLLOVER_HOOKS:
            hook(period, session)


def ensure_month_closed(session: Session, today: Date) -> None:
    """Idempotent daily 'ensure': close the current calendar month.

    The scheduler (P7) calls this daily. On any day it closes today's month;
    because the registered hooks are idempotent, the repeated calls are no-ops
    and a missed day self-heals on the next run.
    """
    period = f"{today.year:04d}-{today.month:02d}"
    close_month(session, period)
