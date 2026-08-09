"""Pure arithmetic the services fold over — no session, no I/O.

Four groups: which way a movement moves a balance, "YYYY-MM" calendar maths,
what a fund asks and holds, and what a repeating amount comes to in a month.

`recurrence.py` owns the day-level date engine; `last_day_of_month` is
imported from there.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date

from .models import IntervalUnit, TransferDirection, TxType
from .recurrence import last_day_of_month


def delta_balance(tx_type: TxType, amount: int) -> int:
    """Centavos to add to the account balance (amount always positive)."""
    if tx_type == TxType.income:
        return amount
    if tx_type == TxType.expense:
        return -amount
    raise ValueError("delta_balance only applies to expense/income; transfer uses transfer_deltas")


def category_is_income_for(tx_type: TxType) -> bool:
    """Whether this movement must carry an income category (ADR-0042).

    Raises:
        ValueError: transfer carries no category at all, so it has no
            direction; `services.categories.resolve_for_movement` refuses it
            before reaching here.
    """
    if tx_type == TxType.income:
        return True
    if tx_type == TxType.expense:
        return False
    raise ValueError("a transfer carries no category, so it has no direction")


def transfer_deltas(amount: int) -> tuple[int, int]:
    """(delta_from, delta_to) for an internal transfer."""
    return (-amount, amount)


def leg_delta_balance(direction: TransferDirection | None, amount: int) -> int:
    """Centavos this transfer leg added to its account (amount always positive).

    Raises:
        ValueError: the leg carries no stored direction (ADR-0032).
    """
    if direction == TransferDirection.out:
        return -amount
    if direction == TransferDirection.in_:
        return amount
    raise ValueError("leg_delta_balance requires a stored transfer direction")


YEAR_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def is_year_month(value: str | None) -> bool:
    """Whether a string is a well-formed "YYYY-MM"."""
    return YEAR_MONTH_RE.match(value or "") is not None


def _ordinal(year_month: str) -> int:
    """Months since year zero — the one arithmetic every "YYYY-MM" answer folds over."""
    return int(year_month[:4]) * 12 + int(year_month[5:7]) - 1


def _from_ordinal(months: int) -> str:
    year, index = divmod(months, 12)
    return f"{year:04d}-{index + 1:02d}"


def month_bounds(year_month: str) -> tuple[date, date]:
    """First and last calendar day of a "YYYY-MM" string."""
    year, month = int(year_month[:4]), int(year_month[5:7])
    return date(year, month, 1), date(year, month, last_day_of_month(year, month))


def shift_year_month(year_month: str, months: int) -> str:
    """The "YYYY-MM" `months` after this one (before it, when negative)."""
    return _from_ordinal(_ordinal(year_month) + months)


def prev_year_month(year_month: str) -> str:
    """The "YYYY-MM" of the previous calendar month."""
    return shift_year_month(year_month, -1)


def next_year_month(year_month: str) -> str:
    """The "YYYY-MM" of the following calendar month."""
    return shift_year_month(year_month, 1)


def year_month_of(day: date) -> str:
    """The "YYYY-MM" a calendar day falls in."""
    return f"{day.year:04d}-{day.month:02d}"


def months_between(first: str, second: str) -> int:
    """Whole months from one "YYYY-MM" to another; negative when it runs back."""
    return _ordinal(second) - _ordinal(first)


def months_to_fund(year_month: str, charge_month: str | None) -> int:
    """Months, counting this one, left to fill a fund before its charge lands.

    The charge month itself does not contribute (AC-6): the money is whole on
    the last day of the month before it. A fund with no charge date fills in
    the month itself, which is the same floor of one month — so a charge
    landing this month asks for its whole amount now (ADR-0043).
    """
    if charge_month is None:
        return 1
    return max(months_between(year_month, charge_month), 1)


def _ceil_div(numerator: int, denominator: int) -> int:
    return -(-numerator // denominator)


def fund_ask_calc(missing: int, months_left: int) -> int:
    """What a fund asks this month: what is missing over the months left.

    Rounded up, so the last month never comes up short.
    """
    if missing <= 0:
        return 0
    return _ceil_div(missing, max(months_left, 1))


def months_to_meta(year_month: str, target_month: str) -> int:
    """Months, counting this one and the target, left to fill a meta (ADR-0046).

    Deliberately one more than `months_to_fund` gives a charge in the same
    month, and the difference is the whole distinction between the two nouns: a
    bill lands on the first of its month whether or not the owner is ready, so
    the money is whole the month before; a purchase happens when he decides, so
    the month he names is a month he saves in.

    Never below one, so a target already behind still asks for what is missing
    rather than dividing by zero.
    """
    return max(months_between(year_month, target_month) + 1, 1)


def meta_ask_calc(amount: int, held: int, months_left: int) -> int:
    """What a meta asks this month: what is missing over the months left.

    Rounded up at the cent, so the last month never comes up short. Zero only
    because nothing is missing — never because completing, cancelling or
    contributing waived it (ADR-0046).
    """
    return fund_ask_calc(amount - held, months_left)


def meta_uncovered_calc(spent: int, opening: int, ask: int) -> int:
    """What a purchase cost past everything the meta had for the month.

    The same shape as `uncovered_excess_calc`, and for the same reason: only
    what goes past what was actually put by leaves the money available, never
    the whole purchase (AC-12).
    """
    return uncovered_excess_calc(spent, opening, ask)


def split_calc(consumo: int, ahorro: int, income: int) -> int:
    """What the month leaves free once consumo and ahorro are named (AC-37).

    One subtraction rather than a second sum, so `consumo + ahorro + libre`
    equals the income by construction and cannot drift.

    `ahorro` is net and may be negative: a month the owner cancels a meta is a
    month he takes savings back out, and the release comes off what he set
    aside rather than landing in another term. That is what keeps the identity
    true — and it is also what the month actually did.
    """
    return income - consumo - ahorro


def share_calc(part: int, whole: int) -> int:
    """What share of the month a term took, as whole percent.

    Zero income means no share to state rather than a division by zero.
    """
    if whole == 0:
        return 0
    return round(part * 100 / whole)


def monthly_average_calc(spent: int, months_with_data: int) -> int:
    """A category's monthly average over the months the app holds data for.

    A month inside the window with no spending is a real zero and counts; a
    month the app has no data for never reaches this function (AC-3).
    """
    if months_with_data <= 0:
        return 0
    return _ceil_div(spent, months_with_data)


def fund_holds_calc(opening: int, spent: int) -> int:
    """What a fund holds: what it opened with, less what the category spent.

    Never negative — overspend eats the pool instead (product ADR-005).
    """
    return max(opening - spent, 0)


def fund_next_opening_calc(opening: int, spent: int, asks: int, accumulates: bool) -> int:
    """What the fund opens the next month with.

    An accumulating fund carries the month forward and a resetting one starts
    fresh; neither carries a negative balance (product ADR-005, AC-13).
    """
    if not accumulates:
        return 0
    return max(opening + asks - spent, 0)


_MONTHS_PER_UNIT: dict[IntervalUnit, tuple[int, int]] = {
    IntervalUnit.month: (1, 1),
    IntervalUnit.year: (12, 1),
    IntervalUnit.week: (12, 52),
    IntervalUnit.day: (12, 365),
}


def monthly_rate_calc(amount: int, unit: IntervalUnit, count: int) -> int:
    """One month's worth of a repeating amount, whatever its cycle.

    A rate describes the pace of a cycle rather than the month it lands in: a
    quarterly bonus of 3.000.000 is 1.000.000 a month in every month of its
    cycle (AC-14b), and a weekly charge is the ~4,33 turns a month really
    holds rather than the one a calendar month shows. Rounded up, so a rate
    never understates what a cycle costs.

    Raises:
        ValueError: unknown interval unit, or a count below one.
    """
    if count < 1:
        raise ValueError("interval count must be >= 1")
    months = _MONTHS_PER_UNIT.get(unit)
    if months is None:
        raise ValueError(f"invalid interval_unit: {unit}")
    numerator, denominator = months
    return _ceil_div(amount * denominator, numerator * count)


def uncovered_excess_calc(spent: int, opening: int, asks: int) -> int:
    """What a category spent past everything its fund had for the month.

    A fund's month holds what it opened with plus what it asks for; only what
    goes past that leaves the money available, never the whole amount
    (AC-13, product ADR-005).
    """
    return max(spent - opening - asks, 0)


def available_calc(income: int, claimed: int, uncovered: int) -> int:
    """The money available: income, less everything already claimed, less what
    no fund covers.

    `claimed` gathers every fund's and meta's ask, what the owner set aside by
    hand and what a cancelled meta gave back (ADR-0046). One uncovered term
    rather than three, so the breakdown adds up exactly (AC-10).
    """
    return income - claimed - uncovered


def margin_calc(earning: int, cost: int) -> int:
    """What the earning rate leaves after the cost rate (AC-14b)."""
    return earning - cost


def claim_holdings(holds: int, requirements: Sequence[int]) -> list[int]:
    """How much of what a fund holds each obligation can claim, soonest first.

    One fund covers every obligation filed under its category (AC-4), so the
    money it holds has to be attributed before any of them can say what is
    still missing. The nearest charge is served first.
    """
    left = holds
    claimed = []
    for required in requirements:
        taken = max(min(left, required), 0)
        claimed.append(taken)
        left -= taken
    return claimed
