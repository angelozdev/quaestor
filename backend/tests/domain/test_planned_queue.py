"""Unit tests for the OutstandingQueue value object.

The VO is pure data — tests exercise the public surface (constructor,
properties, classmethod) only. No DB, no service, no I/O. The "mutual
exclusion" assertion documents the invariant that `to_pay` must
preserve at the call site; the VO itself does not enforce it
(structurally, the construction site is the only place that produces
buckets, and the date ranges are disjoint by query construction).
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal

import pytest

from quaestor.domain.models import AccountType, Transaction
from quaestor.domain.planned import OutstandingQueue
from quaestor.services import accounts, transactions


def _tx(session, account_id: int, payee: str, amount: int, due: date) -> Transaction:
    return transactions.record_expense(
        session, account_id, amount, "COP", due, payee
    )


def test_outstanding_queue_is_empty_when_both_buckets_empty():
    q = OutstandingQueue()
    assert q.is_empty is True
    assert q.overdue == []
    assert q.upcoming == []
    assert q.total_cop_cents(Decimal("4000")) == 0
    assert q.all_items() == []


def test_outstanding_queue_total_is_read_time_sum_of_both_buckets(session):
    a = accounts.create_account(session, "A", AccountType.debit, "COP", balance=10_000_000)
    overdue = _tx(session, a.id, "Rent past", 100_000, date(2026, 6, 1))
    upcoming = _tx(session, a.id, "Rent next", 200_000, date(2026, 7, 10))
    q = OutstandingQueue(overdue=[overdue], upcoming=[upcoming])
    assert q.total_cop_cents(Decimal("4000")) == 300_000
    assert q.is_empty is False


def test_outstanding_queue_total_converts_usd_at_the_given_trm(session):
    a = accounts.create_account(session, "Wise", AccountType.debit, "USD", balance=10_000_000)
    usd = transactions.record_expense(session, a.id, 1_000, "USD", date(2026, 7, 1), "Sub")
    q = OutstandingQueue(upcoming=[usd])
    assert q.total_cop_cents(Decimal("4000")) == 4_000_000
    assert q.total_cop_cents(Decimal("4100")) == 4_100_000


def test_outstanding_queue_all_items_overdue_first(session):
    a = accounts.create_account(session, "A", AccountType.debit, "COP", balance=10_000_000)
    overdue_oldest = _tx(session, a.id, "oldest overdue", 50_000, date(2026, 5, 1))
    overdue_newer = _tx(session, a.id, "newer overdue", 75_000, date(2026, 6, 15))
    upcoming_earlier = _tx(session, a.id, "upcoming earlier", 100_000, date(2026, 7, 5))
    upcoming_later = _tx(session, a.id, "upcoming later", 150_000, date(2026, 7, 20))
    q = OutstandingQueue(
        overdue=[overdue_oldest, overdue_newer],
        upcoming=[upcoming_earlier, upcoming_later],
    )
    flat = q.all_items()
    assert [t.payee for t in flat] == [
        "oldest overdue",
        "newer overdue",
        "upcoming earlier",
        "upcoming later",
    ]


def test_outstanding_queue_from_lists_eagerly_evaluates_iterables():
    """Iterables are consumed once into lists — no lazy surprise."""
    overdue_iter = iter([_FakeTx(1), _FakeTx(2)])
    upcoming_iter = iter([_FakeTx(3)])
    q = OutstandingQueue.from_lists(overdue_iter, upcoming_iter)
    assert len(q.overdue) == 2
    assert len(q.upcoming) == 1
    assert list(overdue_iter) == []
    assert list(upcoming_iter) == []


def test_outstanding_queue_is_frozen():
    """The VO is immutable — attribute assignment raises FrozenInstanceError.

    `pytest.raises(FrozenInstanceError)` is the strict form; the loose
    `pytest.raises(Exception)` would also accept any unrelated error
    (KeyError, TypeError from a typo, etc.) and silently pass.
    """
    q = OutstandingQueue()

    with pytest.raises(FrozenInstanceError):
        q.overdue = []  # type: ignore[misc]


class _FakeTx:
    """Minimal stand-in for a Transaction — tests don't need a real row."""

    def __init__(self, id: int) -> None:
        self.id = id
        self.payee = f"fake-{id}"
        self.amount = id * 100
        self.currency = "COP"
