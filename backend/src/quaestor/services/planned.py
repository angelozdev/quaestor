"""Planned payments: the to-pay queue, plan/confirm/skip (ADR-007).

confirm_payment is the only planned -> posted transition and fires the
post-confirm hooks (the seam P4 uses to record goal contributions).
"""
from __future__ import annotations

from datetime import date as Date

from sqlmodel import Session

from ..domain.errors import NotFound, ValidationError
from ..domain.models import (
    Account,
    Category,
    Source,
    Transaction,
    TxStatus,
    TxType,
)
from ..domain.money import is_supported, to_base_cents
from . import transactions as _tx


def _require_account(session: Session, account_id: int) -> Account:
    acc = session.get(Account, account_id)
    if acc is None:
        raise NotFound(f"account {account_id} not found")
    if acc.archived:
        raise ValidationError(f"account {account_id} is archived")
    return acc


def plan_payment(
    session: Session,
    payee: str,
    amount: int,
    currency: str,
    due_date: Date,
    account_id: int,
    category_id: int | None = None,
    notes: str | None = None,
) -> Transaction:
    """Create a standalone `planned` expense due on `due_date`. No balance change.

    Raises:
        ValidationError: amount <= 0, unsupported currency, unknown/archived category.
        NotFound: account does not exist.
        MissingRate: non-COP with no rate for due_date.
    """
    if amount <= 0:
        raise ValidationError("amount must be > 0")
    if not is_supported(currency):
        raise ValidationError(f"unsupported currency: {currency}")
    _require_account(session, account_id)
    if category_id is not None:
        cat = session.get(Category, category_id)
        if cat is None:
            raise ValidationError(f"category {category_id} not found")
        if cat.archived:
            raise ValidationError(f"category {category_id} is archived")
    rate = _tx._resolve_fx(session, currency, due_date, None)
    tx = Transaction(
        date=due_date,
        payee=payee or "",
        notes=notes,
        type=TxType.expense,
        status=TxStatus.planned,
        amount=amount,
        currency=currency,
        fx_rate=rate,
        to_base=to_base_cents(amount, rate),
        account_id=account_id,
        category_id=category_id,
        source=Source.manual,
    )
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx


def to_pay(session: Session, since: Date, until: Date) -> dict:
    """The single confirmation queue: all `planned` txs in [since, until].

    Ordered by date. `total_base` is the sum of `to_base` (COP cents). Excludes
    `posted` and `skipped`.

    Raises:
        ValidationError: since > until (inverted window).
    """
    if since > until:
        raise ValidationError("to_pay window is inverted (since > until)")
    items = _tx.list_transactions(
        session, status="planned", date_from=since, date_to=until
    )
    total_base = sum(t.to_base for t in items)
    return {"items": items, "total_base": total_base}
