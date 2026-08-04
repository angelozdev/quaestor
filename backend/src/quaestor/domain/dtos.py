"""Output DTOs returned by the fund and recurring services (not DB models)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import RecurringOccurrence


@dataclass(frozen=True)
class FundLine:
    """One fund, as the screen and the assistant list it."""

    fund_id: int
    category_id: int
    name: str
    rule: str
    start_month: str
    accumulates: bool


@dataclass(frozen=True)
class FundStatus:
    """What one fund asks, holds and reports for one month (ADR-0043).

    `averaged_over` is filled by the `average` rule only; `spreads_over` and
    `whole_by` by the rules that save toward a dated charge.
    """

    fund_id: int
    category_id: int
    name: str
    year_month: str
    rule: str
    asks: int
    holds: int
    accumulates: bool
    accumulation_is_implied: bool
    on_track: bool
    averaged_over: int | None = None
    spreads_over: int | None = None
    whole_by: str | None = None


@dataclass(frozen=True)
class MonthAvailable:
    """The money available for one month, opened into the terms that make it.

    `income − Σ funds asks − uncovered = free` holds exactly, which is why
    `uncovered` is one term and not three (AC-10, ADR-0044).
    """

    year_month: str
    income: int
    funds: list[FundStatus]
    uncovered: int
    free: int


@dataclass(frozen=True)
class MonthRates:
    """What the owner earns and what the owner costs, each a month's worth.

    Rates are smoothed across a cycle and are never the money available: a
    quarterly income counts every month here and only in the month it is due
    there (AC-14b).
    """

    year_month: str
    earning: int
    cost: int
    margin: int


@dataclass(frozen=True)
class FundPreview:
    """What a fund would ask before it exists, and the warning it carries (AC-24)."""

    category_id: int
    would_ask: int
    warning: str | None = None


@dataclass(frozen=True)
class RunFailure:
    """One obligation the engine could not charge, and why (ADR-0036)."""

    recurring_id: int
    name: str
    reason: str

    def __str__(self) -> str:
        return f"{self.name}: {self.reason}"


@dataclass(frozen=True)
class MaterializationReport:
    """The outcome of one engine run: what landed, and what needs attention.

    A run is no longer all-or-nothing — each charge commits on its own, so a
    failure costs its obligation the day and nothing else (ADR-0036).
    """

    created: list[RecurringOccurrence]
    failures: list[RunFailure]
