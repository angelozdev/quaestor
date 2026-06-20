from datetime import date

import pytest

from quaestor.domain.errors import NotFound, ValidationError
from quaestor.domain.models import AccountType
from quaestor.services import accounts, budgets, categories, transactions
from quaestor.services.budgets import budget_status as budget_status_for


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


def _acc(session, balance=10_000_000):
    return accounts.create_account(session, "Bank", AccountType.debit, "COP", balance=balance)


def test_budget_status_sums_only_expense_posted_in_month_category(session):
    cat = _cat(session)
    other = _cat(session, name="Other")
    acc = _acc(session)
    budgets.set_budget(session, cat.id, "2026-06", 100_000)
    transactions.record_expense(session, acc.id, 20_000, "COP", date(2026, 6, 10), "x", category_id=cat.id)
    transactions.record_expense(session, acc.id, 5_000, "COP", date(2026, 7, 1), "next month", category_id=cat.id)
    transactions.record_expense(session, acc.id, 9_000, "COP", date(2026, 6, 12), "other cat", category_id=other.id)
    transactions.record_income(session, acc.id, 50_000, "COP", date(2026, 6, 12), "salary", category_id=cat.id)
    s = budget_status_for(session, cat.id, "2026-06")
    assert s.spent == 20_000
    assert s.assigned == 100_000
    assert s.available == 80_000
    assert s.status == "under"


def test_budget_status_ignores_planned(session):
    from quaestor.services import planned
    cat = _cat(session)
    acc = _acc(session)
    budgets.set_budget(session, cat.id, "2026-06", 100_000)
    planned.plan_payment(session, payee="p", amount=40_000, currency="COP",
                         due_date=date(2026, 6, 15), account_id=acc.id, category_id=cat.id)
    s = budget_status_for(session, cat.id, "2026-06")
    assert s.spent == 0


def test_budget_status_respects_exclude_flags(session):
    cat = _cat(session, exclude_from_budget=True)
    acc = _acc(session)
    budgets.set_budget(session, cat.id, "2026-06", 100_000)
    transactions.record_expense(session, acc.id, 30_000, "COP", date(2026, 6, 10), "x", category_id=cat.id)
    s = budget_status_for(session, cat.id, "2026-06")
    assert s.spent == 0


def test_budget_status_positive_rollover_carries_over(session):
    cat = _cat(session)
    acc = _acc(session)
    budgets.set_budget(session, cat.id, "2026-05", 100_000)
    transactions.record_expense(session, acc.id, 30_000, "COP", date(2026, 5, 10), "may", category_id=cat.id)
    budgets.set_budget(session, cat.id, "2026-06", 50_000)
    transactions.record_expense(session, acc.id, 20_000, "COP", date(2026, 6, 10), "jun", category_id=cat.id)
    s = budget_status_for(session, cat.id, "2026-06")
    assert s.rollover_in == 70_000  # max(100k - 30k, 0)
    assert s.available == 100_000  # 70k + 50k - 20k


def test_budget_status_negative_rollover_resets_to_zero(session):
    cat = _cat(session)
    acc = _acc(session)
    budgets.set_budget(session, cat.id, "2026-05", 100_000)
    transactions.record_expense(session, acc.id, 150_000, "COP", date(2026, 5, 10), "overspent", category_id=cat.id)
    budgets.set_budget(session, cat.id, "2026-06", 50_000)
    s = budget_status_for(session, cat.id, "2026-06")
    assert s.rollover_in == 0  # max(-50k, 0)
