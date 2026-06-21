"""Pydantic request/response models. `*Out` mirror the SQLModel rows (cents as int)."""
from __future__ import annotations

from datetime import date as Date
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ..domain.models import AccountType, IntervalUnit, OccurrenceStatus, RecurringMode, Source, TxStatus, TxType


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


class TransactionUpdate(BaseModel):
    payee: str | None = None
    notes: str | None = None
    category_id: int | None = None
    date: Date | None = None


class RecurringCreate(BaseModel):
    name: str
    payee: str = ""
    type: TxType
    mode: RecurringMode
    amount: int
    currency: str = "COP"
    category_id: int | None = None
    account_id: int
    interval_unit: IntervalUnit
    interval_count: int = 1
    start_date: Date
    end_date: Date | None = None


class RecurringUpdate(BaseModel):
    name: str | None = None
    payee: str | None = None
    mode: RecurringMode | None = None
    amount: int | None = None
    category_id: int | None = None
    account_id: int | None = None
    interval_unit: IntervalUnit | None = None
    interval_count: int | None = None
    start_date: Date | None = None
    end_date: Date | None = None


class RecurringOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    payee: str
    type: TxType
    mode: RecurringMode
    amount: int
    currency: str
    category_id: int | None
    account_id: int
    interval_unit: IntervalUnit
    interval_count: int
    start_date: Date
    end_date: Date | None
    active: bool


class OccurrenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recurring_id: int
    due_date: Date
    status: OccurrenceStatus
    transaction_id: int | None


class SkipRecurringIn(BaseModel):
    due_date: Date


class PlanPaymentIn(BaseModel):
    payee: str
    amount: int
    currency: str = "COP"
    due_date: Date
    account_id: int
    category_id: int | None = None
    notes: str | None = None


class ConfirmPaymentIn(BaseModel):
    amount: int | None = None
    date: Date | None = None


class ToPayOut(BaseModel):
    items: list[TransactionOut]
    total_base: int


class CloseMonthIn(BaseModel):
    period: str  # "YYYY-MM"


class EnvelopesSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    n_green: int
    n_red: int
    rollover_generated: int


class EnvelopeLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category: str
    allocated: int
    rollover_in: int
    spent: int
    available: int
    status: str


class CategorySectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category: str
    group: str | None
    total: int
    pct: float


class GroupSectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    group: str
    total: int
    pct: float


class GoalLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    accumulated: int
    target: int | None = None
    eta: Date | None = None
    on_track: bool | None = None


class AccountBalanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    account: str
    currency: str
    balance: int


class DriftMoMOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    prev_month: str
    income_abs: int
    income_pct: float | None
    expense_abs: int
    expense_pct: float | None
    net_abs: int
    net_pct: float | None


class MonthlyReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    month: str
    income: int
    expense: int
    net: int
    envelopes_summary: EnvelopesSummaryOut
    envelopes: list[EnvelopeLineOut]
    by_category: list[CategorySectionOut]
    by_group: list[GroupSectionOut]
    goals: list[GoalLineOut]
    balances: list[AccountBalanceOut]
    drift_mom: DriftMoMOut | None
    usd_share: float
    pending: list[str]
    safe_to_spend: SafeToSpendOut
    markdown: str


class GoalProgressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    goal_id: int
    name: str
    type: str
    monthly_amount: int
    saved: int
    target_amount: int | None = None
    deadline: Date | None = None
    monthly_required: int | None = None
    on_track: bool | None = None
    eta: Date | None = None
    remaining: int | None = None


class CommittedItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: str
    name: str
    date: Date
    amount: int


class SafeToSpendOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    year_month: str
    income_forecast: int
    committed: int
    assigned_envelopes: int
    free: int
    committed_breakdown: list[CommittedItemOut]
