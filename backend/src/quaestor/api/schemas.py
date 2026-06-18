"""Pydantic request/response models. `*Out` mirror the SQLModel rows (cents as int)."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ..domain.models import AccountType


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
