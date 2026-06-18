"""Transactions REST router — thin adapter over services.transactions."""
from __future__ import annotations

from datetime import date as Date

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ...domain.errors import ValidationError
from ...domain.models import TxType
from ...services import transactions
from ..deps import get_session
from ..schemas import (
    TransactionCreate,
    TransactionOut,
    TransactionUpdate,
    TransferIn,
    TransferOut,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    date_from: Date | None = None,
    date_to: Date | None = None,
    account_id: int | None = None,
    category_id: int | None = None,
    tag: str | None = None,
    type: TxType | None = None,
    status: str | None = None,
    session: Session = Depends(get_session),
):
    return transactions.list_transactions(
        session,
        account_id=account_id,
        category_id=category_id,
        tag=tag,
        type=type,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/{tx_id}", response_model=TransactionOut)
def get_transaction(tx_id: int, session: Session = Depends(get_session)):
    return transactions.get_transaction(session, tx_id)


@router.post("", response_model=TransactionOut, status_code=201)
def create_transaction(body: TransactionCreate, session: Session = Depends(get_session)):
    if body.type == TxType.transfer:
        raise ValidationError("use POST /transactions/transfer for transfers")
    fn = transactions.record_expense if body.type == TxType.expense else transactions.record_income
    return fn(
        session,
        account_id=body.account_id,
        amount=body.amount,
        currency=body.currency,
        date=body.date,
        payee=body.payee,
        category_id=body.category_id,
        notes=body.notes,
        source=body.source,
        fx_rate=body.fx_rate,
    )


@router.post("/transfer", response_model=TransferOut, status_code=201)
def create_transfer(body: TransferIn, session: Session = Depends(get_session)):
    leg_from, leg_to = transactions.transfer(
        session,
        from_account_id=body.from_account_id,
        to_account_id=body.to_account_id,
        amount=body.amount,
        currency=body.currency,
        date=body.date,
        notes=body.notes,
        source=body.source,
        fx_rate=body.fx_rate,
    )
    return TransferOut(from_leg=leg_from, to_leg=leg_to)


@router.patch("/{tx_id}", response_model=TransactionOut)
def update_transaction(
    tx_id: int, body: TransactionUpdate, session: Session = Depends(get_session)
):
    fields = body.model_dump(exclude_unset=True)
    return transactions.update_transaction(session, tx_id, **fields)


@router.delete("/{tx_id}", status_code=204)
def delete_transaction(tx_id: int, session: Session = Depends(get_session)):
    transactions.delete_transaction(session, tx_id)
    return None
