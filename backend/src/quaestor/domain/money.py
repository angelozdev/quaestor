"""Money arithmetic: integer cents, read-time FX conversion, formatting.

ADR-0031: base-currency (COP) figures are never stored; `to_cop_cents` is the
single conversion gate every read path goes through with the current TRM.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from .errors import ValidationError

BASE_CURRENCY = "COP"
SUPPORTED_CURRENCIES = ("COP", "USD")
CENTS_PER_MAJOR = 100


def is_supported(currency: str) -> bool:
    return currency in SUPPORTED_CURRENCIES


def major_to_cents(value) -> int:
    """'12.34' -> 1234 (half-up rounding to cent)."""
    cents = (Decimal(str(value)) * CENTS_PER_MAJOR).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(cents)


def cents_to_major(cents: int) -> Decimal:
    """1234 -> Decimal('12.34')."""
    return (Decimal(cents) / CENTS_PER_MAJOR).quantize(Decimal("0.01"))


def to_cop_cents(amount_cents: int, currency: str, trm: Decimal) -> int:
    """Original-currency cents -> COP cents at the current TRM (read time).

    COP converts at identity (the TRM never touches it); USD multiplies by
    the TRM with half-up rounding to the COP cent.
    """
    if currency == BASE_CURRENCY:
        return amount_cents
    cop = (Decimal(amount_cents) * trm).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(cop)


def implied_rate(sent_cents: int, received_cents: int) -> Decimal:
    """Effective rate of a cross-currency transfer: received / sent.

    Information only (AC-8): shown live in the transfer form, never stored
    and never validated against a market rate.
    """
    if sent_cents <= 0 or received_cents <= 0:
        raise ValidationError("implied rate needs positive sent and received amounts")
    return Decimal(received_cents) / Decimal(sent_cents)


@dataclass(frozen=True)
class Money:
    cents: int
    currency: str

    def __post_init__(self) -> None:
        if not is_supported(self.currency):
            raise ValueError(f"unsupported currency: {self.currency}")

    @classmethod
    def from_major(cls, value, currency: str) -> Money:
        return cls(major_to_cents(value), currency)

    def format(self) -> str:
        return f"{cents_to_major(self.cents)} {self.currency}"
