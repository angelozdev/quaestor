"""Monthly report: posted-only aggregation + formatting (P5).

Reuses P0 (reads), P3 (to_pay), P4 (budget_status, safe_to_spend, goals_progress).
Every aggregate is in to_base (COP cents); FX is never reconverted here.
"""
from __future__ import annotations

import re
from datetime import date as Date

from sqlmodel import Session, select

from ..domain.errors import ValidationError
from ..domain.models import Category, CategoryGroup, Transaction, TxStatus, TxType
from ..domain.report_types import CategorySection, GroupSection
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


def _group_name(session: Session, category_id: int | None) -> str | None:
    """Resolve a category's group name, or None when uncategorised/ungrouped."""
    if category_id is None:
        return None
    cat = session.get(Category, category_id)
    if cat is None or cat.group_id is None:
        return None
    grp = session.get(CategoryGroup, cat.group_id)
    return grp.name if grp is not None else None


def _category_sections(
    session: Session, expenses: list[Transaction], expense_total: int
) -> list[CategorySection]:
    """Group expenses by category (None -> 'Uncategorized'); pct over total expense."""
    buckets: dict[int | None, int] = {}
    for tx in expenses:
        buckets[tx.category_id] = buckets.get(tx.category_id, 0) + tx.to_base
    sections: list[CategorySection] = []
    for cat_id, total in buckets.items():
        if cat_id is None:
            name, group = "Uncategorized", None
        else:
            cat = session.get(Category, cat_id)
            name = cat.name if cat is not None else f"category {cat_id}"
            group = _group_name(session, cat_id)
        pct = (total / expense_total * 100) if expense_total > 0 else 0.0
        sections.append(CategorySection(category=name, group=group, total=total, pct=pct))
    sections.sort(key=lambda s: (-s.total, s.category))
    return sections


def _group_sections(
    session: Session, expenses: list[Transaction], expense_total: int
) -> list[GroupSection]:
    """Rollup of expenses by CategoryGroup name; pct over total expense (ADR-023)."""
    buckets: dict[str, int] = {}
    for tx in expenses:
        name = _group_name(session, tx.category_id) or "Ungrouped"
        buckets[name] = buckets.get(name, 0) + tx.to_base
    sections = [
        GroupSection(
            group=name,
            total=total,
            pct=(total / expense_total * 100) if expense_total > 0 else 0.0,
        )
        for name, total in buckets.items()
    ]
    sections.sort(key=lambda s: (-s.total, s.group))
    return sections
