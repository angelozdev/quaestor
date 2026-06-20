"""Monthly report: posted-only aggregation + formatting (P5).

Reuses P0 (reads), P3 (to_pay), P4 (budget_status, safe_to_spend, goals_progress).
Every aggregate is in to_base (COP cents); FX is never reconverted here.
"""
from __future__ import annotations

import re
from datetime import date as Date

from sqlmodel import Session, select

from ..domain.errors import ValidationError
from ..domain.models import Category, Transaction, TxStatus, TxType
from ..domain.rules import month_bounds

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _validate_month(month: str) -> None:
    if not _MONTH_RE.match(month):
        raise ValidationError(f"malformed month (expected YYYY-MM): {month!r}")


def _posted_for_totals(
    session: Session, tx_type: TxType, start: Date, end: Date
) -> list[Transaction]:
    """Posted txs of one type in [start, end], minus exclude_from_totals categories."""
    rows = session.exec(
        select(Transaction).where(
            Transaction.type == tx_type,
            Transaction.status == TxStatus.posted,
            Transaction.date >= start,
            Transaction.date <= end,
        )
    ).all()
    kept: list[Transaction] = []
    for tx in rows:
        if tx.category_id is not None:
            cat = session.get(Category, tx.category_id)
            if cat is not None and cat.exclude_from_totals:
                continue
        kept.append(tx)
    return kept


def _totals(session: Session, start: Date, end: Date) -> tuple[int, int, int]:
    """(income, expense, net) in COP cents — posted, transfers/planned excluded."""
    expenses = _posted_for_totals(session, TxType.expense, start, end)
    incomes = _posted_for_totals(session, TxType.income, start, end)
    expense = sum(t.to_base for t in expenses)
    income = sum(t.to_base for t in incomes)
    return income, expense, income - expense


def _usd_share(expenses: list[Transaction], expense_total: int) -> float:
    """Fraction of expense (to_base) originated in USD, [0, 1]. 0.0 if no expense."""
    if expense_total == 0:
        return 0.0
    usd = sum(t.to_base for t in expenses if t.currency == "USD")
    return usd / expense_total
