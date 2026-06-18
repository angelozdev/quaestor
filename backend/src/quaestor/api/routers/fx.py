"""FX REST router — thin adapter over services.fx."""
from __future__ import annotations

from datetime import date as Date

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ...services import fx
from ..deps import get_session
from ..schemas import FxIn, FxOut

router = APIRouter(prefix="/fx", tags=["fx"])


@router.get("", response_model=FxOut)
def get_rate(date: Date | None = None, session: Session = Depends(get_session)):
    target = date or Date.today()
    rate = fx.get_current_rate(session, target)  # raises MissingRate -> 409
    return FxOut(date=target, usd_cop=rate)


@router.post("", response_model=FxOut, status_code=201)
def set_rate(body: FxIn, session: Session = Depends(get_session)):
    row = fx.set_fx_rate(session, body.date, body.usd_cop)
    return FxOut(date=row.date, usd_cop=row.usd_cop)
