"""P5 contract dataclasses for the monthly report and the CSV importer.

These are the stable types P1 (endpoints), P2 (MCP tools), and P6 (screens) wire
against. MonthAvailable is reused from the fund service's DTOs — single source
of truth for the closing line.
"""

from __future__ import annotations

from dataclasses import dataclass

from .dtos import MonthAvailable  # re-exported on purpose

__all__ = [
    "AccountBalance",
    "CategorySection",
    "DriftMoM",
    "FundReportLine",
    "FundsSummary",
    "GroupSection",
    "MonthAvailable",
    "MonthlyReport",
]


@dataclass(frozen=True)
class FundsSummary:
    n_on_track: int  # funds the month's spending did not push behind
    n_behind: int  # funds asking more than the month opened needing
    set_aside: int  # Σ what the funds hold, COP cents


@dataclass(frozen=True)
class FundReportLine:
    """One fund inside the month's report (ADR-0043).

    `category_name` and `spent` carry the same names the envelope line used, so
    a reader of the report keeps asking what a category spent in the month
    regardless of what set money aside for it.
    """

    category_name: str
    asks: int  # COP cents
    holds: int  # COP cents
    spent: int  # COP cents
    on_track: bool


@dataclass(frozen=True)
class MetaReportLine:
    """One meta inside the month's report (AC-36).

    Listed by meta and never folded into a category: a meta belongs to none
    until its purchase names one. The figures are in the meta's own currency,
    the way every other figure it reports is (AC-26); only the month's combined
    total is in pesos.
    """

    meta_name: str
    currency: str
    asks: int  # cents, in the meta's own currency
    holds: int  # cents, in the meta's own currency


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
    funds_summary: FundsSummary
    funds: list[FundReportLine]
    metas: list[MetaReportLine]
    asked: int  # Σ what the funds and the metas ask, COP cents (AC-36)
    by_category: list[CategorySection]
    by_group: list[GroupSection]
    balances: list[AccountBalance]
    drift_mom: DriftMoM | None  # None on cold start (no previous-month activity)
    usd_share: float  # fraction of expense originated in USD, [0, 1]
    pending: list[str]  # alert lines: unconfirmed manual entries
    available: MonthAvailable  # closing line, not headline (ADR-019)
    markdown: str
