"""What one month has, and what already has a claim on it.

Neither the fund nor the meta owns this: a month is where the two meet, plus
the income that is not either one's business. `services.funds` folds the funds
and `services.metas` folds the metas; this module asks both and adds nothing to
either. Both are imported here and neither imports this, so the two nouns stay
independent of each other.

Every figure is derived from the month asked about and from what is known now,
never from a stored snapshot (AC-16), so no clock is needed to read a past
month.
"""

from __future__ import annotations

from collections import Counter

from sqlmodel import Session

from ..domain.dtos import MonthAvailable, MonthRates, MonthSplit
from ..domain.models import RecurringItem, TxType
from ..domain.money import to_cop_cents
from ..domain.rules import available_calc, margin_calc, monthly_rate_calc, share_calc, split_calc
from . import funds, metas
from .month_aggregate import MonthAggregate, load_month, require_year_month


def _promised(agg: MonthAggregate, item: RecurringItem) -> int:
    return len(agg.live_turns(item)) * to_cop_cents(item.amount, item.currency, agg.trm)


def _income(agg: MonthAggregate) -> int:
    """What the month actually has, reconciled per income category (ADR-0044).

    Once money lands in an income category, that category stops guessing: what
    its obligations promised is dropped whole and the month counts what
    arrived, so a salary expecting 5.000.000 where 4.200.000 was recorded
    counts 4.200.000 rather than both (AC-14c). The boundary is per category
    and not per obligation — chosen, not overlooked, and ADR-0044 says why.
    """
    arrived: dict[int | None, int] = {}
    for tx in agg.month_income():
        arrived[tx.category_id] = arrived.get(tx.category_id, 0) + agg.to_cop_cents(tx)
    promised: dict[int | None, int] = {}
    for item in agg.active_recurring:
        if item.type == TxType.income and item.category_id not in arrived:
            promised[item.category_id] = promised.get(item.category_id, 0) + _promised(agg, item)
    return sum(arrived.values()) + sum(promised.values())


def _unsettled_promise(agg: MonthAggregate, item: RecurringItem, posted_turns: int) -> int:
    """What an obligation still promises, after the turns that already posted.

    A turn that posted is not promised any more — it happened, and the money
    that left is counted at its real figure instead (product ADR-039). Only the
    turns still ahead carry the declared amount.
    """
    remaining = max(len(agg.live_turns(item)) - posted_turns, 0)
    return remaining * to_cop_cents(item.amount, item.currency, agg.trm)


def _uncovered(agg: MonthAggregate, overspill: int) -> int:
    """Everything the month owes that no fund covers (ADR-0044).

    One term on purpose: spending in categories with no fund, obligations in
    categories with no fund, and the excess past what a fund had — only the
    excess leaves the money available, never the whole amount (AC-13).
    Splitting it would stop the breakdown adding up (AC-10).

    An obligation stops guessing the moment its charge posts, the same way an
    income category does (product ADR-039, mirroring D5): a bill declaring
    200.000 that posts at 250.000 costs the month 250.000, and one whose
    obligation is switched off after posting still costs what it really did.
    Every posted expense counts once, at what left the account.
    """
    funded = {fund.category_id for fund in agg.funds}
    posted = [tx for tx in agg.month_expense() if tx.category_id not in funded and tx.meta_id is None]
    spent = sum(agg.to_cop_cents(tx) for tx in posted)
    posted_turns = Counter(tx.recurring_id for tx in posted if tx.recurring_id is not None)
    obligations = sum(
        _unsettled_promise(agg, item, posted_turns[item.id])
        for item in agg.active_recurring
        if item.type == TxType.expense and item.category_id not in funded
    )
    planned = sum(
        agg.to_cop_cents(tx) for tx in agg.month_planned_expense if tx.category_id not in funded and tx.meta_id is None
    )
    return spent + obligations + planned + overspill + metas.uncovered_total(agg)


def month_available(agg: MonthAggregate) -> MonthAvailable:
    """The money available for the month this aggregate already holds.

    The entry point for a caller that has loaded the month already — the
    monthly report — so the fund is folded once per read and not twice.
    `available` is the same answer for a caller holding only a session.
    """
    year_month = agg.year_month
    folded = funds.fold(agg)
    lines = folded.lines
    income = _income(agg)
    uncovered = _uncovered(agg, folded.overspill)
    contributed = metas.contributed_total(agg)
    released = metas.released_total(agg)
    claimed = (
        sum(line.asks for line in lines)
        + metas.asks_total(agg)
        + metas.cancelled_asks_total(agg)
        + contributed
        - released
    )
    return MonthAvailable(
        year_month=year_month,
        income=income,
        funds=lines,
        uncovered=uncovered,
        free=available_calc(income, claimed, uncovered),
        metas=metas.statuses(agg) + metas.cancelled_statuses(agg),
        contributed=contributed,
        released=released,
    )


