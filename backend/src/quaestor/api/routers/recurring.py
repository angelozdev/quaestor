"""Recurring REST router — thin adapter over services.recurring."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ...services import recurring
from ..deps import get_session
from ..schemas import OccurrenceOut, RecurringCreate, RecurringOut, SkipRecurringIn

router = APIRouter(prefix="/recurring", tags=["recurring"])


@router.get("", response_model=list[RecurringOut])
def list_recurring(active: bool | None = None, session: Session = Depends(get_session)):
    return recurring.list_recurring(session, active=active)


@router.post("", response_model=RecurringOut, status_code=201)
def create_recurring(body: RecurringCreate, session: Session = Depends(get_session)):
    return recurring.create_recurring(
        session,
        name=body.name,
        payee=body.payee,
        type=body.type,
        mode=body.mode,
        amount=body.amount,
        currency=body.currency,
        category_id=body.category_id,
        account_id=body.account_id,
        interval_unit=body.interval_unit,
        interval_count=body.interval_count,
        start_date=body.start_date,
        end_date=body.end_date,
    )


@router.post("/{recurring_id}/skip", response_model=OccurrenceOut)
def skip_recurring(
    recurring_id: int, body: SkipRecurringIn, session: Session = Depends(get_session)
):
    return recurring.skip_recurring(session, recurring_id, body.due_date)
