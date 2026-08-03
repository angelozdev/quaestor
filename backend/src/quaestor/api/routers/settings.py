"""Settings REST router — thin adapter over services.settings."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ...services import settings
from ..deps import get_session
from ..schemas import SettingsOut, SettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsOut)
def get_settings(session: Session = Depends(get_session)):
    return settings.get_settings(session)


@router.patch("", response_model=SettingsOut)
def update_settings(body: SettingsUpdate, session: Session = Depends(get_session)):
    fields = body.model_dump(exclude_unset=True)
    return settings.update_settings(session, **fields)
