"""Goals REST router — thin adapter over services.goals."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ...services import goals
from ..deps import get_session
from ..schemas import (
    GoalContributeIn,
    GoalContributionOut,
    GoalCreate,
    GoalOut,
    GoalProgressOut,
    GoalUpdate,
)

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("/progress", response_model=list[GoalProgressOut])
def goals_progress(session: Session = Depends(get_session)):
    return goals.goals_progress(session)


@router.get("", response_model=list[GoalOut])
def list_goals(session: Session = Depends(get_session)):
    return goals.list_goals(session)


@router.post("", response_model=GoalOut, status_code=201)
def create_goal(body: GoalCreate, session: Session = Depends(get_session)):
    return goals.create_goal(
        session,
        name=body.name,
        monthly_amount=body.monthly_amount,
        savings_account_id=body.savings_account_id,
        target_amount=body.target_amount,
        deadline=body.deadline,
    )


@router.patch("/{goal_id}", response_model=GoalOut)
def update_goal(goal_id: int, body: GoalUpdate, session: Session = Depends(get_session)):
    fields = body.model_dump(exclude_unset=True)
    return goals.update_goal(session, goal_id, **fields)


@router.delete("/{goal_id}", status_code=204)
def pause_goal(goal_id: int, session: Session = Depends(get_session)):
    goals.pause_goal(session, goal_id)
    return


@router.post("/{goal_id}/contribute", response_model=GoalContributionOut, status_code=201)
def contribute(goal_id: int, body: GoalContributeIn, session: Session = Depends(get_session)):
    return goals.goal_contribution(session, goal_id, body.amount, body.date)


@router.post("/{goal_id}/restore", response_model=GoalOut)
def restore_goal(goal_id: int, session: Session = Depends(get_session)):
    return goals.restore_goal(session, goal_id)
