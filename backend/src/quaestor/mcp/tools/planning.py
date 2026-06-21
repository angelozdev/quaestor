"""MCP planning tools (P4): budgets envelope assign and goals management.

Mirrors temporal.py: parse input, resolve names, call ONE service, format output.
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from sqlmodel import Session

from ...services import budgets
from .. import format
from .core import _as_text, _resolve_category


class AssignBudgetInput(BaseModel):
    category: str = Field(description="Category name to assign an envelope to")
    year_month: str = Field(description="Target month, YYYY-MM")
    amount: int = Field(ge=0, description="Amount to assign in cents (0 unassigns)")


@_as_text
def assign_budget(session: Session, inp: AssignBudgetInput) -> str:
    category = _resolve_category(session, inp.category)
    budgets.set_budget(session, category.id, inp.year_month, inp.amount)
    status = budgets.budget_status(session, category.id, inp.year_month)
    return format.budget_assigned(status, category.name)
