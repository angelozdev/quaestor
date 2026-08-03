"""Tags REST router — thin adapter over services.tags."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ...services import tags
from ..deps import get_session
from ..schemas import TagCreate, TagOut, TagUpdate

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("", response_model=list[TagOut])
def list_tags(session: Session = Depends(get_session)):
    return tags.list_tags(session)


@router.post("", response_model=TagOut, status_code=201)
def create_tag(body: TagCreate, session: Session = Depends(get_session)):
    return tags.create_tag(session, body.name)


@router.patch("/{tag_id}", response_model=TagOut)
def update_tag(tag_id: int, body: TagUpdate, session: Session = Depends(get_session)):
    return tags.update_tag(session, tag_id, body.name)


@router.delete("/{tag_id}", status_code=204)
def delete_tag(tag_id: int, session: Session = Depends(get_session)):
    tags.delete_tag(session, tag_id)
    return
