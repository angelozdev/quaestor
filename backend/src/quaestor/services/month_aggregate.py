"""Single-pass month loader: bulk-load once, compute aggregates in memory.

Replaces the per-category query fanout in the report and fund read-path.
Expense history is loaded as GROUP BY sums (rows bounded by categories ×
active months); full transaction rows are loaded only for the report month
and its previous month. All accessors read memory — no DB access after
`load_month_aggregate`. Response contracts are unchanged; callers orchestrate
over this unit.

Consistency: the ~10 loads run as separate statements (READ COMMITTED on
Postgres — each sees its own snapshot). A concurrent write landing mid-load
can skew one aggregate against another within a single response. Accepted
for this app; see the bounded-read-path ADR.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date
from decimal import Decimal

from sqlalchemy import extract, func, or_
from sqlmodel import Session, select

from ..domain.errors import ValidationError
from ..domain.models import (
    Category,
    CategoryGroup,
    Fund,
    Meta,
    MetaAmendment,
    MetaContribution,
    OccurrenceStatus,
    RecurringItem,
    RecurringOccurrence,
    Transaction,
    TxStatus,
    TxType,
)
from ..domain.money import to_cop_cents
from ..domain.recurrence import due_dates
from ..domain.rules import is_year_month, month_bounds, prev_year_month, year_month_of
from . import fx as _fx


@dataclass
class MonthAggregate:
    """In-memory month snapshot at one TRM; every accessor is DB-free.

    The `_window_*` lists hold full rows only for [previous month, report
    month]; all earlier history lives in `_spent_by_cat_month` as
    per-(category, month) COP sums.

    `contributions` holds only the money still set aside. A contribution a
    restore left behind was already handed back when the meta was cancelled
    (ADR-0055), so it stays in the owner's list and out of every figure.
    """

    year_month: str
    start: Date
    end: Date
    trm: Decimal
    categories: dict[int, Category]
    groups: dict[int, CategoryGroup]
    active_recurring: list[RecurringItem]
    month_planned_expense: list[Transaction]
    funds: list[Fund]
    metas: list[Meta]
    cancelled_this_month: list[Meta]
    contributions: dict[int, dict[str, int]]
    amendments: dict[int, list[MetaAmendment]]
    linked_by_meta: dict[int, list[Transaction]]
    first_movement_month: str | None
    skipped_turns: frozenset[tuple[int, Date]]
    _window_expense: list[Transaction]
    _window_income: list[Transaction]
    _spent_by_cat_month: dict[tuple[int | None, str], int]

    def category(self, category_id: int | None) -> Category | None:
        return self.categories.get(category_id) if category_id is not None else None

    def group_name(self, category_id: int | None) -> str | None:
        cat = self.category(category_id)
        if cat is None or cat.group_id is None:
            return None
        grp = self.groups.get(cat.group_id)
        return grp.name if grp is not None else None

    def spent_in(self, category_id: int, year_month: str) -> int:
        """A category's posted spending for one month, in COP cents.

        This hides nothing a fund is answerable for: a fund covers whatever its
        category spent, and money set aside that vanished from the figure would
        leave the fund reporting a balance it does not have.

        A purchase pointed at a meta is the one exception, and it is not
        hiding: the meta counted it, so counting it here too would count the
        same money twice (ADR-0046). Only the *plan* reads this — the fund's
        fold and the report's funds section. What was actually spent is read
        from the movements themselves, and the spending report still shows the
        purchase in full (AC-33).
        """
        return self._spent_by_cat_month.get((category_id, year_month), 0)

    def obligations_in(self, category_id: int) -> list[RecurringItem]:
        """The live expense obligations filed under one category (AC-4)."""
        return [i for i in self.active_recurring if i.type == TxType.expense and i.category_id == category_id]

    def funded_categories(self) -> frozenset[int]:
        """The categories a fund answers for, so the month need not ask twice.

        What is left over is what nothing covers, and the month reads that set
        three times per request (AC-13).
        """
        return frozenset(fund.category_id for fund in self.funds)

    def was_skipped(self, recurring_id: int, due_date: Date) -> bool:
        """Whether the owner said this turn will not happen (AC-17)."""
        return (recurring_id, due_date) in self.skipped_turns

    def turns_in(self, item: RecurringItem, year_month: str) -> list[Date]:
        """Every turn this obligation falls due on inside one month.

        The month is named rather than assumed: a fold walks months behind the
        one the aggregate was loaded for, and reading this month's turns for
        all of them would make a skipped charge skip every earlier month too.
        """
        start, end = month_bounds(year_month)
        return due_dates(item.start_date, item.end_date, item.interval_unit, item.interval_count, start, end)

    def live_turns(self, item: RecurringItem) -> list[Date]:
        """This month's turns that are still going to happen (AC-17)."""
        return [due for due in self.turns_in(item, self.year_month) if not self.was_skipped(item.id, due)]

    def posted_in_month(self, year_month: str, tx_type: TxType) -> list[Transaction]:
        """Posted rows of the month, minus excluded categories. Valid ONLY
        for the report month and its previous month (the loaded window)."""
        source = self._window_expense if tx_type == TxType.expense else self._window_income
        kept: list[Transaction] = []
        for tx in source:
            if year_month_of(tx.date) != year_month:
                continue
            cat = self.category(tx.category_id)
            if cat is not None and cat.exclude_from_totals:
                continue
            kept.append(tx)
        return kept

    def linked_to(self, meta_id: int, *, posted_only: bool = True) -> list[Transaction]:
        """Purchases pointed at one meta, on or before this month.

        Posted by default: only money that left completes a meta. The month's
        arithmetic asks for the planned ones too, because a debt owed this
        month costs this month and must be netted against what the meta holds
        (AC-43).

        Indexed by meta rather than filtered: the fold asks this once per month
        walked, per meta, so scanning every linked row each time made the read
        path quadratic in the number of metas.
        """
        rows = self.linked_by_meta.get(meta_id, ())
        return [tx for tx in rows if tx.status == TxStatus.posted] if posted_only else list(rows)

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


