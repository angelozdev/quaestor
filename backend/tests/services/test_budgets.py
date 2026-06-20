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


from quaestor.services import planned, recurring
from quaestor.domain.models import IntervalUnit, RecurringMode, TxType


def _income(session, acc, amount=1_000_000, start=date(2026, 6, 1)):
    return recurring.create_recurring(
        session, name="Salary", payee="Job", type=TxType.income, mode=RecurringMode.manual,
        amount=amount, currency="COP", category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=start,
    )


def test_safe_to_spend_basic_cascade(session):
    acc = _acc(session)
    cat = _cat(session)
    _income(session, acc)  # 1,000,000 forecast
    budgets.set_budget(session, cat.id, "2026-06", 300_000)
    planned.plan_payment(session, payee="Rent", amount=200_000, currency="COP",
                         due_date=date(2026, 6, 15), account_id=acc.id)  # no category -> committed
    sts = budgets.safe_to_spend(session, "2026-06")
    assert sts.income_forecast == 1_000_000
    assert sts.committed == 200_000
    assert sts.assigned_envelopes == 300_000
    assert sts.free == 500_000
    assert any(ci.kind == "planned" for ci in sts.committed_breakdown)


def test_safe_to_spend_optional_envelopes_do_not_subtract_twice(session):
    acc = _acc(session)
    env = _cat(session, name="Groceries")
    unb = _cat(session, name="Fun")
    _income(session, acc)
    budgets.set_budget(session, env.id, "2026-06", 200_000)
    transactions.record_expense(session, acc.id, 150_000, "COP", date(2026, 6, 10), "in envelope", category_id=env.id)
    transactions.record_expense(session, acc.id, 100_000, "COP", date(2026, 6, 11), "no envelope", category_id=unb.id)
    sts = budgets.safe_to_spend(session, "2026-06")
    # envelope spend claimed by assignment (200k), only unbudgeted 100k extra
    assert sts.free == 700_000  # 1,000,000 - 0 - 200,000 - 100,000 - 0


def test_safe_to_spend_double_count_guard_auto_recurring(session):
    acc = _acc(session)
    _income(session, acc)
    recurring.create_recurring(
        session, name="Netflix", payee="Netflix", type=TxType.expense, mode=RecurringMode.auto,
        amount=250_000, currency="COP", category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 6, 5),
    )
    free_before = budgets.safe_to_spend(session, "2026-06").free
    recurring.materialize_due(session, date(2026, 6, 30))  # posts the recurring tx
    free_after = budgets.safe_to_spend(session, "2026-06").free
    assert free_before == 750_000 == free_after  # posting doesn't move it


def test_safe_to_spend_due_driven_stability_manual(session):
    acc = _acc(session)
    _income(session, acc)
    recurring.create_recurring(
        session, name="Gym", payee="Gym", type=TxType.expense, mode=RecurringMode.manual,
        amount=80_000, currency="COP", category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 6, 20),
    )
    recurring.materialize_due(session, date(2026, 6, 5))  # nothing due yet
    free_day5 = budgets.safe_to_spend(session, "2026-06").free
    recurring.materialize_due(session, date(2026, 6, 25))  # now a planned occurrence exists
    free_day25 = budgets.safe_to_spend(session, "2026-06").free
    assert free_day5 == 920_000 == free_day25  # committed projects the month regardless


def test_safe_to_spend_confirm_planned_does_not_move_it(session):
    acc = _acc(session)
    _income(session, acc)
    tx = planned.plan_payment(session, payee="Vet", amount=120_000, currency="COP",
                              due_date=date(2026, 6, 15), account_id=acc.id)  # no category
    free_before = budgets.safe_to_spend(session, "2026-06").free
    planned.confirm_payment(session, tx.id)  # planned expense -> posted unbudgeted
    free_after = budgets.safe_to_spend(session, "2026-06").free
    assert free_before == 880_000 == free_after


def test_safe_to_spend_overspend_reduces_pool_and_rollover_protects(session):
    acc = _acc(session)
    cat = _cat(session, name="Dining")
    _income(session, acc)
    # May builds rollover_in for June: assigned 100k, spent 30k -> available 70k
    budgets.set_budget(session, cat.id, "2026-05", 100_000)
    transactions.record_expense(session, acc.id, 30_000, "COP", date(2026, 5, 10), "may", category_id=cat.id)
    budgets.set_budget(session, cat.id, "2026-06", 50_000)
    # June overspends: spent 200k vs assigned 50k + rollover 70k = 120k -> overspend 80k
    transactions.record_expense(session, acc.id, 200_000, "COP", date(2026, 6, 10), "jun", category_id=cat.id)
    sts = budgets.safe_to_spend(session, "2026-06")
    assert sts.free == 870_000  # 1,000,000 - 0 - 50,000 - 0 - 80,000


def test_safe_to_spend_rollover_protects_against_false_overspend(session):
    acc = _acc(session)
    cat = _cat(session, name="Dining")
    _income(session, acc)
    budgets.set_budget(session, cat.id, "2026-05", 100_000)
    transactions.record_expense(session, acc.id, 30_000, "COP", date(2026, 5, 10), "may", category_id=cat.id)
    budgets.set_budget(session, cat.id, "2026-06", 50_000)
    transactions.record_expense(session, acc.id, 100_000, "COP", date(2026, 6, 10), "jun", category_id=cat.id)
    sts = budgets.safe_to_spend(session, "2026-06")
    # spent 100k <= assigned 50k + rollover 70k = 120k -> overspend 0
    assert sts.free == 950_000  # 1,000,000 - 0 - 50,000 - 0 - 0


def test_safe_to_spend_goal_proposals_not_counted_as_committed(session):
    from quaestor.services import accounts as accs, goals as goals_svc
    from quaestor.domain.models import AccountType, GoalStatus
    acc = _acc(session)
    sav = accs.create_account(session, "Savings", AccountType.savings, "COP", balance=0)
    _income(session, acc)  # 1,000,000 forecast
    g = goals_svc.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    goals_svc.propose_goal_contributions("2026-06", session)
    session.commit()
    sts = budgets.safe_to_spend(session, "2026-06")
    # Goal proposals are transfers, not expenses — must NOT be in committed
    assert sts.committed == 0
    assert sts.free == 1_000_000
