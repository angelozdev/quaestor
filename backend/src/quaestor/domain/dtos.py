"""Output DTOs returned by budget/goal services (not DB models)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


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
