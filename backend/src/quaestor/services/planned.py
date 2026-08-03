"""Planned payments: the to-pay queue, plan/confirm/skip (ADR-007).

confirm_payment is the only planned -> posted transition and fires the
post-confirm hooks (the seam P4 uses to record goal contributions).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date as Date

from sqlmodel import Session

from ..domain.errors import IllegalTransition, NotFound, ValidationError
from ..domain.models import (
    Account,
    Category,
    OccurrenceStatus,
    Settings,
    Source,
    Transaction,
    TransferDirection,
    TxStatus,
    TxType,
)
from ..domain.money import is_supported
from ..domain.planned import OutstandingQueue
from ..domain.rules import delta_balance, transfer_deltas
from . import occurrences as _occ
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
    """
    if amount <= 0:
        raise ValidationError("amount must be > 0")
    if not is_supported(currency):
        raise ValidationError(f"unsupported currency: {currency}")
    acc = _require_account(session, account_id)
    if currency != acc.currency:
        raise ValidationError(f"currency {currency} does not match account currency {acc.currency}")
    if category_id is not None:
        cat = session.get(Category, category_id)
        if cat is None:
            raise ValidationError(f"category {category_id} not found")
        if cat.archived:
            raise ValidationError(f"category {category_id} is archived")
    tx = Transaction(
        date=due_date,
        payee=payee or "",
        notes=notes,
        type=TxType.expense,
        status=TxStatus.planned,
        amount=amount,
        currency=currency,
        account_id=account_id,
        category_id=category_id,
        source=Source.manual,
    )
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx


_OBLIGATION_TYPES: frozenset[TxType] = frozenset({TxType.expense, TxType.transfer})


def _obligations(items: list[Transaction]) -> list[Transaction]:
    """Only what the user owes: expenses and transfers. Planned income is not debt."""
    return [t for t in items if t.type in _OBLIGATION_TYPES]


def to_pay(
    session: Session,
    since: Date,
    until: Date,
    *,
    retrospective: bool = False,
    today: Date | None = None,
) -> OutstandingQueue:
    """Build the user's outstanding queue for the [since, until] window.

    Two mutually-exclusive buckets, populated by two disjoint queries:
    - `upcoming` = planned txs with `date in [max(since, today_resolved), until]`,
      ordered by date ASC.
    - `overdue`  = planned txs with `date < today_resolved AND date <= until`,
      ordered by date ASC, iff `retrospective=False`.

    Both buckets carry obligations only — expenses and transfers. Planned
    income is expected money in, not debt, so it never reaches the queue
    or its total.

    `today_resolved` is `today` if provided, else `date.today()`. The
    `today` kwarg exists for testability (the same pattern as
    `goals.goals_progress` and `reports.monthly_report`).

    The overdue bucket is constrained by `until` so callers that scope
    to a window don't get items from a future retrospective they
    didn't ask for.

    Args:
        session: DB session.
        since: Lower bound for the upcoming bucket (inclusive).
        until: Hard cap for both buckets (inclusive).
        retrospective: When False (default), the overdue bucket
            contains all planned txs with `date < today_resolved` whose
            `date <= until`. When True, the overdue bucket is empty
            (retrospective view: monthly report).
        today: Override for `date.today()` — used by tests for
            deterministic boundary assertions.

    Raises:
        ValidationError: `since > until` (inverted window).
    """
    if since > until:
        raise ValidationError("to_pay window is inverted (since > until)")

    today_resolved = today if today is not None else Date.today()

    if not retrospective:
        overdue_rows = _tx.list_transactions(
            session,
            status="planned",
            date_to=min(today_resolved, until),
            sort="date",
            order="asc",
        )
        overdue_items = _obligations([t for t in overdue_rows if t.date < today_resolved])
    else:
        overdue_items = []

    upcoming_since = max(since, today_resolved)
    if upcoming_since > until:
        upcoming_items: list[Transaction] = []
    else:
        upcoming_items = _obligations(
            _tx.list_transactions(
                session,
                status="planned",
                date_from=upcoming_since,
                date_to=until,
                sort="date",
                order="asc",
            )
        )

    return OutstandingQueue.from_lists(overdue_items, upcoming_items)


def _sync_occurrence_posted(session: Session, tx: Transaction) -> None:
    """If tx came from a manual occurrence, mark that occurrence posted."""
    _occ.sync_occurrence_status(session, tx, OccurrenceStatus.posted)


