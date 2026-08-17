"""Sinking funds: one rule per expense category, and the balance it implies.

A fund stores its funding **rule**, never a balance (ADR-0043). What it holds
is folded forward from the owner's own anchor over the spending the month
aggregate already carries, so a configured fund costs nothing per month
forever — there is no ritual to run and nothing to advance.

The dated rule is one division: *what is still missing ÷ the months from
this one through the month before the charge*, floored at one month
(`rules.fund_ask_calc`). The two undated ones never look at what the fund
holds — a fixed rule asks its amount, an average rule asks the window's
average. Two behaviours fall out of the floor rather than being coded: the
month a charge lands does not contribute (AC-6), and an obligation due now
asks for its full amount.

Every figure is derived from what is known now, including past months (AC-16):
nothing here reads a stored monthly snapshot, and asking about August after
switching an obligation off in October gives August without it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date
from datetime import timedelta
from functools import partial

from sqlmodel import Session, select

from ..domain.dtos import ChargeMark, FundCharge, FundLine, FundPreview, FundStatus
from ..domain.errors import NotFound, ValidationError
from ..domain.models import (
    Category,
    Fund,
    FundRule,
    IntervalUnit,
    RecurringItem,
    Transaction,
    TxStatus,
    TxType,
)
from ..domain.money import cents_to_major, to_cop_cents
from ..domain.recurrence import next_due_on_or_after
from ..domain.rules import (
    claim_holdings,
    fund_ask_calc,
    fund_holds_calc,
    fund_next_opening_calc,
    month_bounds,
    monthly_average_calc,
    months_to_fund,
    next_year_month,
    prev_year_month,
    shift_year_month,
    uncovered_excess_calc,
    year_month_of,
)
from . import occurrences
from .month_aggregate import MonthAggregate, load_month, require_year_month

_DATED_RULES = (FundRule.from_recurring,)


@dataclass(frozen=True)
class _Ask:
    """What a fund asks for one month, and what it learned working it out.

    `charges` are the terms `amount` is the sum of. Keeping them is the whole
    of ADR-0054's second half: the division was always done per obligation and
    then thrown away, so the breakdown costs no reading and cannot fail to add
    up — it *is* the addends.
    """

    amount: int
    charge_month: str | None = None
    averaged_over: int | None = None
    charges: tuple[FundCharge, ...] = ()


@dataclass(frozen=True)
class _Month:
    """One month of the fold."""

    opening: int
    holds: int
    spent: int
    ask: _Ask
    ask_before_spending: _Ask
    carries: int


@dataclass(frozen=True)
class _Obligation:
    name: str
    required: int
    charge_month: str
    can_be_spread: bool


def _settled_by_spending(
    agg: MonthAggregate, category_id: int, year_month: str, turns: list[tuple[RecurringItem, list[Date]]]
) -> set[int]:
    """The obligations whose turn this month the category's spending already paid.

    Money that left the category covers the nearest turn first — the fund saved
    for it month by month and then spent it, so the cycle is done and the next
    one begins (AC-11). Riding `spent_in` keeps this free: the aggregate already
    holds every month's spending.
    """
    soonest_first = sorted(
        ((due, item) for item, dues in turns for due in dues),
        key=lambda pair: (pair[0], pair[1].id),
    )
    left = agg.spent_in(category_id, year_month)
    settled = set()
    for _, item in soonest_first:
        required = to_cop_cents(item.amount, item.currency, agg.trm)
        if left < required:
            continue
        left -= required
        settled.add(item.id)
    return settled


def _turn_after(item: RecurringItem, year_month: str, ends_on: Date | None) -> str | None:
    """The month of this obligation's first turn after `year_month`, if it has one.

    `ends_on` is handed in rather than read off the item because the two callers
    ask different questions. What the fund fills for next stops at the end date;
    whether a charge can be spread is about the cadence, which an end date does
    not change.
    """
    _, end = month_bounds(year_month)
    after = next_due_on_or_after(
        item.start_date, ends_on, item.interval_unit, item.interval_count, end + timedelta(days=1)
    )
    return year_month_of(after) if after is not None else None


def _charge_month_for(
    agg: MonthAggregate, item: RecurringItem, year_month: str, dues: list[Date], settled: bool
) -> str | None:
    """The month of the charge this obligation is being funded for.

    The fund fills for the next turn nobody has settled. A turn the owner
    skipped is not going to happen, so the obligation asks nothing at all that
    month (AC-17); a turn already paid moves the fund on to the next cycle
    (AC-11); a turn still standing in this very month leaves zero months to
    save, and the floor of one makes the fund ask for all of it now (AC-4).
    """
    if any(agg.was_skipped(item.id, due) for due in dues):
        return None
    if dues and not settled:
        return year_month
    return _turn_after(item, year_month, item.end_date)


def _can_be_spread(item: RecurringItem, charge_month: str) -> bool:
    """Whether a whole month fits between this charge and the next its cadence gives (ADR-0054).

    A charge that lands every month never leaves one, so the fund can only ever
    ask it whole — which is why it is never the surprise the warning announces.

    Asked of the cadence and not of the calendar an end date cuts short. An
    obligation ending on this very turn has no turn after it, and reading that
    as "nothing forces it into one month" let a monthly charge in its last month
    announce itself — the defect ADR-0054 exists to kill, in a narrower shape.
    A charge that arrives every month does not stop being ordinary by being the
    last of its kind (AC-13).

    Read from the rhythm rather than from the declared interval, so "every 45
    days" and "every 6 weeks" answer by what they actually do.
    """
    following = _turn_after(item, charge_month, None)
    return following is None or months_to_fund(charge_month, following) > 1


def _still_charges(agg: MonthAggregate, item: RecurringItem, year_month: str) -> bool:
    """Whether this obligation has a turn that will actually happen, now or later.

    A turn the owner skipped is not going to happen, and a rule left switched on
    past its end date has none coming. Either alone leaves the fund with nothing
    to set aside this month; both together leave the category finished — and
    those are the two different sentences AC-8 and AC-9 ask for.
    """
    if any(not agg.was_skipped(item.id, due) for due in agg.turns_in(item, year_month)):
        return True
    return _turn_after(item, year_month, item.end_date) is not None


def _still_charges_in(agg: MonthAggregate, category_id: int, year_month: str) -> bool:
    """Whether the category holds any obligation still due something."""
    return any(_still_charges(agg, item, year_month) for item in agg.obligations_in(category_id))


def _still_waiting_for(agg: MonthAggregate, fund: Fund, year_month: str) -> bool:
    """Whether this fund still has a charge coming — its own, or its category's."""
    if fund.recurring_id is None:
        return _still_charges_in(agg, fund.category_id, year_month)
    item = agg.obligation(fund.recurring_id)
    return item is not None and _still_charges(agg, item, year_month)


