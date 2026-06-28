"""Behavior tests for the SortSpec value object.

Every test exercises an observable outcome — input rejected with a useful
error, or a SQL query returns rows in a specific order. Tests of pure
implementation details (e.g. that SortSpec is a frozen dataclass, or that
the Literal types compile to certain strings) are intentionally omitted:
the runtime ordering tests below would catch any mutation that actually
broke behavior, and the Literal types are validated by Pydantic at the
REST/MCP boundary in Tasks 4 and 5.
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlmodel import select

from quaestor.domain.errors import ValidationError
from quaestor.domain.models import AccountType, Transaction
from quaestor.domain.sort import SortSpec
from quaestor.services import accounts, transactions


def _sortable() -> dict[str, object]:
    return {"date": Transaction.date, "created_at": Transaction.created_at}


def _seed(session):
    a = accounts.create_account(session, "A", AccountType.debit, "COP", balance=100_000)
    t1 = transactions.record_expense(session, a.id, 100, "COP", date(2026, 6, 1), "first")
    t2 = transactions.record_expense(session, a.id, 200, "COP", date(2026, 6, 2), "second")
    t3 = transactions.record_expense(session, a.id, 300, "COP", date(2026, 6, 3), "third")
    return t1, t2, t3


def test_sort_spec_rejects_unknown_field():
    """An unknown field is rejected at the boundary instead of silently
    passing through to SQL."""
    spec = SortSpec(field="amount", order="asc")  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="unknown sort field"):
        spec.resolve(_sortable(), Transaction.id)  # type: ignore[arg-type]


def test_sort_spec_error_lists_allowed_fields():
    """An unknown-field error must enumerate the allowed values so callers
    can self-correct without reading the source."""
    spec = SortSpec(field="amount", order="asc")  # type: ignore[arg-type]
    with pytest.raises(ValidationError) as exc_info:
        spec.resolve(_sortable(), Transaction.id)  # type: ignore[arg-type]
    msg = str(exc_info.value)
    assert "date" in msg and "created_at" in msg


def test_sort_spec_resolve_desc_orders_newest_creation_first(session):
    """resolved (created_at, desc) applied to a real query returns
    newest-created row first."""
    _seed(session)
    spec = SortSpec(field="created_at", order="desc")
    primary, secondary = spec.resolve(_sortable(), Transaction.id)
    rows = session.exec(select(Transaction).order_by(primary, secondary)).all()
    assert [r.payee for r in rows] == ["third", "second", "first"]


def test_sort_spec_resolve_asc_orders_oldest_date_first(session):
    """resolved (date, asc) returns oldest-date row first."""
    _seed(session)
    spec = SortSpec(field="date", order="asc")
    primary, secondary = spec.resolve(_sortable(), Transaction.id)
    rows = session.exec(select(Transaction).order_by(primary, secondary)).all()
    assert [r.payee for r in rows] == ["first", "second", "third"]


def test_sort_spec_resolve_date_desc_orders_newest_date_first(session):
    """resolved (date, desc) returns newest-date row first."""
    _seed(session)
    spec = SortSpec(field="date", order="desc")
    primary, secondary = spec.resolve(_sortable(), Transaction.id)
    rows = session.exec(select(Transaction).order_by(primary, secondary)).all()
    assert [r.payee for r in rows] == ["third", "second", "first"]
