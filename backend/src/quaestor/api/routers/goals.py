"""Goals REST router — thin adapter over services.goals."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ...services import goals
from ..deps import get_session
from ..schemas import GoalProgressOut

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("/progress", response_model=list[GoalProgressOut])
def goals_progress(session: Session = Depends(get_session)):
    return goals.goals_progress(session)