def _obligations(agg: MonthAggregate, category_id: int, year_month: str) -> list[_Obligation]:
    """What each obligation in the category still needs, soonest charge first.

    Each obligation's turns for the month are worked out once here and handed to
    both readers: which turns the spending settled, and which charge the fund is
    filling for.

    This is the category-wide reading, which still has to guess which charge the
    spending paid. A fund that hangs off one charge does not guess (ADR-0057).
    """
    turns = [(item, agg.turns_in(item, year_month)) for item in agg.obligations_in(category_id)]
    settled = _settled_by_spending(agg, category_id, year_month, turns)
    found = []
    for item, dues in turns:
        charge = _charge_month_for(agg, item, year_month, dues, item.id in settled)
        if charge is None:
            continue
        found.append(
            _Obligation(
                name=item.name,
                required=to_cop_cents(item.amount, item.currency, agg.trm),
                charge_month=charge,
                can_be_spread=_can_be_spread(item, charge),
            )
        )
    return sorted(found, key=lambda o: o.charge_month)


def _charge_obligation(agg: MonthAggregate, item: RecurringItem, year_month: str) -> list[_Obligation]:
    """What the one charge a fund hangs off still needs, in its own money.

    Nothing is converted: a fund filling for a 600 dollar charge reports fifty
    dollars a month, and only the month's total ever becomes pesos (AC-11).

    The fund fills for the first turn nobody has settled or skipped, found by
    walking the turns themselves (ADR-0058). Asked that way the answer does not
    depend on which month is doing the asking, which is the whole point: read a
    month at a time, an early payment was forgotten the month after it was made
    and the owner was asked again for money that had already left, and a late
    one read as a cycle skipped.

    A turn still standing in the month being read is the one it fills for, and
    the floor of one month in `fund_ask_calc` makes it ask for all of it now.
    """
    start, _ = month_bounds(year_month)
    due = agg.open_turn_on_or_after(item, start)
    if due is None:
        return []
    charge = year_month_of(due)
    return [
        _Obligation(
            name=item.name,
            required=item.amount,
            charge_month=charge,
            can_be_spread=_can_be_spread(item, charge),
        )
    ]


def _obligations_of(agg: MonthAggregate, fund: Fund, year_month: str) -> list[_Obligation]:
    """What this fund is filling for — one charge, or its whole category."""
    if fund.recurring_id is None:
        return _obligations(agg, fund.category_id, year_month)
    item = agg.obligation(fund.recurring_id)
    return _charge_obligation(agg, item, year_month) if item is not None else []


def _ask_from_obligations(agg: MonthAggregate, fund: Fund, year_month: str, holds: int) -> _Ask:
    obligations = _obligations_of(agg, fund, year_month)
    claimed = claim_holdings(holds, [o.required for o in obligations])
    charges = tuple(
        FundCharge(
            name=o.name,
            costs=o.required,
            charge_month=o.charge_month,
            asks=fund_ask_calc(o.required - taken, months_to_fund(year_month, o.charge_month)),
            can_be_spread=o.can_be_spread,
        )
        for o, taken in zip(obligations, claimed, strict=True)
    )
    return _Ask(
        sum(charge.asks for charge in charges),
        charge_month=charges[0].charge_month if charges else None,
        charges=charges,
    )


