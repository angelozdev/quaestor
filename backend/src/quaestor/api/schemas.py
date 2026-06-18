"""Pydantic request/response models. `*Out` mirror the SQLModel rows (cents as int)."""
from __future__ import annotations

from datetime import date as Date
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ..domain.models import AccountType, Source, TxStatus, TxType


class AccountCreate(BaseModel):
    name: str
    type: AccountType
    currency: str
    balance: int = 0


class AccountUpdate(BaseModel):
    name: str | None = None
    type: AccountType | None = None


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: AccountType
    currency: str
    balance: int
    archived: bool


class CategoryGroupCreate(BaseModel):
    name: str
    sort_order: int = 0


class CategoryGroupUpdate(BaseModel):
    name: str | None = None
    sort_order: int | None = None


class CategoryGroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sort_order: int
    archived: bool


class CategoryCreate(BaseModel):
    name: str
    group_id: int | None = None
    is_income: bool = False
    exclude_from_budget: bool = False
    exclude_from_totals: bool = False


class CategoryUpdate(BaseModel):
    name: str | None = None
    group_id: int | None = None
    is_income: bool | None = None
    exclude_from_budget: bool | None = None
    exclude_from_totals: bool | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    group_id: int | None
    is_income: bool
    exclude_from_budget: bool
    exclude_from_totals: bool
    archived: bool


class TagCreate(BaseModel):
    name: str


class TagUpdate(BaseModel):
    name: str


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class FxIn(BaseModel):
    date: Date
    usd_cop: Decimal


class FxOut(BaseModel):
    date: Date
    usd_cop: Decimal


class SettingsUpdate(BaseModel):
    base_currency: str | None = None
    default_source_account_id: int | None = None


class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    base_currency: str
    default_source_account_id: int | None


class TransactionCreate(BaseModel):
    type: TxType
    account_id: int
    amount: int
    currency: str
    date: Date
    payee: str = ""
    category_id: int | None = None
    notes: str | None = None
    source: str = "manual"
    fx_rate: Decimal | None = None


class TransferIn(BaseModel):
    from_account_id: int
    to_account_id: int
    amount: int
    currency: str
    date: Date
    notes: str | None = None
    source: str = "manual"
    fx_rate: Decimal | None = None


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: Date
    payee: str
    notes: str | None
    type: TxType
    status: TxStatus
    amount: int
    currency: str
    fx_rate: Decimal
    to_base: int
    account_id: int
    category_id: int | None
    transfer_group_id: str | None
    source: Source
    created_at: datetime


class TransferOut(BaseModel):
    from_leg: TransactionOut
    to_leg: TransactionOut
