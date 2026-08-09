"""Monthly report: posted-only aggregation + formatting (P5).

Reuses P0 (reads), P3 (to_pay) and the fund read path of feature 003 — the
fund lines and the closing line both come out of one walk of the month.
Every COP aggregate converts at read time from the current TRM (ADR-0031),
fetched once per report.
"""

from __future__ import annotations

from datetime import date as Date
from datetime import timedelta
from decimal import Decimal

from sqlmodel import Session

from ..domain.models import Account, Transaction
from ..domain.money import to_cop_cents
from ..domain.report_markdown import money, render_markdown
from ..domain.report_types import (
    AccountBalance,
    CategorySection,
    DriftMoM,
    FundReportLine,
    FundsSummary,
    GroupSection,
    MetaReportLine,
    MonthAvailable,
    MonthlyReport,
)
from ..domain.rules import prev_year_month
from . import accounts as _accounts
from . import metas as metas_service
from . import month as month_service
from . import planned as _planned
from .month_aggregate import MonthAggregate, load_month, require_year_month


def _usd_share(agg: MonthAggregate, expenses: list[Transaction], expense_total: int) -> float:
    """Fraction of expense (COP at the current TRM) originated in USD, [0, 1]."""
    if expense_total == 0:
        return 0.0
    usd = sum(agg.to_cop_cents(t) for t in expenses if t.currency == "USD")
    return usd / expense_total


def _category_sections(agg: MonthAggregate, expenses: list[Transaction], expense_total: int) -> list[CategorySection]:
    """Group expenses by category (None -> 'Uncategorized'); pct over total expense."""
    buckets: dict[int | None, int] = {}
    for tx in expenses:
        buckets[tx.category_id] = buckets.get(tx.category_id, 0) + agg.to_cop_cents(tx)
    sections: list[CategorySection] = []
    for cat_id, total in buckets.items():
        if cat_id is None:
            name, group = "Uncategorized", None
        else:
            cat = agg.category(cat_id)
            name = cat.name if cat is not None else f"category {cat_id}"
            group = agg.group_name(cat_id)
        pct = (total / expense_total * 100) if expense_total > 0 else 0.0
        sections.append(CategorySection(category=name, group=group, total=total, pct=pct))
    sections.sort(key=lambda s: (-s.total, s.category))
    return sections


def _group_sections(agg: MonthAggregate, expenses: list[Transaction], expense_total: int) -> list[GroupSection]:
    """Rollup of expenses by CategoryGroup name; pct over total expense (ADR-023)."""
    buckets: dict[str, int] = {}
    for tx in expenses:
        name = agg.group_name(tx.category_id) or "Ungrouped"
        buckets[name] = buckets.get(name, 0) + agg.to_cop_cents(tx)
    sections = [
        GroupSection(
            group=name,
            total=total,
            pct=(total / expense_total * 100) if expense_total > 0 else 0.0,
        )
        for name, total in buckets.items()
    ]
    sections.sort(key=lambda s: (-s.total, s.group))
    return sections


def _drift(agg: MonthAggregate, income: int, expense: int, net: int) -> DriftMoM | None:
    """MoM drift vs the previous calendar month. None on cold start (no prior activity)."""
    prev = prev_year_month(agg.year_month)
    p_income, p_expense, p_net = agg.totals_for(prev)
    if p_income == 0 and p_expense == 0:
        return None

    def pct(curr: int, base: int) -> float | None:
        return ((curr - base) / base * 100) if base != 0 else None

    return DriftMoM(
        prev_month=prev,
        income_abs=income - p_income,
        income_pct=pct(income, p_income),
        expense_abs=expense - p_expense,
        expense_pct=pct(expense, p_expense),
        net_abs=net - p_net,
        net_pct=pct(net, p_net),
    )


