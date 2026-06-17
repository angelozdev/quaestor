from datetime import date
from decimal import Decimal

import pytest

from quaestor.domain.errors import MissingRate, ValidationError
from quaestor.services import fx


def test_fijar_y_leer_tasa(session):
    fx.fijar_tasa_fx(session, date(2026, 6, 1), "4150")
    assert fx.tasa_vigente(session, date(2026, 6, 1)) == Decimal("4150")


def test_upsert_por_fecha(session):
    fx.fijar_tasa_fx(session, date(2026, 6, 1), "4150")
    fx.fijar_tasa_fx(session, date(2026, 6, 1), "4200")  # mismo día -> actualiza
    assert fx.tasa_vigente(session, date(2026, 6, 1)) == Decimal("4200")


def test_tasa_vigente_toma_la_ultima_anterior(session):
    fx.fijar_tasa_fx(session, date(2026, 6, 1), "4100")
    fx.fijar_tasa_fx(session, date(2026, 6, 10), "4300")
    assert fx.tasa_vigente(session, date(2026, 6, 7)) == Decimal("4100")
    assert fx.tasa_vigente(session, date(2026, 6, 12)) == Decimal("4300")


def test_missing_rate(session):
    with pytest.raises(MissingRate):
        fx.tasa_vigente(session, date(2026, 6, 1))


def test_tasa_invalida(session):
    with pytest.raises(ValidationError):
        fx.fijar_tasa_fx(session, date(2026, 6, 1), "0")
