"""FX rate use cases. Daily job (P7) populates this table; manual override available."""
from __future__ import annotations

from datetime import date as Date
from decimal import Decimal

from sqlmodel import Session, select

from ..domain.errors import MissingRate, ValidationError
from ..domain.models import FxRate


def fijar_tasa_fx(session: Session, date: Date, usd_cop) -> FxRate:
    rate = Decimal(str(usd_cop))
    if rate <= 0:
        raise ValidationError("usd_cop must be > 0")
    existing = session.exec(select(FxRate).where(FxRate.date == date)).first()
    if existing is not None:
        existing.usd_cop = rate
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    fr = FxRate(date=date, usd_cop=rate)
    session.add(fr)
    session.commit()
    session.refresh(fr)
    return fr


def tasa_vigente(session: Session, date: Date) -> Decimal:
    stmt = (
        select(FxRate)
        .where(FxRate.date <= date)
        .order_by(FxRate.date.desc())
    )
    fr = session.exec(stmt).first()
    if fr is None:
        raise MissingRate(f"set usd_cop rate for {date}")
    return Decimal(str(fr.usd_cop))
