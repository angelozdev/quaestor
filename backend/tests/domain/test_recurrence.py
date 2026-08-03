from datetime import date

from quaestor.domain.models import IntervalUnit
from quaestor.domain.recurrence import due_dates, has_ended, is_due_on


def test_monthly_due_dates_in_window():
    got = due_dates(
        date(2026, 1, 15),
        None,
        IntervalUnit.month,
        1,
        since=date(2026, 1, 1),
        until=date(2026, 4, 30),
    )
    assert got == [date(2026, 1, 15), date(2026, 2, 15), date(2026, 3, 15), date(2026, 4, 15)]


def test_daily_lands_on_consecutive_days():
    got = due_dates(
        date(2026, 1, 1),
        None,
        IntervalUnit.day,
        1,
        since=date(2026, 1, 1),
        until=date(2026, 1, 4),
    )
    assert got == [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3), date(2026, 1, 4)]


def test_every_three_days_counts_forward_from_the_start():
    got = due_dates(
        date(2026, 1, 1),
        None,
        IntervalUnit.day,
        3,
        since=date(2026, 1, 1),
        until=date(2026, 1, 10),
    )
    assert got == [date(2026, 1, 1), date(2026, 1, 4), date(2026, 1, 7), date(2026, 1, 10)]


def test_daily_crosses_a_month_boundary():
    got = due_dates(
        date(2026, 1, 30),
        None,
        IntervalUnit.day,
        1,
        since=date(2026, 1, 30),
        until=date(2026, 2, 2),
    )
    assert got == [date(2026, 1, 30), date(2026, 1, 31), date(2026, 2, 1), date(2026, 2, 2)]


def test_weekly_lands_seven_days_forward_not_back():
    got = due_dates(
        date(2026, 1, 8),
        None,
        IntervalUnit.week,
        1,
        since=date(2026, 1, 1),
        until=date(2026, 1, 22),
    )
    assert got == [date(2026, 1, 8), date(2026, 1, 15), date(2026, 1, 22)]


def test_is_due_on_covers_the_daily_cadence():
    assert is_due_on(date(2026, 1, 1), None, IntervalUnit.day, 3, date(2026, 1, 7))
    assert not is_due_on(date(2026, 1, 1), None, IntervalUnit.day, 3, date(2026, 1, 8))


def test_biweekly_generates_several_in_a_month():
    got = due_dates(
        date(2026, 1, 1),
        None,
        IntervalUnit.week,
        2,
        since=date(2026, 1, 1),
        until=date(2026, 2, 28),
    )
    assert got == [date(2026, 1, 1), date(2026, 1, 15), date(2026, 1, 29), date(2026, 2, 12), date(2026, 2, 26)]


def test_every_three_months_quarterly():
    got = due_dates(
        date(2026, 1, 10),
        None,
        IntervalUnit.month,
        3,
        since=date(2026, 1, 1),
        until=date(2026, 12, 31),
    )
    assert got == [date(2026, 1, 10), date(2026, 4, 10), date(2026, 7, 10), date(2026, 10, 10)]


def test_annual():
    got = due_dates(
        date(2024, 3, 5),
        None,
        IntervalUnit.year,
        1,
        since=date(2024, 1, 1),
        until=date(2026, 12, 31),
    )
    assert got == [date(2024, 3, 5), date(2025, 3, 5), date(2026, 3, 5)]


def test_end_of_month_clamping_anchors_to_start_day():
    # day-31 anchor: Feb clamps to 28, but March returns to 31 (not chained off Feb)
    got = due_dates(
        date(2026, 1, 31),
        None,
        IntervalUnit.month,
        1,
        since=date(2026, 1, 1),
        until=date(2026, 4, 30),
    )
    assert got == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)]


def test_leap_year_february_clamp():
    got = due_dates(
        date(2024, 1, 29),
        None,
        IntervalUnit.year,
        1,
        since=date(2024, 1, 1),
        until=date(2025, 12, 31),
    )
    assert got == [date(2024, 1, 29), date(2025, 1, 29)]  # both valid; check Feb separately
    feb = due_dates(
        date(2024, 2, 29),
        None,
        IntervalUnit.year,
        1,
        since=date(2024, 1, 1),
        until=date(2025, 12, 31),
    )
    assert feb == [date(2024, 2, 29), date(2025, 2, 28)]  # 2025 is not a leap year


def test_end_date_truncates_window():
    got = due_dates(
        date(2026, 1, 1),
        date(2026, 3, 1),
        IntervalUnit.month,
        1,
        since=date(2026, 1, 1),
        until=date(2026, 12, 31),
    )
    assert got == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]


def test_since_skips_earlier_occurrences():
    got = due_dates(
        date(2026, 1, 1),
        None,
        IntervalUnit.month,
        1,
        since=date(2026, 3, 1),
        until=date(2026, 5, 31),
    )
    assert got == [date(2026, 3, 1), date(2026, 4, 1), date(2026, 5, 1)]


def test_empty_when_start_after_until():
    assert (
        due_dates(
            date(2027, 1, 1),
            None,
            IntervalUnit.month,
            1,
            since=date(2026, 1, 1),
            until=date(2026, 12, 31),
        )
        == []
    )


def test_is_due_on_accepts_a_real_due_date():
    assert is_due_on(date(2026, 1, 5), None, IntervalUnit.week, 1, date(2026, 1, 12))


def test_is_due_on_rejects_a_date_between_two_due_dates():
    assert not is_due_on(date(2026, 1, 5), None, IntervalUnit.week, 1, date(2026, 1, 8))


def test_is_due_on_rejects_a_date_before_the_start():
    assert not is_due_on(date(2026, 1, 5), None, IntervalUnit.week, 1, date(2025, 12, 29))


def test_is_due_on_rejects_a_date_past_the_end():
    assert not is_due_on(date(2026, 1, 5), date(2026, 1, 12), IntervalUnit.week, 1, date(2026, 1, 19))


def test_is_due_on_accepts_the_end_date_itself():
    assert is_due_on(date(2026, 1, 5), date(2026, 1, 12), IntervalUnit.week, 1, date(2026, 1, 12))


def test_is_due_on_honours_the_end_of_month_clamp():
    assert is_due_on(date(2026, 1, 31), None, IntervalUnit.month, 1, date(2026, 2, 28))
    assert not is_due_on(date(2026, 1, 31), None, IntervalUnit.month, 1, date(2026, 2, 27))


def test_has_ended_is_false_without_an_end_date():
    assert not has_ended(None, date(2026, 8, 2))


def test_has_ended_is_false_on_the_end_date_itself():
    assert not has_ended(date(2026, 8, 2), date(2026, 8, 2))


def test_has_ended_is_true_the_day_after_the_end_date():
    assert has_ended(date(2026, 8, 1), date(2026, 8, 2))
