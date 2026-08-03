from datetime import date

from quaestor.domain.rules import goal_progress_calc

TODAY = date(2026, 6, 19)


def test_open_ended_reports_only_saved():
    g = goal_progress_calc(
        1, "Buffer", monthly_amount=100_000, saved=450_000, target_amount=None, deadline=None, today=TODAY
    )
    assert g.type == "open-ended"
    assert g.saved == 450_000
    assert g.monthly_required is None and g.on_track is None and g.eta is None
    assert g.remaining is None


def test_defined_on_track_with_eta():
    g = goal_progress_calc(
        1,
        "Trip",
        monthly_amount=200_000,
        saved=200_000,
        target_amount=1_200_000,
        deadline=date(2026, 12, 1),
        today=TODAY,
    )
    assert g.type == "defined"
    assert g.remaining == 1_000_000
    assert g.monthly_required == 166_667  # ceil(1_000_000 / 6)
    assert g.on_track is True
    assert g.eta == date(2026, 11, 19)  # today + ceil(1_000_000/200_000)=5 months


def test_defined_behind_when_monthly_amount_too_small():
    g = goal_progress_calc(
        1,
        "Trip",
        monthly_amount=100_000,
        saved=200_000,
        target_amount=1_200_000,
        deadline=date(2026, 12, 1),
        today=TODAY,
    )
    assert g.on_track is False
    assert g.eta == date(2027, 4, 19)  # today + ceil(1_000_000/100_000)=10 months


def test_defined_past_deadline_clamps_months_left_to_one():
    g = goal_progress_calc(
        1,
        "Trip",
        monthly_amount=100_000,
        saved=200_000,
        target_amount=1_200_000,
        deadline=date(2026, 1, 1),
        today=TODAY,
    )
    assert g.monthly_required == 1_000_000  # remaining / 1


def test_defined_reached_when_saved_meets_target():
    g = goal_progress_calc(
        1,
        "Trip",
        monthly_amount=200_000,
        saved=1_200_000,
        target_amount=1_200_000,
        deadline=date(2026, 12, 1),
        today=TODAY,
    )
    assert g.remaining == 0
    assert g.monthly_required == 0
    assert g.on_track is True
    assert g.eta == TODAY
