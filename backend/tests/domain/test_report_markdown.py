from quaestor.domain.dtos import MonthAvailable
from quaestor.domain.report_markdown import money, render_markdown
from quaestor.domain.report_types import (
    AccountBalance,
    CategorySection,
    DriftMoM,
    FundReportLine,
    FundsSummary,
    GroupSection,
    MetaReportLine,
    MonthlyReport,
)


def _full_report():
    return MonthlyReport(
        month="2026-06",
        income=5_000_000,
        expense=3_000_000,
        net=2_000_000,
        funds_summary=FundsSummary(n_on_track=2, n_behind=1, set_aside=150_000),
        funds=[
            FundReportLine("Food", 1_000_000, 200_000, 800_000, True),
            FundReportLine("Fun", 200_000, 0, 250_000, False),
        ],
        metas=[
            MetaReportLine("Celular", "COP", 1_600_000, 3_200_000),
            MetaReportLine("Curso", "USD", 33_334, 66_668),
        ],
        asked=2_800_000,
        by_category=[
            CategorySection("Food", "Essentials", 800_000, 26.666666666666668),
            CategorySection("Uncategorized", None, 100_000, 3.3333333333333335),
        ],
        by_group=[GroupSection("Essentials", 800_000, 26.666666666666668)],
        balances=[AccountBalance("Bank", "COP", 9_000_000), AccountBalance("USD Wallet", "USD", 12_345)],
        drift_mom=DriftMoM("2026-05", 100_000, 2.0, -50_000, -1.5, 150_000, None),
        usd_share=0.25,
        pending=["Bank: $40,000.00 COP pending"],
        available=MonthAvailable("2026-06", 0, [], 0, 1_750_000),
        markdown="",
    )


def test_money_formats_cents_with_currency():
    assert money(1_234_567) == "$12,345.67 COP"
    assert money(12_345, "USD") == "$123.45 USD"
    assert money(0) == "$0.00 COP"


def test_render_is_deterministic():
    report = _full_report()
    assert render_markdown(report) == render_markdown(report)


def test_render_headline_and_section_order():
    out = render_markdown(_full_report())
    # headline = net + how the funds did (ADR-019, ADR-0043)
    assert "# Monthly report — 2026-06" in out
    assert "**Net:** $20,000.00 COP" in out
    assert "2 on track / 1 behind" in out
    # section ordering: net before funds before categories before closing
    assert out.index("Net:") < out.index("## Funds")
    assert out.index("## Funds") < out.index("## Metas")
    assert out.index("## Metas") < out.index("## Expense by category")
    assert out.index("## Expense by category") < out.index("## Account balances")
    assert out.index("## Account balances") < out.index("## Month-over-month")
    assert out.index("## Month-over-month") < out.index("## Closing")
    # the money left over is the closing line, not the headline
    assert "You closed with $17,500.00 COP free" in out


def test_render_names_every_fund_with_what_it_asks_and_holds():
    out = render_markdown(_full_report())
    assert "| Food | $10,000.00 COP | $2,000.00 COP | $8,000.00 COP | on track |" in out
    assert "| Fun | $2,000.00 COP | $0.00 COP | $2,500.00 COP | behind |" in out


def test_render_usd_share_as_percentage():
    out = render_markdown(_full_report())
    assert "USD share of expense: 25.0%" in out


def test_render_cold_start_drift_none():
    report = _full_report()
    report.drift_mom = None
    out = render_markdown(report)
    assert "cold start" in out.lower()


def test_render_empty_sections_do_not_crash():
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
        available=MonthAvailable("2026-06", 0, [], 0, 0),
        markdown="",
    )
    out = render_markdown(report)
    assert "# Monthly report — 2026-06" in out
    assert "## Closing" in out


def test_render_names_every_meta_by_meta_and_in_its_own_currency():
    """AC-36: the metas are their own section, never folded into a category."""
    out = render_markdown(_full_report())

    assert "| Celular | $16,000.00 COP | $32,000.00 COP |" in out
    assert "| Curso | $333.34 USD | $666.68 USD |" in out


def test_render_states_what_the_month_asks_in_all():
    """A report that showed only the funds would understate the month (AC-36)."""
    assert "**The month asks $28,000.00 COP in all**" in render_markdown(_full_report())


def test_render_a_month_with_no_metas_says_so():
    report = _full_report()
    report.metas = []

    assert "_No metas this month._" in render_markdown(report)
