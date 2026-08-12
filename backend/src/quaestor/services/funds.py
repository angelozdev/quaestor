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

from sqlmodel import Session, select

from ..domain.dtos import FundCharge, FundLine, FundPreview, FundStatus
from ..domain.errors import NotFound, ValidationError
from ..domain.models import Category, Fund, FundRule, RecurringItem, Transaction, TxStatus, TxType
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


def _turn_after(item: RecurringItem, year_month: str) -> str | None:
    """The month of this obligation's first turn after `year_month`, if it has one."""
    _, end = month_bounds(year_month)
    after = next_due_on_or_after(
        item.start_date, item.end_date, item.interval_unit, item.interval_count, end + timedelta(days=1)
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
    return _turn_after(item, year_month)


def _can_be_spread(item: RecurringItem, charge_month: str) -> bool:
    """Whether a whole month fits between this charge and the one after it (ADR-0054).

    A charge that lands every month never leaves one, so the fund can only ever
    ask it whole — which is why it is never the surprise the warning announces.
    A charge with no turn after it is a one-off, and nothing forces it to be
    asked in a single month.

    Read from the obligation's own rhythm rather than from its declared
    interval, so "every 45 days" and "every 6 weeks" answer by what they
    actually do.
    """
    following = _turn_after(item, charge_month)
    return following is None or months_to_fund(charge_month, following) > 1


def _obligations(agg: MonthAggregate, category_id: int, year_month: str) -> list[_Obligation]:
    """What each obligation in the category still needs, soonest charge first.

    Each obligation's turns for the month are worked out once here and handed to
    both readers: which turns the spending settled, and which charge the fund is
    filling for.
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


def _ask_from_obligations(agg: MonthAggregate, fund: Fund, year_month: str, holds: int) -> _Ask:
    obligations = _obligations(agg, fund.category_id, year_month)
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


def _walk(agg: MonthAggregate, fund: Fund) -> _Month:
    """Fold the fund forward to the month this aggregate holds (ADR-0043)."""
    year_month = agg.year_month
    month, opening = _fold_start(fund, year_month)
    if year_month < month:
        return _Month(
            opening=0,
            holds=0,
            spent=agg.spent_in(fund.category_id, year_month),
            ask=_Ask(0),
            ask_before_spending=_Ask(0),
            carries=_opening_next(fund, year_month),
        )
    while True:
        spent = agg.spent_in(fund.category_id, month)
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
    return uncovered_excess_calc(walked.spent, walked.opening, walked.ask.amount)


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


def _status(agg: MonthAggregate, fund: Fund, walked: _Month) -> FundStatus:
    year_month = agg.year_month
    charge = walked.ask.charge_month
    category = agg.category(fund.category_id)
    next_month_has = _look_ahead(agg, fund, walked)
    return FundStatus(
        fund_id=fund.id,
        category_id=fund.category_id,
        name=category.name if category is not None else "",
        year_month=year_month,
        rule=fund.rule.value,
        asks=walked.ask.amount,
        holds=walked.holds,
        spent=walked.spent,
        carries=walked.carries,
        next_month_has=next_month_has,
        accumulates=fund.accumulates,
        accumulation_is_implied=_accumulation_is_implied(fund),
        on_track=_on_track(walked),
        charges=list(walked.ask.charges),
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
    """The one fund a category carries, or nothing at all (AC-25)."""
    return session.exec(select(Fund).where(Fund.category_id == category_id)).first()


@dataclass(frozen=True)
class FundFold:
    """What every fund does to one month, folded once.

    `lines` is what each fund reports; `overspill` is what they spent past what
    they had, which is the only part of a fund's month that leaves the money
    available (AC-13). Both come out of one walk, because walking the funds is
    the dominant cost of the whole read path.
    """

    lines: list[FundStatus]
    overspill: int


def fold(agg: MonthAggregate) -> FundFold:
    """Every fund's month, walked once. The seam `services.month` reads."""
    walked = {fund.id: _walk(agg, fund) for fund in agg.funds}
    return FundFold(
        lines=[_status(agg, fund, walked[fund.id]) for fund in agg.funds],
        overspill=sum(_overspill(walked[fund.id]) for fund in agg.funds),
    )


def list_funds(session: Session) -> list[FundLine]:
    """Every fund, for the screen and the assistant. Empty until the owner makes one (AC-20)."""
    names = {category.id: category.name for category in session.exec(select(Category)).all()}
    return [
        FundLine(
            fund_id=fund.id,
            category_id=fund.category_id,
            name=names.get(fund.category_id, ""),
            rule=fund.rule.value,
            start_month=fund.start_month,
            accumulates=fund.accumulates,
        )
        for fund in session.exec(select(Fund).order_by(Fund.id)).all()
    ]


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
    return FundPreview(
        category_id=category_id,
        would_ask=walked.ask.amount,
        warning=_warning(unsaved, walked.ask.charges),
        has_something_to_spread=any(o.can_be_spread for o in _obligations(agg, category_id, start)),
    )


def _crowded(fund: Fund, charges: tuple[FundCharge, ...]) -> FundCharge | None:
    """The first charge that could have been spread and has no month to spread over.

    Both halves are needed and neither alone is enough. Without the first, a
    charge that lands every month answers yes forever — there are never months
    between one turn and the next — which is how the announcement came to fire
    in four categories that had nothing to announce (ADR-0054). Without the
    second, a yearly charge a year out would be announced for no reason.

    Asked of the very divisor the ask uses, so it cannot stay silent on a month
    the charge lands on: one the month after the start still has to be whole by
    the end of the start month (003, AC-6).
    """
    return next(
        (
            charge
            for charge in charges
            if charge.can_be_spread and months_to_fund(fund.start_month, charge.charge_month) <= 1
        ),
        None,
    )


def _warning(fund: Fund, charges: tuple[FundCharge, ...]) -> str | None:
    """The announcement AC-24 asks for, said about the charge it is true of.

    It names the obligation and quotes that obligation's own figure. Quoting
    the fund's total mixed what does spread with what cannot, and frightened
    the owner with a number nobody was ever going to pay at once (ADR-0054).
    """
    crowded = _crowded(fund, charges)
    if crowded is None:
        return None
    return (
        f"{crowded.name} charges in {crowded.charge_month}, which leaves no month to save in: "
        f"the whole {cents_to_major(crowded.asks)} COP falls on {fund.start_month}"
    )


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
