"""Savings goals: create, standalone contribution, progress, and the P3 hook seam (ADR-006/007)."""
from __future__ import annotations

import uuid
from datetime import date as Date

from sqlmodel import Session, select

from ..domain.dtos import GoalProgress
from ..domain.errors import NotFound, ValidationError
from ..domain.models import (
    Account,
    AccountType,
    ContributionSource,
    Goal,
    GoalContribution,
    GoalStatus,
    Settings,
    Source,
    Transaction,
    TxStatus,
    TxType,
)
from ..domain.money import to_base_cents
from ..domain.rules import goal_progress_calc, month_bounds, transfer_deltas
from . import transactions as _tx


def create_goal(
    session: Session,
    name: str,
    monthly_amount: int,
    savings_account_id: int,
    target_amount: int | None = None,
    deadline: Date | None = None,
) -> Goal:
    """Create a savings goal (defined if target+deadline; open-ended if neither).

    Raises:
        ValidationError: monthly_amount <= 0; only one of target/deadline given;
            target_amount <= 0; savings account missing, not savings, or archived.
    """
    if monthly_amount <= 0:
        raise ValidationError("monthly_amount must be > 0")
    has_target = target_amount is not None
    has_deadline = deadline is not None
    if has_target != has_deadline:
        raise ValidationError(
            "a defined goal needs both target_amount and deadline; "
            "an open-ended goal needs neither"
        )
    if has_target and target_amount <= 0:
        raise ValidationError("target_amount must be > 0")
    acc = session.get(Account, savings_account_id)
    if acc is None:
        raise ValidationError(f"savings account {savings_account_id} does not exist")
    if acc.type != AccountType.savings:
        raise ValidationError(f"account {savings_account_id} is not a savings account")
    if acc.archived:
        raise ValidationError(f"savings account {savings_account_id} is archived")
    goal = Goal(
        name=name, monthly_amount=monthly_amount, savings_account_id=savings_account_id,
        target_amount=target_amount, deadline=deadline, status=GoalStatus.active,
    )
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal
