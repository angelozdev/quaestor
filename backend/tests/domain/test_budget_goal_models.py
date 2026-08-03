from datetime import date

import pytest
from quaestor.db import init_db, make_engine
from quaestor.domain.models import (
    Account,
    AccountType,
    Budget,
    ContributionSource,
    Goal,
    GoalContribution,
    GoalStatus,
    Transaction,
    TxType,
)
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select


@pytest.fixture
def session():
    engine = make_engine(memory=True)
    init_db(engine)
    with Session(engine) as s:
        yield s


def test_budget_unique_per_category_and_month(session):
    session.add(Budget(category_id=1, year_month="2026-06", amount_assigned=100_000))
    session.commit()
    session.add(Budget(category_id=1, year_month="2026-06", amount_assigned=50_000))
    with pytest.raises(IntegrityError):
        session.commit()


def test_goal_defaults_to_active_and_allows_nullable_target(session):
    acc = Account(name="Savings", type=AccountType.savings, currency="COP")
    session.add(acc)
    session.commit()
    goal = Goal(name="Trip", monthly_amount=200_000, savings_account_id=acc.id)
    session.add(goal)
    session.commit()
    session.refresh(goal)
    assert goal.status == GoalStatus.active
    assert goal.target_amount is None and goal.deadline is None


def test_goal_contribution_links_goal_and_transaction(session):
    acc = Account(name="Savings", type=AccountType.savings, currency="COP")
    session.add(acc)
    session.commit()
    goal = Goal(name="Trip", monthly_amount=200_000, savings_account_id=acc.id)
    session.add(goal)
    session.commit()
    c = GoalContribution(
        goal_id=goal.id,
        date=date(2026, 6, 30),
        amount=200_000,
        source=ContributionSource.confirmed,
        transaction_id=None,
    )
    session.add(c)
    session.commit()
    rows = session.exec(select(GoalContribution).where(GoalContribution.goal_id == goal.id)).all()
    assert len(rows) == 1 and rows[0].source == ContributionSource.confirmed


def test_transaction_has_goal_id_column(session):
    acc = Account(name="Bank", type=AccountType.debit, currency="COP")
    session.add(acc)
    session.commit()
    goal = Goal(name="Trip", monthly_amount=200_000, savings_account_id=acc.id)
    session.add(goal)
    session.commit()
    tx = Transaction(
        date=date(2026, 6, 30),
        type=TxType.transfer,
        amount=200_000,
        currency="COP",
        account_id=acc.id,
        goal_id=goal.id,
    )
    session.add(tx)
    session.commit()
    session.refresh(tx)
    assert tx.goal_id == goal.id
