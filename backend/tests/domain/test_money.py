from decimal import Decimal

import pytest
from quaestor.domain import money
from quaestor.domain.errors import ValidationError
from quaestor.domain.money import Money


def test_major_to_cents_rounds_half_up():
    assert money.major_to_cents("12.00") == 1200
    assert money.major_to_cents("0.005") == 1


def test_cents_to_major():
    assert money.cents_to_major(1200) == Decimal("12.00")


def test_to_cop_cents_usd_converts_at_trm():
    assert money.to_cop_cents(1200, "USD", Decimal("4150")) == 4_980_000


def test_to_cop_cents_cop_ignores_the_trm():
    assert money.to_cop_cents(5000, "COP", Decimal("4150")) == 5000


def test_to_cop_cents_one_usd_cent_rounds_half_up():
    assert money.to_cop_cents(1, "USD", Decimal("4122.50")) == 4123


def test_to_cop_cents_three_usd_cents_round_half_up():
    assert money.to_cop_cents(3, "USD", Decimal("4122.50")) == 12368


def test_to_cop_cents_fractional_trm_rounds_half_up():
    assert money.to_cop_cents(100, "USD", Decimal("3.335")) == 334


def test_implied_rate_is_received_over_sent():
    assert money.implied_rate(10_000, 40_000_000) == Decimal("4000")


def test_implied_rate_keeps_precision():
    assert money.implied_rate(10_000, 5_000) == Decimal("0.5")


def test_implied_rate_rejects_non_positive_amounts():
    with pytest.raises(ValidationError):
        money.implied_rate(0, 40_000_000)
    with pytest.raises(ValidationError):
        money.implied_rate(10_000, 0)
    with pytest.raises(ValidationError):
        money.implied_rate(-100, 40_000_000)


def test_implied_rate_accepts_one_cent_legs():
    assert money.implied_rate(1, 1) == Decimal("1")


def test_money_from_major_and_format():
    m = Money.from_major("12.50", "USD")
    assert m.cents == 1250
    assert m.format() == "12.50 USD"


def test_money_rejects_unsupported_currency():
    with pytest.raises(ValueError):
        Money(100, "EUR")
