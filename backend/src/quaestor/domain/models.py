"""SQLModel tables and enums from the domain (P0)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from sqlalchemy import BigInteger, CheckConstraint, Column, Index, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel


class AccountType(StrEnum):
    debit = "debit"
    credit = "credit"
    cash = "cash"
    savings = "savings"


class TxType(StrEnum):
    expense = "expense"
    income = "income"
    transfer = "transfer"


class IntervalUnit(StrEnum):
    day = "day"
    week = "week"
    month = "month"
    year = "year"


class RecurringMode(StrEnum):
    auto = "auto"
    manual = "manual"


class OccurrenceStatus(StrEnum):
    """`offered` is a due date waiting for the user's answer: it consumes the
    date so no run creates it, but it is not a charge (ADR-0035)."""

    posted = "posted"
    planned = "planned"
    skipped = "skipped"
    offered = "offered"


class TxStatus(StrEnum):
    """`skipped` is a terminal cancel: it affects neither balances nor to-pay."""

    planned = "planned"
    posted = "posted"
    skipped = "skipped"


class Source(StrEnum):
    """Who created the row. `recurring` is the engine acting on its own,
    which is what makes an unattended balance change reconcilable (ADR-0038)."""

    manual = "manual"
    agent = "agent"
    import_ = "import"
    recurring = "recurring"


class TransferDirection(StrEnum):
    """Which way a transfer leg moved its account balance (ADR-0032)."""

    out = "out"
    in_ = "in"


class Account(SQLModel, table=True):
    """`balance` is integer cents in the account's own currency."""

    id: Annotated[int | None, Field(default=None, primary_key=True)] = None
    name: str
    type: AccountType
    currency: str
    balance: Annotated[int, Field(default=0, sa_type=BigInteger)] = 0
    archived: bool = False


class CategoryGroup(SQLModel, table=True):
    __tablename__ = "category_group"
    id: Annotated[int | None, Field(default=None, primary_key=True)] = None
    name: str
    sort_order: int = 0
    archived: bool = False


class Category(SQLModel, table=True):
    id: Annotated[int | None, Field(default=None, primary_key=True)] = None
    name: str
    group_id: Annotated[int | None, Field(default=None, foreign_key="category_group.id")] = None
    is_income: bool = False
    exclude_from_budget: bool = False
    exclude_from_totals: bool = False
    counts_as_saving: bool = False
    archived: bool = False


class Transaction(SQLModel, table=True):
    """`amount` is positive integer cents in the account's currency; no rate
    or converted amount is stored — COP figures are read-time (ADR-0031).

    `category_id` is nullable in the column but not in practice: the CHECK
    requires one on an expense or income and forbids one on a transfer
    (ADR-0041). Declared here as well as in revision 0010 so the model and the
    schema cannot drift.

    `meta_id` is the owner naming, once, which purchase a meta was for
    (ADR-0046). A CHECK confines it to expenses the same way `category_id` is
    confined by direction: money coming in and money moving between the owner's
    own accounts are not purchases.
    """

    __table_args__ = (
        Index("ix_transaction_type_status_date", "type", "status", "date"),
        CheckConstraint(
            "(type IN ('expense', 'income') AND category_id IS NOT NULL)"
            " OR (type = 'transfer' AND category_id IS NULL)",
            name="ck_transaction_category_by_type",
        ),
        CheckConstraint(
            "meta_id IS NULL OR type = 'expense'",
            name="ck_transaction_meta_only_on_expense",
        ),
    )

    id: Annotated[int | None, Field(default=None, primary_key=True)] = None
    date: date
    payee: str = ""
    notes: str | None = None
    type: TxType
    status: TxStatus = TxStatus.posted
    amount: Annotated[int, Field(sa_type=BigInteger)]
    currency: str
    account_id: Annotated[int, Field(foreign_key="account.id")]
    category_id: Annotated[int | None, Field(default=None, foreign_key="category.id")] = None
    recurring_id: Annotated[int | None, Field(default=None, foreign_key="recurring_item.id")] = None
    meta_id: Annotated[int | None, Field(default=None, foreign_key="meta.id")] = None
    transfer_group_id: Annotated[str | None, Field(default=None, index=True)] = None
    transfer_direction: Annotated[TransferDirection | None, Field(default=None)] = None
    source: Source = Source.manual
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Meta(SQLModel, table=True):
    """A named thing to save for, belonging to no category (ADR-0046).

    No balance column, the same constraint ADR-0043 put on the fund and for the
    same reason: what a meta holds is folded forward from its start month, so a
    past month answers as that month stood and cancelling now cannot rewrite it.

    `stated_opening` is the owner's own statement of what he had already put by
    before the meta existed. It costs no month — unlike a contribution, which is
    money set aside now — and it is read for the start month only.

    `amount` is cents in `currency`. A meta held in dollars reports every figure
    in dollars; only its peso cost converts, at the single scalar TRM.
    """

    __table_args__ = (UniqueConstraint("name", name="uq_meta_name"),)
    id: Annotated[int | None, Field(default=None, primary_key=True)] = None
    name: str
    amount: Annotated[int, Field(sa_type=BigInteger)]
    currency: str = "COP"
    start_month: str
    target_month: str
    stated_opening: Annotated[int | None, Field(default=None, sa_type=BigInteger)] = None
    closed: bool = False
    archived: bool = False


