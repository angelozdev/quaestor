"""Pure renderer: MonthlyReport -> markdown string. No I/O, no session.

Both views (MCP chat in P2, the /reports screen in P6) consume the same object;
this module turns its data into the markdown half. Section order follows ADR-019:
the headline is net + envelope performance; safe-to-spend is the closing line.
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


def render_markdown(report: "MonthlyReport") -> str:
    lines: list[str] = []

    # 1. Headline — net + envelope performance (ADR-019)
    lines.append(f"# Monthly report — {report.month}")
    lines.append("")
    lines.append(
        f"**Net:** {money(report.net)}  "
        f"(income {money(report.income)} − expense {money(report.expense)})"
    )
    s = report.envelopes_summary
    lines.append(
        f"**Envelopes:** {s.n_green} green / {s.n_red} red · "
        f"rollover generated {money(s.rollover_generated)}"
    )
    lines.append("")

    # 2. Envelopes detail
    lines.append("## Envelopes")
    if report.envelopes:
        lines.append("| Category | Allocated | Rollover in | Spent | Available | Status |")
        lines.append("|---|---|---|---|---|---|")
        for e in report.envelopes:
            lines.append(
                f"| {e.category} | {money(e.allocated)} | {money(e.rollover_in)} | "
                f"{money(e.spent)} | {money(e.available)} | {e.status} |"
            )
    else:
        lines.append("_No envelopes this month._")
    lines.append("")

    # 3. Expense by category
    lines.append("## Expense by category")
    if report.by_category:
        lines.append("| Category | Group | Total | % |")
        lines.append("|---|---|---|---|")
        for c in report.by_category:
            lines.append(
                f"| {c.category} | {c.group or '—'} | {money(c.total)} | {_pct(c.pct)} |"
            )
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

    # 5. Goals — ETA/on-track only on defined goals
    lines.append("## Goals")
    if report.goals:
        for g in report.goals:
            if g.target is not None:
                track = "on track" if g.on_track else "behind"
                eta = g.eta.isoformat() if g.eta else "—"
                lines.append(
                    f"- **{g.name}**: {money(g.accumulated)} / {money(g.target)} "
                    f"· ETA {eta} · {track}"
                )
            else:
                lines.append(f"- **{g.name}**: {money(g.accumulated)} (open-ended)")
    else:
        lines.append("_No goals._")
    lines.append("")

    # 6. Account balances
    lines.append("## Account balances")
    if report.balances:
        for b in report.balances:
            lines.append(f"- {b.account}: {money(b.balance, b.currency)}")
    else:
        lines.append("_No accounts._")
    lines.append("")

    # 7. Month-over-month drift + USD share
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

    # 8. Pending confirmations (only when present)
    if report.pending:
        lines.append("## Pending confirmations")
        for p in report.pending:
            lines.append(f"- {p}")
        lines.append("")

    # 9. Closing — safe-to-spend (ADR-019: not a headline)
    lines.append("## Closing")
    lines.append(f"You closed with {money(report.safe_to_spend.free)} free to spend.")

    return "\n".join(lines)
