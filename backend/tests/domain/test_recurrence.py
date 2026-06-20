from datetime import date

from quaestor.domain.models import IntervalUnit
from quaestor.domain.rules import due_dates


def test_monthly_due_dates_in_window():
    got = due_dates(
        date(2026, 1, 15), None, IntervalUnit.month, 1,
        since=date(2026, 1, 1), until=date(2026, 4, 30),
    )
    assert got == [date(2026, 1, 15), date(2026, 2, 15), date(2026, 3, 15), date(2026, 4, 15)]


def test_biweekly_generates_several_in_a_month():
    got = due_dates(
        date(2026, 1, 1), None, IntervalUnit.week, 2,
        since=date(2026, 1, 1), until=date(2026, 2, 28),
    )
    assert got == [date(2026, 1, 1), date(2026, 1, 15), date(2026, 1, 29), date(2026, 2, 12), date(2026, 2, 26)]


def test_every_three_months_quarterly():
    got = due_dates(
        date(2026, 1, 10), None, IntervalUnit.month, 3,
        since=date(2026, 1, 1), until=date(2026, 12, 31),
    )
    assert got == [date(2026, 1, 10), date(2026, 4, 10), date(2026, 7, 10), date(2026, 10, 10)]


def test_annual():
    got = due_dates(
        date(2024, 3, 5), None, IntervalUnit.year, 1,
        since=date(2024, 1, 1), until=date(2026, 12, 31),
    )
    assert got == [date(2024, 3, 5), date(2025, 3, 5), date(2026, 3, 5)]


def test_end_of_month_clamping_anchors_to_start_day():
    # day-31 anchor: Feb clamps to 28, but March returns to 31 (not chained off Feb)
    got = due_dates(
        date(2026, 1, 31), None, IntervalUnit.month, 1,
        since=date(2026, 1, 1), until=date(2026, 4, 30),
    )
    assert got == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)]


def test_leap_year_february_clamp():
    got = due_dates(
        date(2024, 1, 29), None, IntervalUnit.year, 1,
        since=date(2024, 1, 1), until=date(2025, 12, 31),
    )
    assert got == [date(2024, 1, 29), date(2025, 1, 29)]  # both valid; check Feb separately
    feb = due_dates(
        date(2024, 2, 29), None, IntervalUnit.year, 1,
        since=date(2024, 1, 1), until=date(2025, 12, 31),
    )
    assert feb == [date(2024, 2, 29), date(2025, 2, 28)]  # 2025 is not a leap year


def test_end_date_truncates_window():
    got = due_dates(
        date(2026, 1, 1), date(2026, 3, 1), IntervalUnit.month, 1,
        since=date(2026, 1, 1), until=date(2026, 12, 31),
    )
    assert got == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]


def test_since_skips_earlier_occurrences():
    got = due_dates(
        date(2026, 1, 1), None, IntervalUnit.month, 1,
        since=date(2026, 3, 1), until=date(2026, 5, 31),
    )
    assert got == [date(2026, 3, 1), date(2026, 4, 1), date(2026, 5, 1)]


def test_empty_when_start_after_until():
    assert due_dates(
        date(2027, 1, 1), None, IntervalUnit.month, 1,
        since=date(2026, 1, 1), until=date(2026, 12, 31),
    ) == []