def _window_months(agg: MonthAggregate, fund: Fund, year_month: str) -> list[str]:
    """The completed months the average divides by.

    A month inside the window that the app has no data for is not counted at
    all; one that existed and spent nothing is a real zero and counts. The
    month in course never averages itself (AC-3).
    """
    first = agg.first_movement_month
    months = []
    month = shift_year_month(year_month, -(fund.window_months or 0))
    while month < year_month:
        if first is not None and month >= first:
            months.append(month)
        month = next_year_month(month)
    return months


def _ask_average(agg: MonthAggregate, fund: Fund, year_month: str) -> _Ask:
    months = _window_months(agg, fund, year_month)
    spent = sum(agg.spent_in(fund.category_id, month) for month in months)
    return _Ask(monthly_average_calc(spent, len(months)), averaged_over=len(months))


def _ask(agg: MonthAggregate, fund: Fund, year_month: str, holds: int) -> _Ask:
    """What the fund asks in `year_month`, given what it holds by then.

    Never asked about a month before the fund starts: the fold begins at
    `max(anchor, start)` and only moves forward, so `_walk`'s own early return
    is the one that answers that case.
    """
    if fund.rule == FundRule.fixed:
        return _Ask(fund.amount or 0)
    if fund.rule == FundRule.average:
        return _ask_average(agg, fund, year_month)
    return _ask_from_obligations(agg, fund, year_month, holds)


def _fold_start(fund: Fund, year_month: str) -> tuple[str, int]:
    """Where the fold starts, and what the fund opens that month with.

    The anchor is a statement by the owner, not a computed figure — which is
    why it does not contradict AC-16 and why nothing in the app writes it. One
    written without a month was stated for whatever month is being looked at,
    that being the only clock the writing call has.
    """
    if fund.anchor_amount is None:
        return fund.start_month, 0
    stated_for = fund.anchor_month or year_month
    if stated_for > year_month:
        return fund.start_month, 0
    return max(stated_for, fund.start_month), fund.anchor_amount


def _drained(agg: MonthAggregate, fund: Fund, year_month: str) -> int:
    """What left this fund in one month, in the money the fund reports in.

    A fund that covers a category is drained by everything that category spent.
    A fund that fills for one charge is drained by what paid *that charge* and
    by nothing else — which is the whole difference between a guess and a fact,
    and the reason the same peso can no longer empty two funds (ADR-0057).
    """
    if fund.recurring_id is None:
        return agg.spent_in(fund.category_id, year_month)
    item = agg.obligation(fund.recurring_id)
    return agg.settled_in(item, year_month) if item is not None else 0


def _walk(agg: MonthAggregate, fund: Fund) -> _Month:
    """Fold the fund forward to the month this aggregate holds (ADR-0043)."""
    year_month = agg.year_month
    month, opening = _fold_start(fund, year_month)
    if year_month < month:
        return _Month(
            opening=0,
            holds=0,
            spent=_drained(agg, fund, year_month),
            ask=_Ask(0),
            ask_before_spending=_Ask(0),
            carries=_opening_next(fund, year_month),
        )
    while True:
        spent = _drained(agg, fund, month)
        holds = fund_holds_calc(opening, spent)
        ask = _ask(agg, fund, month, holds)
        next_opening = fund_next_opening_calc(opening, spent, ask.amount, fund.accumulates)
        if month == year_month:
            return _Month(
                opening=opening,
                holds=holds,
                spent=spent,
                ask=ask,
                ask_before_spending=_ask(agg, fund, month, max(opening, 0)),
                carries=next_opening,
            )
        opening = next_opening
        month = next_year_month(month)


def _accumulation_is_implied(fund: Fund) -> bool:
    """A fund saving toward a date always accumulates and is never asked (AC-8)."""
    return fund.rule in _DATED_RULES


def _overspill(walked: _Month) -> int:
    """What the month spent past everything the fund had for it (AC-13).

    One reading, two readers: the money the overspill costs the month, and
    whether the fund lost ground keeping it.
    """
    return uncovered_excess_calc(walked.spent, walked.opening + walked.ask.amount)


def _on_track(walked: _Month) -> bool:
    """Whether the month left the fund no worse than not touching it would (product ADR-040).

    A fund loses ground two ways, and a rule that can only lose it one way
    still has to be able to say so: the spending pushed up what it must ask,
    or the spending went past everything it had. Asking only the first leaves
    a fixed or averaged fund unable to ever be behind — it asks the same
    however much is spent — and leaves any fund opening at zero the same way.
    """
    return walked.ask.amount <= walked.ask_before_spending.amount and _overspill(walked) == 0


def _opening_next(fund: Fund, year_month: str) -> int:
    """What a fund that has not begun by `year_month` opens the next month with.

    `_walk`'s own early return read one month on: nothing at all while the fund
    is still ahead of the calendar, and whatever `_fold_start` puts there once
    it is not.
    """
    ahead = next_year_month(year_month)
    begins, opening = _fold_start(fund, ahead)
    return opening if ahead >= begins else 0


