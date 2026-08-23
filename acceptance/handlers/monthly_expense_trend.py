"""Step handlers — feature 020 monthly-expense-trend.

Written at Checkpoint 3 against a report section that does not exist yet:
``reports.monthly_report`` builds a ``MonthlyReport`` with no trend field at
all, so ``the user views the last 12 months of spending trend`` reaches for
``report.trend`` and gets an ``AttributeError`` — captured by
``world.attempt`` into the error stream, then surfaced by every ``Then``
step's ``world.require_clean`` call. That is the correct red for this
checkpoint; Checkpoint 4/5 gives ``MonthAggregate``/``reports.monthly_report``
a real trend section (ADR-0028/0044) and these assertions start reading it.

The shape a ``Then`` step reads, ``report.trend`` (``domain.report_types.Trend``,
settled by plan.md at Checkpoint 4 — CP3's original guess named the category
row's name field ``.name``; updated here to ``.category`` to match):

- ``.months``      one entry per month in the 12-month window, oldest first,
                    each carrying ``.month`` ("YYYY-MM"), ``.total`` (COP
                    cents) and ``.by_group`` (group name -> COP cents)
- ``.categories``   one row per category with any spend in the window,
                    ordered by total spend descending, each carrying
                    ``.category``, ``.group`` (or "Sin grupo"), ``.total``
                    (COP cents across the window) and ``.by_month``
                    ("YYYY-MM" -> COP cents)

Only ``a recorded expense of N CUR in category "X" in YYYY-MM`` is new Given
vocabulary here — it extends the family ``fx_read_time.py`` already has for
"in the current month" / "dated in a previous month" to an explicit,
arbitrary month, dated to the 15th for the same month-boundary safety
``world.previous_month_day`` already relies on.
"""

from __future__ import annotations

from datetime import date as Date

from quaestor.domain.money import major_to_cents
from quaestor.services import reports

from . import step
from .fx_read_time import _DEC, _month_str, _record_default_expense
from .sinking_funds import _MONTH
from .world import World


def _month_mid(month: str) -> Date:
    year, mon = (int(part) for part in month.split("-"))
    return Date(year, mon, 15)


def _month_entry(trend, month: str):
    for entry in trend.months:
        if entry.month == month:
            return entry
    present = [entry.month for entry in trend.months]
    raise AssertionError(f"the trend has no entry for {month!r}; months present: {present}")


def _category_row(trend, name: str):
    return next((row for row in trend.categories if row.category == name), None)


# ------------------------------------------------------------------- Given


@step(
    r"a recorded expense of (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3})"
    r' in category "(?P<name>[^"]+)" in (?P<month>' + _MONTH + r")"
)
def given_recorded_expense_in_category_and_month(
    world: World, amount: str, currency: str, name: str, month: str
) -> None:
    _record_default_expense(world, amount, currency, _month_mid(month), category_id=world.categories[name])


# -------------------------------------------------------------------- When


@step(r"the user views the last 12 months of spending trend")
def when_view_trend(world: World) -> None:
    world.report = None
    world.trend = None

    def action():
        report = reports.monthly_report(world.session, _month_str(world.today), today=world.today)
        world.report = report
        world.trend = report.trend

    world.attempt(action)


# -------------------------------------------------------------------- Then


@step(r"the trend's window runs from (?P<start>" + _MONTH + r") to (?P<end>" + _MONTH + r")")
def then_trend_window(world: World, start: str, end: str) -> None:
    world.require_clean("viewing the trend should have succeeded")
    months = [entry.month for entry in world.trend.months]
    assert months and months[0] == start and months[-1] == end, (
        f"expected the window to run from {start} to {end}, got {months}"
    )


@step(r"in (?P<month>" + _MONTH + r') the group "(?P<group>[^"]+)" totals (?P<amount>' + _DEC + r") COP")
def then_group_totals_in_month(world: World, month: str, group: str, amount: str) -> None:
    world.require_clean("viewing the trend should have succeeded")
    entry = _month_entry(world.trend, month)
    expected = major_to_cents(amount)
    got = entry.by_group.get(group, 0)
    assert got == expected, f"{month}: group {group!r} expected {expected} cents ({amount} COP), got {got}"


@step(r"in (?P<month>" + _MONTH + r") the total shown is (?P<amount>" + _DEC + r") COP")
def then_month_total_shown(world: World, month: str, amount: str) -> None:
    world.require_clean("viewing the trend should have succeeded")
    entry = _month_entry(world.trend, month)
    expected = major_to_cents(amount)
    assert entry.total == expected, f"{month}: expected total {expected} cents ({amount} COP), got {entry.total}"


@step(r'the table lists "(?P<name>[^"]+)"')
def then_table_lists(world: World, name: str) -> None:
    world.require_clean("viewing the trend should have succeeded")
    names = [row.category for row in world.trend.categories]
    assert name in names, f'expected the table to list "{name}"; got {names}'


@step(r'the table does not list "(?P<name>[^"]+)"')
def then_table_does_not_list(world: World, name: str) -> None:
    world.require_clean("viewing the trend should have succeeded")
    names = [row.category for row in world.trend.categories]
    assert name not in names, f'expected the table to leave out "{name}"; got {names}'


@step(r'the table lists "(?P<first>[^"]+)" before "(?P<second>[^"]+)"')
def then_table_lists_before(world: World, first: str, second: str) -> None:
    world.require_clean("viewing the trend should have succeeded")
    names = [row.category for row in world.trend.categories]
    assert first in names and second in names, f'expected both "{first}" and "{second}" in the table; got {names}'
    assert names.index(first) < names.index(second), f'expected "{first}" before "{second}" in the table; got {names}'


@step(r'the table lists "(?P<name>[^"]+)" totaling (?P<amount>' + _DEC + r") COP across the window")
def then_table_lists_totaling(world: World, name: str, amount: str) -> None:
    world.require_clean("viewing the trend should have succeeded")
    row = _category_row(world.trend, name)
    assert row is not None, f'the table does not list "{name}"'
    expected = major_to_cents(amount)
    assert row.total == expected, (
        f'"{name}": expected {expected} cents ({amount} COP) across the window, got {row.total}'
    )


@step(r'the table lists "(?P<name>[^"]+)" with (?P<amount>' + _DEC + r") COP in (?P<month>" + _MONTH + r")")
def then_table_lists_with_month(world: World, name: str, amount: str, month: str) -> None:
    world.require_clean("viewing the trend should have succeeded")
    row = _category_row(world.trend, name)
    assert row is not None, f'the table does not list "{name}"'
    expected = major_to_cents(amount)
    got = row.by_month.get(month, 0)
    assert got == expected, f'"{name}" in {month}: expected {expected} cents ({amount} COP), got {got}'


@step(r'the group for "(?P<name>[^"]+)" is "(?P<group>[^"]+)"')
def then_group_for(world: World, name: str, group: str) -> None:
    world.require_clean("viewing the trend should have succeeded")
    row = _category_row(world.trend, name)
    assert row is not None, f'the table does not list "{name}"'
    assert row.group == group, f'"{name}": expected group "{group}", got {row.group!r}'