def require_year_month(year_month: str, what: str = "year_month") -> str:
    """The month a caller asked for, or a refusal naming the field it came from.

    Month knowledge, not fund or meta knowledge: three services were each
    keeping their own copy of this guard.
    """
    if not is_year_month(year_month):
        raise ValidationError(f"malformed {what} (expected YYYY-MM): {year_month!r}")
    return year_month


def load_month(session: Session, year_month: str) -> MonthAggregate:
    """The month, loaded once at the rate demanded on entry.

    Reading anything in COP needs the rate, even a month in pure pesos: the
    app never guesses one (ADR-0031, product ADR-038).

    Raises:
        MissingRate: no TRM is set.
    """
    return load_month_aggregate(session, year_month, _fx.get_trm(session))


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
            Transaction.meta_id.is_(None),
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

    windowed = session.exec(
        select(Transaction).where(
            Transaction.type.in_([TxType.expense, TxType.income]),
            Transaction.status == TxStatus.posted,
            Transaction.date >= prev_start,
            Transaction.date <= end,
        )
    ).all()
    window_expense = [tx for tx in windowed if tx.type == TxType.expense]
    window_income = [tx for tx in windowed if tx.type == TxType.income]

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

    funds = list(session.exec(select(Fund)).all())
    every_meta = list(
        session.exec(select(Meta).where(or_(Meta.cancelled_month.is_(None), Meta.cancelled_month >= year_month))).all()
    )
    metas = [m for m in every_meta if m.cancelled_month is None or m.cancelled_month > year_month]
    cancelled_this_month = [m for m in every_meta if m.cancelled_month == year_month]
    contributions: dict[int, dict[str, int]] = {}
    for meta_id, month, total in session.exec(
        select(
            MetaContribution.meta_id,
            MetaContribution.year_month,
            func.sum(MetaContribution.amount),
        )
        .where(MetaContribution.year_month <= year_month, MetaContribution.returned_month.is_(None))
        .group_by(MetaContribution.meta_id, MetaContribution.year_month)
    ).all():
        contributions.setdefault(meta_id, {})[month] = int(total)
    amendments: dict[int, list[MetaAmendment]] = {}
    for row in session.exec(
        select(MetaAmendment).where(MetaAmendment.year_month <= year_month).order_by(MetaAmendment.year_month)
    ).all():
        amendments.setdefault(row.meta_id, []).append(row)
    linked_by_meta: dict[int, list[Transaction]] = {}
    for tx in session.exec(
        select(Transaction).where(
            Transaction.meta_id.is_not(None),
            Transaction.status.in_([TxStatus.posted, TxStatus.planned]),
            Transaction.date <= end,
        )
    ).all():
        linked_by_meta.setdefault(tx.meta_id, []).append(tx)
    first_movement = session.exec(
        select(Transaction.date).where(Transaction.status == TxStatus.posted).order_by(Transaction.date).limit(1)
    ).first()
    skipped_turns = frozenset(
        session.exec(
            select(RecurringOccurrence.recurring_id, RecurringOccurrence.due_date).where(
                RecurringOccurrence.status == OccurrenceStatus.skipped
            )
        ).all()
    )

    return MonthAggregate(
        year_month=year_month,
        start=start,
        end=end,
        trm=trm,
        categories=categories,
        groups=groups,
        active_recurring=active_recurring,
        month_planned_expense=month_planned_expense,
        funds=funds,
        metas=metas,
        cancelled_this_month=cancelled_this_month,
        contributions=contributions,
        amendments=amendments,
        linked_by_meta=linked_by_meta,
        first_movement_month=year_month_of(first_movement) if first_movement is not None else None,
        skipped_turns=skipped_turns,
        _window_expense=window_expense,
        _window_income=window_income,
        _spent_by_cat_month=spent_by_cat_month,
    )
