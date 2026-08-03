"""Rollover REST router — internal admin/debug trigger for close_month.

The scheduler (P7) is the real driver (ADR-017); this endpoint exists for
manual/debug closes. It stays behind require_auth like the other routers.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ...services import rollover
from ..deps import get_session
from ..schemas import CloseMonthIn

router = APIRouter(prefix="/rollover", tags=["rollover"])


@router.post("")
def close_month(body: CloseMonthIn, session: Session = Depends(get_session)):
    rollover.close_month(session, body.period)
    return {"ok": True, "period": body.period}
