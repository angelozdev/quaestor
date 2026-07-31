"""Recurring items: create/list, and the due-driven materialization (ADR-020)."""
from __future__ import annotations

from datetime import date as Date

from sqlmodel import Session, select

from ..domain.errors import NotFound, ValidationError
from ..domain.models import (
    Account,
    Category,
    IntervalUnit,
    OccurrenceStatus,
    RecurringItem,
    RecurringMode,
    RecurringOccurrence,
    Source,
    Transaction,
    TxStatus,
    TxType,
)
from ..domain.money import is_supported
from ..domain.rules import delta_balance, due_dates

_UNSET = object()


def _require_account(session: Session, account_id: int) -> Account:
    acc = session.get(Account, account_id)
    if acc is None:
        raise NotFound(f"account {account_id} not found")
    if acc.archived:
        raise ValidationError(f"account {account_id} is archived")
    return acc


def create_recurring(
    session: Session,
    name: str,
    payee: str,
    type: TxType,
    mode: RecurringMode,
    amount: int,
    currency: str,
    category_id: int | None,
    account_id: int,
    interval_unit: IntervalUnit,
    interval_count: int,
    start_date: Date,
    end_date: Date | None = None,
) -> RecurringItem:
    """Create a recurring item. Validates frequency, money, and references.

    Raises:
        ValidationError: amount <= 0, unsupported currency, transfer type,
            interval_count < 1, end_date < start_date, unknown/archived category.
        NotFound: account does not exist.
    """
    type = TxType(type)
    mode = RecurringMode(mode)
    interval_unit = IntervalUnit(interval_unit)
    if type == TxType.transfer:
        raise ValidationError("recurring type must be expense or income, not transfer")
    if amount <= 0:
        raise ValidationError("amount must be > 0")
    if not is_supported(currency):
        raise ValidationError(f"unsupported currency: {currency}")
    if interval_count < 1:
        raise ValidationError("interval_count must be >= 1")
    if end_date is not None and end_date < start_date:
        raise ValidationError("end_date must be on or after start_date")
    acc = _require_account(session, account_id)
    if currency != acc.currency:
        raise ValidationError(f"currency {currency} does not match account currency {acc.currency}")
    if category_id is not None:
        cat = session.get(Category, category_id)
        if cat is None:
            raise ValidationError(f"category {category_id} not found")
        if cat.archived:
            raise ValidationError(f"category {category_id} is archived")
    item = RecurringItem(
        name=name,
        payee=payee or "",
        type=type,
        mode=mode,
        amount=amount,
        currency=currency,
        category_id=category_id,
        account_id=account_id,
        interval_unit=interval_unit,
        interval_count=interval_count,
        start_date=start_date,
        end_date=end_date,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def list_recurring(session: Session, active: bool | None = None) -> list[RecurringItem]:
    """List recurring items, optionally filtered by `active`, ordered by id."""
    stmt = select(RecurringItem)
    if active is not None:
        stmt = stmt.where(RecurringItem.active == active)
    return list(session.exec(stmt.order_by(RecurringItem.id)).all())


def update_recurring(
    session: Session,
    recurring_id: int,
    *,
    name: str | None = None,
    payee: str | None = None,
    mode: RecurringMode | None = None,
    amount: int | None = None,
    category_id=_UNSET,
    account_id: int | None = None,
    interval_unit: IntervalUnit | None = None,
    interval_count: int | None = None,
    start_date: Date | None = None,
    end_date=_UNSET,
) -> RecurringItem:
    """Edit a recurring item. type and currency are immutable. Changes affect only
    future un-materialized occurrences (materialize_due reads current fields).

    `category_id=_UNSET`/`end_date=_UNSET` leave unchanged; `=None` clears them.

    Raises:
        NotFound: the item or a new account does not exist.
        ValidationError: amount <= 0, interval_count < 1, end_date < start_date,
            account currency mismatch, unknown/archived category.
    """
    item = session.get(RecurringItem, recurring_id)
    if item is None:
        raise NotFound(f"recurring item {recurring_id} not found")
    if name is not None:
        item.name = name
    if payee is not None:
        item.payee = payee
    if mode is not None:
        item.mode = RecurringMode(mode)
    if amount is not None:
        if amount <= 0:
            raise ValidationError("amount must be > 0")
        item.amount = amount
    if interval_unit is not None:
        item.interval_unit = IntervalUnit(interval_unit)
    if interval_count is not None:
        if interval_count < 1:
            raise ValidationError("interval_count must be >= 1")
        item.interval_count = interval_count
    if start_date is not None:
        item.start_date = start_date
    if end_date is not _UNSET:
        item.end_date = end_date
    if item.end_date is not None and item.end_date < item.start_date:
        raise ValidationError("end_date must be on or after start_date")
    if account_id is not None:
        acc = _require_account(session, account_id)
        if item.currency != acc.currency:
            raise ValidationError(
                f"currency {item.currency} does not match account currency {acc.currency}"
            )
        item.account_id = account_id
    if category_id is not _UNSET:
        if category_id is not None:
            cat = session.get(Category, category_id)
            if cat is None:
                raise ValidationError(f"category {category_id} not found")
            if cat.archived:
                raise ValidationError(f"category {category_id} is archived")
        item.category_id = category_id
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def _existing_due_dates(session: Session, recurring_id: int) -> set[Date]:
    rows = session.exec(
        select(RecurringOccurrence.due_date).where(
            RecurringOccurrence.recurring_id == recurring_id
        )
    ).all()
    return set(rows)


def _create_occurrence_tx(
    session: Session, item: RecurringItem, due_date: Date
) -> RecurringOccurrence:
    """Create the tx + occurrence for one (item, due_date).

    auto  -> posted tx on due_date, balance moved, occurrence posted.
    manual-> planned tx on due_date, no balance, occurrence planned.
    Does NOT commit; the caller commits the whole batch.
    """
    is_auto = item.mode == RecurringMode.auto
    tx = Transaction(
        date=due_date,
        payee=item.payee,
        notes=None,
        type=item.type,
        status=TxStatus.posted if is_auto else TxStatus.planned,
        amount=item.amount,
        currency=item.currency,
        account_id=item.account_id,
        category_id=item.category_id,
        recurring_id=item.id,
        source=Source.manual,
    )
    session.add(tx)
    if is_auto:
        acc = session.get(Account, item.account_id)
        acc.balance += delta_balance(item.type, item.amount)
        session.add(acc)
    session.flush()
    occ = RecurringOccurrence(
        recurring_id=item.id,
        due_date=due_date,
        status=OccurrenceStatus.posted if is_auto else OccurrenceStatus.planned,
        transaction_id=tx.id,
    )
    session.add(occ)
    return occ


def materialize_due(session: Session, until_date: Date) -> list[RecurringOccurrence]:
    """Create every not-yet-materialized occurrence with due_date <= until_date.

    Due-driven (ADR-020): runs daily via the scheduler with until_date=today.
    Idempotent by (recurring_id, due_date). Returns the occurrences created now.
    On any error the whole batch rolls back (self-heals on the next run).
    """
    created: list[RecurringOccurrence] = []
    try:
        for item in list_recurring(session, active=True):
            existing = _existing_due_dates(session, item.id)
            for d in due_dates(
                item.start_date, item.end_date, item.interval_unit,
                item.interval_count, item.start_date, until_date,
            ):
                if d in existing:
                    continue
                created.append(_create_occurrence_tx(session, item, d))
        session.commit()
    except Exception:
        session.rollback()
        raise
    for occ in created:
        session.refresh(occ)
    return created


def _set_active(session: Session, recurring_id: int, active: bool) -> RecurringItem:
    """Private helper to set the active flag on a recurring item.

    Raises:
        NotFound: the item does not exist.
    """
    item = session.get(RecurringItem, recurring_id)
    if item is None:
        raise NotFound(f"recurring item {recurring_id} not found")
    item.active = active
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def deactivate_recurring(session: Session, recurring_id: int) -> RecurringItem:
    """Soft-delete: stop materializing future occurrences (existing ones stay).

    Raises:
        NotFound: the item does not exist.
    """
    return _set_active(session, recurring_id, False)


def restore_recurring(session: Session, recurring_id: int) -> RecurringItem:
    """Re-activate a deactivated recurring item. Idempotent no-op if already active.

    Raises:
        NotFound: the item does not exist.
    """
    return _set_active(session, recurring_id, True)


def skip_recurring(
    session: Session, recurring_id: int, due_date: Date
) -> RecurringOccurrence:
    """Mark (or create) the occurrence for (recurring_id, due_date) as skipped.

    A planned tx already materialized for that occurrence is skipped too, so it
    leaves to_pay. materialize_due will not recreate the date afterwards.

    Raises:
        NotFound: the recurring item does not exist.
    """
    item = session.get(RecurringItem, recurring_id)
    if item is None:
        raise NotFound(f"recurring item {recurring_id} not found")
    occ = session.exec(
        select(RecurringOccurrence).where(
            RecurringOccurrence.recurring_id == recurring_id,
            RecurringOccurrence.due_date == due_date,
        )
    ).first()
    if occ is None:
        occ = RecurringOccurrence(
            recurring_id=recurring_id,
            due_date=due_date,
            status=OccurrenceStatus.skipped,
        )
    else:
        occ.status = OccurrenceStatus.skipped
        if occ.transaction_id is not None:
            tx = session.get(Transaction, occ.transaction_id)
            if tx is not None and tx.status == TxStatus.planned:
                tx.status = TxStatus.skipped
                session.add(tx)
    session.add(occ)
    session.commit()
    session.refresh(occ)
    return occ
