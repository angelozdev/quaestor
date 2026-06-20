from datetime import date

from quaestor.domain.rules import (
    envelope_status_calc,
    month_bounds,
    prev_year_month,
)


def test_month_bounds_handles_february_and_year():
    assert month_bounds("2026-02") == (date(2026, 2, 1), date(2026, 2, 28))
    assert month_bounds("2026-12") == (date(2026, 12, 1), date(2026, 12, 31))


def test_prev_year_month_wraps_january():
    assert prev_year_month("2026-06") == "2026-05"
    assert prev_year_month("2026-01") == "2025-12"


def test_envelope_available_and_status_under():
    s = envelope_status_calc(1, "2026-06", assigned=100_000, rollover_in=20_000, spent=30_000)
    assert s.available == 90_000
    assert s.pct_used == 25  # round(30000 / 120000 * 100)
    assert s.status == "under"


def test_envelope_over_when_spent_exceeds_assigned_plus_rollover():
    s = envelope_status_calc(1, "2026-06", assigned=50_000, rollover_in=0, spent=60_000)
    assert s.available == -10_000
    assert s.status == "over"


def test_envelope_zero_denominator_does_not_divide():
    s = envelope_status_calc(1, "2026-06", assigned=0, rollover_in=0, spent=0)
    assert s.pct_used == 0
    assert s.status == "under"
