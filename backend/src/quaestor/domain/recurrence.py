"""The recurrence date engine: cadence arithmetic and due-date questions.

Pure — no session, no I/O. Split out of `rules.py`, which mixes balance signs,
recurrence, envelope math and goal progress. Calendar helpers stay here and
`rules.py` imports them.
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta

from .models import IntervalUnit


def last_day_of_month(year: int, month: int) -> int:
    """The last calendar day of a given month."""
    return calendar.monthrange(year, month)[1]


def add_months(anchor: date, months: int) -> date:
    """anchor shifted by `months`, clamping the day to the target month's last day.

    Anchored to anchor.day every time (never chained), so Jan 31 -> Feb 28 -> Mar 31.
    """
    total = (anchor.year * 12 + (anchor.month - 1)) + months
    year, month_index = divmod(total, 12)
    month = month_index + 1
    day = min(anchor.day, last_day_of_month(year, month))
    return date(year, month, day)


def _add_interval(anchor: date, unit: IntervalUnit, count: int, k: int) -> date:
    """The k-th occurrence after `anchor` for interval (count x unit)."""
    n = count * k
    if unit == IntervalUnit.day:
        return anchor + timedelta(days=n)
    if unit == IntervalUnit.week:
        return anchor + timedelta(weeks=n)
    if unit == IntervalUnit.month:
        return add_months(anchor, n)
    if unit == IntervalUnit.year:
        return add_months(anchor, n * 12)
    raise ValueError(f"invalid interval_unit: {unit}")


def due_dates(
    start_date: date,
    end_date: date | None,
    interval_unit: IntervalUnit,
    interval_count: int,
    since: date,
    until: date,
) -> list[date]:
    """Due dates in [since, until] for interval (interval_count x interval_unit).

    Each due date is start_date + k x interval, with end-of-month clamping for
    month/year units. Respects end_date (inclusive). Returns dates ascending.
    """
    if interval_count < 1:
        raise ValueError("interval_count must be >= 1")
    results: list[date] = []
    k = 0
    while True:
        d = _add_interval(start_date, interval_unit, interval_count, k)
        if d > until:
            break
        if end_date is not None and d > end_date:
            break
        if d >= since:
            results.append(d)
        k += 1
    return results


def is_due_on(
    start_date: date,
    end_date: date | None,
    interval_unit: IntervalUnit,
    interval_count: int,
    target: date,
) -> bool:
    """Whether the cadence actually falls on `target`.

    A monthly obligation anchored to the 5th is not due on the 3rd, and a date
    past `end_date` or before `start_date` is not due at all.
    """
    if target < start_date:
        return False
    return bool(
        due_dates(
            start_date, end_date, interval_unit, interval_count, target, target
        )
    )


def has_ended(end_date: date | None, today: date) -> bool:
    """Whether the obligation is past its end date.

    The end date is itself a due date, so an obligation ending today has not
    ended yet. An obligation with no end date never ends.
    """
    return end_date is not None and end_date < today
