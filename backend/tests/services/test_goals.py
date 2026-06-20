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
