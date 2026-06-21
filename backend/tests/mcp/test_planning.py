from sqlmodel import Session

from quaestor.mcp.tools import planning
from quaestor.mcp.tools.planning import AssignBudgetInput
from quaestor.services import budgets, categories


def test_mcp_assign_budget(engine):
    with Session(engine) as s:
        cat = categories.create_category(s, name="Food")
        out = planning.assign_budget(
            s, AssignBudgetInput(category="Food", year_month="2026-06", amount=500_000)
        )
        assert "Food" in out
        assert budgets.budget_status(s, cat.id, "2026-06").assigned == 500_000


def test_mcp_create_goal(engine):
    from quaestor.mcp.tools.planning import CreateGoalInput
    from quaestor.services import accounts
    from quaestor.domain.models import AccountType
    with Session(engine) as s:
        accounts.create_account(s, "Savings", AccountType.savings, "COP", balance=0)
        out = planning.create_goal(s, CreateGoalInput(name="Trip", monthly_amount=200_000, savings_account="Savings"))
        assert "Trip" in out
        from quaestor.services import goals
        assert [g.name for g in goals.list_goals(s)] == ["Trip"]
