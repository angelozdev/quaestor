"""MCP budget read tools (ADR-0009): list_budgets, safe_to_spend.

Writes (`assign_budget`) live in `planning.py`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from sqlmodel import Session

from ...services import budgets
from .. import format
from .core import _as_text, _validate_month


class _MonthField(BaseModel):
    month: str = Field(description="YYYY-MM")


class ListBudgetsInput(_MonthField):
    pass


class SafeToSpendInput(_MonthField):
    pass


@_as_text
def list_budgets(session: Session, inp: ListBudgetsInput) -> str:
    _validate_month(inp.month)
    lines = budgets.list_budgets(session, inp.month)
    return format.budgets_table(lines)


@_as_text
def safe_to_spend(session: Session, inp: SafeToSpendInput) -> str:
    _validate_month(inp.month)
    sts = budgets.safe_to_spend(session, inp.month)
    return format.safe_to_spend_card(sts)
