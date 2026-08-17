"""Recurring items: the catalogue — declare, list, edit, switch off and on.

Materializing a due date and skipping one belong to `occurrences.py`, which is
the only module that writes a `RecurringOccurrence`.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date as Date

from sqlmodel import Session, select

from ..domain.errors import NotFound, ValidationError
from ..domain.models import (
    Account,
    IntervalUnit,
    RecurringItem,
    RecurringMode,
    RecurringOccurrence,
    Transaction,
    TxType,
)
from ..domain.money import is_supported
from ..domain.recurrence import due_dates, has_ended
from ..domain.rules import year_month_of
from . import categories, funds, occurrences

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


def _account_holding(session: Session, account_id: int) -> Account:
    """The account an obligation already points at, archived or not.

    Retiring an account must not freeze the obligations that name it: the
    remedy for one of those is to move it elsewhere, and refusing every edit
    would take that remedy away too.

    Raises:
        NotFound: the account does not exist.
    """
    acc = session.get(Account, account_id)
    if acc is None:
        raise NotFound(f"account {account_id} not found")
    return acc


def _require_account(session: Session, account_id: int) -> Account:
    """An account an obligation may be pointed at — which a retired one may not.

    Raises:
        NotFound: the account does not exist.
        ValidationError: the account is archived.
    """
    acc = _account_holding(session, account_id)
    if acc.archived:
        raise ValidationError(f"account {account_id} is archived")
    return acc


def _require_chargeable(mode: RecurringMode, currency: str, account_currency: str) -> None:
    """An obligation that pays itself is stated in the currency its account holds.

    The price is the merchant's and the account decides what is debited
    (ADR-0053), so the two are free to differ — except when nobody is there to
    say what the debit really was. A charge that posts itself copies the
    obligation's figure straight onto its account's balance, so a peso price
    paying itself from a dollar account would add pesos to a dollar balance.

    Raises:
        ValidationError: the obligation pays itself and the two disagree.
    """
    if mode == RecurringMode.auto and currency != account_currency:
        raise ValidationError(
            f"an obligation that pays itself must be stated in {account_currency}, "
            f"the currency its account holds: restate it in {account_currency}, "
            f"or set it to wait for approval and state the real figure when it arrives"
        )


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
    new_category: str | None = None,
) -> RecurringItem:
    """Create a recurring item. Validates frequency, money, and references.

    `declared_on` is the day the user set this up (today by default, and not
    stored). Due dates before it already fell due when the obligation entered
    the system, so they are offered for the user to accept or decline rather
    than charged unattended (ADR-0035). An obligation declared on or before its
    start date has nothing pending and the engine charges it normally, which is
    what keeps the catch-up after downtime working.

    Every charge the engine produces from this item is born carrying its
    category (`occurrences._create_occurrence_tx` copies it), so the obligation
    itself cannot be declared without one (ADR-0042).

    Raises:
        ValidationError: amount <= 0, unsupported currency, transfer type,
            interval_count < 1, end_date < start_date, or any refusal from
            `categories.resolve_for_movement`.
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
    _require_chargeable(mode, currency, acc.currency)
    as_of = declared_on or Date.today()
    if start_date < as_of:
        occurrences.guard_offer_size(
            name,
            due_dates(
                start_date,
                end_date,
                interval_unit,
                interval_count,
                start_date,
                as_of,
            ),
        )
    category_id = categories.resolve_for_movement(session, type, category_id, new_category)
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


def list_recurring(session: Session, active: bool | None = None, today: Date | None = None) -> list[RecurringItem]:
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
    currency: str | None = None,
    category_id=_UNSET,
    account_id: int | None = None,
    interval_unit: IntervalUnit | None = None,
    interval_count: int | None = None,
    start_date: Date | None = None,
    end_date=_UNSET,
    today: Date | None = None,
) -> RecurringItem:
    """Edit a recurring item. `type` is immutable; the price and the account are not.

    Changes affect only future un-materialized occurrences (materialize_due reads
    current fields), so a turn already charged keeps the currency and the figure it
    was written with; that one is restated on its own through a correction.

    `amount` and `currency` are the price the merchant charges and travel
    together; `account_id` is where it is debited from. They are free to
    disagree — 99900 COP is what the charge costs however it is paid — except
    when the obligation pays itself, where `_require_chargeable` refuses
    (ADR-0053). Moving to another account therefore restates nothing on its own:
    the caller passes the new price when the owner accepted the conversion, and
    leaves it alone when he did not.

    `category_id=_UNSET`/`end_date=_UNSET` leave unchanged; `end_date=None`
    clears it. `category_id=None` does not clear the category — an obligation
    cannot be left uncategorised any more than a movement can (ADR-0042).

    Raises:
        NotFound: the item or a new account does not exist.
        ValidationError: amount <= 0, an unsupported currency, interval_count < 1,
            end_date < start_date, an archived destination account, an obligation
            left paying itself in a currency its account does not hold, or any
            refusal from `categories.resolve_for_movement`.
    """
    item = session.get(RecurringItem, recurring_id)
    if item is None:
        raise NotFound(f"recurring item {recurring_id} not found")
    try:
        edited = _apply_edit(
            session,
            item,
            name=name,
            payee=payee,
            mode=mode,
            amount=amount,
            currency=currency,
            category_id=category_id,
            account_id=account_id,
            interval_unit=interval_unit,
            interval_count=interval_count,
            start_date=start_date,
            end_date=end_date,
            today=today,
        )
    except Exception:
        session.rollback()
        raise
    funds.follow_its_charge(session, recurring_id)
    funds.unmark_if_it_can_no_longer_be_saved_for(session, recurring_id, year_month_of(today or Date.today()))
    session.refresh(edited)
    return edited


