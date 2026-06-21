"""Budgets REST router — thin adapter over services.budgets."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ...domain.dtos import BudgetLine
from ...domain.models import Category
from ...services import budgets
from ..deps import get_session
from ..schemas import BudgetAssignIn, BudgetLineOut, SafeToSpendOut

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("", response_model=list[BudgetLineOut])
def list_budgets(month: str, session: Session = Depends(get_session)):
    return budgets.list_budgets(session, month)


@router.put("", response_model=BudgetLineOut)
def assign_budget(body: BudgetAssignIn, session: Session = Depends(get_session)):
    budgets.set_budget(session, body.category_id, body.year_month, body.amount_assigned)
    st = budgets.budget_status(session, body.category_id, body.year_month)
    cat = session.get(Category, body.category_id)
    return BudgetLine(
        category_id=st.category_id, category_name=cat.name, assigned=st.assigned,
        rollover_in=st.rollover_in, spent=st.spent, available=st.available,
        pct_used=st.pct_used, status=st.status,
    )


@router.get("/safe-to-spend", response_model=SafeToSpendOut)
def safe_to_spend(month: str, session: Session = Depends(get_session)):
    return budgets.safe_to_spend(session, month)
