"""Planned payments: the to-pay queue, plan/confirm/skip (ADR-007).

confirm_payment is the only planned -> posted transition and fires the
post-confirm hooks (the seam P4 uses to record goal contributions).
"""
from __future__ import annotations

from datetime import date as Date
from typing import Callable

from sqlmodel import Session, select

from ..domain.errors import IllegalTransition, NotFound, ValidationError
from ..domain.models import (
    Account,
    Category,
    OccurrenceStatus,
    RecurringOccurrence,
    Source,
    Transaction,
    TxStatus,
    TxType,
)
from ..domain.money import is_supported, to_base_cents
from ..domain.rules import delta_balance
from . import transactions as _tx


POST_CONFIRM_HOOKS: list[Callable[[Transaction, Session], None]] = []


def register_post_confirm_hook(fn: Callable[[Transaction, Session], None]) -> None:
    """Register a hook fired inside confirm_payment's transaction, after posting."""
    POST_CONFIRM_HOOKS.append(fn)


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


def _sync_occurrence_posted(session: Session, tx: Transaction) -> None:
    """If tx came from a manual occurrence, mark that occurrence posted."""
    occ = session.exec(
        select(RecurringOccurrence).where(
            RecurringOccurrence.transaction_id == tx.id
        )
    ).first()
    if occ is not None and occ.status != OccurrenceStatus.posted:
        occ.status = OccurrenceStatus.posted
        session.add(occ)


def confirm_payment(
    session: Session,
    tx_id: int,
    amount: int | None = None,
    date: Date | None = None,
) -> Transaction:
    """planned -> posted; the only such transition. Fires post-confirm hooks.

    Applies the real amount/date if provided, recomputes to_base, moves the
    balance, and syncs a manual occurrence to posted. A `transfer` tx is
    materialized into a real posted pair (Task 9). Everything (post + hooks)
    runs in one transaction; any failure rolls back.

    Raises:
        NotFound: the tx does not exist.
        IllegalTransition: the tx is not `planned`.
        ValidationError: a non-positive adjusted amount.
        MissingRate: a non-COP tx with no rate for its date.
    """
    tx = _tx.get_transaction(session, tx_id)
    if tx.status != TxStatus.planned:
        raise IllegalTransition(
            f"transaction {tx_id} is {tx.status.value}, not planned"
        )
    try:
        if tx.type == TxType.transfer:
            result = _materialize_planned_transfer(session, tx, amount, date)
        else:
            if amount is not None:
                tx.amount = amount
            if date is not None:
                tx.date = date
            if tx.amount <= 0:
                raise ValidationError("amount must be > 0")
            rate = _tx._resolve_fx(session, tx.currency, tx.date, None)
            tx.fx_rate = rate
            tx.to_base = to_base_cents(tx.amount, rate)
            acc = _require_account(session, tx.account_id)
            acc.balance += delta_balance(tx.type, tx.amount)
            tx.status = TxStatus.posted
            _sync_occurrence_posted(session, tx)
            session.add(tx)
            session.add(acc)
            result = tx
        for hook in POST_CONFIRM_HOOKS:
            hook(result, session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(result)
    return result


def _materialize_planned_transfer(session, tx, amount, date):  # replaced in Task 9
    raise NotImplementedError("planned transfer materialization arrives in Task 9")