class MetaContribution(SQLModel, table=True):
    """Money the owner set aside by hand, on top of what the meta asks.

    A row exists only because he pressed the button, and he can delete it
    (AC-42). Nothing generates these: there is no month-end routine, no
    proposal to confirm and no source account — which is what separates this
    from the `goal_contribution` table migration 0012 removed.
    """

    __tablename__ = "meta_contribution"
    id: Annotated[int | None, Field(default=None, primary_key=True)] = None
    meta_id: Annotated[int, Field(foreign_key="meta.id")]
    year_month: str
    amount: Annotated[int, Field(sa_type=BigInteger)]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Tag(SQLModel, table=True):
    id: Annotated[int | None, Field(default=None, primary_key=True)] = None
    name: Annotated[str, Field(index=True, unique=True)]


class TransactionTag(SQLModel, table=True):
    __tablename__ = "transaction_tag"
    transaction_id: Annotated[int, Field(foreign_key="transaction.id", primary_key=True)]
    tag_id: Annotated[int, Field(foreign_key="tag.id", primary_key=True)]


class Settings(SQLModel, table=True):
    """Single-row app settings; `usd_cop` is the scalar TRM (ADR-0031), None until first set."""

    id: Annotated[int | None, Field(default=1, primary_key=True)] = 1
    base_currency: str = "COP"
    default_source_account_id: Annotated[int | None, Field(default=None, foreign_key="account.id")] = None
    usd_cop: Annotated[Decimal | None, Field(default=None, sa_column=Column(Numeric(18, 6)))] = None


class RecurringItem(SQLModel, table=True):
    """`type` is expense or income (service-validated; never transfer);
    `amount` is the default occurrence amount in positive cents of `currency`.

    `category_id` is required: every charge copies it, so a source that could
    be empty would produce uncategorised charges (ADR-0041)."""

    __tablename__ = "recurring_item"
    id: Annotated[int | None, Field(default=None, primary_key=True)] = None
    name: str
    payee: str = ""
    type: TxType
    mode: RecurringMode
    amount: int
    currency: str
    category_id: Annotated[int, Field(foreign_key="category.id")]
    account_id: Annotated[int, Field(foreign_key="account.id")]
    interval_unit: IntervalUnit
    interval_count: int = 1
    start_date: date
    end_date: date | None = None
    active: bool = True


class RecurringOccurrence(SQLModel, table=True):
    __tablename__ = "recurring_occurrence"
    __table_args__ = (UniqueConstraint("recurring_id", "due_date", name="uq_occurrence_recurring_due"),)
    id: Annotated[int | None, Field(default=None, primary_key=True)] = None
    recurring_id: Annotated[int, Field(foreign_key="recurring_item.id", index=True)]
    due_date: date
    status: OccurrenceStatus
    transaction_id: Annotated[int | None, Field(default=None, foreign_key="transaction.id")] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class FundRule(StrEnum):
    """How a fund works out what it asks for each month (ADR-0043)."""

    fixed = "fixed"
    average = "average"
    from_recurring = "from-recurring"
    target_by_date = "target-by-date"


class Fund(SQLModel, table=True):
    """One fund per expense category: the rule is stored, the balance derived.

    No balance column and no account reference — what a fund holds is folded
    forward from its start month over the category's posted spending
    (ADR-0043). `anchor_amount` is the owner's own statement of what it already
    holds; `anchor_month` is the month that statement was made for, and `None`
    means it was made for whatever month is being looked at.
    """

    __table_args__ = (UniqueConstraint("category_id", name="uq_fund_category"),)
    id: Annotated[int | None, Field(default=None, primary_key=True)] = None
    category_id: Annotated[int, Field(foreign_key="category.id")]
    rule: FundRule
    start_month: str
    accumulates: bool = True
    amount: Annotated[int | None, Field(default=None, sa_type=BigInteger)] = None
    window_months: int | None = None
    target_amount: Annotated[int | None, Field(default=None, sa_type=BigInteger)] = None
    target_month: str | None = None
    anchor_month: str | None = None
    anchor_amount: Annotated[int | None, Field(default=None, sa_type=BigInteger)] = None