def _look_ahead(agg: MonthAggregate, fund: Fund, walked: _Month) -> int:
    """What next month has to spend: what the fund carries, plus what it asks then.

    The carry itself is `_walk`'s, not this function's — the fold step lives in
    the loop that owns it, so the two can never disagree about it. What is new
    here is the ask, taken before anything is spent because the month has not
    happened.

    Every input is already in the aggregate the caller loaded, so looking one
    month ahead costs no query (ADR-0028).
    """
    ahead = next_year_month(agg.year_month)
    begins, _ = _fold_start(fund, ahead)
    if ahead < begins:
        return 0
    return walked.carries + _ask(agg, fund, ahead, walked.carries).amount


def _fills_for(agg: MonthAggregate, fund: Fund) -> RecurringItem | None:
    """The charge this fund hangs off, if it hangs off one."""
    return None if fund.recurring_id is None else agg.obligation(fund.recurring_id)


def _name_and_currency(agg: MonthAggregate, fund: Fund) -> tuple[str, str]:
    """What the fund is called, and the money every figure of its own is in.

    A fund that fills for one charge takes the charge's name and the charge's
    currency: the owner marked 🛡️ Seguro del Carro, not 🛡️ Auto Insurance, and a
    600 dollar charge is saved for fifty dollars at a time (AC-1, AC-11).
    """
    item = _fills_for(agg, fund)
    if item is not None:
        return item.name, item.currency
    category = agg.category(fund.category_id)
    return (category.name if category is not None else ""), "COP"


def _status(agg: MonthAggregate, fund: Fund, walked: _Month) -> FundStatus:
    year_month = agg.year_month
    charge = walked.ask.charge_month
    name, currency = _name_and_currency(agg, fund)
    next_month_has = _look_ahead(agg, fund, walked)
    in_pesos = partial(to_cop_cents, currency=currency, trm=agg.trm)
    return FundStatus(
        fund_id=fund.id,
        category_id=fund.category_id,
        recurring_id=fund.recurring_id,
        name=name,
        currency=currency,
        year_month=year_month,
        rule=fund.rule.value,
        asks=walked.ask.amount,
        asks_cop=in_pesos(walked.ask.amount),
        holds=walked.holds,
        holds_cop=in_pesos(walked.holds),
        spent=walked.spent,
        carries=walked.carries,
        next_month_has=next_month_has,
        accumulates=fund.accumulates,
        accumulation_is_implied=_accumulation_is_implied(fund),
        on_track=_on_track(walked),
        charges=list(walked.ask.charges),
        has_repeating_charges=_still_waiting_for(agg, fund, year_month),
        averaged_over=walked.ask.averaged_over,
        spreads_over=months_to_fund(year_month, charge) if charge else None,
        whole_by=prev_year_month(charge) if charge else None,
    )


def fund_status(session: Session, fund_id: int, year_month: str) -> FundStatus:
    """What a fund asks, holds and reports for one month.

    Every figure is derived from the month asked about and from what is known
    now, never from a stored snapshot of it (AC-16) — so no clock is needed.

    Raises:
        NotFound: the fund does not exist.
        ValidationError: malformed year_month.
        MissingRate: no TRM is set.
    """
    require_year_month(year_month)
    fund = _require_fund(session, fund_id)
    agg = load_month(session, year_month)
    return _status(agg, fund, _walk(agg, fund))


def fund_on_category(session: Session, category_id: int) -> Fund | None:
    """The one fund a category carries *of its own*, or nothing at all (AC-25).

    A charge fund copies its category id, so a plain match by category would
    return one of those and report the category as taken — which would refuse a
    perfectly legal `fixed` fund on a category that merely holds a marked
    charge. `recurring_id IS NULL` is the same boundary the partial unique index
    draws in the schema (ADR-0057).
    """
    return session.exec(select(Fund).where(Fund.category_id == category_id, Fund.recurring_id.is_(None))).first()


@dataclass(frozen=True)
class FundFold:
    """What every fund does to one month, folded once.

    `lines` is what each fund reports, each in its own currency; `overspill` is
    what they spent past what they had, which is the only part of a fund's month
    that leaves the money available (AC-13). Both come out of one walk, because
    walking the funds is the dominant cost of the whole read path.

    **`overspill` is pesos and the lines are not.** It is a sum across funds
    that a peso term subtracts, so a dollar fund's excess is converted before it
    joins — the same seam `asks_cop` crosses, for the same reason: a total that
    adds funds together can never depend on what currency each one speaks
    (AC-11, ADR-0031).
    """

    lines: list[FundStatus]
    overspill: int


def fold(agg: MonthAggregate) -> FundFold:
    """Every fund's month, walked once. The seam `services.month` reads."""
    walked = {fund.id: _walk(agg, fund) for fund in agg.funds}
    return FundFold(
        lines=[_status(agg, fund, walked[fund.id]) for fund in agg.funds],
        overspill=sum(
            to_cop_cents(_overspill(walked[fund.id]), _name_and_currency(agg, fund)[1], agg.trm) for fund in agg.funds
        ),
    )


