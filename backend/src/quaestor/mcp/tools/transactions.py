"""MCP transaction write tools (ADR-0009): get/update/delete by id.

Reads (list_transactions, list_transactions-filtered) live in `core.py`.
Writes to fields beyond payee/notes/category_id/date are not allowed — those
are immutable in the service layer (P0 invariant: balances only move via
record_expense / record_income / transfer).
"""
from __future__ import annotations

from datetime import date as Date

from pydantic import BaseModel, Field
from sqlmodel import Session

from ...services import transactions
from .. import format
from .core import _as_text, _resolve_category


class GetTransactionInput(BaseModel):
    tx_id: int = Field(description="Transaction id")


class UpdateTransactionInput(BaseModel):
    tx_id: int = Field(description="Transaction id")
    payee: str | None = Field(default=None, description="New payee")
    notes: str | None = Field(default=None, description="New notes")
    clear_notes: bool = Field(default=False, description="Set notes to None")
    category: str | None = Field(default=None, description="New category name (empty string clears)")
    date: Date | None = Field(default=None, description="New date")


class DeleteTransactionInput(BaseModel):
    tx_id: int = Field(description="Transaction id")


@_as_text
def get_transaction(session: Session, inp: GetTransactionInput) -> str:
    tx = transactions.get_transaction(session, inp.tx_id)
    return format.transaction_card(tx)


@_as_text
def update_transaction(session: Session, inp: UpdateTransactionInput) -> str:
    notes = None if inp.clear_notes else inp.notes
    category_id = transactions._UNSET
    if inp.category is not None:
        category_id = (
            None if inp.category == "" else _resolve_category(session, inp.category).id
        )
    updated = transactions.update_transaction(
        session,
        inp.tx_id,
        payee=inp.payee,
        notes=notes,
        category_id=category_id,
        date=inp.date,
    )
    return format.transaction_card(updated)


@_as_text
def delete_transaction(session: Session, inp: DeleteTransactionInput) -> str:
    tx = transactions.get_transaction(session, inp.tx_id)
    payee = tx.payee
    transactions.delete_transaction(session, inp.tx_id)
    return f"Deleted transaction '{payee}' (id {inp.tx_id})."