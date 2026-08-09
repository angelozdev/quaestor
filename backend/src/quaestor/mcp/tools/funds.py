"""MCP fund tools (ADR-0009): the assistant reaches funds exactly as the app does.

Same shape as every other tool module — parse input, resolve names, call ONE
service, format output. No rule lives here: the refusals a fund can meet are
raised by `services.funds` and reach the agent as text through `_as_text`
(AC-28).

The agent speaks category names because a fund is the one rule a spending
category carries; the service is called with ids, like `assign_budget` did
before it (ADR-0006, superseded by ADR-0043).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from sqlmodel import Session

from ...domain.errors import NotFound
from ...domain.models import Category
from ...services import funds
from ...services import month as month_service
from .. import format
from .core import _as_text, _resolve_category_by_name, _validate_month

FundRuleName = Literal["fixed", "average", "from-recurring"]


class FundSpecInput(BaseModel):
    """What a fund is made of: the category it covers, its rule, its month."""

    category: str = Field(description="Name of the expense category the fund covers")
    rule: FundRuleName = Field(description="How the fund works out what it asks each month")
    start_month: str = Field(description="First month the fund asks for anything, YYYY-MM")
    amount: int | None = Field(default=None, description="Cents asked each month (rule 'fixed')")
    window_months: int | None = Field(default=None, description="Months to average over (rule 'average')")
    accumulates: bool | None = Field(default=None, description="Whether what is left over carries into next month")
    opening_balance: int | None = Field(default=None, description="Cents the fund already holds, as the owner states")


class CreateFundInput(FundSpecInput):
    pass


class PreviewFundInput(FundSpecInput):
    pass


class SetFundInput(BaseModel):
    category: str = Field(description="Name of the category whose fund changes")
    rule: FundRuleName | None = Field(default=None, description="A new rule for the fund")
    amount: int | None = Field(default=None, description="New cents asked each month (rule 'fixed')")
    window_months: int | None = Field(default=None, description="New window in months (rule 'average')")
    accumulates: bool | None = Field(default=None, description="Whether what is left over carries into next month")
    balance: int | None = Field(default=None, description="Cents the fund holds, as the owner states")


class FundInput(BaseModel):
    category: str = Field(description="Name of the category the fund covers")


class FundStatusInput(BaseModel):
    category: str = Field(description="Name of the category the fund covers")
    month: str = Field(description="YYYY-MM")


class MonthInput(BaseModel):
    month: str = Field(description="YYYY-MM")


def _fund_of(session: Session, category_name: str) -> tuple[Category, int]:
    """The category the agent named and the fund on it, or a not-found it can act on."""
    category = _resolve_category_by_name(session, category_name)
    fund = funds.fund_on_category(session, category.id)
    if fund is None:
        raise NotFound(f"'{category.name}' has no fund. Create one with create_fund.")
    return category, fund.id


def _spec_of(inp: BaseModel) -> dict:
    return inp.model_dump(exclude_none=True, exclude={"category"})


@_as_text
def create_fund(session: Session, inp: CreateFundInput) -> str:
    category = _resolve_category_by_name(session, inp.category)
    return format.fund_saved(funds.create_fund(session, category.id, **_spec_of(inp)), category.name)


@_as_text
def preview_fund(session: Session, inp: PreviewFundInput) -> str:
    category = _resolve_category_by_name(session, inp.category)
    return format.fund_preview_card(funds.preview_fund(session, category.id, **_spec_of(inp)), category.name)


@_as_text
def list_funds(session: Session) -> str:
    return format.funds_list(funds.list_funds(session))


@_as_text
def fund_status(session: Session, inp: FundStatusInput) -> str:
    _validate_month(inp.month)
    _, fund_id = _fund_of(session, inp.category)
    return format.fund_card(funds.fund_status(session, fund_id, inp.month))


@_as_text
def set_fund(session: Session, inp: SetFundInput) -> str:
    category, fund_id = _fund_of(session, inp.category)
    return format.fund_saved(funds.set_fund(session, fund_id, **_spec_of(inp)), category.name)


@_as_text
def delete_fund(session: Session, inp: FundInput) -> str:
    category, fund_id = _fund_of(session, inp.category)
    funds.delete_fund(session, fund_id)
    return format.fund_deleted(category.name)


@_as_text
def money_available(session: Session, inp: MonthInput) -> str:
    _validate_month(inp.month)
    return format.money_available_card(month_service.available(session, inp.month))


@_as_text
def money_rates(session: Session, inp: MonthInput) -> str:
    _validate_month(inp.month)
    return format.money_rates_card(month_service.rates(session, inp.month))
