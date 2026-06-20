"""Hybrid budget services: envelopes with rollover + global safe-to-spend (ADR-002/003/005)."""
from __future__ import annotations

import re

from sqlmodel import Session, select

from ..domain.dtos import BudgetStatus, CommittedItem, SafeToSpend
from ..domain.errors import NotFound, ValidationError
from ..domain.models import (
    Budget,
    Category,
    RecurringItem,
    Transaction,
    TxStatus,
    TxType,
)
from ..domain.money import to_base_cents
from ..domain.rules import (
    due_dates,
    envelope_status_calc,
    month_bounds,
    prev_year_month,
    safe_to_spend_calc,
)
from . import transactions as _tx

_YEAR_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _validate_year_month(year_month: str) -> None:
    if not _YEAR_MONTH_RE.match(year_month):
        raise ValidationError(f"malformed year_month (expected YYYY-MM): {year_month!r}")


def set_budget(
    session: Session, category_id: int, year_month: str, amount_assigned: int
) -> Budget:
    """Upsert a category's envelope for a month.

    Raises:
        ValidationError: malformed year_month or amount_assigned < 0.
        NotFound: the category does not exist.
    """
    _validate_year_month(year_month)
    if amount_assigned < 0:
        raise ValidationError("amount_assigned must be >= 0")
    if session.get(Category, category_id) is None:
        raise NotFound(f"category {category_id} not found")
    budget = session.exec(
        select(Budget).where(
            Budget.category_id == category_id, Budget.year_month == year_month
        )
    ).first()
    if budget is None:
        budget = Budget(
            category_id=category_id, year_month=year_month, amount_assigned=amount_assigned
        )
    else:
        budget.amount_assigned = amount_assigned
    session.add(budget)
    session.commit()
    session.refresh(budget)
    return budget


def _assigned(session: Session, category_id: int, year_month: str) -> int:
    budget = session.exec(
        select(Budget).where(
            Budget.category_id == category_id, Budget.year_month == year_month
        )
    ).first()
    return budget.amount_assigned if budget is not None else 0


def _spent(session: Session, category_id: int, year_month: str) -> int:
    """Sum of expense+posted to_base for the month/category, across all accounts.

    Returns 0 when the category opts out via exclude_from_budget/exclude_from_totals.
    """
    cat = session.get(Category, category_id)
    if cat is None:
        raise NotFound(f"category {category_id} not found")
    if cat.exclude_from_budget or cat.exclude_from_totals:
        return 0
    start, end = month_bounds(year_month)
    rows = session.exec(
        select(Transaction).where(
            Transaction.category_id == category_id,
            Transaction.type == TxType.expense,
            Transaction.status == TxStatus.posted,
            Transaction.date >= start,
            Transaction.date <= end,
        )
    ).all()
    return sum(t.to_base for t in rows)


def _available(session: Session, category_id: int, year_month: str) -> int:
    """rollover_in + assigned - spent, recursing into prior months.

    Base case: a month with no assignment and no spending contributes 0 and
    stops the recursion (no infinite climb into the past).
    """
    assigned = _assigned(session, category_id, year_month)
    spent = _spent(session, category_id, year_month)
    if assigned == 0 and spent == 0:
        return 0
    rollover_in = max(_available(session, category_id, prev_year_month(year_month)), 0)
    return rollover_in + assigned - spent


def budget_status(session: Session, category_id: int, year_month: str) -> BudgetStatus:
    """Envelope status with rollover for a category/month.

    Raises:
        ValidationError: malformed year_month.
        NotFound: the category does not exist.
    """
    _validate_year_month(year_month)
    if session.get(Category, category_id) is None:
        raise NotFound(f"category {category_id} not found")
    assigned = _assigned(session, category_id, year_month)
    spent = _spent(session, category_id, year_month)
    rollover_in = max(_available(session, category_id, prev_year_month(year_month)), 0)
    return envelope_status_calc(category_id, year_month, assigned, rollover_in, spent)
