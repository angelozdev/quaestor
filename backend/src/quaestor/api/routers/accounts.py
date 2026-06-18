"""Accounts REST router — thin adapter over services.accounts."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ...services import accounts
from ..deps import get_session
from ..schemas import AccountCreate, AccountOut, AccountUpdate

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountOut])
def list_accounts(archived: bool = False, session: Session = Depends(get_session)):
    return accounts.list_accounts(session, include_archived=archived)


@router.get("/{account_id}", response_model=AccountOut)
def get_account(account_id: int, session: Session = Depends(get_session)):
    return accounts.get_account(session, account_id)


@router.post("", response_model=AccountOut, status_code=201)
def create_account(body: AccountCreate, session: Session = Depends(get_session)):
    return accounts.create_account(
        session, name=body.name, type=body.type, currency=body.currency, balance=body.balance
    )


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(
    account_id: int, body: AccountUpdate, session: Session = Depends(get_session)
):
    return accounts.update_account(session, account_id, name=body.name, type=body.type)


@router.delete("/{account_id}", status_code=204)
def archive_account(account_id: int, session: Session = Depends(get_session)):
    accounts.archive_account(session, account_id)
    return None
