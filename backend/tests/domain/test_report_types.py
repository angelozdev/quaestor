from quaestor.domain.report_types import (
    AccountBalance,
    CategorySection,
    DriftMoM,
    FundReportLine,
    FundsSummary,
    GroupSection,
    MonthAvailable,  # re-exported from dtos
    MonthlyReport,
)


def test_the_money_available_is_reexported_from_dtos():
    from quaestor.domain import dtos

    assert MonthAvailable is dtos.MonthAvailable


def test_value_types_hold_their_fields():
    summary = FundsSummary(n_on_track=2, n_behind=1, set_aside=5000)
    assert (summary.n_on_track, summary.n_behind, summary.set_aside) == (2, 1, 5000)

    line = FundReportLine(
        category_name="Food",
        asks=100,
        holds=70,
        spent=40,
        on_track=True,
    )
    assert line.category_name == "Food" and line.holds == 70

    cat = CategorySection(category="Food", group="Essentials", total=400, pct=25.0)
    assert cat.group == "Essentials" and cat.pct == 25.0

    grp = GroupSection(group="Essentials", total=400, pct=25.0)
    assert grp.group == "Essentials"

    bal = AccountBalance(account="Bank", currency="COP", balance=999)
    assert bal.currency == "COP"

    drift = DriftMoM(
        prev_month="2026-05",
        income_abs=10,
        income_pct=5.0,
        expense_abs=-20,
        expense_pct=None,
        net_abs=30,
        net_pct=None,
    )
    assert drift.prev_month == "2026-05" and drift.expense_pct is None


def test_monthly_report_markdown_is_mutable():
    available = MonthAvailable(year_month="2026-06", income=0, funds=[], uncovered=0, free=12345)
    report = MonthlyReport(
        month="2026-06",
        income=0,
        expense=0,
        net=0,
        funds_summary=FundsSummary(0, 0, 0),
        funds=[],
        metas=[],
        asked=0,
        by_category=[],
        by_group=[],
        balances=[],
        drift_mom=None,
        usd_share=0.0,
        pending=[],
        available=available,
        markdown="",
    )
    report.markdown = "rendered"  # must be reassignable (renderer fills it last)
    assert report.markdown == "rendered"
