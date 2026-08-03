"""MCP settings tools (ADR-0009): get/update the singleton Settings row.

Lets the agent set `default_source_account_id`, which is required by
`contribute_goal` (services/goals.py).
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from sqlmodel import Session

from ...domain.errors import ValidationError
from ...domain.money import is_supported
from ...services import settings
from .. import format
from .core import _as_text, _resolve_account


class GetSettingsInput(BaseModel):
    pass


class UpdateSettingsInput(BaseModel):
    # NOTE: brief specified `Literal["COP", "USD"] | None`. Literal makes
    # Pydantic raise ValidationError at model construction (outside @_as_text),
    # so the test `test_update_settings_rejects_unsupported_currency` would
    # not get back "Invalid input" via the wrapper. To keep the brief's
    # test passing without modifying `core._as_text`, base_currency is typed
    # as `str | None` and validated inside `update_settings` (which raises
    # `domain.errors.ValidationError`; caught by `@_as_text` → "Invalid input").
    base_currency: str | None = Field(default=None, description="New base currency (COP or USD)")
    default_source_account: str | None = Field(
        default=None, description="New default source account name (None to clear)"
    )


@_as_text
def get_settings(session: Session, inp: GetSettingsInput) -> str:
    s = settings.get_settings(session)
    return format.settings_card(s)


@_as_text
def update_settings(session: Session, inp: UpdateSettingsInput) -> str:
    default_source_id = settings._UNSET  # unchanged by default
    if inp.default_source_account is not None:
        if inp.default_source_account == "":
            default_source_id = None
        else:
            default_source_id = _resolve_account(session, inp.default_source_account).id
    if inp.base_currency is not None and not is_supported(inp.base_currency):
        raise ValidationError(f"unsupported currency: {inp.base_currency}")
    updated = settings.update_settings(
        session,
        base_currency=inp.base_currency,
        default_source_account_id=default_source_id,
    )
    return format.settings_card(updated)
