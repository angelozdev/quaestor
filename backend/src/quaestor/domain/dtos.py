"""Output DTOs returned by budget/goal/recurring services (not DB models)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import RecurringOccurrence


@dataclass(frozen=True)
class BudgetStatus:
    category_id: int
    year_month: str
    assigned: int
    rollover_in: int
    spent: int
    available: int
    pct_used: int
    status: str  # "over" | "under"


@dataclass(frozen=True)
class BudgetLine:
    category_id: int
    category_name: str
    assigned: int
    rollover_in: int
    spent: int
    available: int
    pct_used: int
    status: str  # "over" | "under"


@dataclass(frozen=True)
class CommittedItem:
    kind: str  # "recurring" | "planned"
    name: str
    date: date
    amount: int  # COP cents


@dataclass(frozen=True)
class SafeToSpend:
    year_month: str
    income_forecast: int
    committed: int
    assigned_envelopes: int
    free: int
    committed_breakdown: list  # list[CommittedItem]


@dataclass(frozen=True)
class GoalProgress:
    goal_id: int
    name: str
    type: str  # "defined" | "open-ended"
    monthly_amount: int
    saved: int
    target_amount: int | None = None
    deadline: date | None = None
    monthly_required: int | None = None
    on_track: bool | None = None
    eta: date | None = None
    remaining: int | None = None


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
