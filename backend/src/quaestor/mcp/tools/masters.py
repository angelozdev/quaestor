"""MCP masters tools (ADR-0009): accounts, categories, category-groups, tags.

One module hosts the input models + the per-entity impls for all four master
entities so each task (accounts / categories / groups / tags) can land
independently while sharing helpers (resolve-by-name, register functions).

Tasks 3-6 each add input models, impls, and a `register_<entity>_tools(mcp)`
function. Task 13 wires them all into the FastMCP instance via the registry.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from sqlmodel import Session

from ...domain.errors import NotFound
from ...domain.models import Account
from ...services import accounts, categories, tags
from .. import format
from .core import _as_text, _resolve_account


# ===== accounts =====


class CreateAccountInput(BaseModel):
    name: str = Field(min_length=1, max_length=80, description="Account name")
    type: Literal["debit", "credit", "cash", "savings"] = Field(description="Account type")
    currency: str = Field(default="COP", description="ISO currency code; defaults to COP")
    initial_balance_cents: int = Field(default=0, ge=0, description="Initial balance in cents")


class UpdateAccountInput(BaseModel):
    account: str = Field(description="Account name")
    name: str | None = Field(default=None, description="New name")
    type: Literal["debit", "credit", "cash", "savings"] | None = Field(
        default=None, description="New type"
    )


class ArchiveAccountInput(BaseModel):
    account: str = Field(description="Account name")


class RestoreAccountInput(BaseModel):
    account: str = Field(description="Account name")


class GetAccountInput(BaseModel):
    account: str = Field(description="Account name")


@_as_text
def create_account(session: Session, inp: CreateAccountInput) -> str:
    acc = accounts.create_account(
        session,
        name=inp.name,
        type=inp.type,
        currency=inp.currency,
        balance=inp.initial_balance_cents,
    )
    return format.account_card(acc)


@_as_text
def update_account(session: Session, inp: UpdateAccountInput) -> str:
    acc = _resolve_account(session, inp.account)
    updated = accounts.update_account(
        session, acc.id, name=inp.name, type=inp.type
    )
    return format.account_card(updated)


@_as_text
def archive_account(session: Session, inp: ArchiveAccountInput) -> str:
    # Include archived so re-archiving / restoring an already-archived account still resolves.
    all_accounts = accounts.list_accounts(session, include_archived=True)
    target = inp.account.strip().lower()
    match = next((a for a in all_accounts if a.name.lower() == target), None)
    if match is None:
        available = ", ".join(a.name for a in all_accounts) or "(none)"
        raise NotFound(f"Account '{inp.account}' not found. Available: {available}.")
    archived = accounts.archive_account(session, match.id)
    return f"✅ archived **{archived.name}** (id={archived.id})."


@_as_text
def restore_account(session: Session, inp: RestoreAccountInput) -> str:
    # Include archived so restoring an archived account resolves.
    all_accounts = accounts.list_accounts(session, include_archived=True)
    target = inp.account.strip().lower()
    match = next((a for a in all_accounts if a.name.lower() == target), None)
    if match is None:
        available = ", ".join(a.name for a in all_accounts) or "(none)"
        raise NotFound(f"Account '{inp.account}' not found. Available: {available}.")
    restored = accounts.unarchive_account(session, match.id)
    return f"✅ restored **{restored.name}** (id={restored.id})."


@_as_text
def get_account(session: Session, inp: GetAccountInput) -> str:
    acc = _resolve_account(session, inp.account)
    return format.account_card(acc)
