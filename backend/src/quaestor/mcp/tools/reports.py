"""MCP report tools (ADR-0009): monthly_report.

The full markdown body comes from `services.reports.monthly_report`; the tool
wrapper adds a compact headline (income/expense/net) so the agent gets the
summary without parsing the long-form body.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field
from sqlmodel import Session

from ...domain.errors import ValidationError
from ...services import reports
from .. import format
from .core import _as_text


_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class MonthlyReportInput(BaseModel):
    month: str = Field(description="YYYY-MM")


def _validate_month(month: str) -> None:
    if not _MONTH_RE.match(month):
        raise ValidationError(f"malformed month (expected YYYY-MM): {month!r}")


@_as_text
def monthly_report(session: Session, inp: MonthlyReportInput) -> str:
    _validate_month(inp.month)
    report = reports.monthly_report(session, inp.month)
    return format.monthly_report_card(report)
