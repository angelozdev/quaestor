"""Planned-payments REST router — thin adapter over services.planned."""
from __future__ import annotations

from datetime import date as Date

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ...services import planned
from ..deps import get_session
from ..schemas import ConfirmPaymentIn, PlanPaymentIn, ToPayOut, TransactionOut

router = APIRouter(prefix="/planned", tags=["planned"])


@router.get("/to-pay", response_model=ToPayOut)
def to_pay(since: Date, until: Date, session: Session = Depends(get_session)):
    return planned.to_pay(session, since, until)


@router.post("", response_model=TransactionOut, status_code=201)
def plan_payment(body: PlanPaymentIn, session: Session = Depends(get_session)):
    return planned.plan_payment(
        session,
        payee=body.payee,
        amount=body.amount,
        currency=body.currency,
        due_date=body.due_date,
        account_id=body.account_id,
        category_id=body.category_id,
        notes=body.notes,
    )


@router.post("/{tx_id}/confirm", response_model=TransactionOut)
def confirm_payment(
    tx_id: int, body: ConfirmPaymentIn, session: Session = Depends(get_session)
):
    return planned.confirm_payment(session, tx_id, amount=body.amount, date=body.date)


@router.post("/{tx_id}/skip", response_model=TransactionOut)
def skip_payment(tx_id: int, session: Session = Depends(get_session)):
    return planned.skip_payment(session, tx_id)
