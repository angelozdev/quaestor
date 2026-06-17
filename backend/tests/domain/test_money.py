from decimal import Decimal

import pytest

from quaestor.domain import money
from quaestor.domain.money import Money


def test_major_to_cents_rounds_half_up():
    assert money.major_to_cents("12.00") == 1200
    assert money.major_to_cents("0.005") == 1   # 0.5 cent rounds up


def test_cents_to_major():
    assert money.cents_to_major(1200) == Decimal("12.00")


def test_to_base_cents_usd_to_cop():
    # 12.00 USD at 4150 COP/USD = 49.800,00 COP
    assert money.to_base_cents(1200, Decimal("4150")) == 4_980_000


def test_to_base_cents_cop_is_identity():
    assert money.to_base_cents(5000, Decimal("1")) == 5000


def test_to_base_cents_rounds_half_up():
    assert money.to_base_cents(100, Decimal("3.335")) == 334


def test_money_from_major_and_format():
    m = Money.from_major("12.50", "USD")
    assert m.cents == 1250
    assert m.format() == "12.50 USD"


def test_money_rejects_unsupported_currency():
    with pytest.raises(ValueError):
        Money(100, "EUR")
