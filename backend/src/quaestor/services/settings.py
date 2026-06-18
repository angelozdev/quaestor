"""Settings singleton use cases (id=1 row, seeded by init_db)."""
from __future__ import annotations

from sqlmodel import Session

from ..domain.errors import ValidationError
from ..domain.models import Account, Settings
from ..domain.money import is_supported

_UNSET = object()


def get_settings(session: Session) -> Settings:
    """Return the singleton Settings row, seeding it if absent."""
    s = session.get(Settings, 1)
    if s is None:
        s = Settings(id=1, base_currency="COP")
        session.add(s)
        session.commit()
        session.refresh(s)
    return s


def update_settings(
    session: Session, base_currency=None, default_source_account_id=_UNSET
) -> Settings:
    """Update app settings.

    Raises:
        ValidationError: Unsupported base_currency, or a default_source_account_id
            that does not reference an existing account.
    """
    s = get_settings(session)
    if base_currency is not None:
        if not is_supported(base_currency):
            raise ValidationError(f"unsupported currency: {base_currency}")
        s.base_currency = base_currency
    if default_source_account_id is not _UNSET:
        if (
            default_source_account_id is not None
            and session.get(Account, default_source_account_id) is None
        ):
            raise ValidationError(f"account {default_source_account_id} does not exist")
        s.default_source_account_id = default_source_account_id
    session.add(s)
    session.commit()
    session.refresh(s)
    return s
