"""P5 contract dataclasses for the monthly report and the CSV importer.

These are the stable types P1 (endpoints), P2 (MCP tools), and P6 (screens) wire
against. SafeToSpend is reused from P4 (domain.dtos) — single source of truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .dtos import SafeToSpend  # re-exported on purpose

__all__ = [
    "SafeToSpend",
    "EnvelopesSummary",
    "EnvelopeLine",
    "CategorySection",
    "GroupSection",
    "GoalLine",
    "AccountBalance",
    "DriftMoM",
    "MonthlyReport",
]


@dataclass(frozen=True)
class EnvelopesSummary:
    n_green: int  # envelopes with status "under"
    n_red: int  # envelopes with status "over"
    rollover_generated: int  # Σ max(available, 0), COP cents — rolls into next month


@dataclass(frozen=True)
class EnvelopeLine:
    category: str
    allocated: int  # assigned, COP cents
    rollover_in: int  # COP cents
    spent: int  # COP cents
    available: int  # COP cents
    status: str  # "over" | "under"


@dataclass(frozen=True)
class CategorySection:
    category: str
    group: str | None
    total: int  # COP cents
    pct: float  # percentage of total expense, [0, 100]


@dataclass(frozen=True)
class GroupSection:
    group: str
    total: int  # COP cents
    pct: float  # percentage of total expense, [0, 100]


@dataclass(frozen=True)
class GoalLine:
    name: str
    accumulated: int  # saved, COP cents
    target: int | None = None  # COP cents; None => open-ended
    eta: date | None = None  # only on defined goals
    on_track: bool | None = None  # only on defined goals


@dataclass(frozen=True)
class AccountBalance:
    account: str
    currency: str
    balance: int  # cents, in the account's own currency


@dataclass(frozen=True)
class DriftMoM:
    prev_month: str
    income_abs: int  # current - previous, COP cents
    income_pct: float | None  # None when previous == 0
    expense_abs: int
    expense_pct: float | None
    net_abs: int
    net_pct: float | None


@dataclass
class MonthlyReport:  # not frozen: markdown is filled in after the data is built
    month: str
    income: int  # COP cents, posted only
    expense: int
    net: int  # income - expense
    envelopes_summary: EnvelopesSummary
    envelopes: list[EnvelopeLine]
    by_category: list[CategorySection]
    by_group: list[GroupSection]
    goals: list[GoalLine]
    balances: list[AccountBalance]
    drift_mom: DriftMoM | None  # None on cold start (no previous-month activity)
    usd_share: float  # fraction of expense originated in USD, [0, 1]
    pending: list[str]  # alert lines: unconfirmed manual entries
    safe_to_spend: SafeToSpend  # closing line, not headline (ADR-019)
    markdown: str
