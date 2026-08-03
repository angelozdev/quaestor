"""Recurring REST router — thin adapter over services.recurring/occurrences."""
from __future__ import annotations

from datetime import date as Date

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ...services import occurrences, recurring
from ..deps import get_session
from ..schemas import (
    OccurrenceOut,
    PendingDatesIn,
    RecurringCreate,
    RecurringOut,
    RecurringUpdate,
    SkipRecurringIn,
)

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


@router.patch("/{recurring_id}", response_model=RecurringOut)
def update_recurring(
    recurring_id: int, body: RecurringUpdate, session: Session = Depends(get_session)
):
    fields = body.model_dump(exclude_unset=True)
    return recurring.update_recurring(session, recurring_id, **fields)


@router.delete("/{recurring_id}", status_code=204)
def deactivate_recurring(recurring_id: int, session: Session = Depends(get_session)):
    recurring.deactivate_recurring(session, recurring_id)
    return


@router.post("/{recurring_id}/restore", response_model=RecurringOut)
def restore_recurring(recurring_id: int, session: Session = Depends(get_session)):
    return recurring.restore_recurring(session, recurring_id)


@router.post("/{recurring_id}/skip", response_model=OccurrenceOut)
def skip_recurring(
    recurring_id: int, body: SkipRecurringIn, session: Session = Depends(get_session)
):
    return recurring.skip_recurring(session, recurring_id, body.due_date)


@router.get("/{recurring_id}/pending-dates", response_model=list[Date])
def pending_dates(recurring_id: int, session: Session = Depends(get_session)):
    return occurrences.pending_dates(session, recurring_id)


@router.post("/{recurring_id}/pending-dates/accept", response_model=list[OccurrenceOut])
def accept_pending_dates(
    recurring_id: int, body: PendingDatesIn, session: Session = Depends(get_session)
):
    return occurrences.accept_pending_dates(session, recurring_id, body.due_dates)


@router.post("/{recurring_id}/pending-dates/decline", response_model=list[OccurrenceOut])
def decline_pending_dates(
    recurring_id: int, body: PendingDatesIn, session: Session = Depends(get_session)
):
    return occurrences.decline_pending_dates(session, recurring_id, body.due_dates)
