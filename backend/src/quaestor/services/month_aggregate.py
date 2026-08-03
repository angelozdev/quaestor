"""Single-pass month loader: bulk-load once, compute aggregates in memory.

Replaces the per-category rollover recursion and per-budget query fanout in
the report/budget read-path. Expense history is loaded as GROUP BY sums
(rows bounded by categories × active months); full transaction rows are
loaded only for the report month and its previous month. All accessors read
memory — no DB access after `load_month_aggregate`. Response contracts are
unchanged; callers orchestrate over this unit.

Consistency: the ~8 loads run as separate statements (READ COMMITTED on
Postgres — each sees its own snapshot). A concurrent write landing mid-load
can skew one aggregate against another within a single response. Accepted
for this app; see the bounded-read-path ADR.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as Date
from decimal import Decimal

from sqlalchemy import extract, func
from sqlmodel import Session, select

from ..domain.models import (
    Budget,
    Category,
    CategoryGroup,
    RecurringItem,
    Transaction,
    TxStatus,
    TxType,
)
from ..domain.money import to_cop_cents
from ..domain.rules import month_bounds, prev_year_month


def _ym(d: Date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _next_year_month(year_month: str) -> str:
    year, month = int(year_month[:4]), int(year_month[5:7])
    if month == 12:
        return f"{year + 1:04d}-01"
    return f"{year:04d}-{month + 1:02d}"


@dataclass
class MonthAggregate:
    """In-memory month snapshot at one TRM; every accessor is DB-free.

    The `_window_*` lists hold full rows only for [previous month, report
    month]; all earlier history lives in `_spent_by_cat_month` /
    `_assigned_by_cat_month` as per-(category, month) COP sums.
    """

    year_month: str
    start: Date
    end: Date
    trm: Decimal
    categories: dict[int, Category]
    groups: dict[int, CategoryGroup]
    budgets_month: list[Budget]
    budgeted_category_ids: frozenset[int]
    active_recurring: list[RecurringItem]
    month_planned_expense: list[Transaction]
    _window_expense: list[Transaction]
    _window_income: list[Transaction]
    _spent_by_cat_month: dict[tuple[int | None, str], int]
    _assigned_by_cat_month: dict[tuple[int, str], int]
    _first_active: dict[int, str]
    _available_cache: dict[int, dict[str, int]] = field(default_factory=dict)

    def category(self, category_id: int | None) -> Category | None:
        return self.categories.get(category_id) if category_id is not None else None

    def group_name(self, category_id: int | None) -> str | None:
        cat = self.category(category_id)
        if cat is None or cat.group_id is None:
            return None
        grp = self.groups.get(cat.group_id)
        return grp.name if grp is not None else None

    def assigned(self, category_id: int, year_month: str) -> int:
        return self._assigned_by_cat_month.get((category_id, year_month), 0)

    def spent_for_budget(self, category_id: int, year_month: str) -> int:
        cat = self.categories.get(category_id)
        if cat is not None and (cat.exclude_from_budget or cat.exclude_from_totals):
            return 0
        return self._spent_by_cat_month.get((category_id, year_month), 0)

    def available(self, category_id: int, year_month: str) -> int:
        """Iterative forward fold with memo, including the gap-month reset
        (an inactive month yields 0 and passes no rollover forward)."""
        cache = self._available_cache.setdefault(category_id, {})
        cached = cache.get(year_month)
        if cached is not None:
            return cached
        start = self._first_active.get(category_id)
        if start is None or year_month < start:
            return 0
        prev_avail = 0
        ym = start
        while True:
            assigned = self.assigned(category_id, ym)
            spent = self.spent_for_budget(category_id, ym)
            avail = 0 if assigned == 0 and spent == 0 else max(prev_avail, 0) + assigned - spent
            cache[ym] = avail
            if ym == year_month:
                return avail
            prev_avail = avail
            ym = _next_year_month(ym)

    def posted_in_month(self, year_month: str, tx_type: TxType) -> list[Transaction]:
        """Posted rows of the month, minus excluded categories. Valid ONLY
        for the report month and its previous month (the loaded window)."""
        source = self._window_expense if tx_type == TxType.expense else self._window_income
        kept: list[Transaction] = []
        for tx in source:
            if _ym(tx.date) != year_month:
                continue
            cat = self.category(tx.category_id)
            if cat is not None and cat.exclude_from_totals:
                continue
            kept.append(tx)
        return kept

    def month_expense(self) -> list[Transaction]:
        return self.posted_in_month(self.year_month, TxType.expense)

    def month_income(self) -> list[Transaction]:
        return self.posted_in_month(self.year_month, TxType.income)

    def to_cop_cents(self, tx: Transaction) -> int:
        """Read-time COP cents for one row at this aggregate's TRM."""
        return to_cop_cents(tx.amount, tx.currency, self.trm)

    def totals_for(self, year_month: str) -> tuple[int, int, int]:
        income = sum(self.to_cop_cents(t) for t in self.posted_in_month(year_month, TxType.income))
        expense = sum(self.to_cop_cents(t) for t in self.posted_in_month(year_month, TxType.expense))
        return income, expense, income - expense