def _fund_lines(agg: MonthAggregate, statuses: list) -> tuple[list[FundReportLine], FundsSummary]:
    """One FundReportLine per fund in the month + the on-track/behind summary.

    The statuses come from the same walk that produced the closing line, so a
    fund is folded forward once per report and not twice.

    The month's record is unchanged by whatever set money aside for it: a
    charge a fund saved for shows under its category like any other (AC-12).
    """
    lines = sorted(
        (
            FundReportLine(
                category_name=status.name,
                asks=status.asks,
                holds=status.holds,
                spent=agg.spent_in(status.category_id, agg.year_month),
                on_track=status.on_track,
            )
            for status in statuses
        ),
        key=lambda f: f.category_name,
    )
    n_on_track = sum(1 for f in lines if f.on_track)
    return lines, FundsSummary(
        n_on_track=n_on_track,
        n_behind=len(lines) - n_on_track,
        set_aside=sum(f.holds for f in lines),
    )


def _meta_lines(statuses: list) -> list[MetaReportLine]:
    """One MetaReportLine per meta the month reports, by name (AC-36).

    The metas come from the same walk that produced the closing line, so a meta
    is folded forward once per report and not twice.
    """
    return sorted(
        (
            MetaReportLine(
                meta_name=status.name,
                currency=status.currency,
                asks=status.asks,
                holds=status.holds,
            )
            for status in statuses
        ),
        key=lambda m: m.meta_name,
    )


def _balance_lines(session: Session) -> list[AccountBalance]:
    """Balance per non-archived account (account's own currency), sorted by name."""
    accs = _accounts.list_accounts(session, include_archived=False)
    return [
        AccountBalance(account=a.name, currency=a.currency, balance=a.balance)
        for a in sorted(accs, key=lambda a: a.name)
    ]


def _pending_lines(session: Session, start: Date, end: Date, trm: Decimal) -> list[str]:
    """Alert lines for unconfirmed (planned) entries in the month, grouped by account.

    Retrospective view: pass `retrospective=True` so the
    report for 2026-07 doesn't show items overdue from June. The
    retrospective only counts what was planned IN this month.
    `today=start - 1 day` anchors the upcoming bucket's lower bound
    to the start of the month so the full month is in scope regardless
    of when the report is generated.
    """
    queue = _planned.to_pay(
        session,
        start,
        end,
        retrospective=True,
        today=start - timedelta(days=1),
    )
    by_account: dict[int, int] = {}
    for tx in queue.upcoming:
        by_account[tx.account_id] = by_account.get(tx.account_id, 0) + to_cop_cents(tx.amount, tx.currency, trm)
    rows: list[tuple[str, int]] = []
    for account_id, total in by_account.items():
        acc = session.get(Account, account_id)
        name = acc.name if acc is not None else f"account {account_id}"
        rows.append((name, total))
    rows.sort(key=lambda r: r[0])
    return [f"{name}: {money(total)} pending" for name, total in rows]


def monthly_report(session: Session, month: str, *, today: Date | None = None) -> MonthlyReport:
    """Build the retrospective monthly report (data + markdown) for "YYYY-MM".

    Posted-only aggregates in COP cents, converted at read time from ONE
    TRM fetch; reuses P3 for pending and feature 003's fund read path for both
    the fund lines and the closing line. `today` is accepted and unused on
    purpose — the goal ETAs that needed a clock are gone, and every figure now
    comes from the month asked about.

    Raises:
        ValidationError: malformed month.
        MissingRate: no TRM set (005 AC-9 — even for all-COP data).
    """
    require_year_month(month, "month")
    agg = load_month(session, month)
    trm = agg.trm
    start, end = agg.start, agg.end

    expenses = agg.month_expense()
    income, expense, net = agg.totals_for(month)
    available: MonthAvailable = month_service.month_available(agg)
    funds, funds_summary = _fund_lines(agg, available.funds)
    report = MonthlyReport(
        month=month,
        income=income,
        expense=expense,
        net=net,
        funds_summary=funds_summary,
        funds=funds,
        metas=_meta_lines(available.metas),
        asked=sum(f.asks for f in funds) + metas_service.asks_total(agg) + metas_service.cancelled_asks_total(agg),
        by_category=_category_sections(agg, expenses, expense),
        by_group=_group_sections(agg, expenses, expense),
        balances=_balance_lines(session),
        drift_mom=_drift(agg, income, expense, net),
        usd_share=_usd_share(agg, expenses, expense),
        pending=_pending_lines(session, start, end, trm),
        available=available,
        markdown="",
    )
    report.markdown = render_markdown(report)
    return report
