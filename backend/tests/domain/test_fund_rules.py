"""The fund arithmetic, on its own: no session, no models (ADR-0043)."""

from datetime import date

import pytest
from quaestor.domain.models import IntervalUnit
from quaestor.domain.recurrence import next_due_on_or_after
from quaestor.domain.rules import (
    available_calc,
    claim_holdings,
    fund_ask_calc,
    fund_holds_calc,
    fund_next_opening_calc,
    margin_calc,
    monthly_average_calc,
    monthly_rate_calc,
    months_between,
    months_to_fund,
    next_year_month,
    shift_year_month,
    uncovered_excess_calc,
    year_month_of,
)


def test_year_month_of_a_day():
    assert year_month_of(date(2026, 11, 10)) == "2026-11"


@pytest.mark.parametrize(
    ("year_month", "expected"),
    [("2026-11", "2026-12"), ("2026-12", "2027-01")],
)
def test_next_year_month(year_month, expected):
    assert next_year_month(year_month) == expected


@pytest.mark.parametrize(
    ("year_month", "months", "expected"),
    [
        ("2026-11", 0, "2026-11"),
        ("2026-11", 3, "2027-02"),
        ("2026-11", -3, "2026-08"),
        ("2026-01", -1, "2025-12"),
    ],
)
def test_shift_year_month(year_month, months, expected):
    assert shift_year_month(year_month, months) == expected


def test_months_between_counts_whole_months():
    assert months_between("2026-11", "2027-05") == 6
    assert months_between("2027-05", "2027-05") == 0
    assert months_between("2027-05", "2026-11") == -6


def test_a_fund_fills_from_this_month_through_the_month_before_the_charge():
    assert months_to_fund("2026-11", "2027-05") == 6
    assert months_to_fund("2027-04", "2027-05") == 1


def test_a_charge_landing_this_month_still_leaves_one_month_to_fill():
    assert months_to_fund("2027-05", "2027-05") == 1


def test_a_fund_with_no_charge_date_fills_in_the_month_itself():
    assert months_to_fund("2026-11", None) == 1


def test_the_ask_is_what_is_missing_over_the_months_left():
    assert fund_ask_calc(447_300_00, 6) == 74_550_00
    assert fund_ask_calc(298_200_00, 4) == 74_550_00


def test_a_fund_that_needs_nothing_asks_nothing():
    assert fund_ask_calc(0, 6) == 0
    assert fund_ask_calc(-5, 6) == 0


def test_the_ask_rounds_up_so_the_money_arrives():
    assert fund_ask_calc(100, 3) == 34


def test_a_single_centavo_missing_is_still_asked_for():
    """The guard turns nothing away but nothing — one centavo short is short."""
    assert fund_ask_calc(1, 6) == 1
    assert fund_ask_calc(2, 6) == 1


def test_a_fund_with_no_months_left_asks_for_all_of_it_at_once():
    """`months_to_fund` floors at one, and the ask holds that floor on its own."""
    assert fund_ask_calc(100, 0) == 100
    assert fund_ask_calc(100, -3) == 100


def test_the_average_divides_by_the_months_the_app_has_data_for():
    assert monthly_average_calc(430_950_00, 3) == 143_650_00
    assert monthly_average_calc(300_000_00, 2) == 150_000_00


def test_a_single_month_of_data_averages_to_that_month():
    assert monthly_average_calc(300_00, 1) == 300_00


def test_the_average_of_no_months_is_nothing():
    assert monthly_average_calc(0, 0) == 0


def test_a_fund_holds_what_it_opened_with_minus_what_was_spent():
    assert fund_holds_calc(447_300_00, 100_000_00) == 347_300_00


def test_an_overspent_fund_falls_to_zero_and_never_below():
    assert fund_holds_calc(100_000_00, 400_000_00) == 0


def test_an_accumulating_fund_carries_its_balance_into_the_next_month():
    assert fund_next_opening_calc(0, 0, 100_000_00, accumulates=True) == 100_000_00


def test_a_resetting_fund_opens_the_next_month_at_zero():
    assert fund_next_opening_calc(500_000_00, 0, 100_000_00, accumulates=False) == 0


def test_an_accumulating_fund_never_carries_a_negative_balance_forward():
    assert fund_next_opening_calc(0, 400_000_00, 100_000_00, accumulates=True) == 0


def test_the_soonest_obligation_claims_what_the_fund_holds_first():
    assert claim_holdings(100, [60, 60]) == [60, 40]


def test_nothing_is_claimed_by_a_fund_holding_nothing():
    assert claim_holdings(0, [60, 60]) == [0, 0]


def test_a_fund_holding_more_than_it_needs_leaves_the_rest_unclaimed():
    assert claim_holdings(500, [60, 60]) == [60, 60]


def test_the_next_due_date_on_or_after_a_day():
    due = next_due_on_or_after(date(2026, 1, 5), None, IntervalUnit.month, 1, date(2026, 12, 1))
    assert due == date(2026, 12, 5)


def test_the_next_due_date_of_a_cadence_that_has_not_started_is_its_first():
    due = next_due_on_or_after(date(2027, 5, 2), None, IntervalUnit.year, 1, date(2026, 12, 1))
    assert due == date(2027, 5, 2)


def test_a_cadence_past_its_end_has_no_next_due_date():
    due = next_due_on_or_after(date(2026, 1, 5), date(2026, 6, 5), IntervalUnit.month, 1, date(2026, 12, 1))
    assert due is None


# ------------------------------------------------ the month's number (F1)


@pytest.mark.parametrize(
    ("amount", "unit", "count", "expected"),
    [
        (5_000_000_00, IntervalUnit.month, 1, 5_000_000_00),
        (3_000_000_00, IntervalUnit.month, 3, 1_000_000_00),
        (600_000_00, IntervalUnit.year, 1, 50_000_00),
        (1_200_000_00, IntervalUnit.year, 2, 50_000_00),
    ],
)
def test_a_cycle_is_brought_to_one_month(amount, unit, count, expected):
    assert monthly_rate_calc(amount, unit, count) == expected


def test_a_weekly_charge_costs_the_turns_a_month_really_holds():
    assert monthly_rate_calc(100_00, IntervalUnit.week, 1) == 433_34  # 52/12 weeks, rounded up


def test_a_daily_charge_costs_a_month_of_days():
    assert monthly_rate_calc(100_00, IntervalUnit.day, 1) == 3041_67  # 365/12 days, rounded up


def test_a_rate_refuses_a_cycle_it_cannot_read():
    with pytest.raises(ValueError):
        monthly_rate_calc(100_00, IntervalUnit.month, 0)


def test_only_the_excess_past_a_fund_leaves_the_money_available():
    assert uncovered_excess_calc(spent=350_000_00, covered=200_000_00) == 150_000_00


def test_spending_inside_what_a_fund_had_leaves_nothing_uncovered():
    assert uncovered_excess_calc(spent=150_000_00, covered=200_000_00) == 0
    assert uncovered_excess_calc(spent=447_300_00, covered=447_300_00 + 74_550_00) == 0


def test_the_breakdown_is_income_less_every_ask_less_what_no_fund_covers():
    assert available_calc(5_000_000_00, 500_000_00, 150_000_00) == 4_350_000_00


def test_the_money_available_may_go_negative():
    assert available_calc(5_000_000_00, 10_000_000_00, 0) == -5_000_000_00


def test_the_margin_is_what_the_earning_rate_leaves():
    assert margin_calc(5_000_000_00, 200_000_00) == 4_800_000_00
