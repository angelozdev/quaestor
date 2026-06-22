"""MCP budget read tools (ADR-0009): list_budgets, safe_to_spend.

Writes (`assign_budget`) live in `planning.py`.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field
from sqlmodel import Session

from ...domain.errors import ValidationError
from ...services import budgets
from .. import format
from .core import _as_text


_YEAR_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class _MonthField(BaseModel):
    month: str = Field(description="YYYY-MM")


class ListBudgetsInput(_MonthField):
    pass


class SafeToSpendInput(_MonthField):
    pass


def _validate_month(month: str) -> None:
    if not _YEAR_MONTH_RE.match(month):
        raise ValidationError(f"malformed year_month (expected YYYY-MM): {month!r}")


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