def list_funds(session: Session) -> list[FundLine]:
    """Every fund, for the screen and the assistant. Empty until the owner makes one (AC-20).

    A fund that fills for one charge is listed under the charge's own name: the
    owner marked 🛡️ Seguro del Carro, and a row reading 🛡️ Auto Insurance would
    name the category two of his funds share (AC-1).
    """
    names = {category.id: category.name for category in session.exec(select(Category)).all()}
    charges = {item.id: item for item in session.exec(select(RecurringItem)).all()}
    listed = []
    for fund in session.exec(select(Fund).order_by(Fund.id)).all():
        charge = charges.get(fund.recurring_id)
        listed.append(
            FundLine(
                fund_id=fund.id,
                category_id=fund.category_id,
                recurring_id=fund.recurring_id,
                name=charge.name if charge is not None else names.get(fund.category_id, ""),
                currency=charge.currency if charge is not None else "COP",
                rule=fund.rule.value,
                start_month=fund.start_month,
                accumulates=fund.accumulates,
            )
        )
    return listed


def _require_fund(session: Session, fund_id: int) -> Fund:
    fund = session.get(Fund, fund_id)
    if fund is None:
        raise NotFound(f"fund {fund_id} not found")
    return fund


def _spending_category(session: Session, category_id: int) -> Category:
    """The category a fund may cover: one that records money going out (AC-22)."""
    category = session.get(Category, category_id)
    if category is None:
        raise NotFound(f"category {category_id} not found")
    if category.is_income:
        raise ValidationError(
            f"a fund only covers money going out, and {category.name!r} is an income category — "
            f"a fund there could never be spent against"
        )
    return category


def _refuse_a_second_fund(session: Session, category: Category) -> None:
    """Two funds on one category would be two ways to lower the same headline (AC-25)."""
    if fund_on_category(session, category.id) is not None:
        raise ValidationError(f"{category.name!r} already has a fund — change that one instead of adding a second")


def _has_spending_before(session: Session, category_id: int, start_month: str) -> bool:
    """Whether the category ever spent anything in a month completed before the fund starts."""
    start, _ = month_bounds(start_month)
    earliest = session.exec(
        select(Transaction.date)
        .where(
            Transaction.category_id == category_id,
            Transaction.type == TxType.expense,
            Transaction.status == TxStatus.posted,
            Transaction.date < start,
        )
        .limit(1)
    ).first()
    return earliest is not None


_WITHDRAWN = "target-by-date"


def _rule_of(rule: str | FundRule) -> FundRule:
    """The rule, or the refusal that names what replaced it.

    `target-by-date` was withdrawn by feature 009 (product ADR-043): saving an
    amount by a date is said one way, as a meta. The name is refused by name
    rather than falling into "unknown funding rule", because an owner reaching
    for it wants the thing, not the spelling.
    """
    if rule == _WITHDRAWN:
        raise ValidationError(
            "a fund no longer saves toward a date — make a meta instead, "
            "which is not tied to a category and can be linked to the purchase"
        )
    try:
        return FundRule(rule)
    except ValueError as exc:
        raise ValidationError(f"unknown funding rule: {rule!r}") from exc


def _validated_spec(session: Session, category: Category, rule: FundRule, spec: dict) -> dict:
    """The stored shape of one rule, or the refusal that stops it."""
    start_month = require_year_month(spec.get("start_month"), "start_month")
    accumulates = spec.get("accumulates")
    stored = {"rule": rule, "start_month": start_month, "accumulates": True if accumulates is None else accumulates}
    if rule == FundRule.fixed:
        amount = spec.get("amount")
        if amount is None or amount <= 0:
            raise ValidationError("a fund asking a fixed amount needs an amount above zero")
        stored["amount"] = amount
    elif rule == FundRule.average:
        window = spec.get("window_months")
        if window is None or window < 1:
            raise ValidationError("a fund asking an average needs a window of at least one month")
        if not _has_spending_before(session, category.id, start_month):
            raise ValidationError(
                f"nothing has ever been spent in {category.name!r}, so there is no average to take — "
                f"name a fixed amount instead"
            )
        stored["window_months"] = window
    if rule in _DATED_RULES:
        if accumulates is False:
            raise ValidationError(
                "a fund saving toward a date must accumulate — one that reset every month would never arrive"
            )
        stored["accumulates"] = True
    opening = spec.get("opening_balance")
    if opening is not None:
        stored["anchor_month"] = start_month
        stored["anchor_amount"] = opening
    return stored


