"""Pydantic request/response models. `*Out` mirror the SQLModel rows (cents as int)."""
from __future__ import annotations

from datetime import date as Date
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from ..domain.models import (
    AccountType,
    IntervalUnit,
    OccurrenceStatus,
    RecurringMode,
    Source,
    Transaction,
    TxStatus,
    TxType,
)
from ..domain.money import to_cop_cents


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
    usd_cop: Decimal = Field(gt=0, le=100000)


class FxOut(BaseModel):
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


class TransferIn(BaseModel):
    from_account_id: int
    to_account_id: int
    amount: int
    amount_received: int | None = None
    currency: str | None = None
    date: Date
    notes: str | None = None
    source: str = "manual"


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
    cop_equivalent: int | None = None
    account_id: int
    category_id: int | None
    transfer_group_id: str | None
    source: Source
    created_at: datetime

    @classmethod
    def from_tx(cls, tx: Transaction, trm: Decimal | None) -> "TransactionOut":
        """Serialize a Transaction, computing `cop_equivalent` at read time
        when a TRM is available (ADR-0031)."""
        out = cls.model_validate(tx)
        if trm is not None:
            out.cop_equivalent = to_cop_cents(tx.amount, tx.currency, trm)
        return out


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
    interval_count: int = Field(default=1, gt=0, le=1000)
    start_date: Date
    end_date: Date | None = None


class RecurringUpdate(BaseModel):
    name: str | None = None
    payee: str | None = None
    mode: RecurringMode | None = None
    amount: int | None = Field(default=None, gt=0)
    category_id: int | None = None
    account_id: int | None = None
    interval_unit: IntervalUnit | None = None
    interval_count: int | None = Field(default=None, gt=0, le=1000)
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
    amount: int = Field(gt=0)
    currency: str = "COP"
    due_date: Date
    account_id: int
    category_id: int | None = None
    notes: str | None = None


class ConfirmPaymentIn(BaseModel):
    amount: int | None = None
    date: Date | None = None


class ToPayOut(BaseModel):
    overdue: list[TransactionOut]
    upcoming: list[TransactionOut]
    total_base: int


class CloseMonthIn(BaseModel):
    period: str


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


class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    target_amount: int | None
    deadline: Date | None
    monthly_amount: int
    savings_account_id: int
    status: str


class GoalCreate(BaseModel):
    name: str
    monthly_amount: int = Field(gt=0)
    savings_account_id: int
    target_amount: int | None = Field(default=None, gt=0)
    deadline: Date | None = None


class GoalUpdate(BaseModel):
    name: str | None = None
    monthly_amount: int | None = Field(default=None, gt=0)
    target_amount: int | None = None
    deadline: Date | None = None
    savings_account_id: int | None = None


class GoalContributeIn(BaseModel):
    amount: int = Field(gt=0)
    date: Date


class GoalContributionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    goal_id: int
    date: Date
    amount: int
    source: str
    transaction_id: int | None


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


class BudgetLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category_id: int
    category_name: str
    assigned: int
    rollover_in: int
    spent: int
    available: int
    pct_used: int
    status: str


class BudgetAssignIn(BaseModel):
    category_id: int
    year_month: str
    amount_assigned: int
