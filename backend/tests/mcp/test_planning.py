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
