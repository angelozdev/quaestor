"""Pure renderer: MonthlyReport -> markdown string. No I/O, no session.

Both views (MCP chat in P2, the /reports screen in P6) consume the same object;
this module turns its data into the markdown half. Section order follows ADR-019:
the headline is net + how the funds did; the money left over is the closing line.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .money import cents_to_major

if TYPE_CHECKING:
    from .report_types import MonthlyReport


def money(cents: int, currency: str = "COP") -> str:
    """Format integer cents, e.g. 1234567 -> '$12,345.67 COP'."""
    return f"${cents_to_major(cents):,.2f} {currency}"


def _pct(value: float) -> str:
    return f"{value:.1f}%"


def render_markdown(report: MonthlyReport) -> str:
    lines: list[str] = []

    # 1. Headline — net + how the funds did (ADR-019, ADR-0043)
    lines.append(f"# Monthly report — {report.month}")
    lines.append("")
    lines.append(f"**Net:** {money(report.net)}  (income {money(report.income)} − expense {money(report.expense)})")
    s = report.funds_summary
    lines.append(f"**Funds:** {s.n_on_track} on track / {s.n_behind} behind · set aside {money(s.set_aside)}")
    lines.append("")

    # 2. Funds detail
    lines.append("## Funds")
    if report.funds:
        lines.append("| Category | Asks | Holds | Spent | Status |")
        lines.append("|---|---|---|---|---|")
        for f in report.funds:
            status = "on track" if f.on_track else "behind"
            lines.append(f"| {f.category_name} | {money(f.asks)} | {money(f.holds)} | {money(f.spent)} | {status} |")
    else:
        lines.append("_No funds this month._")
    lines.append("")

    # 3. Expense by category
    lines.append("## Expense by category")
    if report.by_category:
        lines.append("| Category | Group | Total | % |")
        lines.append("|---|---|---|---|")
        for c in report.by_category:
            lines.append(f"| {c.category} | {c.group or '—'} | {money(c.total)} | {_pct(c.pct)} |")
    else:
        lines.append("_No expenses this month._")
    lines.append("")

    # 4. Expense by group
    lines.append("## Expense by group")
    if report.by_group:
        lines.append("| Group | Total | % |")
        lines.append("|---|---|---|")
        for g in report.by_group:
            lines.append(f"| {g.group} | {money(g.total)} | {_pct(g.pct)} |")
    else:
        lines.append("_No expenses this month._")
    lines.append("")

    # 5. Account balances
    lines.append("## Account balances")
    if report.balances:
        for b in report.balances:
            lines.append(f"- {b.account}: {money(b.balance, b.currency)}")
    else:
        lines.append("_No accounts._")
    lines.append("")

    # 6. Month-over-month drift + USD share
    lines.append("## Month-over-month")
    if report.drift_mom is not None:
        d = report.drift_mom

        def fmt(abs_v: int, pct_v: float | None) -> str:
            p = f"{pct_v:+.1f}%" if pct_v is not None else "n/a"
            return f"{money(abs_v)} ({p})"

        lines.append(
            f"vs {d.prev_month}: income {fmt(d.income_abs, d.income_pct)}, "
            f"expense {fmt(d.expense_abs, d.expense_pct)}, "
            f"net {fmt(d.net_abs, d.net_pct)}"
        )
    else:
        lines.append("_No previous month to compare (cold start)._")
    lines.append(f"USD share of expense: {report.usd_share * 100:.1f}%")
    lines.append("")

    # 7. Pending confirmations (only when present)
    if report.pending:
        lines.append("## Pending confirmations")
        for p in report.pending:
            lines.append(f"- {p}")
        lines.append("")

    # 8. Closing — the money available (ADR-019: not a headline)
    lines.append("## Closing")
    lines.append(f"You closed with {money(report.available.free)} free to spend.")

    return "\n".join(lines)
