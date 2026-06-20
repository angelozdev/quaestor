"""MCP temporal tools (P3): recurring items + the to-pay confirmation queue.

Mirrors core.py: parse input, resolve names, call ONE service, format output.
materialize_due/close_month are NOT exposed (the scheduler runs them, ADR-017/020).
"""
from __future__ import annotations

from datetime import date as Date
from typing import Literal

from pydantic import BaseModel, Field
from sqlmodel import Session

from ...domain.models import RecurringMode, TxType
from ...services import planned, recurring
from .. import format
from .core import _as_text, _resolve_account, _resolve_category


# ----- input models -----


class CreateRecurringInput(BaseModel):
    name: str = Field(description="Display name, e.g. 'Rent'")
    payee: str = Field(description="Payee/source, e.g. 'Landlord'")
    type: Literal["expense", "income"] = Field(description="expense or income")
    mode: Literal["auto", "manual"] = Field(
        description="auto posts on each due date; manual goes to to-pay for confirmation"
    )
    amount: int = Field(gt=0, description="Default amount in cents, original currency")
    account: str = Field(description="Account name")
    currency: str = Field(default="COP", description="ISO currency code; defaults to COP")
    category: str | None = Field(default=None, description="Category name (optional)")
    interval_unit: Literal["day", "week", "month", "year"] = Field(
        description="Interval unit; combine with interval_count (e.g. 2 week = biweekly)"
    )
    interval_count: int = Field(default=1, ge=1, description="How many units per interval")
    start_date: Date = Field(description="Anchor date YYYY-MM-DD")
    end_date: Date | None = Field(default=None, description="Optional last date YYYY-MM-DD")


class ListRecurringInput(BaseModel):
    active: bool | None = Field(default=None, description="Filter by active state")


class PlanPaymentInput(BaseModel):
    payee: str = Field(description="Who you owe, e.g. 'Friend'")
    amount: int = Field(gt=0, description="Amount in cents, original currency")
    account: str = Field(description="Account the payment will come from")
    currency: str = Field(default="COP", description="ISO currency code; defaults to COP")
    category: str | None = Field(default=None, description="Category name (optional)")
    due_date: Date = Field(description="When it is due, YYYY-MM-DD")
    notes: str | None = Field(default=None, description="Free-form notes (optional)")


class ConfirmPaymentInput(BaseModel):
    tx_id: int = Field(description="The planned transaction id (from to_pay)")
    amount: int | None = Field(default=None, gt=0, description="Real amount if it differs")
    date: Date | None = Field(default=None, description="Real date if it differs")


class SkipPaymentInput(BaseModel):
    tx_id: int = Field(description="The planned transaction id to cancel")


class SkipRecurringInput(BaseModel):
    recurring_id: int = Field(description="The recurring item id")
    due_date: Date = Field(description="The single occurrence date to skip, YYYY-MM-DD")


class ToPayInput(BaseModel):
    since: Date = Field(description="Window start, YYYY-MM-DD")
    until: Date = Field(description="Window end, YYYY-MM-DD")


# ----- impls -----


@_as_text
def create_recurring(session: Session, inp: CreateRecurringInput) -> str:
    account = _resolve_account(session, inp.account)
    category = _resolve_category(session, inp.category) if inp.category else None
    item = recurring.create_recurring(
        session,
        name=inp.name,
        payee=inp.payee,
        type=TxType(inp.type),
        mode=RecurringMode(inp.mode),
        amount=inp.amount,
        currency=inp.currency,
        category_id=category.id if category else None,
        account_id=account.id,
        interval_unit=inp.interval_unit,
        interval_count=inp.interval_count,
        start_date=inp.start_date,
        end_date=inp.end_date,
    )
    return format.recurring_created(item)


@_as_text
def list_recurring(session: Session, inp: ListRecurringInput) -> str:
    return format.recurring_list(recurring.list_recurring(session, active=inp.active))


@_as_text
def plan_payment(session: Session, inp: PlanPaymentInput) -> str:
    account = _resolve_account(session, inp.account)
    category = _resolve_category(session, inp.category) if inp.category else None
    tx = planned.plan_payment(
        session,
        payee=inp.payee,
        amount=inp.amount,
        currency=inp.currency,
        due_date=inp.due_date,
        account_id=account.id,
        category_id=category.id if category else None,
        notes=inp.notes,
    )
    return format.payment_planned(tx)


@_as_text
def confirm_payment(session: Session, inp: ConfirmPaymentInput) -> str:
    tx = planned.confirm_payment(session, inp.tx_id, amount=inp.amount, date=inp.date)
    return format.payment_confirmed(tx)


@_as_text
def skip_payment(session: Session, inp: SkipPaymentInput) -> str:
    tx = planned.skip_payment(session, inp.tx_id)
    return format.payment_skipped(tx)


@_as_text
def skip_recurring(session: Session, inp: SkipRecurringInput) -> str:
    occ = recurring.skip_recurring(session, inp.recurring_id, inp.due_date)
    return format.recurring_skipped(occ)


@_as_text
def to_pay(session: Session, inp: ToPayInput) -> str:
    return format.to_pay_table(planned.to_pay(session, inp.since, inp.until))
