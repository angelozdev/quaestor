from decimal import Decimal

import pytest
from quaestor.domain.errors import MissingRate, ValidationError
from quaestor.services import fx


def test_set_and_read_trm(session):
    fx.set_trm(session, "4150")
    assert fx.get_trm(session) == Decimal("4150")


def test_set_trm_overwrites_last_write_wins(session):
    fx.set_trm(session, "4150")
    fx.set_trm(session, "4200")
    assert fx.get_trm(session) == Decimal("4200")


def test_get_trm_unset_raises_missing_rate_naming_the_trm(session):
    with pytest.raises(MissingRate) as exc_info:
        fx.get_trm(session)
    assert "trm" in str(exc_info.value).lower()


def test_set_trm_rejects_zero(session):
    with pytest.raises(ValidationError):
        fx.set_trm(session, "0")


def test_set_trm_rejects_negative(session):
    with pytest.raises(ValidationError):
        fx.set_trm(session, "-100")


def test_rejected_set_keeps_previous_trm(session):
    fx.set_trm(session, "4000")
    with pytest.raises(ValidationError):
        fx.set_trm(session, "-1")
    assert fx.get_trm(session) == Decimal("4000")


def test_set_trm_returns_the_decimal(session):
    assert fx.set_trm(session, 4100.5) == Decimal("4100.5")


def test_set_trm_accepts_rates_at_or_below_one(session):
    fx.set_trm(session, "0.5")
    assert fx.get_trm(session) == Decimal("0.5")
