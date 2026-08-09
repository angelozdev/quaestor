"""Metas REST router — thin adapter over services.metas.

Every refusal a meta can meet lives in the service, so this router carries no
rule of its own: it translates a request into a service call and the result
into JSON (ADR-0046).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ...services import metas
from ...services import month as month_service
from ..deps import get_session
from ..schemas import (
    MetaContributionIn,
    MetaContributionOut,
    MetaCreate,
    MetaOut,
    MetaPreviewOut,
    MetaStatusOut,
    MetaUpdate,
    MonthSplitOut,
)

router = APIRouter(prefix="/metas", tags=["metas"])


@router.get("", response_model=list[MetaStatusOut])
def list_metas(month: str, session: Session = Depends(get_session)):
    return metas.list_metas(session, month)


@router.get("/split", response_model=MonthSplitOut)
def month_split(month: str, session: Session = Depends(get_session)):
    return month_service.split(session, month)


@router.get("/archived", response_model=list[MetaOut])
def list_archived(session: Session = Depends(get_session)):
    return metas.list_archived(session)


@router.post("/preview", response_model=MetaPreviewOut)
def preview_meta(body: MetaCreate, month: str, session: Session = Depends(get_session)):
    return metas.preview_meta(
        amount=body.amount,
        target_month=body.target_month,
        today=month,
        income=month_service.income_of(session, month),
    )


@router.post("", response_model=MetaOut, status_code=201)
def create_meta(body: MetaCreate, month: str, session: Session = Depends(get_session)):
    return metas.create_meta(session, today=month, **body.model_dump(exclude_unset=True))


@router.patch("/{meta_id}", response_model=MetaOut)
def set_meta(meta_id: int, body: MetaUpdate, month: str, session: Session = Depends(get_session)):
    return metas.set_meta(session, meta_id, today=month, **body.model_dump(exclude_unset=True))


@router.post("/{meta_id}/contributions", response_model=MetaContributionOut, status_code=201)
def contribute(meta_id: int, body: MetaContributionIn, month: str, session: Session = Depends(get_session)):
    metas.contribute(session, meta_id, year_month=month, amount=body.amount)
    return metas.contributions_of(session, meta_id)[-1]


@router.get("/{meta_id}/contributions", response_model=list[MetaContributionOut])
def list_contributions(meta_id: int, session: Session = Depends(get_session)):
    return metas.contributions_of(session, meta_id)


@router.delete("/contributions/{contribution_id}", status_code=204)
def remove_contribution(contribution_id: int, session: Session = Depends(get_session)):
    metas.remove_contribution(session, contribution_id)


@router.delete("/{meta_id}", status_code=204)
def cancel_meta(meta_id: int, month: str, session: Session = Depends(get_session)):
    metas.cancel_meta(session, meta_id, year_month=month)


@router.post("/{meta_id}/close", response_model=MetaOut)
def close_meta(meta_id: int, month: str, session: Session = Depends(get_session)):
    return metas.close_meta(session, meta_id, year_month=month)


@router.post("/{meta_id}/restore", response_model=MetaOut)
def restore_meta(meta_id: int, month: str, session: Session = Depends(get_session)):
    return metas.restore_meta(session, meta_id, today=month)