def create_fund(session: Session, category_id: int, **spec) -> Fund:
    """Create the one fund a spending category may carry.

    Args:
        session: Database session.
        category_id: The expense category the fund covers.
        **spec: `rule` and its parameters — `amount` (fixed), `window_months`
            (average) —
            plus `start_month`, an optional `accumulates`, and an optional
            `opening_balance` the owner types once (AC-19).

    Raises:
        NotFound: the category does not exist.
        ValidationError: the category records money coming in (AC-22), already
            has a fund (AC-25), the rule's parameters are missing or out of
            range, the average rule was asked for where nothing was ever spent
            (AC-23), or a fund saving toward a date was told to reset (AC-8).
    """
    category = _spending_category(session, category_id)
    _refuse_a_second_fund(session, category)
    stored = _validated_spec(session, category, _rule_of(spec.get("rule")), spec)
    fund = Fund(category_id=category_id, **stored)
    session.add(fund)
    session.commit()
    session.refresh(fund)
    return fund


def preview_fund(session: Session, category_id: int, **spec) -> FundPreview:
    """What a fund would ask in its first month, before it exists (AC-24).

    The surprise arrives at creation, never later on the headline: a target
    whose date leaves no month to save in is announced with its figure, and the
    owner may still go ahead.

    Raises:
        NotFound: the category does not exist.
        ValidationError: every refusal `create_fund` raises about the rule and
            its parameters. The one it does not raise is AC-25 — a category
            that already has a fund still previews, and only creation refuses.
    """
    category = _spending_category(session, category_id)
    stored = _validated_spec(session, category, _rule_of(spec.get("rule")), spec)
    unsaved = Fund(category_id=category_id, **stored)
    start = unsaved.start_month
    agg = load_month(session, start)
    walked = _walk(agg, unsaved)
    crowded = _crowded(unsaved, walked.ask.charges)
    return FundPreview(
        category_id=category_id,
        would_ask=walked.ask.amount,
        warning=_warning(unsaved, crowded),
        crowded=list(crowded),
        has_something_to_spread=any(o.can_be_spread for o in _obligations(agg, category_id, start)),
    )


def _crowded(fund: Fund, charges: tuple[FundCharge, ...]) -> tuple[FundCharge, ...]:
    """Every charge that could have been spread and has no month to spread over.

    Both halves are needed and neither alone is enough. Without the first, a
    charge that lands every month answers yes forever — there are never months
    between one turn and the next — which is how the announcement came to fire
    in four categories that had nothing to announce (ADR-0054). Without the
    second, a yearly charge a year out would be announced for no reason.

    Asked of the very divisor the ask uses, so it cannot stay silent on a month
    the charge lands on: one the month after the start still has to be whole by
    the end of the start month (003, AC-6).

    All of them and not the first, because the announcement quotes what falls,
    and naming one of two understates it as badly as quoting the fund's total
    overstated it. A charge asking nothing is left out: the fund already holds
    what it needs, so nothing falls on anyone.
    """
    return tuple(
        charge
        for charge in charges
        if charge.can_be_spread and charge.asks > 0 and months_to_fund(fund.start_month, charge.charge_month) <= 1
    )


def _warning(fund: Fund, crowded: tuple[FundCharge, ...]) -> str | None:
    """The announcement AC-24 asks for, for a surface that renders nothing itself.

    It names the obligations and quotes what they add up to. Quoting the fund's
    total mixed what does spread with what cannot and frightened the owner with
    a number nobody was going to pay at once; quoting one of several does the
    opposite and promises a month cheaper than it is (ADR-0054).

    The screen does not read this — it words the same charges in the owner's own
    language and money format. This is what the assistant prints, which is the
    one surface with nowhere else to compose it.
    """
    if not crowded:
        return None
    named = ", ".join(charge.name for charge in crowded)
    falls = sum(charge.asks for charge in crowded)
    return f"{named} leaves no month to save in: the whole {cents_to_major(falls)} COP falls on {fund.start_month}"


def set_fund(session: Session, fund_id: int, **changes) -> Fund:
    """Change a fund's rule, its parameters, or what the owner says it holds.

    `balance` is the owner's statement of what the fund already holds. It is
    recorded as stated and never re-read from an account, before or after
    (AC-19).

    Raises:
        NotFound: the fund does not exist.
        ValidationError: the new rule's parameters are missing or out of range.
    """
    fund = _require_fund(session, fund_id)
    balance = changes.pop("balance", None)
    if balance is not None:
        fund.anchor_month = None
        fund.anchor_amount = balance
    if changes:
        category = session.get(Category, fund.category_id)
        rule = _rule_of(changes.get("rule", fund.rule))
        spec = {"start_month": fund.start_month, "accumulates": fund.accumulates, **changes}
        for name, value in _validated_spec(session, category, rule, spec).items():
            setattr(fund, name, value)
    session.add(fund)
    session.commit()
    session.refresh(fund)
    return fund


def fund_for_charge(session: Session, recurring_id: int) -> Fund | None:
    """The fund that fills for one charge, or nothing when it was never marked."""
    return session.exec(select(Fund).where(Fund.recurring_id == recurring_id)).first()