def _apply_edit(
    session: Session,
    item: RecurringItem,
    *,
    name: str | None,
    payee: str | None,
    mode: RecurringMode | None,
    amount: int | None,
    currency: str | None,
    category_id,
    account_id: int | None,
    interval_unit: IntervalUnit | None,
    interval_count: int | None,
    start_date: Date | None,
    end_date,
    today: Date | None,
) -> RecurringItem:
    """Write the edit onto `item`, or raise leaving the caller to undo it.

    Every field is applied before the whole obligation is judged, because the
    rules that can refuse it — the price against its account, the end against
    the start — read fields the same edit may have changed. Nothing here
    rolls back: `update_recurring` owns that, so a refusal cannot leave the
    row half-changed in the session it was read from.
    """
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
    if currency is not None:
        if not is_supported(currency):
            raise ValidationError(f"unsupported currency: {currency}")
        item.currency = currency
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
                    item.start_date,
                    item.end_date,
                    item.interval_unit,
                    item.interval_count,
                    item.start_date,
                    as_of,
                )
                if d not in claimed
            ],
        )
    if account_id is not None:
        _require_account(session, account_id)
        item.account_id = account_id
    _require_chargeable(item.mode, item.currency, _account_holding(session, item.account_id).currency)
    if category_id is not _UNSET:
        item.category_id = categories.resolve_for_movement(session, item.type, category_id)
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

    Whatever was being saved for this charge stops with it. A fund is a rule
    attached to something that still charges, so one left behind would go on
    asking for money toward a bill that is never coming — and switching the
    charge back on brings it back unmarked, because the owner decides again
    (ADR-0057, AC-7/AC-8). No movement is touched either way: a fund never held
    money, only a figure.

    Raises:
        NotFound: the item does not exist.
    """
    item = _set_active(session, recurring_id, False)
    funds.unmark_charge(session, recurring_id)
    session.refresh(item)
    return item


def restore_recurring(session: Session, recurring_id: int, today: Date | None = None) -> RecurringItem:
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


def skip_recurring(session: Session, recurring_id: int, due_date: Date) -> RecurringOccurrence:
    """Mark (or create) the occurrence for (recurring_id, due_date) as skipped.

    Raises:
        NotFound: the recurring item does not exist.
    """
    return occurrences.skip(session, recurring_id, due_date)


def prices_by_transaction(session: Session, txs: Sequence[Transaction]) -> dict[int, tuple[int, str]]:
    """The merchant's price behind each charge, for the charges where it differs.

    A charge records what the account was debited; the rule holds what the
    merchant charges. The two only differ when the rule is stated in a currency
    the charge is not, and only then is there anything to say. The price is read
    from the rule already linked to the charge — nothing new is stored and no
    rate is involved (ADR-0031, AC-21).

    Rules the owner switched off are left out: carrying them would grow this read
    path with every subscription ever cancelled, in exchange for a label on an
    old charge.
    """
    wanted = {tx.recurring_id for tx in txs if tx.recurring_id is not None}
    if not wanted:
        return {}
    rules = session.exec(
        select(RecurringItem).where(
            RecurringItem.id.in_(wanted),  # type: ignore[attr-defined]
            RecurringItem.active,  # type: ignore[arg-type]
        )
    ).all()
    price = {rule.id: (rule.amount, rule.currency) for rule in rules}
    return {
        tx.id: price[tx.recurring_id]
        for tx in txs
        if tx.recurring_id in price and price[tx.recurring_id][1] != tx.currency
    }
