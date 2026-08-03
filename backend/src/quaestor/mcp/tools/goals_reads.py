"""MCP goal read tools (ADR-0009): list_goals, goals_progress.

Writes (`create_goal`, `update_goal`, `contribute_goal`, `pause_goal`,
`restore_goal`) live in `planning.py`.
"""

from __future__ import annotations

from pydantic import BaseModel
from sqlmodel import Session

from ...services import goals
from .. import format
from .core import _as_text


class ListGoalsInput(BaseModel):
    pass


class GoalsProgressInput(BaseModel):
    pass


@_as_text
def list_goals(session: Session, inp: ListGoalsInput) -> str:
    return format.goals_table(goals.list_goals(session))


@_as_text
def goals_progress(session: Session, inp: GoalsProgressInput) -> str:
    return format.goals_progress_table(goals.goals_progress(session))