def open_turns_of(session: Session, recurring_id: int) -> list[Date]:
    """The turns of one charge a payment written down today could be settling.

    One cycle either side of today, and no wider. A bill paid after it fell due
    is the ordinary case, so the offer has to reach back far enough to hold the
    turn the owner is answering for; and a bill paid early reaches forward the
    same distance. Beyond that is not a payment being written down, it is a
    different conversation — and offering it would bury the one turn the owner
    means under years of bills he is not paying (ADR-0058).

    Raises:
        NotFound: no such charge.
    """
    item = session.get(RecurringItem, recurring_id)
    if item is None:
        raise NotFound(f"repeating charge {recurring_id} not found")
    today = Date.today()
    one_cycle = _one_cycle_of(item)
    return occurrences.open_turns(session, item, today - one_cycle, today + one_cycle)


def _one_cycle_of(item: RecurringItem) -> timedelta:
    """How long this charge takes to come back, near enough to bound an offer."""
    return {
        IntervalUnit.day: timedelta(days=item.interval_count),
        IntervalUnit.week: timedelta(weeks=item.interval_count),
        IntervalUnit.month: timedelta(days=31 * item.interval_count),
        IntervalUnit.year: timedelta(days=366 * item.interval_count),
    }[item.interval_unit]


_LANDS_THIS_MONTH = "it charges this month, so there are no months left to save in — mark it once it has been paid"
_MONEY_COMING_IN = "a fund only covers money going out"
_NO_TURN_LEFT = "it has no turn left to save for"
_NO_MONTH_TO_SAVE_IN = (
    "it comes back before a whole month has passed, so saving for it would ask the whole amount every month"
)


def _why_it_could_never_be_saved_for(agg: MonthAggregate, item: RecurringItem, year_month: str) -> str | None:
    """What disqualifies this charge for good, rather than only for now.

    Direction, having a turn at all, and the rhythm — none of which the calendar
    moving forward can change. Nothing here reads `IntervalUnit`, so «every 45
    days» and «every 6 weeks» answer by what they actually do (ADR-0056).

    Kept apart from the reason a charge cannot be marked *this* month because
    the two are asked at different moments: one decides whether the box may be
    ticked, and this one decides whether an already-ticked box may stay. Mixing
    them would drop a fund the month its charge finally arrives, which is the
    month it exists for.
    """
    if item.type != TxType.expense:
        return _MONEY_COMING_IN
    charge_month = _charge_month_for(agg, item, year_month, agg.turns_in(item, year_month), settled=False)
    if charge_month is None:
        return _NO_TURN_LEFT
    if not _can_be_spread(item, charge_month):
        return _NO_MONTH_TO_SAVE_IN
    return None


def _why_not_markable(agg: MonthAggregate, item: RecurringItem, year_month: str) -> str | None:
    """Why this charge cannot be saved for right now, or nothing when it can.

    The lasting reasons first, then the one that is only about timing: a charge
    landing this very month has no months left to spread over, so saving for it
    would ask the whole amount at once — which is what paying it does.
    """
    lasting = _why_it_could_never_be_saved_for(agg, item, year_month)
    if lasting is not None:
        return lasting
    charge_month = _charge_month_for(agg, item, year_month, agg.turns_in(item, year_month), settled=False)
    return _LANDS_THIS_MONTH if charge_month == year_month else None


def charge_marks(session: Session, year_month: str) -> list[ChargeMark]:
    """Every live repeating charge, and whether the owner may save for it.

    One aggregate for the whole list rather than one reading per charge: the
    screen shows every row at once, and ADR-0028 does not stop being true
    because the loop is in a service (AC-2).
    """
    require_year_month(year_month)
    agg = load_month(session, year_month)
    marked = {fund.recurring_id: fund.id for fund in agg.funds if fund.recurring_id is not None}
    found = []
    for item in agg.active_recurring:
        fund_id = marked.get(item.id)
        why_not = None if fund_id is not None else _why_not_markable(agg, item, year_month)
        found.append(
            ChargeMark(
                recurring_id=item.id,
                category_id=item.category_id,
                name=item.name,
                currency=item.currency,
                can_be_marked=fund_id is None and why_not is None,
                why_not=why_not,
                fund_id=fund_id,
            )
        )
    return found


def mark_charge(session: Session, recurring_id: int, year_month: str | None = None) -> Fund:
    """Save for this charge from this month on. Marking it *is* what creates the fund.

    No form and nothing to confirm afterwards: the owner ticks the box in the
    list of repeating charges and the fund exists (AC-1).

    Args:
        session: Database session.
        recurring_id: The charge to save for.
        year_month: The month saving starts in. Defaults to the month in course.

    Raises:
        NotFound: the charge does not exist or is switched off.
        ValidationError: it is money coming in, it charges this very month, it
            has no turn left, it comes back before a whole month has passed, or
            it is already marked (AC-10).
        MissingRate: no TRM is set.
    """
    start_month = require_year_month(year_month or year_month_of(Date.today()))
    item = session.get(RecurringItem, recurring_id)
    if item is None or not item.active:
        raise NotFound(f"repeating charge {recurring_id} not found")
    if fund_for_charge(session, recurring_id) is not None:
        raise ValidationError(f"{item.name!r} already has a fund — unmark it first if you want to start over")
    agg = load_month(session, start_month)
    why_not = _why_not_markable(agg, item, start_month)
    if why_not is not None:
        raise ValidationError(f"{item.name!r} cannot be saved for: {why_not}")
    fund = Fund(
        category_id=item.category_id,
        recurring_id=recurring_id,
        rule=FundRule.from_recurring,
        start_month=start_month,
        accumulates=True,
    )
    session.add(fund)
    session.commit()
    session.refresh(fund)
    return fund