def load_month_aggregate(session: Session, year_month: str, trm: Decimal) -> MonthAggregate:
    """Bulk-load the month at one TRM, fetched once by the caller
    (the read path entry point) and used for every read-time conversion."""
    start, end = month_bounds(year_month)
    prev_start, _ = month_bounds(prev_year_month(year_month))

    categories = {c.id: c for c in session.exec(select(Category)).all()}
    groups = {g.id: g for g in session.exec(select(CategoryGroup)).all()}

    spent_rows = session.exec(
        select(
            Transaction.category_id,
            extract("year", Transaction.date),
            extract("month", Transaction.date),
            Transaction.currency,
            func.sum(Transaction.amount),
        )
        .where(
            Transaction.type == TxType.expense,
            Transaction.status == TxStatus.posted,
        )
        .group_by(
            Transaction.category_id,
            extract("year", Transaction.date),
            extract("month", Transaction.date),
            Transaction.currency,
        )
    ).all()
    spent_by_cat_month: dict[tuple[int | None, str], int] = {}
    for cat_id, y, m, currency, total in spent_rows:
        key = (cat_id, f"{int(y):04d}-{int(m):02d}")
        spent_by_cat_month[key] = spent_by_cat_month.get(key, 0) + to_cop_cents(int(total), currency, trm)

    def _window(tx_type: TxType) -> list[Transaction]:
        return list(
            session.exec(
                select(Transaction).where(
                    Transaction.type == tx_type,
                    Transaction.status == TxStatus.posted,
                    Transaction.date >= prev_start,
                    Transaction.date <= end,
                )
            ).all()
        )

    window_expense = _window(TxType.expense)
    window_income = _window(TxType.income)

    budgets_all = list(session.exec(select(Budget)).all())
    active_recurring = list(
        session.exec(
            select(RecurringItem).where(RecurringItem.active == True)  # noqa: E712
        ).all()
    )
    month_planned_expense = list(
        session.exec(
            select(Transaction).where(
                Transaction.type == TxType.expense,
                Transaction.status == TxStatus.planned,
                Transaction.recurring_id == None,  # noqa: E711
                Transaction.date >= start,
                Transaction.date <= end,
            )
        ).all()
    )

    assigned_by_cat_month = {(b.category_id, b.year_month): b.amount_assigned for b in budgets_all}
    budgets_month = [b for b in budgets_all if b.year_month == year_month]

    first_active: dict[int, str] = {}
    for cat_id, ym in list(spent_by_cat_month) + list(assigned_by_cat_month):
        if cat_id is None:
            continue
        if cat_id not in first_active or ym < first_active[cat_id]:
            first_active[cat_id] = ym

    return MonthAggregate(
        year_month=year_month,
        start=start,
        end=end,
        trm=trm,
        categories=categories,
        groups=groups,
        budgets_month=budgets_month,
        budgeted_category_ids=frozenset(b.category_id for b in budgets_month),
        active_recurring=active_recurring,
        month_planned_expense=month_planned_expense,
        _window_expense=window_expense,
        _window_income=window_income,
        _spent_by_cat_month=spent_by_cat_month,
        _assigned_by_cat_month=assigned_by_cat_month,
        _first_active=first_active,
    )
