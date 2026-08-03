from datetime import date

from quaestor.mcp.tools import goals_reads
from quaestor.services import accounts, goals


def _bank(session):
    return accounts.create_account(session, "Savings", "savings", "COP", balance=0)


def test_list_goals_empty(session):
    out = goals_reads.list_goals(session, goals_reads.ListGoalsInput())
    assert out == "No goals."


def test_list_goals_table_with_one(session):
    _bank(session)
    goals.create_goal(
        session,
        name="Trip",
        monthly_amount=500_000,
        savings_account_id=1,
        target_amount=2_000_000,
        deadline=date(2026, 12, 31),
    )
    out = goals_reads.list_goals(session, goals_reads.ListGoalsInput())
    assert "Trip" in out and "| id |" in out


def test_goals_progress_empty(session):
    out = goals_reads.goals_progress(session, goals_reads.GoalsProgressInput())
    assert out == "No goal progress."


def test_goals_progress_active_goal(session):
    _bank(session)
    goals.create_goal(
        session,
        name="Trip",
        monthly_amount=500_000,
        savings_account_id=1,
        target_amount=2_000_000,
        deadline=date(2026, 12, 31),
    )
    out = goals_reads.goals_progress(session, goals_reads.GoalsProgressInput())
    assert "Trip" in out and "on-track" in out
