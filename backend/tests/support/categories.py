"""The category a test files money under when it is not about categories.

Mandatory since feature 008 (ADR-0042): every expense and income carries one.
A test that pins ordering, balances, FX or the recurring engine still has to
say what its money was for, so it says this — one category per direction per
session, created on first use.
"""

from quaestor.domain.models import TxType
from quaestor.domain.rules import category_is_income_for
from quaestor.services.categories import create_category, list_categories

EXPENSE_CATEGORY_NAME = "Test expenses"
INCOME_CATEGORY_NAME = "Test income"

_NAMES = {False: EXPENSE_CATEGORY_NAME, True: INCOME_CATEGORY_NAME}


def a_category(session, tx_type: TxType = TxType.expense) -> int:
    """Id of this session's category for that direction."""
    name = _NAMES[category_is_income_for(tx_type)]
    return a_named_category(session, name, tx_type)


def a_named_category(session, name: str, tx_type: TxType = TxType.expense) -> int:
    """Id of a category with this exact name, created once per session."""
    is_income = category_is_income_for(tx_type)
    existing = next((cat for cat in list_categories(session) if cat.name == name), None)
    if existing is not None:
        return existing.id
    return create_category(session, name, is_income=is_income).id
