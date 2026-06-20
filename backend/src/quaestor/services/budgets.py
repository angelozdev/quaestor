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
