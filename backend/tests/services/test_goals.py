from datetime import date

import pytest

from quaestor.domain.errors import NotFound, ValidationError
from quaestor.domain.models import AccountType, GoalStatus
from quaestor.services import accounts, goals


def _savings(session, archived=False):
    acc = accounts.create_account(session, "Savings", AccountType.savings, "COP", balance=0)
    if archived:
        accounts.archive_account(session, acc.id)
    return acc


def test_create_defined_goal(session):
    sav = _savings(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000,
                          savings_account_id=sav.id, target_amount=1_200_000,
                          deadline=date(2026, 12, 1))
    assert g.id is not None and g.status == GoalStatus.active
    assert g.target_amount == 1_200_000 and g.deadline == date(2026, 12, 1)


def test_create_open_ended_goal(session):
    sav = _savings(session)
    g = goals.create_goal(session, name="Buffer", monthly_amount=100_000, savings_account_id=sav.id)
    assert g.target_amount is None and g.deadline is None


def test_create_goal_only_target_raises(session):
    sav = _savings(session)
    with pytest.raises(ValidationError):
        goals.create_goal(session, name="x", monthly_amount=100_000,
                          savings_account_id=sav.id, target_amount=500_000)


def test_create_goal_only_deadline_raises(session):
    sav = _savings(session)
    with pytest.raises(ValidationError):
        goals.create_goal(session, name="x", monthly_amount=100_000,
                          savings_account_id=sav.id, deadline=date(2026, 12, 1))


def test_create_goal_rejects_non_positive_monthly(session):
    sav = _savings(session)
    with pytest.raises(ValidationError):
        goals.create_goal(session, name="x", monthly_amount=0, savings_account_id=sav.id)


def test_create_goal_rejects_non_savings_account(session):
    acc = accounts.create_account(session, "Checking", AccountType.debit, "COP", balance=0)
    with pytest.raises(ValidationError):
        goals.create_goal(session, name="x", monthly_amount=100_000, savings_account_id=acc.id)


def test_create_goal_rejects_archived_savings(session):
    sav = _savings(session, archived=True)
    with pytest.raises(ValidationError):
        goals.create_goal(session, name="x", monthly_amount=100_000, savings_account_id=sav.id)


def test_create_goal_rejects_unknown_account(session):
    with pytest.raises(ValidationError):
        goals.create_goal(session, name="x", monthly_amount=100_000, savings_account_id=999)


from quaestor.domain.models import TxType
from quaestor.services import settings as settings_svc, transactions


def _funded(session):
    src = accounts.create_account(session, "Checking", AccountType.debit, "COP", balance=1_000_000)
    sav = accounts.create_account(session, "Savings", AccountType.savings, "COP", balance=0)
    settings_svc.update_settings(session, default_source_account_id=src.id)
    return src, sav


def test_goal_contribution_creates_manual_contribution_and_transfer(session):
    src, sav = _funded(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    c = goals.goal_contribution(session, g.id, 150_000, date(2026, 6, 15))
    assert c.source.value == "manual" and c.amount == 150_000
    assert c.transaction_id is not None
    assert accounts.get_account(session, src.id).balance == 850_000
    assert accounts.get_account(session, sav.id).balance == 150_000


def test_goal_contribution_is_not_expense_or_income(session):
    src, sav = _funded(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    goals.goal_contribution(session, g.id, 150_000, date(2026, 6, 15))
    assert transactions.list_transactions(session, type=TxType.expense) == []
    assert transactions.list_transactions(session, type=TxType.income) == []
    transfers = transactions.list_transactions(session, type=TxType.transfer, status="posted")
    assert len(transfers) == 2


def test_goal_contribution_without_default_source_is_atomic(session):
    sav = accounts.create_account(session, "Savings", AccountType.savings, "COP", balance=0)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    with pytest.raises(ValidationError):
        goals.goal_contribution(session, g.id, 150_000, date(2026, 6, 15))
    from sqlmodel import select
    from quaestor.domain.models import GoalContribution
    assert session.exec(select(GoalContribution)).all() == []  # nothing recorded


def test_goal_contribution_reaching_target_marks_reached(session):
    src, sav = _funded(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id,
                          target_amount=300_000, deadline=date(2026, 12, 1))
    goals.goal_contribution(session, g.id, 300_000, date(2026, 6, 15))
    from quaestor.domain.models import Goal, GoalStatus
    assert session.get(Goal, g.id).status == GoalStatus.reached


def test_goal_contribution_rejects_bad_amount_and_unknown_goal(session):
    src, sav = _funded(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    with pytest.raises(ValidationError):
        goals.goal_contribution(session, g.id, 0, date(2026, 6, 15))
    with pytest.raises(NotFound):
        goals.goal_contribution(session, 999, 100_000, date(2026, 6, 15))
