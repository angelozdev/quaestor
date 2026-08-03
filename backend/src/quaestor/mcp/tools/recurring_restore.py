"""MCP recurring restore tool (ADR-0009): undo an archive_recurring call."""

from __future__ import annotations

from pydantic import BaseModel, Field
from sqlmodel import Session

from ...services import recurring
from .. import format
from .core import _as_text


class RestoreRecurringInput(BaseModel):
    recurring_id: int = Field(description="The recurring item id to restore")


@_as_text
def restore_recurring(session: Session, inp: RestoreRecurringInput) -> str:
    item = recurring.restore_recurring(session, inp.recurring_id)
    return format.recurring_restored(item)
