"""SQLModel tables and enums from the domain (P0)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Annotated, Optional

from sqlalchemy import BigInteger, Column, Index, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel


class AccountType(str, Enum):
    debit = "debit"
    credit = "credit"
    cash = "cash"
    savings = "savings"


class TxType(str, Enum):
    expense = "expense"
    income = "income"
    transfer = "transfer"


class IntervalUnit(str, Enum):
    day = "day"
    week = "week"
    month = "month"
    year = "year"


class RecurringMode(str, Enum):
    auto = "auto"
    manual = "manual"


class OccurrenceStatus(str, Enum):
    """`offered` is a due date waiting for the user's answer: it consumes the
    date so no run creates it, but it is not a charge (ADR-0035)."""

    posted = "posted"
    planned = "planned"
    skipped = "skipped"
    offered = "offered"


class TxStatus(str, Enum):
    """`skipped` is a terminal cancel: it affects neither balances nor to-pay."""

    planned = "planned"
    posted = "posted"
    skipped = "skipped"


class Source(str, Enum):
    """Who created the row. `recurring` is the engine acting on its own,
    which is what makes an unattended balance change reconcilable (ADR-0038)."""

    manual = "manual"
    agent = "agent"
    import_ = "import"
    recurring = "recurring"


class TransferDirection(str, Enum):
    """Which way a transfer leg moved its account balance (ADR-0032)."""

    out = "out"
    in_ = "in"


class Account(SQLModel, table=True):
    """`balance` is integer cents in the account's own currency."""

    id: Annotated[Optional[int], Field(default=None, primary_key=True)] = None
    name: str
    type: AccountType
    currency: str
    balance: Annotated[int, Field(default=0, sa_type=BigInteger)] = 0
    archived: bool = False


class CategoryGroup(SQLModel, table=True):
    __tablename__ = "category_group"
    id: Annotated[Optional[int], Field(default=None, primary_key=True)] = None
    name: str
    sort_order: int = 0
    archived: bool = False


class Category(SQLModel, table=True):
    id: Annotated[Optional[int], Field(default=None, primary_key=True)] = None
    name: str
    group_id: Annotated[Optional[int], Field(default=None, foreign_key="category_group.id")] = None
    is_income: bool = False
    exclude_from_budget: bool = False
    exclude_from_totals: bool = False
    archived: bool = False


class Transaction(SQLModel, table=True):
    """`amount` is positive integer cents in the account's currency; no rate
    or converted amount is stored — COP figures are read-time (ADR-0031)."""

    __table_args__ = (
        Index("ix_transaction_type_status_date", "type", "status", "date"),
    )

    id: Annotated[Optional[int], Field(default=None, primary_key=True)] = None
    date: date
    payee: str = ""
    notes: Optional[str] = None
    type: TxType
    status: TxStatus = TxStatus.posted
    amount: Annotated[int, Field(sa_type=BigInteger)]
    currency: str
    account_id: Annotated[int, Field(foreign_key="account.id")]
    category_id: Annotated[Optional[int], Field(default=None, foreign_key="category.id")] = None
    recurring_id: Annotated[Optional[int], Field(default=None, foreign_key="recurring_item.id")] = None
    goal_id: Annotated[Optional[int], Field(default=None, foreign_key="goal.id")] = None
    transfer_group_id: Annotated[Optional[str], Field(default=None, index=True)] = None
    transfer_direction: Annotated[Optional[TransferDirection], Field(default=None)] = None
    source: Source = Source.manual
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Tag(SQLModel, table=True):
    id: Annotated[Optional[int], Field(default=None, primary_key=True)] = None
    name: Annotated[str, Field(index=True, unique=True)]


class TransactionTag(SQLModel, table=True):
    __tablename__ = "transaction_tag"
    transaction_id: Annotated[int, Field(foreign_key="transaction.id", primary_key=True)]
    tag_id: Annotated[int, Field(foreign_key="tag.id", primary_key=True)]


class Settings(SQLModel, table=True):
    """Single-row app settings; `usd_cop` is the scalar TRM (ADR-0031), None until first set."""

    id: Annotated[Optional[int], Field(default=1, primary_key=True)] = 1
    base_currency: str = "COP"
    default_source_account_id: Annotated[Optional[int], Field(default=None, foreign_key="account.id")] = None
    usd_cop: Annotated[Optional[Decimal], Field(default=None, sa_column=Column(Numeric(18, 6)))] = None


class RecurringItem(SQLModel, table=True):
    """`type` is expense or income (service-validated; never transfer);
    `amount` is the default occurrence amount in positive cents of `currency`."""

    __tablename__ = "recurring_item"
    id: Annotated[Optional[int], Field(default=None, primary_key=True)] = None
    name: str
    payee: str = ""
    type: TxType
    mode: RecurringMode
    amount: int
    currency: str
    category_id: Annotated[Optional[int], Field(default=None, foreign_key="category.id")] = None
    account_id: Annotated[int, Field(foreign_key="account.id")]
    interval_unit: IntervalUnit
    interval_count: int = 1
    start_date: date
    end_date: Optional[date] = None
    active: bool = True


class RecurringOccurrence(SQLModel, table=True):
    __tablename__ = "recurring_occurrence"
    __table_args__ = (
        UniqueConstraint("recurring_id", "due_date", name="uq_occurrence_recurring_due"),
    )
    id: Annotated[Optional[int], Field(default=None, primary_key=True)] = None
    recurring_id: Annotated[int, Field(foreign_key="recurring_item.id", index=True)]
    due_date: date
    status: OccurrenceStatus
    transaction_id: Annotated[Optional[int], Field(default=None, foreign_key="transaction.id")] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GoalStatus(str, Enum):
    active = "active"
    reached = "reached"
    paused = "paused"


class ContributionSource(str, Enum):
    """`confirmed`: proposed by rollover, confirmed in To-pay.
    `manual`: standalone contribution."""

    confirmed = "confirmed"
    manual = "manual"


class Budget(SQLModel, table=True):
    """`year_month` is "YYYY-MM"; `amount_assigned` is COP cents, >= 0."""

    __table_args__ = (
        UniqueConstraint("category_id", "year_month", name="uq_budget_category_month"),
    )
    id: Annotated[Optional[int], Field(default=None, primary_key=True)] = None
    category_id: Annotated[int, Field(foreign_key="category.id")]
    year_month: str
    amount_assigned: int = 0


class Goal(SQLModel, table=True):
    """Amounts are COP cents. A defined goal has both `target_amount` and
    `deadline`; an open-ended goal has neither. `monthly_amount` is > 0."""

    id: Annotated[Optional[int], Field(default=None, primary_key=True)] = None
    name: str
    target_amount: Optional[int] = None
    deadline: Optional[date] = None
    monthly_amount: int
    savings_account_id: Annotated[int, Field(foreign_key="account.id")]
    status: GoalStatus = GoalStatus.active


class GoalContribution(SQLModel, table=True):
    """`amount` is the physical cents of the contribution's transfer leg, in
    the savings account's currency — no COP snapshot is stored (ADR-0031)."""

    __tablename__ = "goal_contribution"
    __table_args__ = (
        Index("ix_goal_contribution_goal_date", "goal_id", "date"),
    )
    id: Annotated[Optional[int], Field(default=None, primary_key=True)] = None
    goal_id: Annotated[int, Field(foreign_key="goal.id")]
    date: date
    amount: int
    source: ContributionSource
    transaction_id: Annotated[Optional[int], Field(default=None, foreign_key="transaction.id")] = None
