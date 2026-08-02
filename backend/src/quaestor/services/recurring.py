"""Recurring items: the catalogue — declare, list, edit, switch off and on.

Materializing a due date and skipping one belong to `occurrences.py`, which is
the only module that writes a `RecurringOccurrence`.
"""
from __future__ import annotations

from datetime import date as Date

from sqlmodel import Session, select

from ..domain.errors import NotFound, ValidationError
from ..domain.models import (
    Account,
    Category,
    IntervalUnit,
    RecurringItem,
    RecurringMode,
    RecurringOccurrence,
    TxType,
)
from ..domain.money import is_supported
from ..domain.recurrence import due_dates, has_ended
from . import occurrences

_UNSET = object()


def is_live(item: RecurringItem, today: Date) -> bool:
    """Whether the obligation is still going to produce charges.

    Two different facts, deliberately kept apart (ADR-0037): `active` is the
    user switching it off, and the end date having passed is the obligation
    finishing on its own. Only the first is stored.
    """
    return item.active and not has_ended(item.end_date, today)


def _reject_manual_income(type: TxType, mode: RecurringMode) -> None:
    """An income that waits for approval can never be resolved (AC-6).

    Raises:
        ValidationError: the pair is income + manual.
    """
    if type == TxType.income and mode == RecurringMode.manual:
        raise ValidationError(
            "a repeating income must pay itself; expected money never enters "
            "the to-pay queue, so a manual one could never be confirmed"
        )


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
    declared_on: Date | None = None,
) -> RecurringItem:
    """Create a recurring item. Validates frequency, money, and references.

    `declared_on` is the day the user set this up (today by default, and not
    stored). Due dates before it already fell due when the obligation entered
    the system, so they are offered for the user to accept or decline rather
    than charged unattended (ADR-0035). An obligation declared on or before its
    start date has nothing pending and the engine charges it normally, which is
    what keeps the catch-up after downtime working.

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
    _reject_manual_income(type, mode)
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
    as_of = declared_on or Date.today()
    if start_date < as_of:
        occurrences.guard_offer_size(
            name,
            due_dates(
                start_date, end_date, interval_unit, interval_count,
                start_date, as_of,
            ),
        )
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
    if start_date < as_of:
        occurrences.offer_passed_dates(session, item, as_of)
    return item


def get_recurring(session: Session, recurring_id: int) -> RecurringItem:
    """Fetch a recurring item by id.

    Raises:
        NotFound: the item does not exist.
    """
    item = session.get(RecurringItem, recurring_id)
    if item is None:
        raise NotFound(f"recurring item {recurring_id} not found")
    return item


def list_recurring(
    session: Session, active: bool | None = None, today: Date | None = None
) -> list[RecurringItem]:
    """List recurring items, optionally filtered by `active`, ordered by id.

    `active=True` is the live list: what is still going to be charged. An
    obligation past its end date is not in it, and appears among the
    switched-off ones instead (ADR-0037) — the flag itself is untouched.

    This is NOT the set the engine charges: an obligation that has ended can
    still hold a due date the engine never got to. `occurrences.py` runs its
    own query for that.
    """
    items = list(session.exec(select(RecurringItem).order_by(RecurringItem.id)).all())
    if active is None:
        return items
    as_of = today or Date.today()
    return [item for item in items if is_live(item, as_of) == active]


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
    today: Date | None = None,
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
        _reject_manual_income(item.type, RecurringMode(mode))
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
    as_of = today or Date.today()
    moved_start_back = start_date is not None and start_date < item.start_date
    if start_date is not None:
        item.start_date = start_date
    if end_date is not _UNSET:
        item.end_date = end_date
    if item.end_date is not None and item.end_date < item.start_date:
        raise ValidationError("end_date must be on or after start_date")
    if moved_start_back:
        claimed = occurrences.existing_due_dates(session, item.id)
        occurrences.guard_offer_size(
            item.name,
            [
                d
                for d in due_dates(
                    item.start_date, item.end_date, item.interval_unit,
                    item.interval_count, item.start_date, as_of,
                )
                if d not in claimed
            ],
        )
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
    if moved_start_back:
        occurrences.offer_passed_dates(session, item, as_of)
    return item


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


def restore_recurring(
    session: Session, recurring_id: int, today: Date | None = None
) -> RecurringItem:
    """Switch a paused obligation back on, picking up from today.

    The due dates left behind are offered for the user to accept or decline,
    rather than charged in one lump or written off: the engine may have been
    down before the pause, and only the user knows which dates were which
    (ADR-0037). Idempotent no-op if it was already live, so nothing is offered
    by mistake.

    Raises:
        NotFound: the item does not exist.
    """
    item = session.get(RecurringItem, recurring_id)
    if item is None:
        raise NotFound(f"recurring item {recurring_id} not found")
    if item.active:
        return item
    item = _set_active(session, recurring_id, True)
    occurrences.offer_paused_stretch(session, item, today or Date.today())
    session.refresh(item)
    return item


def skip_recurring(
    session: Session, recurring_id: int, due_date: Date
) -> RecurringOccurrence:
    """Mark (or create) the occurrence for (recurring_id, due_date) as skipped.

    Raises:
        NotFound: the recurring item does not exist.
    """
    return occurrences.skip(session, recurring_id, due_date)