def confirm_payment(
    session: Session,
    tx_id: int,
    amount: int | None = None,
    date: Date | None = None,
) -> Transaction:
    """planned -> posted; the only such transition. Fires post-confirm hooks.

    Applies the real amount/date if provided, moves the balance, and syncs
    a manual occurrence to posted. A `transfer` tx is materialized into a
    real posted pair (Task 9). Everything (post + hooks) runs in one
    transaction; any failure rolls back.

    Raises:
        NotFound: the tx does not exist.
        IllegalTransition: the tx is not `planned`.
        ValidationError: a non-positive adjusted amount.
    """
    tx = _tx.get_transaction(session, tx_id)
    if tx.status != TxStatus.planned:
        raise IllegalTransition(f"transaction {tx_id} is {tx.status.value}, not planned")
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


def _materialize_planned_transfer(
    session: Session, tx: Transaction, amount: int | None, date: Date | None
) -> Transaction:
    """Turn a planned transfer into a real posted pair.

    tx.account_id is the destination (ADR-015); the source is the global
    Settings.default_source_account_id. The original row becomes the
    destination leg; a new source leg is created sharing a transfer_group_id.
    Does NOT commit (the caller's transaction owns the commit).
    """
    if amount is not None:
        tx.amount = amount
    if date is not None:
        tx.date = date
    if tx.amount <= 0:
        raise ValidationError("amount must be > 0")
    settings = session.get(Settings, 1)
    src_id = settings.default_source_account_id if settings else None
    if src_id is None:
        raise ValidationError("no default source account configured for transfers")
    if src_id == tx.account_id:
        raise ValidationError("source and destination cannot be the same account")
    src = _require_account(session, src_id)
    dst = _require_account(session, tx.account_id)
    if tx.currency != src.currency or tx.currency != dst.currency:
        raise ValidationError("transfer currency must match both accounts")
    group = uuid.uuid4().hex
    d_from, d_to = transfer_deltas(tx.amount)
    from_leg = Transaction(
        date=tx.date,
        payee=tx.payee,
        notes=tx.notes,
        type=TxType.transfer,
        status=TxStatus.posted,
        amount=tx.amount,
        currency=tx.currency,
        account_id=src_id,
        transfer_group_id=group,
        transfer_direction=TransferDirection.out,
        source=Source.manual,
    )
    tx.transfer_group_id = group
    tx.transfer_direction = TransferDirection.in_
    tx.status = TxStatus.posted
    src.balance += d_from
    dst.balance += d_to
    _sync_occurrence_posted(session, tx)
    session.add_all([from_leg, tx, src, dst])
    return tx


def _move_status(
    session: Session,
    tx_id: int,
    *,
    from_status: TxStatus,
    to_status: TxStatus,
    occurrence_status: OccurrenceStatus,
) -> Transaction:
    """Flip a tx from `from_status` to `to_status`, keeping its occurrence in step.

    Moves no balance and fires no hooks — `confirm_payment` owns the only
    path to `posted`.
    """
    tx = _tx.get_transaction(session, tx_id)
    if tx.status != from_status:
        raise IllegalTransition(f"transaction {tx_id} is {tx.status.value}, not {from_status.value}")
    tx.status = to_status
    _occ.sync_occurrence_status(session, tx, occurrence_status)
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx


def skip_payment(session: Session, tx_id: int) -> Transaction:
    """Cancel a `planned` tx (planned -> skipped). Syncs its occurrence if any.

    Raises:
        NotFound: the tx does not exist.
        IllegalTransition: the tx is not `planned`.
    """
    return _move_status(
        session,
        tx_id,
        from_status=TxStatus.planned,
        to_status=TxStatus.skipped,
        occurrence_status=OccurrenceStatus.skipped,
    )


def restore_payment(session: Session, tx_id: int) -> Transaction:
    """Undo a skip (skipped -> planned). The exact inverse of skip_payment (ADR-0034).

    Returns the payment to the outstanding queue and its recurring
    occurrence to `planned`, so the recurring machinery still recognises
    the date as taken. Moves no balance; `confirm_payment` stays the only
    door to `posted`.

    Raises:
        NotFound: the tx does not exist.
        IllegalTransition: the tx is not `skipped`.
    """
    return _move_status(
        session,
        tx_id,
        from_status=TxStatus.skipped,
        to_status=TxStatus.planned,
        occurrence_status=OccurrenceStatus.planned,
    )
