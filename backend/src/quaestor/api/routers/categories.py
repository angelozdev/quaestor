"""Categories REST router — thin adapter over services.categories."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ...services import categories
from ..deps import get_session
from ..schemas import CategoryCreate, CategoryOut, CategoryUpdate

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def list_categories(
    archived: bool = False,
    is_income: bool | None = None,
    session: Session = Depends(get_session),
):
    """`is_income` narrows the list to one direction — the offering a movement
    form shows while recording money coming in or going out (ADR-0042)."""
    return categories.list_categories(session, include_archived=archived, is_income=is_income)


@router.get("/{category_id}", response_model=CategoryOut)
def get_category(category_id: int, session: Session = Depends(get_session)):
    return categories.get_category(session, category_id)


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(body: CategoryCreate, session: Session = Depends(get_session)):
    return categories.create_category(
        session,
        name=body.name,
        group_id=body.group_id,
        is_income=body.is_income,
        exclude_from_budget=body.exclude_from_budget,
        exclude_from_totals=body.exclude_from_totals,
        counts_as_saving=body.counts_as_saving,
    )


@router.patch("/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, body: CategoryUpdate, session: Session = Depends(get_session)):
    fields = body.model_dump(exclude_unset=True)
    return categories.update_category(session, category_id, **fields)


@router.delete("/{category_id}", status_code=204)
def archive_category(category_id: int, session: Session = Depends(get_session)):
    categories.archive_category(session, category_id)
    return


@router.post("/{category_id}/restore", response_model=CategoryOut)
def restore_category(category_id: int, session: Session = Depends(get_session)):
    return categories.unarchive_category(session, category_id)
