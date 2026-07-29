from datetime import date

from quaestor.domain.report_types import (
    AccountBalance,
    CategorySection,
    DriftMoM,
    EnvelopeLine,
    EnvelopesSummary,
    GoalLine,
    GroupSection,
    MonthlyReport,
    SafeToSpend,  # re-exported from dtos
)


def test_safe_to_spend_is_reexported_from_dtos():
    from quaestor.domain import dtos
    assert SafeToSpend is dtos.SafeToSpend


def test_value_types_hold_their_fields():
    summary = EnvelopesSummary(n_green=2, n_red=1, rollover_generated=5000)
    assert (summary.n_green, summary.n_red, summary.rollover_generated) == (2, 1, 5000)

    line = EnvelopeLine(
        category="Food", allocated=100, rollover_in=10, spent=40,
        available=70, status="under",
    )
    assert line.category == "Food" and line.available == 70

    cat = CategorySection(category="Food", group="Essentials", total=400, pct=25.0)
    assert cat.group == "Essentials" and cat.pct == 25.0

    grp = GroupSection(group="Essentials", total=400, pct=25.0)
    assert grp.group == "Essentials"

    goal = GoalLine(name="Trip", accumulated=300)
    assert goal.target is None and goal.eta is None and goal.on_track is None

    bal = AccountBalance(account="Bank", currency="COP", balance=999)
    assert bal.currency == "COP"

    drift = DriftMoM(
        prev_month="2026-05", income_abs=10, income_pct=5.0,
        expense_abs=-20, expense_pct=None, net_abs=30, net_pct=None,
    )
    assert drift.prev_month == "2026-05" and drift.expense_pct is None


def test_monthly_report_markdown_is_mutable():
    sts = SafeToSpend(
        year_month="2026-06", income_forecast=0, committed=0,
        assigned_envelopes=0, free=12345, committed_breakdown=[],
    )
    report = MonthlyReport(
        month="2026-06", income=0, expense=0, net=0,
        envelopes_summary=EnvelopesSummary(0, 0, 0), envelopes=[],
        by_category=[], by_group=[], goals=[], balances=[],
        drift_mom=None, usd_share=0.0, pending=[], safe_to_spend=sts, markdown="",
    )
    report.markdown = "rendered"  # must be reassignable (renderer fills it last)
    assert report.markdown == "rendered"
