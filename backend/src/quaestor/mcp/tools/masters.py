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

from ...domain.errors import NotFound, ValidationError
from ...domain.models import Account
from ...services import accounts, categories, tags
from .. import format
from .core import _as_text, _resolve_account, _resolve_category


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


# ===== categories =====


class CreateCategoryInput(BaseModel):
    name: str = Field(min_length=1, max_length=80, description="Category name")
    group: str | None = Field(default=None, description="Category group name (optional)")
    is_income: bool = Field(default=False, description="Income category flag")
    exclude_from_budget: bool = Field(default=False, description="Exclude from budget")
    exclude_from_totals: bool = Field(default=False, description="Exclude from totals")


class UpdateCategoryInput(BaseModel):
    category: str = Field(description="Category name")
    name: str | None = Field(default=None, description="New name")
    group: str | None = Field(default=None, description="New group name (None to clear)")
    is_income: bool | None = Field(default=None, description="New income flag")
    exclude_from_budget: bool | None = Field(default=None, description="New exclude_from_budget")
    exclude_from_totals: bool | None = Field(default=None, description="New exclude_from_totals")


class ArchiveCategoryInput(BaseModel):
    category: str = Field(description="Category name")


class RestoreCategoryInput(BaseModel):
    category: str = Field(description="Category name")


class GetCategoryInput(BaseModel):
    category: str = Field(description="Category name")


def _resolve_category_group(session: Session, name: str):
    """Resolve a category group by name (case-insensitive). Raise ValidationError with hints."""
    all_groups = categories.list_groups(session, include_archived=True)
    target = name.strip().lower()
    for g in all_groups:
        if g.name.lower() == target:
            return g
    available = ", ".join(g.name for g in all_groups) or "(none)"
    raise ValidationError(
        f"category group '{name}' not found. Available: {available}."
    )


def _category_group_by_id(session: Session, group_id: int):
    """Look up a category group by id; returns None if missing."""
    for g in categories.list_groups(session, include_archived=True):
        if g.id == group_id:
            return g
    return None


@_as_text
def create_category(session: Session, inp: CreateCategoryInput) -> str:
    group = _resolve_category_group(session, inp.group) if inp.group else None
    cat = categories.create_category(
        session,
        name=inp.name,
        group_id=group.id if group else None,
        is_income=inp.is_income,
        exclude_from_budget=inp.exclude_from_budget,
        exclude_from_totals=inp.exclude_from_totals,
    )
    return format.category_card(cat, group)


@_as_text
def update_category(session: Session, inp: UpdateCategoryInput) -> str:
    cat = _resolve_category(session, inp.category)
    group_id = categories._UNSET  # unchanged by default
    group_for_card = None
    if inp.group is not None:
        if inp.group == "":
            group_id = None  # explicitly clear
            group_for_card = None
        else:
            g = _resolve_category_group(session, inp.group)
            group_id = g.id
            group_for_card = g
    updated = categories.update_category(
        session,
        cat.id,
        name=inp.name,
        group_id=group_id,
        is_income=inp.is_income,
        exclude_from_budget=inp.exclude_from_budget,
        exclude_from_totals=inp.exclude_from_totals,
    )
    return format.category_card(updated, group_for_card)


@_as_text
def archive_category(session: Session, inp: ArchiveCategoryInput) -> str:
    cat = _resolve_category(session, inp.category)
    archived = categories.archive_category(session, cat.id)
    return f"✅ archived **{archived.name}** (id={archived.id})."


@_as_text
def restore_category(session: Session, inp: RestoreCategoryInput) -> str:
    cat = _resolve_category(session, inp.category)
    restored = categories.unarchive_category(session, cat.id)
    group = _category_group_by_id(session, restored.group_id)
    return format.category_card(restored, group)


@_as_text
def get_category(session: Session, inp: GetCategoryInput) -> str:
    cat = _resolve_category(session, inp.category)
    group = _category_group_by_id(session, cat.group_id)
    return format.category_card(cat, group)


# ===== category groups =====


class CreateCategoryGroupInput(BaseModel):
    name: str = Field(min_length=1, max_length=80, description="Group name")
    sort_order: int = Field(default=0, description="Display order")


class UpdateCategoryGroupInput(BaseModel):
    group: str = Field(description="Category group name")
    name: str | None = Field(default=None, description="New name")
    sort_order: int | None = Field(default=None, description="New display order")


class ArchiveCategoryGroupInput(BaseModel):
    group: str = Field(description="Category group name")


class RestoreCategoryGroupInput(BaseModel):
    group: str = Field(description="Category group name")


@_as_text
def create_category_group(session: Session, inp: CreateCategoryGroupInput) -> str:
    g = categories.create_group(session, name=inp.name, sort_order=inp.sort_order)
    return format.category_group_card(g)


@_as_text
def update_category_group(session: Session, inp: UpdateCategoryGroupInput) -> str:
    g = _resolve_category_group(session, inp.group)
    updated = categories.update_group(
        session, g.id, name=inp.name, sort_order=inp.sort_order
    )
    return format.category_group_card(updated)


@_as_text
def archive_category_group(session: Session, inp: ArchiveCategoryGroupInput) -> str:
    g = _resolve_category_group(session, inp.group)
    archived = categories.archive_group(session, g.id)
    return f"✅ archived **{archived.name}** (id={archived.id})."


@_as_text
def restore_category_group(session: Session, inp: RestoreCategoryGroupInput) -> str:
    g = _resolve_category_group(session, inp.group)
    restored = categories.unarchive_group(session, g.id)
    return f"✅ restored **{restored.name}** (id={restored.id})."


# ===== tags =====


class CreateTagInput(BaseModel):
    name: str = Field(min_length=1, max_length=40, description="Tag name")


class UpdateTagInput(BaseModel):
    tag: str = Field(description="Existing tag name")
    name: str = Field(min_length=1, max_length=40, description="New name")


class DeleteTagInput(BaseModel):
    tag: str = Field(description="Tag name to delete")


def _resolve_tag(session: Session, name: str):
    target = name.strip().lower()
    for t in tags.list_tags(session):
        if t.name.lower() == target:
            return t
    available = ", ".join(t.name for t in tags.list_tags(session)) or "(none)"
    raise NotFound(f"Tag '{name}' not found. Available: {available}.")


@_as_text
def create_tag(session: Session, inp: CreateTagInput) -> str:
    tag = tags.create_tag(session, inp.name)
    return format.tag_card(tag)


@_as_text
def update_tag(session: Session, inp: UpdateTagInput) -> str:
    tag = _resolve_tag(session, inp.tag)
    updated = tags.update_tag(session, tag.id, inp.name)
    return format.tag_card(updated)


@_as_text
def delete_tag(session: Session, inp: DeleteTagInput) -> str:
    tag = _resolve_tag(session, inp.tag)
    tags.delete_tag(session, tag.id)
    return f"Deleted tag '{tag.name}'."
