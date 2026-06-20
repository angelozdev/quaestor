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


def _has_envelope(session: Session, category_id: int, year_month: str) -> bool:
    return session.exec(
        select(Budget).where(
            Budget.category_id == category_id, Budget.year_month == year_month
        )
    ).first() is not None


def _income_forecast(session: Session, start, end) -> int:
    total = 0
    items = session.exec(
        select(RecurringItem).where(
            RecurringItem.active == True,  # noqa: E712
            RecurringItem.type == TxType.income,
        )
    ).all()
    for item in items:
        for d in due_dates(
            item.start_date, item.end_date, item.interval_unit,
            item.interval_count, start, end,
        ):
            rate = _tx._resolve_fx(session, item.currency, d, None)
            total += to_base_cents(item.amount, rate)
    return total


def _committed(session: Session, year_month: str, start, end) -> tuple[int, list]:
    """Projected month obligations in non-envelope categories, counted once."""
    total = 0
    breakdown: list[CommittedItem] = []
    items = session.exec(
        select(RecurringItem).where(
            RecurringItem.active == True,  # noqa: E712
            RecurringItem.type == TxType.expense,
        )
    ).all()
    for item in items:
        if item.category_id is not None and _has_envelope(session, item.category_id, year_month):
            continue
        for d in due_dates(
            item.start_date, item.end_date, item.interval_unit,
            item.interval_count, start, end,
        ):
            rate = _tx._resolve_fx(session, item.currency, d, None)
            amount = to_base_cents(item.amount, rate)
            total += amount
            breakdown.append(CommittedItem(kind="recurring", name=item.name, date=d, amount=amount))
    planned_txs = session.exec(
        select(Transaction).where(
            Transaction.status == TxStatus.planned,
            Transaction.recurring_id == None,  # noqa: E711
            Transaction.date >= start,
            Transaction.date <= end,
        )
    ).all()
    for tx in planned_txs:
        if tx.category_id is not None and _has_envelope(session, tx.category_id, year_month):
            continue
        total += tx.to_base
        breakdown.append(CommittedItem(kind="planned", name=tx.payee, date=tx.date, amount=tx.to_base))
    return total, breakdown


def _unbudgeted_spending(session: Session, year_month: str, start, end) -> int:
    total = 0
    rows = session.exec(
        select(Transaction).where(
            Transaction.type == TxType.expense,
            Transaction.status == TxStatus.posted,
            Transaction.recurring_id == None,  # noqa: E711
            Transaction.date >= start,
            Transaction.date <= end,
        )
    ).all()
    for tx in rows:
        if tx.category_id is None:
            total += tx.to_base
            continue
        cat = session.get(Category, tx.category_id)
        if cat is not None and (cat.exclude_from_budget or cat.exclude_from_totals):
            continue
        if _has_envelope(session, tx.category_id, year_month):
            continue
        total += tx.to_base
    return total


def _sum_assigned(session: Session, year_month: str) -> int:
    rows = session.exec(
        select(Budget.amount_assigned).where(Budget.year_month == year_month)
    ).all()
    return sum(rows)


def _sum_overspend(session: Session, year_month: str) -> int:
    total = 0
    budgets_ = session.exec(
        select(Budget).where(Budget.year_month == year_month)
    ).all()
    for b in budgets_:
        spent = _spent(session, b.category_id, year_month)
        rollover_in = max(_available(session, b.category_id, prev_year_month(year_month)), 0)
        over = spent - (b.amount_assigned + rollover_in)
        if over > 0:
            total += over
    return total


def safe_to_spend(session: Session, year_month: str) -> SafeToSpend:
    """Global safe-to-spend headline + breakdown (ADR-003/005/014/016).

    Raises:
        ValidationError: malformed year_month.
    """
    _validate_year_month(year_month)
    start, end = month_bounds(year_month)
    income = _income_forecast(session, start, end)
    committed, breakdown = _committed(session, year_month, start, end)
    assigned = _sum_assigned(session, year_month)
    unbudgeted = _unbudgeted_spending(session, year_month, start, end)
    overspend = _sum_overspend(session, year_month)
    free = safe_to_spend_calc(income, committed, assigned, unbudgeted, overspend)
    return SafeToSpend(
        year_month=year_month, income_forecast=income, committed=committed,
        assigned_envelopes=assigned, free=free, committed_breakdown=breakdown,
    )


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
