from datetime import date
from decimal import Decimal

import pytest

from quaestor.domain.errors import MissingRate, ValidationError
from quaestor.services import fx


def test_set_and_read_rate(session):
    fx.set_fx_rate(session, date(2026, 6, 1), "4150")
    assert fx.get_current_rate(session, date(2026, 6, 1)) == Decimal("4150")


def test_upsert_by_date(session):
    fx.set_fx_rate(session, date(2026, 6, 1), "4150")
    fx.set_fx_rate(session, date(2026, 6, 1), "4200")  # same day -> updates
    assert fx.get_current_rate(session, date(2026, 6, 1)) == Decimal("4200")


def test_current_rate_uses_last_prior(session):
    fx.set_fx_rate(session, date(2026, 6, 1), "4100")
    fx.set_fx_rate(session, date(2026, 6, 10), "4300")
    assert fx.get_current_rate(session, date(2026, 6, 7)) == Decimal("4100")
    assert fx.get_current_rate(session, date(2026, 6, 12)) == Decimal("4300")


def test_missing_rate(session):
    with pytest.raises(MissingRate):
        fx.get_current_rate(session, date(2026, 6, 1))


def test_invalid_rate(session):
    with pytest.raises(ValidationError):
        fx.set_fx_rate(session, date(2026, 6, 1), "0")
