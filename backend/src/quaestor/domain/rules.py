"""Balance sign rules and the recurrence date engine (ADR-020)."""
from __future__ import annotations

import calendar
from datetime import date, timedelta

from .dtos import BudgetStatus
from .models import IntervalUnit, TxType


def delta_balance(tx_type: TxType, amount: int) -> int:
    """Centavos to add to the account balance (amount always positive)."""
    if tx_type == TxType.income:
        return amount
    if tx_type == TxType.expense:
        return -amount
    raise ValueError(
        "delta_balance only applies to expense/income; transfer uses transfer_deltas"
    )


def transfer_deltas(amount: int) -> tuple[int, int]:
    """(delta_from, delta_to) for an internal transfer."""
    return (-amount, amount)


def _last_day_of_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _add_months(anchor: date, months: int) -> date:
    """anchor shifted by `months`, clamping the day to the target month's last day.

    Anchored to anchor.day every time (never chained), so Jan 31 -> Feb 28 -> Mar 31.
    """
    total = (anchor.year * 12 + (anchor.month - 1)) + months
    year, month_index = divmod(total, 12)
    month = month_index + 1
    day = min(anchor.day, _last_day_of_month(year, month))
    return date(year, month, day)


def _add_interval(anchor: date, unit: IntervalUnit, count: int, k: int) -> date:
    """The k-th occurrence after `anchor` for interval (count x unit)."""
    n = count * k
    if unit == IntervalUnit.day:
        return anchor + timedelta(days=n)
    if unit == IntervalUnit.week:
        return anchor + timedelta(weeks=n)
    if unit == IntervalUnit.month:
        return _add_months(anchor, n)
    if unit == IntervalUnit.year:
        return _add_months(anchor, n * 12)
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


def month_bounds(year_month: str) -> tuple[date, date]:
    """First and last calendar day of a "YYYY-MM" string."""
    year, month = int(year_month[:4]), int(year_month[5:7])
    return date(year, month, 1), date(year, month, _last_day_of_month(year, month))


def prev_year_month(year_month: str) -> str:
    """The "YYYY-MM" of the previous calendar month."""
    year, month = int(year_month[:4]), int(year_month[5:7])
    if month == 1:
        return f"{year - 1:04d}-12"
    return f"{year:04d}-{month - 1:02d}"


def envelope_status_calc(
    category_id: int, year_month: str, assigned: int, rollover_in: int, spent: int
) -> BudgetStatus:
    """Envelope math: available, pct_used, over/under (ADR-003/005). Pure."""
    denom = rollover_in + assigned
    available = denom - spent
    pct_used = round(spent / denom * 100) if denom > 0 else 0
    status = "over" if spent > denom else "under"
    return BudgetStatus(
        category_id=category_id, year_month=year_month, assigned=assigned,
        rollover_in=rollover_in, spent=spent, available=available,
        pct_used=pct_used, status=status,
    )
