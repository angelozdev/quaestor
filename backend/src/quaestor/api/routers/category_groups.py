"""Category-groups REST router — thin adapter over services.categories (group fns)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ...services import categories
from ..deps import get_session
from ..schemas import CategoryGroupCreate, CategoryGroupOut, CategoryGroupUpdate

router = APIRouter(prefix="/category-groups", tags=["category-groups"])


@router.get("", response_model=list[CategoryGroupOut])
def list_groups(archived: bool = False, session: Session = Depends(get_session)):
    return categories.list_groups(session, include_archived=archived)


@router.post("", response_model=CategoryGroupOut, status_code=201)
def create_group(body: CategoryGroupCreate, session: Session = Depends(get_session)):
    return categories.create_group(session, name=body.name, sort_order=body.sort_order)


@router.patch("/{group_id}", response_model=CategoryGroupOut)
def update_group(
    group_id: int, body: CategoryGroupUpdate, session: Session = Depends(get_session)
):
    return categories.update_group(
        session, group_id, name=body.name, sort_order=body.sort_order
    )


@router.delete("/{group_id}", status_code=204)
def archive_group(group_id: int, session: Session = Depends(get_session)):
    categories.archive_group(session, group_id)
    return None