def month_split(agg: MonthAggregate) -> MonthSplit:
    """What share of the month was spent, set aside, or left (AC-37).

    Nothing new is computed: it is `month_available`'s own terms, split by the
    one thing that already tells the two shapes apart. A *presupuesto* is a
    ceiling and counts as consumo; a *fondo* carries its leftover forward and
    counts as ahorro; a meta is always ahorro; and spending in a category the
    owner marked as saving is ahorro too (AC-41).

    `ahorro` is net and may be negative — a month a meta is cancelled is a
    month savings come back out. That is what keeps `consumo + ahorro + libre`
    equal to the income in every month, which is the property AC-37 exists for.
    `saved` is the same month before the give-back, so a month that both set
    money aside and cancelled a meta can say so twice instead of once.
    """
    view = month_available(agg)
    presupuesto = sum(line.asks for line in view.funds if not line.accumulates)
    fondo = sum(line.asks for line in view.funds if line.accumulates)
    saved_by_spending = _spent_where_spending_is_saving(agg)
    consumo = presupuesto + view.uncovered - saved_by_spending
    saved = fondo + sum(line.asks for line in view.metas) + view.contributed + saved_by_spending
    ahorro = saved - view.released
    libre = split_calc(consumo, ahorro, view.income)
    return MonthSplit(
        year_month=agg.year_month,
        income=view.income,
        consumo=consumo,
        ahorro=ahorro,
        libre=libre,
        ahorro_share=share_calc(ahorro, view.income),
        saved=saved,
        saved_share=share_calc(saved, view.income),
        released=view.released,
        gave_back=[line for line in view.metas if line.released > 0],
    )


def _spent_where_spending_is_saving(agg: MonthAggregate) -> int:
    """Spending the owner declared to be saving, out of the uncovered term.

    Only the uncovered part: spending a fund already covers is the fund's
    business, and the mark moves what nothing else claims (AC-41).
    """
    funded = {fund.category_id for fund in agg.funds}
    saving = {cid for cid, cat in agg.categories.items() if cat.counts_as_saving}
    return sum(
        agg.to_cop_cents(tx)
        for tx in agg.month_expense()
        if tx.category_id in saving and tx.category_id not in funded and tx.meta_id is None
    )


def split(session: Session, year_month: str) -> MonthSplit:
    """What share of a month is spent, set aside, or left.

    Raises:
        ValidationError: malformed year_month.
        MissingRate: no TRM is set.
    """
    require_year_month(year_month)
    return month_split(load_month(session, year_month))


def available(session: Session, year_month: str) -> MonthAvailable:
    """The money available for a month, opened into the terms that make it.

    A balance, never a rate: it counts income the month is actually owed and
    nothing that has not arrived yet (AC-14). Every figure is derived from the
    month asked about and from what is known now, never from a stored snapshot
    (AC-16) — so no clock is needed.

    Raises:
        ValidationError: malformed year_month.
        MissingRate: no TRM is set.
    """
    require_year_month(year_month)
    return month_available(load_month(session, year_month))


def rates(session: Session, year_month: str) -> MonthRates:
    """What the owner earns a month, what the owner costs a month, and the gap.

    Rates, never the money available: each cycle is spread across its own
    months, so a quarterly income counts here in every month of its cycle and
    there only in the month it is due (AC-14b).

    Raises:
        ValidationError: malformed year_month.
        MissingRate: no TRM is set.
    """
    require_year_month(year_month)
    agg = load_month(session, year_month)
    funded = {fund.category_id for fund in agg.funds}
    earning = 0
    cost = sum(line.asks for line in funds.fold(agg).lines)
    for item in agg.active_recurring:
        share = monthly_rate_calc(
            to_cop_cents(item.amount, item.currency, agg.trm), item.interval_unit, item.interval_count
        )
        if item.type == TxType.income:
            earning += share
        elif item.category_id not in funded:
            cost += share
    return MonthRates(year_month=year_month, earning=earning, cost=cost, margin=margin_calc(earning, cost))
