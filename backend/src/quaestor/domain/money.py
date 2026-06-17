"""Money arithmetic: integer cents, FX conversion, formatting."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

BASE_CURRENCY = "COP"
SUPPORTED_CURRENCIES = ("COP", "USD")
SCALE = 100  # COP and USD use 2 decimals


def is_supported(currency: str) -> bool:
    return currency in SUPPORTED_CURRENCIES


def major_to_cents(value) -> int:
    """'12.34' -> 1234 (half-up rounding to cent)."""
    cents = (Decimal(str(value)) * SCALE).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(cents)


def cents_to_major(cents: int) -> Decimal:
    """1234 -> Decimal('12.34')."""
    return (Decimal(cents) / SCALE).quantize(Decimal("0.01"))


def to_base_cents(amount_cents: int, fx_rate: Decimal) -> int:
    """Original currency cents -> COP cents, frozen at registration."""
    base = (Decimal(amount_cents) * Decimal(str(fx_rate))).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    return int(base)


@dataclass(frozen=True)
class Money:
    cents: int
    currency: str

    def __post_init__(self) -> None:
        if not is_supported(self.currency):
            raise ValueError(f"unsupported currency: {self.currency}")

    @classmethod
    def from_major(cls, value, currency: str) -> "Money":
        return cls(major_to_cents(value), currency)

    def format(self) -> str:
        return f"{cents_to_major(self.cents)} {self.currency}"
