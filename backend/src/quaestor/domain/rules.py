"""Balance sign rules: the sign is determined by the type, not the amount."""
from __future__ import annotations

from .models import TxType


def delta_balance(tx_type: TxType, amount: int) -> int:
    """Centavos to add to the account balance (amount always positive)."""
    if tx_type == TxType.income:
        return amount
    if tx_type == TxType.expense:
        return -amount
    raise ValueError(
        "delta_balance only applies to expense/income; transfer uses transfer_deltas"
    )


def transfer_deltas(amount: int) -> tuple[int, int]:
    """(delta_from, delta_to) for an internal transfer."""
    return (-amount, amount)
