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
    """Id of a category with this name, created once per session.

    Matched the way `create_category` refuses duplicates (AC-13): ignoring case
    and including archived ones. A stricter lookup here would miss a match the
    guard then rejects, and the helper would raise instead of returning an id.
    """
    is_income = category_is_income_for(tx_type)
    folded = name.casefold()
    existing = next(
        (
            cat
            for cat in list_categories(session, include_archived=True, is_income=is_income)
            if cat.name.casefold() == folded
        ),
        None,
    )
    if existing is not None:
        return existing.id
    return create_category(session, name, is_income=is_income).id
