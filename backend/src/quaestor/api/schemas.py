"""Pydantic request/response models. `*Out` mirror the SQLModel rows (cents as int)."""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session

from ..domain.models import (
    AccountType,
    FundRule,
    IntervalUnit,
    OccurrenceStatus,
    RecurringMode,
    Source,
    Transaction,
    TransferDirection,
    TxStatus,
    TxType,
)
from ..domain.money import to_cop_cents
from ..services import tags


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
    new_category: str | None = None
    notes: str | None = None
    source: str = "manual"
    tags: list[str] | None = None


class TransferIn(BaseModel):
    from_account_id: int
    to_account_id: int
    amount: int
    amount_received: int | None = None
    currency: str | None = None
    date: Date
    notes: str | None = None
    source: str = "manual"
    category_id: int | None = None


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
    transfer_direction: TransferDirection | None = None
    source: Source
    created_at: datetime
    tags: list[str] = []

    @classmethod
    def from_tx(
        cls,
        tx: Transaction,
        trm: Decimal | None,
        tag_names: list[str],
    ) -> TransactionOut:
        """Serialize a Transaction, computing `cop_equivalent` at read time
        when a TRM is available (ADR-0031) and attaching its tag names."""
        out = cls.model_validate(tx)
        if trm is not None:
            out.cop_equivalent = to_cop_cents(tx.amount, tx.currency, trm)
        out.tags = tag_names
        return out

    @classmethod
    def from_txs(
        cls,
        session: Session,
        txs: list[Transaction],
        trm: Decimal | None,
    ) -> list[TransactionOut]:
        """Serialize transactions, loading every tag name in one query."""
        names = tags.tag_names_by_transaction(session, [tx.id for tx in txs])
        return [cls.from_tx(tx, trm, names[tx.id]) for tx in txs]

    @classmethod
    def from_one(
        cls,
        session: Session,
        tx: Transaction,
        trm: Decimal | None,
    ) -> TransactionOut:
        """Serialize a single transaction with its tag names loaded."""
        return cls.from_txs(session, [tx], trm)[0]


class TransferOut(BaseModel):
    from_leg: TransactionOut
    to_leg: TransactionOut


class TransactionUpdate(BaseModel):
    payee: str | None = None
    notes: str | None = None
    category_id: int | None = None
    date: Date | None = None
    tags: list[str] | None = None


class RecurringCreate(BaseModel):
    name: str
    payee: str = ""
    type: TxType
    mode: RecurringMode
    amount: int
    currency: str = "COP"
    category_id: int | None = None
    new_category: str | None = None
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


class PendingDatesIn(BaseModel):
    """The passed due dates the user answered, accepted or declined together."""

    due_dates: list[Date]


class PlanPaymentIn(BaseModel):
    payee: str
    amount: int = Field(gt=0)
    currency: str = "COP"
    due_date: Date
    account_id: int
    category_id: int | None = None
    new_category: str | None = None
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


class FundCreate(BaseModel):
    category_id: int
    rule: FundRule
    start_month: str
    accumulates: bool | None = None
    amount: int | None = None
    window_months: int | None = None
    target_amount: int | None = None
    target_month: str | None = None
    opening_balance: int | None = None


class FundUpdate(BaseModel):
    rule: FundRule | None = None
    accumulates: bool | None = None
    amount: int | None = None
    window_months: int | None = None
    target_amount: int | None = None
    target_month: str | None = None
    balance: int | None = None


class FundOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    rule: FundRule
    start_month: str
    accumulates: bool
    amount: int | None
    window_months: int | None
    target_amount: int | None
    target_month: str | None


class FundLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fund_id: int
    category_id: int
    name: str
    rule: str
    start_month: str
    accumulates: bool


class FundPreviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category_id: int
    would_ask: int
    warning: str | None


class MonthRatesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    year_month: str
    earning: int
    cost: int
    margin: int


class FundsSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    n_on_track: int
    n_behind: int
    set_aside: int


class FundReportLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category_name: str
    asks: int
    holds: int
    spent: int
    on_track: bool


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


class FundStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fund_id: int
    category_id: int
    name: str
    year_month: str
    rule: str
    asks: int
    holds: int
    accumulates: bool
    accumulation_is_implied: bool
    on_track: bool
    averaged_over: int | None = None
    spreads_over: int | None = None
    whole_by: str | None = None


class MonthAvailableOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    year_month: str
    income: int
    funds: list[FundStatusOut]
    uncovered: int
    free: int


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
    funds_summary: FundsSummaryOut
    funds: list[FundReportLineOut]
    by_category: list[CategorySectionOut]
    by_group: list[GroupSectionOut]
    balances: list[AccountBalanceOut]
    drift_mom: DriftMoMOut | None
    usd_share: float
    pending: list[str]
    available: MonthAvailableOut
    markdown: str
