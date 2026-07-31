"""The TRM: one scalar USD→COP rate (ADR-0031, amended).

The daily job and manual corrections both go through ``set_trm`` (last
write wins). Every read path that produces COP figures calls ``get_trm``
once per request and converts via ``domain.money.to_cop_cents``.
"""
from __future__ import annotations

from decimal import Decimal

from sqlmodel import Session

from ..domain.errors import MissingRate, ValidationError
from ..domain.models import Settings

_SETTINGS_ID = 1


def set_trm(session: Session, usd_cop: Decimal | float | str) -> Decimal:
    """Overwrite the single TRM. Returns the stored Decimal.

    Raises:
        ValidationError: usd_cop <= 0.
    """
    rate = Decimal(str(usd_cop))
    if rate <= 0:
        raise ValidationError("usd_cop must be > 0")
    settings = session.get(Settings, _SETTINGS_ID)
    if settings is None:
        settings = Settings(id=_SETTINGS_ID)
    settings.usd_cop = rate
    session.add(settings)
    session.commit()
    return rate


def get_trm(session: Session) -> Decimal:
    """Current TRM.

    Raises:
        MissingRate: the TRM was never set (AC-9: reads fail loud; the app
            never assumes a rate of 1).
    """
    settings = session.get(Settings, _SETTINGS_ID)
    if settings is None or settings.usd_cop is None:
        raise MissingRate("no TRM set — set the USD→COP rate (TRM) first")
    return Decimal(str(settings.usd_cop))


def get_trm_or_none(session: Session) -> Decimal | None:
    """Current TRM, or None when unset — for writes, which must succeed
    without a TRM (AC-1). Reads use ``get_trm`` and fail loud."""
    try:
        return get_trm(session)
    except MissingRate:
        return None
