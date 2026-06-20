from datetime import date

from quaestor.domain.dtos import SafeToSpend
from quaestor.domain.report_markdown import money, render_markdown
from quaestor.domain.report_types import (
    AccountBalance,
    CategorySection,
    DriftMoM,
    EnvelopeLine,
    EnvelopesSummary,
    GoalLine,
    GroupSection,
    MonthlyReport,
)


def _full_report():
    return MonthlyReport(
        month="2026-06",
        income=5_000_000, expense=3_000_000, net=2_000_000,
        envelopes_summary=EnvelopesSummary(n_green=2, n_red=1, rollover_generated=150_000),
        envelopes=[
            EnvelopeLine("Food", 1_000_000, 0, 800_000, 200_000, "under"),
            EnvelopeLine("Fun", 200_000, 0, 250_000, -50_000, "over"),
        ],
        by_category=[
            CategorySection("Food", "Essentials", 800_000, 26.666666666666668),
            CategorySection("Uncategorized", None, 100_000, 3.3333333333333335),
        ],
        by_group=[GroupSection("Essentials", 800_000, 26.666666666666668)],
        goals=[
            GoalLine("Trip", 600_000, target=1_200_000, eta=date(2026, 12, 1), on_track=True),
            GoalLine("Buffer", 300_000),
        ],
        balances=[AccountBalance("Bank", "COP", 9_000_000), AccountBalance("USD Wallet", "USD", 12_345)],
        drift_mom=DriftMoM("2026-05", 100_000, 2.0, -50_000, -1.5, 150_000, None),
        usd_share=0.25,
        pending=["Bank: $40,000.00 COP pending"],
        safe_to_spend=SafeToSpend("2026-06", 0, 0, 0, 1_750_000, []),
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
    # headline = net + envelope performance (ADR-019)
    assert "# Monthly report — 2026-06" in out
    assert "**Net:** $20,000.00 COP" in out
    assert "2 green / 1 red" in out
    # section ordering: net before envelopes before categories before closing
    assert out.index("Net:") < out.index("## Envelopes")
    assert out.index("## Envelopes") < out.index("## Expense by category")
    assert out.index("## Expense by category") < out.index("## Goals")
    assert out.index("## Goals") < out.index("## Account balances")
    assert out.index("## Account balances") < out.index("## Month-over-month")
    assert out.index("## Month-over-month") < out.index("## Closing")
    # safe-to-spend is the closing line, not the headline
    assert "You closed with $17,500.00 COP free" in out


def test_render_goal_eta_only_on_defined_goals():
    out = render_markdown(_full_report())
    assert "Trip" in out and "ETA 2026-12-01" in out and "on track" in out
    assert "Buffer" in out and "open-ended" in out


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
        month="2026-06", income=0, expense=0, net=0,
        envelopes_summary=EnvelopesSummary(0, 0, 0), envelopes=[],
        by_category=[], by_group=[], goals=[], balances=[],
        drift_mom=None, usd_share=0.0, pending=[],
        safe_to_spend=SafeToSpend("2026-06", 0, 0, 0, 0, []), markdown="",
    )
    out = render_markdown(report)
    assert "# Monthly report — 2026-06" in out
    assert "## Closing" in out
