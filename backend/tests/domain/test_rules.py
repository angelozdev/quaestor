import pytest
from quaestor.domain import rules
from quaestor.domain.models import TxType


def test_income_adds():
    assert rules.delta_balance(TxType.income, 5000) == 5000


def test_expense_subtracts():
    assert rules.delta_balance(TxType.expense, 5000) == -5000


def test_transfer_type_is_rejected_by_delta_balance():
    with pytest.raises(ValueError):
        rules.delta_balance(TxType.transfer, 5000)


def test_transfer_deltas_are_mirrored():
    assert rules.transfer_deltas(5000) == (-5000, 5000)
