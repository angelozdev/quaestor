"""Budgets REST router — thin adapter over services.budgets."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ...services import budgets
from ..deps import get_session
from ..schemas import SafeToSpendOut

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("/safe-to-spend", response_model=SafeToSpendOut)
def safe_to_spend(month: str, session: Session = Depends(get_session)):
    return budgets.safe_to_spend(session, month)
