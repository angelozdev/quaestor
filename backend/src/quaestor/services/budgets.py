"""Hybrid budget services: envelopes with rollover + global safe-to-spend (ADR-002/003/005)."""
from __future__ import annotations

import re

from sqlmodel import Session, select

from ..domain.dtos import BudgetLine, BudgetStatus, CommittedItem, SafeToSpend
from ..domain.errors import NotFound, ValidationError
from ..domain.models import Budget, Category, TxType
from ..domain.money import to_cop_cents
from ..domain.rules import (
    due_dates,
    envelope_status_calc,
    prev_year_month,
    safe_to_spend_calc,
)
from . import fx as _fx
from .month_aggregate import MonthAggregate, load_month_aggregate

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


def _income_forecast(agg: MonthAggregate) -> int:
    total = 0
    for item in agg.active_recurring:
        if item.type != TxType.income:
            continue
        occurrences = due_dates(
            item.start_date, item.end_date, item.interval_unit,
            item.interval_count, agg.start, agg.end,
        )
        total += len(occurrences) * to_cop_cents(item.amount, item.currency, agg.trm)
    return total


def _committed(agg: MonthAggregate) -> tuple[int, list]:
    total = 0
    breakdown: list[CommittedItem] = []
    for item in agg.active_recurring:
        if item.type != TxType.expense:
            continue
        if item.category_id is not None and item.category_id in agg.budgeted_category_ids:
            continue
        amount = to_cop_cents(item.amount, item.currency, agg.trm)
        for d in due_dates(
            item.start_date, item.end_date, item.interval_unit,
            item.interval_count, agg.start, agg.end,
        ):
            total += amount
            breakdown.append(CommittedItem(kind="recurring", name=item.name, date=d, amount=amount))
    for tx in agg.month_planned_expense:
        if tx.category_id is not None and tx.category_id in agg.budgeted_category_ids:
            continue
        amount = agg.to_cop_cents(tx)
        total += amount
        breakdown.append(CommittedItem(kind="planned", name=tx.payee, date=tx.date, amount=amount))
    return total, breakdown


def _unbudgeted_spending(agg: MonthAggregate) -> int:
    total = 0
    for tx in agg.month_expense():
        if tx.recurring_id is not None:
            continue
        if tx.category_id is None:
            total += agg.to_cop_cents(tx)
            continue
        cat = agg.category(tx.category_id)
        if cat is not None and (cat.exclude_from_budget or cat.exclude_from_totals):
            continue
        if tx.category_id in agg.budgeted_category_ids:
            continue
        total += agg.to_cop_cents(tx)
    return total


def _sum_assigned(agg: MonthAggregate) -> int:
    return sum(b.amount_assigned for b in agg.budgets_month)


def _sum_overspend(agg: MonthAggregate) -> int:
    total = 0
    for b in agg.budgets_month:
        spent = agg.spent_for_budget(b.category_id, agg.year_month)
        rollover_in = max(agg.available(b.category_id, prev_year_month(agg.year_month)), 0)
        over = spent - (b.amount_assigned + rollover_in)
        if over > 0:
            total += over
    return total


def _safe_to_spend(agg: MonthAggregate) -> SafeToSpend:
    income = _income_forecast(agg)
    committed, breakdown = _committed(agg)
    assigned = _sum_assigned(agg)
    unbudgeted = _unbudgeted_spending(agg)
    overspend = _sum_overspend(agg)
    free = safe_to_spend_calc(income, committed, assigned, unbudgeted, overspend)
    return SafeToSpend(
        year_month=agg.year_month, income_forecast=income, committed=committed,
        assigned_envelopes=assigned, free=free, committed_breakdown=breakdown,
    )


def safe_to_spend(session: Session, year_month: str) -> SafeToSpend:
    """Global safe-to-spend headline + breakdown (ADR-003/005/014/016).

    Raises:
        MissingRate: no TRM set (AC-9).
    """
    _validate_year_month(year_month)
    trm = _fx.get_trm(session)
    return _safe_to_spend(load_month_aggregate(session, year_month, trm))


def _status(agg: MonthAggregate, category_id: int) -> BudgetStatus:
    assigned = agg.assigned(category_id, agg.year_month)
    spent = agg.spent_for_budget(category_id, agg.year_month)
    rollover_in = max(agg.available(category_id, prev_year_month(agg.year_month)), 0)
    return envelope_status_calc(category_id, agg.year_month, assigned, rollover_in, spent)


def budget_status(session: Session, category_id: int, year_month: str) -> BudgetStatus:
    """Envelope status with rollover for a category/month.

    Write-path note: callers (PUT /api/budgets, MCP planning) now pay a fixed
    ~8-query aggregate load instead of 3 + 2×(active months) recursion.

    Raises:
        MissingRate: no TRM set (AC-9).
        NotFound: the category does not exist.
    """
    _validate_year_month(year_month)
    if session.get(Category, category_id) is None:
        raise NotFound(f"category {category_id} not found")
    trm = _fx.get_trm(session)
    return _status(load_month_aggregate(session, year_month, trm), category_id)


def _budget_lines(agg: MonthAggregate) -> list[BudgetLine]:
    lines: list[BudgetLine] = []
    eligible = [
        c for c in agg.categories.values()
        if not c.archived and not c.exclude_from_budget
    ]
    for cat in sorted(eligible, key=lambda c: c.id):
        st = _status(agg, cat.id)
        lines.append(
            BudgetLine(
                category_id=cat.id, category_name=cat.name, assigned=st.assigned,
                rollover_in=st.rollover_in, spent=st.spent, available=st.available,
                pct_used=st.pct_used, status=st.status,
            )
        )
    return lines


def list_budgets(session: Session, year_month: str) -> list[BudgetLine]:
    """One envelope line per budget-eligible category for the month.

    Raises:
        MissingRate: no TRM set (AC-9).
    """
    _validate_year_month(year_month)
    trm = _fx.get_trm(session)
    return _budget_lines(load_month_aggregate(session, year_month, trm))
