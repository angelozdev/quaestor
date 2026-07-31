"""Transactions REST router — thin adapter over services.transactions.

Reads compute `cop_equivalent` at the current TRM and fail loud (409)
when it is unset (AC-9); writes succeed without a TRM (AC-1) and omit
the equivalent.
"""
from __future__ import annotations

from datetime import date as Date

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ...domain.errors import ValidationError
from ...domain.models import TxType
from ...domain.sort import Order, SortField
from ...services import fx, transactions
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
    sort: SortField = "date",
    order: Order = "desc",
    session: Session = Depends(get_session),
):
    trm = fx.get_trm(session)
    txs = transactions.list_transactions(
        session,
        account_id=account_id,
        category_id=category_id,
        tag=tag,
        type=type,
        status=status,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        order=order,
    )
    return [TransactionOut.from_tx(tx, trm) for tx in txs]


@router.get("/{tx_id}", response_model=TransactionOut)
def get_transaction(tx_id: int, session: Session = Depends(get_session)):
    trm = fx.get_trm(session)
    return TransactionOut.from_tx(transactions.get_transaction(session, tx_id), trm)


@router.post("", response_model=TransactionOut, status_code=201)
def create_transaction(body: TransactionCreate, session: Session = Depends(get_session)):
    if body.type == TxType.transfer:
        raise ValidationError("use POST /transactions/transfer for transfers")
    fn = transactions.record_expense if body.type == TxType.expense else transactions.record_income
    tx = fn(
        session,
        account_id=body.account_id,
        amount=body.amount,
        currency=body.currency,
        date=body.date,
        payee=body.payee,
        category_id=body.category_id,
        notes=body.notes,
        source=body.source,
    )
    return TransactionOut.from_tx(tx, fx.get_trm_or_none(session))


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
        amount_received=body.amount_received,
    )
    trm = fx.get_trm_or_none(session)
    return TransferOut(
        from_leg=TransactionOut.from_tx(leg_from, trm),
        to_leg=TransactionOut.from_tx(leg_to, trm),
    )


@router.patch("/{tx_id}", response_model=TransactionOut)
def update_transaction(
    tx_id: int, body: TransactionUpdate, session: Session = Depends(get_session)
):
    fields = body.model_dump(exclude_unset=True)
    tx = transactions.update_transaction(session, tx_id, **fields)
    return TransactionOut.from_tx(tx, fx.get_trm_or_none(session))


@router.delete("/{tx_id}", status_code=204)
def delete_transaction(tx_id: int, session: Session = Depends(get_session)):
    transactions.delete_transaction(session, tx_id)
    return None
