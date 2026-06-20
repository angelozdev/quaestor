from datetime import date

import pytest

from quaestor.domain.errors import NotFound, ValidationError
from quaestor.services import budgets, categories


def _cat(session, **kwargs):
    return categories.create_category(session, name=kwargs.pop("name", "Food"), **kwargs)


def test_set_budget_creates_envelope(session):
    cat = _cat(session)
    b = budgets.set_budget(session, cat.id, "2026-06", 300_000)
    assert b.id is not None
    assert b.category_id == cat.id and b.year_month == "2026-06"
    assert b.amount_assigned == 300_000


def test_set_budget_upserts_same_category_month(session):
    cat = _cat(session)
    first = budgets.set_budget(session, cat.id, "2026-06", 300_000)
    second = budgets.set_budget(session, cat.id, "2026-06", 450_000)
    assert second.id == first.id
    assert second.amount_assigned == 450_000


def test_set_budget_rejects_negative_amount(session):
    cat = _cat(session)
    with pytest.raises(ValidationError):
        budgets.set_budget(session, cat.id, "2026-06", -1)


def test_set_budget_rejects_malformed_year_month(session):
    cat = _cat(session)
    with pytest.raises(ValidationError):
        budgets.set_budget(session, cat.id, "2026-13", 100_000)
    with pytest.raises(ValidationError):
        budgets.set_budget(session, cat.id, "June", 100_000)


def test_set_budget_unknown_category_raises_not_found(session):
    with pytest.raises(NotFound):
        budgets.set_budget(session, 999, "2026-06", 100_000)
