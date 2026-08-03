from quaestor.mcp.tools import planning
from quaestor.mcp.tools.planning import AssignBudgetInput
from quaestor.services import budgets, categories, fx
from sqlmodel import Session


def test_mcp_assign_budget(engine):
    with Session(engine) as s:
        fx.set_trm(s, "4000")
        cat = categories.create_category(s, name="Food")
        out = planning.assign_budget(
            s, AssignBudgetInput(category="Food", year_month="2026-06", amount=500_000)
        )
        assert "Food" in out
        assert budgets.budget_status(s, cat.id, "2026-06").assigned == 500_000


def test_mcp_create_goal(engine):
    from quaestor.domain.models import AccountType
    from quaestor.mcp.tools.planning import CreateGoalInput
    from quaestor.services import accounts
    with Session(engine) as s:
        accounts.create_account(s, "Savings", AccountType.savings, "COP", balance=0)
        out = planning.create_goal(s, CreateGoalInput(name="Trip", monthly_amount=200_000, savings_account="Savings"))
        assert "Trip" in out
        from quaestor.services import goals
        assert [g.name for g in goals.list_goals(s)] == ["Trip"]


def test_mcp_update_goal(session):
    from quaestor.mcp.tools import planning
    from quaestor.mcp.tools.planning import CreateGoalInput, UpdateGoalInput
    from quaestor.services import accounts as _acc
    _acc.create_account(session, "Ahorro", "savings", "COP", balance=0)
    planning.create_goal(session, CreateGoalInput(
        name="Viaje", monthly_amount=500_000, savings_account="Ahorro",
    ))
    from quaestor.services import goals as _goals
    goal_id = _goals.list_goals(session)[0].id
    out = planning.update_goal(session, UpdateGoalInput(goal_id=goal_id, name="Viaje 2025"))
    assert "Viaje 2025" in out


def test_mcp_pause_restore_goal(session):
    from quaestor.mcp.tools import planning
    from quaestor.mcp.tools.planning import CreateGoalInput, GoalIdInput
    from quaestor.services import accounts as _acc
    from quaestor.services import goals as _goals
    _acc.create_account(session, "Ahorro", "savings", "COP", balance=0)
    planning.create_goal(session, CreateGoalInput(
        name="Moto", monthly_amount=300_000, savings_account="Ahorro",
    ))
    goal_id = _goals.list_goals(session)[0].id
    out = planning.pause_goal(session, GoalIdInput(goal_id=goal_id))
    assert "pausad" in out.lower() or "Moto" in out
    out2 = planning.restore_goal(session, GoalIdInput(goal_id=goal_id))
    assert "restaurad" in out2.lower() or "Moto" in out2


def test_mcp_contribute_goal(session):
    from quaestor.mcp.tools import planning
    from quaestor.mcp.tools.planning import ContributeGoalInput, CreateGoalInput
    from quaestor.services import accounts as _acc
    from quaestor.services import goals as _goals
    from quaestor.services import settings as _settings
    src = _acc.create_account(session, "Corriente", "debit", "COP", balance=1_000_000)
    _acc.create_account(session, "Ahorro", "savings", "COP", balance=0)
    _settings.update_settings(session, default_source_account_id=src.id)
    planning.create_goal(session, CreateGoalInput(
        name="Fondo", monthly_amount=200_000, savings_account="Ahorro",
    ))
    goal_id = _goals.list_goals(session)[0].id
    out = planning.contribute_goal(session, ContributeGoalInput(
        goal_id=goal_id, amount=100_000, date="2026-06-01",
    ))
    assert "100" in out or "Fondo" in out
