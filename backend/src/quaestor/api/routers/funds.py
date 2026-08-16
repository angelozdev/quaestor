"""Funds REST router — thin adapter over services.funds.

Every refusal a fund can meet lives in the service, so this router carries no
rule of its own: it translates a request into a service call and the result
into JSON (ADR-0043/0044).
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ...services import funds
from ...services import month as month_service
from ..deps import get_session
from ..schemas import (
    ChargeEditCost,
    ChargeEditCostOut,
    ChargeMarkOut,
    FundCreate,
    FundLineOut,
    FundOut,
    FundPreviewOut,
    FundStatusOut,
    FundUpdate,
    MonthAvailableOut,
    MonthRatesOut,
)

router = APIRouter(prefix="/funds", tags=["funds"])


@router.get("/available", response_model=MonthAvailableOut)
def money_available(month: str, session: Session = Depends(get_session)):
    return month_service.available(session, month)


@router.get("/rates", response_model=MonthRatesOut)
def money_rates(month: str, session: Session = Depends(get_session)):
    return month_service.rates(session, month)


@router.get("", response_model=list[FundLineOut])
def list_funds(session: Session = Depends(get_session)):
    return funds.list_funds(session)


@router.get("/charges", response_model=list[ChargeMarkOut])
def charge_marks(month: str, session: Session = Depends(get_session)):
    return funds.charge_marks(session, month)


@router.post("/charges/{recurring_id}", response_model=FundOut, status_code=201)
def mark_charge(recurring_id: int, month: str, session: Session = Depends(get_session)):
    return funds.mark_charge(session, recurring_id, month)


@router.get("/charges/{recurring_id}/turns", response_model=list[date])
def open_turns(recurring_id: int, session: Session = Depends(get_session)):
    """The turns of this charge nobody has settled yet, soonest first (ADR-0058).

    Asked when a payment is being pointed at a charge, so the owner can say
    which of its turns he paid. One charge at a time and only once he has
    chosen one, because asking it for every charge of a screen would cost a
    query each.
    """
    return funds.open_turns_of(session, recurring_id)


@router.post("/charges/{recurring_id}/edit-cost", response_model=ChargeEditCostOut)
def charge_edit_cost(recurring_id: int, body: ChargeEditCost, session: Session = Depends(get_session)):
    """What an edit would cost the charge's fund, asked before it is saved."""
    changes = body.model_dump(exclude_unset=True, exclude={"month"})
    return ChargeEditCostOut(
        would_lose_its_fund=funds.would_lose_its_fund(session, recurring_id, body.month, **changes)
    )


@router.delete("/charges/{recurring_id}", status_code=204)
def unmark_charge(recurring_id: int, session: Session = Depends(get_session)):
    funds.unmark_charge(session, recurring_id)
    return


@router.get("/{fund_id}/status", response_model=FundStatusOut)
def fund_status(fund_id: int, month: str, session: Session = Depends(get_session)):
    return funds.fund_status(session, fund_id, month)


@router.post("", response_model=FundOut, status_code=201)
def create_fund(body: FundCreate, session: Session = Depends(get_session)):
    fields = body.model_dump(exclude_unset=True, exclude={"category_id"})
    return funds.create_fund(session, body.category_id, **fields)


@router.post("/preview", response_model=FundPreviewOut)
def preview_fund(body: FundCreate, session: Session = Depends(get_session)):
    fields = body.model_dump(exclude_unset=True, exclude={"category_id"})
    return funds.preview_fund(session, body.category_id, **fields)


@router.patch("/{fund_id}", response_model=FundOut)
def set_fund(fund_id: int, body: FundUpdate, session: Session = Depends(get_session)):
    return funds.set_fund(session, fund_id, **body.model_dump(exclude_unset=True))


@router.delete("/{fund_id}", status_code=204)
def delete_fund(fund_id: int, session: Session = Depends(get_session)):
    funds.delete_fund(session, fund_id)
    return
