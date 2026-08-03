"""MCP planning tools (P4): budgets envelope assign and goals management.

Mirrors temporal.py: parse input, resolve names, call ONE service, format output.
"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field
from sqlmodel import Session

from ...services import budgets, goals
from .. import format
from .core import _as_text, _resolve_account, _resolve_category


class AssignBudgetInput(BaseModel):
    category: str = Field(description="Category name to assign an envelope to")
    year_month: str = Field(description="Target month, YYYY-MM")
    amount: int = Field(ge=0, description="Amount to assign in cents (0 unassigns)")


@_as_text
def assign_budget(session: Session, inp: AssignBudgetInput) -> str:
    category = _resolve_category(session, inp.category)
    budgets.set_budget(session, category.id, inp.year_month, inp.amount)
    status = budgets.budget_status(session, category.id, inp.year_month)
    return format.budget_assigned(status, category.name)


class CreateGoalInput(BaseModel):
    name: str = Field(description="Goal name, e.g. 'Trip'")
    monthly_amount: int = Field(gt=0, description="Fixed monthly amount in cents")
    savings_account: str = Field(description="Savings account name to hold the goal")
    target_amount: int | None = Field(default=None, description="Target in cents (defined goal)")
    deadline: str | None = Field(default=None, description="Deadline YYYY-MM-DD (defined goal)")


class UpdateGoalInput(BaseModel):
    goal_id: int = Field(description="The goal id")
    name: str | None = Field(default=None, description="New name")
    monthly_amount: int | None = Field(default=None, gt=0, description="New monthly amount in cents")


class ContributeGoalInput(BaseModel):
    goal_id: int = Field(description="The goal id")
    amount: int = Field(gt=0, description="Contribution amount in cents")
    date: str = Field(description="Contribution date YYYY-MM-DD")


class GoalIdInput(BaseModel):
    goal_id: int = Field(description="The goal id")


@_as_text
def create_goal(session: Session, inp: CreateGoalInput) -> str:
    account = _resolve_account(session, inp.savings_account)
    deadline = date.fromisoformat(inp.deadline) if inp.deadline else None
    goal = goals.create_goal(
        session, name=inp.name, monthly_amount=inp.monthly_amount,
        savings_account_id=account.id, target_amount=inp.target_amount, deadline=deadline,
    )
    return format.goal_saved(goal)


@_as_text
def update_goal(session: Session, inp: UpdateGoalInput) -> str:
    fields = inp.model_dump(exclude_unset=True, exclude={"goal_id"})
    goal = goals.update_goal(session, inp.goal_id, **fields)
    return format.goal_saved(goal)


@_as_text
def contribute_goal(session: Session, inp: ContributeGoalInput) -> str:
    contribution = goals.goal_contribution(session, inp.goal_id, inp.amount, date.fromisoformat(inp.date))
    return format.goal_contribution_recorded(contribution)


@_as_text
def pause_goal(session: Session, inp: GoalIdInput) -> str:
    return format.goal_saved(goals.pause_goal(session, inp.goal_id))


@_as_text
def restore_goal(session: Session, inp: GoalIdInput) -> str:
    return format.goal_saved(goals.restore_goal(session, inp.goal_id))
