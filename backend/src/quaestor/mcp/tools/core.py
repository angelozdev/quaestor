"""MCP core tools: parse input, resolve names, call ONE service, format output.

No domain logic lives here. Each public impl is wrapped by ``_as_text``, so a
typed domain error becomes agent text instead of an exception. Impls take a
``Session`` (one per request, opened by the registry wrapper) plus a validated
Pydantic input model.
"""
from __future__ import annotations

import functools
from datetime import date as Date
from typing import Literal

from pydantic import BaseModel, Field
from sqlmodel import Session

from ...domain.errors import NotFound, QuaestorError
from ...domain.models import Account, Category
from ...services import accounts, categories, fx, tags, transactions
from .. import format


# ----- input models (one per tool; the SDK publishes their JSON Schema) -----


class RecordExpenseInput(BaseModel):
    payee: str = Field(description="Merchant or payee, e.g. 'Supermarket'")
    amount: int = Field(
        gt=0, description="Amount in cents, original currency (40000 COP = 4000000)"
    )
    account: str = Field(description="Account name, e.g. 'Bancolombia'")
    currency: str = Field(default="COP", description="ISO currency code; defaults to COP")
    category: str | None = Field(default=None, description="Category name (optional)")
    date: Date | None = Field(default=None, description="Date YYYY-MM-DD; defaults to today")
    tags: list[str] = Field(default_factory=list, description="Tag names")
    notes: str | None = Field(default=None, description="Free-form notes (optional)")


class RecordIncomeInput(BaseModel):
    payee: str = Field(description="Income source, e.g. 'Salary'")
    amount: int = Field(gt=0, description="Amount in cents, original currency")
    account: str = Field(description="Destination account name")
    currency: str = Field(default="COP", description="ISO currency code; defaults to COP")
    category: str | None = Field(default=None, description="Category name (optional)")
    date: Date | None = Field(default=None, description="Date YYYY-MM-DD; defaults to today")
    tags: list[str] = Field(default_factory=list, description="Tag names")
    notes: str | None = Field(default=None, description="Free-form notes (optional)")


class TransferInput(BaseModel):
    from_account: str = Field(description="Source account name")
    to_account: str = Field(description="Destination account name")
    amount: int = Field(gt=0, description="Amount in cents")
    currency: str = Field(default="COP", description="Currency; must match both accounts")
    date: Date | None = Field(default=None, description="Date YYYY-MM-DD; defaults to today")
    notes: str | None = Field(default=None, description="Free-form notes (optional)")


class SetFxRateInput(BaseModel):
    date: Date = Field(description="Rate date, YYYY-MM-DD")
    usd_cop: float = Field(gt=0, description="Pesos per dollar, e.g. 4150")


class GetFxRateInput(BaseModel):
    date: Date | None = Field(default=None, description="Date YYYY-MM-DD; defaults to today")


class ListTransactionsInput(BaseModel):
    date_from: Date | None = Field(default=None, description="Include from this date")
    date_to: Date | None = Field(default=None, description="Include up to this date")
    account: str | None = Field(default=None, description="Filter by account name")
    category: str | None = Field(default=None, description="Filter by category name")
    tag: str | None = Field(default=None, description="Filter by tag name")
    type: Literal["expense", "income", "transfer"] | None = Field(
        default=None, description="Transaction type"
    )
    status: Literal["posted", "planned"] | None = Field(
        default=None, description="Transaction status"
    )


# ----- error-to-text wrapper -----


def _as_text(fn):
    """Wrap an impl so typed domain errors become agent text, not exceptions."""

    @functools.wraps(fn)
    def wrapper(session: Session, *args):
        try:
            return fn(session, *args)
        except QuaestorError as exc:
            return format.domain_error_text(exc)

    return wrapper


# ----- name resolution (agent speaks names; services speak ids) -----


def _resolve_account(session: Session, name: str) -> Account:
    all_accounts = accounts.list_accounts(session)
    target = name.strip().lower()
    for account in all_accounts:
        if account.name.lower() == target:
            return account
    available = ", ".join(a.name for a in all_accounts) or "(none)"
    raise NotFound(f"Account '{name}' not found. Available: {available}.")


def _resolve_category(session: Session, name: str) -> Category:
    target = name.strip().lower()
    for category in categories.list_categories(session):
        if category.name.lower() == target:
            return category
    raise NotFound(
        f"Category '{name}' not found. You can create it or record without a category."
    )


# ----- write tools -----


@_as_text
def record_expense(session: Session, inp: RecordExpenseInput) -> str:
    account = _resolve_account(session, inp.account)
    category = _resolve_category(session, inp.category) if inp.category else None
    tx = transactions.record_expense(
        session,
        account_id=account.id,
        amount=inp.amount,
        currency=inp.currency,
        date=inp.date or Date.today(),
        payee=inp.payee,
        category_id=category.id if category else None,
        notes=inp.notes,
        source="agent",
    )
    if inp.tags:
        tags.tag_transaction(session, tx.id, inp.tags)
    account = accounts.get_account(session, account.id)
    return format.expense_confirmation(tx, account)


@_as_text
def record_income(session: Session, inp: RecordIncomeInput) -> str:
    account = _resolve_account(session, inp.account)
    category = _resolve_category(session, inp.category) if inp.category else None
    tx = transactions.record_income(
        session,
        account_id=account.id,
        amount=inp.amount,
        currency=inp.currency,
        date=inp.date or Date.today(),
        payee=inp.payee,
        category_id=category.id if category else None,
        notes=inp.notes,
        source="agent",
    )
    if inp.tags:
        tags.tag_transaction(session, tx.id, inp.tags)
    account = accounts.get_account(session, account.id)
    return format.income_confirmation(tx, account)


@_as_text
def transfer(session: Session, inp: TransferInput) -> str:
    src = _resolve_account(session, inp.from_account)
    dst = _resolve_account(session, inp.to_account)
    transactions.transfer(
        session,
        from_account_id=src.id,
        to_account_id=dst.id,
        amount=inp.amount,
        currency=inp.currency,
        date=inp.date or Date.today(),
        notes=inp.notes,
        source="agent",
    )
    src = accounts.get_account(session, src.id)
    dst = accounts.get_account(session, dst.id)
    return format.transfer_confirmation(src, dst, inp.amount, inp.currency)


@_as_text
def set_fx_rate(session: Session, inp: SetFxRateInput) -> str:
    fr = fx.set_fx_rate(session, inp.date, inp.usd_cop)
    return format.fx_set(fr)


# ----- read tools -----


@_as_text
def list_transactions(session: Session, inp: ListTransactionsInput) -> str:
    account_id = _resolve_account(session, inp.account).id if inp.account else None
    category_id = (
        _resolve_category(session, inp.category).id if inp.category else None
    )
    txs = transactions.list_transactions(
        session,
        account_id=account_id,
        category_id=category_id,
        tag=inp.tag,
        type=inp.type,
        status=inp.status,
        date_from=inp.date_from,
        date_to=inp.date_to,
    )
    return format.transactions_table(txs)


@_as_text
def get_fx_rate(session: Session, inp: GetFxRateInput) -> str:
    on = inp.date or Date.today()
    rate = fx.get_current_rate(session, on)  # raises MissingRate if absent
    return format.fx_current(rate, on)


@_as_text
def list_accounts(session: Session) -> str:
    return format.accounts_table(accounts.list_accounts(session))


@_as_text
def list_categories(session: Session) -> str:
    return format.categories_table(
        categories.list_categories(session), categories.list_groups(session)
    )


@_as_text
def list_tags(session: Session) -> str:
    return format.tags_list(tags.list_tags(session))
