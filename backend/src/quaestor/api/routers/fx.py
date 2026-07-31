"""FX REST router — thin adapter over services.fx (scalar TRM, ADR-0031)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ...services import fx
from ..deps import get_session
from ..schemas import FxIn, FxOut

router = APIRouter(prefix="/fx", tags=["fx"])


@router.get("", response_model=FxOut)
def get_rate(session: Session = Depends(get_session)):
    return FxOut(usd_cop=fx.get_trm(session))


@router.post("", response_model=FxOut, status_code=201)
def set_rate(body: FxIn, session: Session = Depends(get_session)):
    return FxOut(usd_cop=fx.set_trm(session, body.usd_cop))
