"""SQLModel tables and enums from the domain (P0)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Annotated, Optional

from sqlalchemy import Column, Numeric
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


class TxStatus(str, Enum):
    planned = "planned"
    posted = "posted"


class Source(str, Enum):
    manual = "manual"
    agent = "agent"
    import_ = "import"


class Account(SQLModel, table=True):
    id: Annotated[Optional[int], Field(default=None, primary_key=True)] = None
    name: str
    type: AccountType
    currency: str
    balance: int = 0  # centavos, in the account's currency
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
    id: Annotated[Optional[int], Field(default=None, primary_key=True)] = None
    date: date
    payee: str = ""
    notes: Optional[str] = None
    type: TxType
    status: TxStatus = TxStatus.posted
    amount: int  # centavos, original currency, always positive
    currency: str
    fx_rate: Annotated[Decimal, Field(sa_column=Column(Numeric(18, 6)))]
    to_base: int  # centavos COP, frozen
    account_id: Annotated[int, Field(foreign_key="account.id")]
    category_id: Annotated[Optional[int], Field(default=None, foreign_key="category.id")] = None
    transfer_group_id: Annotated[Optional[str], Field(default=None, index=True)] = None
    source: Source = Source.manual
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Tag(SQLModel, table=True):
    id: Annotated[Optional[int], Field(default=None, primary_key=True)] = None
    name: Annotated[str, Field(index=True, unique=True)]


class TransactionTag(SQLModel, table=True):
    __tablename__ = "transaction_tag"
    transaction_id: Annotated[int, Field(foreign_key="transaction.id", primary_key=True)]
    tag_id: Annotated[int, Field(foreign_key="tag.id", primary_key=True)]


class FxRate(SQLModel, table=True):
    __tablename__ = "fx_rate"
    id: Annotated[Optional[int], Field(default=None, primary_key=True)] = None
    date: Annotated[date, Field(index=True, unique=True)]
    usd_cop: Annotated[Decimal, Field(sa_column=Column(Numeric(18, 6)))]


class Settings(SQLModel, table=True):
    id: Annotated[Optional[int], Field(default=1, primary_key=True)] = 1
    base_currency: str = "COP"
    default_source_account_id: Annotated[Optional[int], Field(default=None, foreign_key="account.id")] = None
