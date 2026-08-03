"""MCP report tools (ADR-0009): monthly_report.

The full markdown body comes from `services.reports.monthly_report`; the tool
wrapper adds a compact headline (income/expense/net) so the agent gets the
summary without parsing the long-form body.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from sqlmodel import Session

from ...services import reports
from .. import format
from .core import _as_text, _validate_month


class MonthlyReportInput(BaseModel):
    month: str = Field(description="YYYY-MM")


@_as_text
def monthly_report(session: Session, inp: MonthlyReportInput) -> str:
    _validate_month(inp.month)
    report = reports.monthly_report(session, inp.month)
    return format.monthly_report_card(report)