def unmark_charge(session: Session, recurring_id: int) -> None:
    """Stop saving for this charge, and remove the fund entirely.

    The whole fund goes, not the months ahead of it: a fund never held money,
    only a figure the app suggested, so every month it ever answered goes back
    to answering without it and **no movement is touched** (AC-4). That is why
    it costs nothing to undo and why it needs none of the handing-back that
    cancelling a meta needed (ADR-0055).

    The saving so far is lost with it, deliberately: marking again starts a new
    fund at zero, and the figure says so. Idempotent — unmarking what was never
    marked is not an error, which is what lets the four doors of AC-8 all close
    the same way.
    """
    fund = fund_for_charge(session, recurring_id)
    if fund is None:
        return
    session.delete(fund)
    session.commit()


def marked_charges_in(session: Session, category_id: int) -> list[str]:
    """The names of the charges under one category that are being saved for."""
    marked = session.exec(
        select(RecurringItem.name)
        .join(Fund, Fund.recurring_id == RecurringItem.id)
        .where(Fund.category_id == category_id)
        .order_by(RecurringItem.id)
    ).all()
    return list(marked)


def _can_still_keep_a_fund(agg: MonthAggregate, item: RecurringItem, year_month: str) -> bool:
    """Whether the charge, as it is now, still justifies the fund it carries."""
    return _why_it_could_never_be_saved_for(agg, item, year_month) is None


def would_lose_its_fund(session: Session, recurring_id: int, year_month: str, **changes) -> bool:
    """Whether saving these changes would leave the charge unable to keep its fund.

    Asked *before* the edit is saved, so the screen can say what is about to
    happen in one step instead of reporting it afterwards (AC-8). The rule is
    not restated here: the proposed charge is measured by the same
    `_can_still_keep_a_fund` the edit itself is judged by, so the two can never
    drift. It is deliberately **not** `_why_not_markable` — that one also
    refuses a charge landing this very month, which is the month a fund exists
    for, so asking it here would drop the fund on the way to its own payment.

    Raises:
        MissingRate: no TRM is set.
    """
    if fund_for_charge(session, recurring_id) is None:
        return False
    item = session.get(RecurringItem, recurring_id)
    if item is None:
        return False
    agg = load_month(session, require_year_month(year_month))
    proposed = item.model_copy(update={name: value for name, value in changes.items() if value is not None})
    return not _can_still_keep_a_fund(agg, proposed, year_month)


def follow_its_charge(session: Session, recurring_id: int) -> None:
    """File the fund where its charge is now, after the charge was moved.

    The fund belongs to the charge and not to the category (ADR-0057), so the
    category it carries is a copy of the charge's — and a copy left behind
    points the wrong way twice. The category the charge arrived at is the one
    AC-8 refuses to archive, and it would archive without a word while the fund
    goes on asking for money nobody can see any more; the category it left
    refuses to archive naming a charge that is no longer filed there.

    Nothing else moves: the fund keeps its rule, its start month and everything
    it has saved, because the owner refiled a bill, he did not change it.
    """
    fund = fund_for_charge(session, recurring_id)
    item = session.get(RecurringItem, recurring_id)
    if fund is None or item is None or fund.category_id == item.category_id:
        return
    fund.category_id = item.category_id
    session.add(fund)
    session.commit()


def unmark_if_it_can_no_longer_be_saved_for(session: Session, recurring_id: int, year_month: str | None = None) -> bool:
    """Remove the fund of a charge whose new rhythm leaves no month to save in.

    The fifth door of AC-8, and the only one that fails quietly: edit the
    insurance from yearly to monthly and its fund stops having a reason to
    exist, but nothing about the edit says so. The screen warns first
    (`would_lose_its_fund`); this is what actually happens when the owner goes
    ahead.

    Returns whether a fund was removed.
    """
    if fund_for_charge(session, recurring_id) is None:
        return False
    item = session.get(RecurringItem, recurring_id)
    if item is None or not item.active:
        unmark_charge(session, recurring_id)
        return True
    month = require_year_month(year_month or year_month_of(Date.today()))
    if _can_still_keep_a_fund(load_month(session, month), item, month):
        return False
    unmark_charge(session, recurring_id)
    return True


def delete_fund(session: Session, fund_id: int) -> None:
    """Remove a fund outright.

    A fund is deleted rather than archived: it is a rule attached to a
    category, not a master record — no history of its own and a derived
    balance — so an archived one would still have to answer what it asks this
    month. The boundary is declared in ADR-0043.

    Raises:
        NotFound: the fund does not exist.
    """
    fund = _require_fund(session, fund_id)
    session.delete(fund)
    session.commit()
