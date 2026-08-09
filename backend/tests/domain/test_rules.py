from datetime import date

import pytest
from quaestor.domain import rules
from quaestor.domain.models import TxType


def test_income_adds():
    assert rules.delta_balance(TxType.income, 5000) == 5000


def test_expense_subtracts():
    assert rules.delta_balance(TxType.expense, 5000) == -5000


def test_transfer_type_is_rejected_by_delta_balance():
    with pytest.raises(ValueError):
        rules.delta_balance(TxType.transfer, 5000)


def test_transfer_deltas_are_mirrored():
    assert rules.transfer_deltas(5000) == (-5000, 5000)


def test_month_bounds_handles_february_and_year():
    assert rules.month_bounds("2026-02") == (date(2026, 2, 1), date(2026, 2, 28))
    assert rules.month_bounds("2026-12") == (date(2026, 12, 1), date(2026, 12, 31))


def test_prev_year_month_wraps_january():
    assert rules.prev_year_month("2026-06") == "2026-05"
    assert rules.prev_year_month("2026-01") == "2025-12"


def test_a_share_of_a_month_with_no_income_is_no_share():
    """The guard is reached on every empty month; what it answers was never asked.

    A month that earned nothing saved no share of it. Anything else puts a
    percentage beside a figure there is no percentage of.
    """
    assert rules.share_calc(500_000, 0) == 0
    assert rules.share_calc(0, 0) == 0


def test_a_share_is_whole_percent_of_the_month():
    assert rules.share_calc(300_000, 1_000_000) == 30
    assert rules.share_calc(-200_000, 1_000_000) == -20
