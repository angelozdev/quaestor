"""MCP core tools: parse input, resolve names, call ONE service, format output.

No domain logic lives here. Each public impl is wrapped by ``_as_text``, so a
typed domain error becomes agent text instead of an exception. Impls take a
``Session`` (one per request, opened by the registry wrapper) plus a validated
Pydantic input model.
"""

from __future__ import annotations

import functools
import re
from datetime import date as Date
from typing import Literal

from pydantic import BaseModel, Field
from sqlmodel import Session

from ...domain.errors import NotFound, QuaestorError, ValidationError
from ...domain.models import Account, Category, CategoryGroup, Tag
from ...domain.money import BASE_CURRENCY, to_cop_cents
from ...services import accounts, categories, fx, tags, transactions
from .. import format

# ----- input models (one per tool; the SDK publishes their JSON Schema) -----


class RecordExpenseInput(BaseModel):
    payee: str = Field(description="Merchant or payee, e.g. 'Supermarket'")
    amount: int = Field(gt=0, description="Amount in cents, original currency (40000 COP = 4000000)")
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
    amount: int = Field(gt=0, description="Amount SENT in cents, in the source account's currency")
    amount_received: int | None = Field(
        default=None,
        gt=0,
        description=(
            "Amount RECEIVED in cents, in the destination account's currency. "
            "Required when the accounts use different currencies; defaults to "
            "the sent amount when they match."
        ),
    )
    currency: str | None = Field(
        default=None,
        description="Sent currency; defaults to the source account's currency",
    )
    date: Date | None = Field(default=None, description="Date YYYY-MM-DD; defaults to today")
    notes: str | None = Field(default=None, description="Free-form notes (optional)")


class SetFxRateInput(BaseModel):
    usd_cop: float = Field(gt=0, description="Pesos per dollar (the TRM), e.g. 4150")


class GetFxRateInput(BaseModel):
    pass


class ListTransactionsInput(BaseModel):
    date_from: Date | None = Field(default=None, description="Include from this date")
    date_to: Date | None = Field(default=None, description="Include up to this date")
    account: str | None = Field(default=None, description="Filter by account name")
    category: str | None = Field(default=None, description="Filter by category name")
    tag: str | None = Field(default=None, description="Filter by tag name")
    type: Literal["expense", "income", "transfer"] | None = Field(default=None, description="Transaction type")
    status: Literal["posted", "planned"] | None = Field(default=None, description="Transaction status")
    sort: Literal["date", "created_at"] = Field(
        default="date",
        description="Primary sort field (date = logical date; created_at = row creation).",
    )
    order: Literal["asc", "desc"] = Field(default="desc", description="Sort direction.")


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


def _resolve_account_by_name(session: Session, name: str, *, allow_archived: bool = False) -> Account:
    all_accounts = accounts.list_accounts(session, include_archived=allow_archived)
    target = name.strip().lower()
    match = next((a for a in all_accounts if a.name.lower() == target), None)
    if match is not None:
        return match
    available = ", ".join(a.name for a in all_accounts) or "(none)"
    raise NotFound(f"Account '{name}' not found. Available: {available}.")


def _resolve_category_by_name(session: Session, name: str) -> Category:
    target = name.strip().lower()
    for category in categories.list_categories(session):
        if category.name.lower() == target:
            return category
    raise NotFound(f"Category '{name}' not found. You can create it or record without a category.")


def _resolve_category_group_by_name(session: Session, name: str) -> CategoryGroup:
    all_groups = categories.list_groups(session, include_archived=True)
    target = name.strip().lower()
    match = next((g for g in all_groups if g.name.lower() == target), None)
    if match is not None:
        return match
    available = ", ".join(g.name for g in all_groups) or "(none)"
    raise NotFound(f"Category group '{name}' not found. Available: {available}.")


def _resolve_tag_by_name(session: Session, name: str) -> Tag:
    all_tags = tags.list_tags(session)
    target = name.strip().lower()
    match = next((t for t in all_tags if t.name.lower() == target), None)
    if match is not None:
        return match
    available = ", ".join(t.name for t in all_tags) or "(none)"
    raise NotFound(f"Tag '{name}' not found. Available: {available}.")


# ----- YYYY-MM validation (shared by budget reads + monthly report) -----


_YEAR_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _validate_month(month: str) -> None:
    if not _YEAR_MONTH_RE.match(month):
        raise ValidationError(f"malformed year_month (expected YYYY-MM): {month!r}")


# ----- legacy aliases kept for backward-compatible imports -----


def _resolve_account(session: Session, name: str) -> Account:
    return _resolve_account_by_name(session, name)


def _resolve_category(session: Session, name: str) -> Category:
    return _resolve_category_by_name(session, name)


# ----- write tools -----


def _confirmation_cop_equivalent(session: Session, tx) -> int | None:
    """COP equivalent for a write confirmation: only non-COP transactions
    show one, and only when a TRM is set (writes succeed without one, AC-1)."""
    if tx.currency == BASE_CURRENCY:
        return None
    trm = fx.get_trm_or_none(session)
    if trm is None:
        return None
    return to_cop_cents(tx.amount, tx.currency, trm)


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
    return format.expense_confirmation(tx, account, _confirmation_cop_equivalent(session, tx))


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
    return format.income_confirmation(tx, account, _confirmation_cop_equivalent(session, tx))


@_as_text
def transfer(session: Session, inp: TransferInput) -> str:
    src = _resolve_account(session, inp.from_account)
    dst = _resolve_account(session, inp.to_account)
    _, leg_to = transactions.transfer(
        session,
        from_account_id=src.id,
        to_account_id=dst.id,
        amount=inp.amount,
        currency=inp.currency,
        date=inp.date or Date.today(),
        notes=inp.notes,
        source="agent",
        amount_received=inp.amount_received,
    )
    src = accounts.get_account(session, src.id)
    dst = accounts.get_account(session, dst.id)
    return format.transfer_confirmation(src, dst, inp.amount, leg_to.amount)


@_as_text
def set_fx_rate(session: Session, inp: SetFxRateInput) -> str:
    rate = fx.set_trm(session, inp.usd_cop)
    return format.fx_set(rate)


# ----- read tools -----


@_as_text
def list_transactions(session: Session, inp: ListTransactionsInput) -> str:
    account_id = _resolve_account(session, inp.account).id if inp.account else None
    category_id = _resolve_category(session, inp.category).id if inp.category else None
    txs = transactions.list_transactions(
        session,
        account_id=account_id,
        category_id=category_id,
        tag=inp.tag,
        type=inp.type,
        status=inp.status,
        date_from=inp.date_from,
        date_to=inp.date_to,
        sort=inp.sort,
        order=inp.order,
    )
    return format.transactions_table(txs, fx.get_trm(session))


@_as_text
def get_fx_rate(session: Session, inp: GetFxRateInput) -> str:
    return format.fx_current(fx.get_trm(session))


@_as_text
def list_accounts(session: Session) -> str:
    return format.accounts_table(accounts.list_accounts(session))


@_as_text
def list_categories(session: Session) -> str:
    return format.categories_table(categories.list_categories(session), categories.list_groups(session))


@_as_text
def list_tags(session: Session) -> str:
    return format.tags_list(tags.list_tags(session))
