"""Reports REST router — thin adapter over services.reports."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ...services import reports
from ..deps import get_session
from ..schemas import MonthlyReportOut

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=MonthlyReportOut)
def monthly_report(month: str, session: Session = Depends(get_session)):
    return reports.monthly_report(session, month)
