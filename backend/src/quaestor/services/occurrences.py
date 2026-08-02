"""Recurring occurrences — the only module that writes a `RecurringOccurrence`.

Everything that consumes a due date lives here: materializing a charge,
skipping a date, and keeping an occurrence in step with the transaction it
produced. `services/recurring.py` owns the item itself and calls in; this
module never imports it back, so the dependency stays one-way.
"""
from __future__ import annotations

from datetime import date as Date

from sqlmodel import Session, select

from ..domain.dtos import MaterializationReport, RunFailure
from ..domain.errors import NotFound, ValidationError
from ..domain.models import (
    Account,
    OccurrenceStatus,
    RecurringItem,
    RecurringMode,
    RecurringOccurrence,
    Source,
    Transaction,
    TxStatus,
)
from ..domain.recurrence import due_dates, is_due_on
from ..domain.rules import delta_balance


def occurrence_of(session: Session, tx: Transaction) -> RecurringOccurrence | None:
    """The recurring occurrence this tx materialized, if it came from one."""
    return session.exec(
        select(RecurringOccurrence).where(
            RecurringOccurrence.transaction_id == tx.id
        )
    ).first()


def sync_occurrence_status(
    session: Session, tx: Transaction, status: OccurrenceStatus
) -> None:
    """Move the occurrence behind `tx`, if any, to `status`. Does NOT commit."""
    occ = occurrence_of(session, tx)
    if occ is not None and occ.status != status:
        occ.status = status
        session.add(occ)


def existing_due_dates(session: Session, recurring_id: int) -> set[Date]:
    """Every due date of this item that already has an occurrence."""
    rows = session.exec(
        select(RecurringOccurrence.due_date).where(
            RecurringOccurrence.recurring_id == recurring_id
        )
    ).all()
    return set(rows)


def _chargeable_account(session: Session, item: RecurringItem) -> Account:
    """The account this obligation charges, refusing one the user retired.

    Raises:
        NotFound: the account is gone.
        ValidationError: the account was archived after the obligation was declared.
    """
    acc = session.get(Account, item.account_id)
    if acc is None:
        raise NotFound(f"account {item.account_id} not found")
    if acc.archived:
        raise ValidationError(f"account {acc.name!r} is archived")
    return acc


def _create_occurrence_tx(
    session: Session, item: RecurringItem, due_date: Date,
    occ: RecurringOccurrence | None = None,
) -> RecurringOccurrence:
    """Create the tx for one (item, due_date) and point an occurrence at it.

    auto  -> posted tx on due_date, balance moved, occurrence posted.
    manual-> planned tx on due_date, no balance, occurrence planned.
    `occ` is the row already standing for that date — an offered one the user
    just accepted — which is filled in rather than duplicated, since
    (recurring_id, due_date) is unique. Does NOT commit; the caller commits.
    """
    acc = _chargeable_account(session, item)
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
        source=Source.recurring,
    )
    session.add(tx)
    if is_auto:
        acc.balance += delta_balance(item.type, item.amount)
        session.add(acc)
    session.flush()
    status = OccurrenceStatus.posted if is_auto else OccurrenceStatus.planned
    if occ is None:
        occ = RecurringOccurrence(
            recurring_id=item.id, due_date=due_date, status=status
        )
    occ.status = status
    occ.transaction_id = tx.id
    session.add(occ)
    return occ


def _items_to_charge(session: Session) -> list[RecurringItem]:
    """The items the engine charges: every one the user has not switched off.

    Deliberately not `recurring.list_recurring(active=True)` — that is the live
    list, which excludes items past their end date, and one of those can still
    hold a due date the engine never got to.
    """
    return list(
        session.exec(
            select(RecurringItem)
            .where(RecurringItem.active)
            .order_by(RecurringItem.id)
        ).all()
    )


def _charge(
    session: Session, item: RecurringItem, due_date: Date,
    occ: RecurringOccurrence | None = None,
) -> RecurringOccurrence:
    """One charge, all-or-nothing: movement, balance and occurrence, or none.

    The commit is per charge, not per run — a failure here costs this
    obligation its day and leaves every other one alone (ADR-0036).
    """
    try:
        occ = _create_occurrence_tx(session, item, due_date, occ)
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(occ)
    return occ


def materialize_due(session: Session, until_date: Date) -> MaterializationReport:
    """Create every not-yet-materialized occurrence with due_date <= until_date.

    Due-driven (ADR-020): runs daily via the scheduler with until_date=today.
    Idempotent by (recurring_id, due_date). An obligation that cannot be
    charged is reported and skipped for the rest of the run; its dates stay
    free, so the next run picks them up once the cause is fixed (ADR-0036).
    """
    created: list[RecurringOccurrence] = []
    failures: list[RunFailure] = []
    for item in _items_to_charge(session):
        existing = existing_due_dates(session, item.id)
        for d in due_dates(
            item.start_date, item.end_date, item.interval_unit,
            item.interval_count, item.start_date, until_date,
        ):
            if d in existing:
                continue
            try:
                created.append(_charge(session, item, d))
            except Exception as exc:
                failures.append(RunFailure(item.id, item.name, str(exc)))
                break
    return MaterializationReport(created=created, failures=failures)


MAX_OFFERED_DATES = 60
"""How many passed dates a person can reasonably be asked to answer at once.

The bound is on the count, not on how far back the start is: five years of a
monthly obligation is 60 boxes to tick, and two months of a daily one is the
same. Sixty covers any history worth pulling in by hand; past that, the start
date is almost always a typo.
"""


def guard_offer_size(name: str, dates: list[Date]) -> list[Date]:
    """Refuse an offer nobody could answer.

    Raises:
        ValidationError: the obligation would put more than `MAX_OFFERED_DATES`
            dates up at once.
    """
    if len(dates) > MAX_OFFERED_DATES:
        raise ValidationError(
            f"{name!r} would put {len(dates)} passed dates up for decision, and "
            f"at most {MAX_OFFERED_DATES} can be answered at once; move the "
            f"start date closer"
        )
    return dates


def _unclaimed_dates(
    session: Session, item: RecurringItem, through: Date
) -> list[Date]:
    """Due dates up to `through` that no occurrence stands for yet."""
    existing = existing_due_dates(session, item.id)
    return [
        d
        for d in due_dates(
            item.start_date, item.end_date, item.interval_unit,
            item.interval_count, item.start_date, through,
        )
        if d not in existing
    ]


def _offer(
    session: Session, item: RecurringItem, dates: list[Date]
) -> list[Date]:
    """Put these dates up for the user's decision.

    Writing the row in `offered` both records the question and consumes the
    date, so the daily run leaves it alone until the user answers (ADR-0035).
    Nothing is charged and no balance moves.
    """
    for d in dates:
        session.add(
            RecurringOccurrence(
                recurring_id=item.id, due_date=d, status=OccurrenceStatus.offered
            )
        )
    session.commit()
    return dates


def offer_passed_dates(session: Session, item: RecurringItem, until: Date) -> list[Date]:
    """Offer the dates that had already fallen due when the obligation arrived."""
    return _offer(session, item, _unclaimed_dates(session, item, until))


def pending_dates(session: Session, recurring_id: int) -> list[Date]:
    """The dates this obligation is waiting on the user to accept or decline."""
    return list(
        session.exec(
            select(RecurringOccurrence.due_date)
            .where(
                RecurringOccurrence.recurring_id == recurring_id,
                RecurringOccurrence.status == OccurrenceStatus.offered,
            )
            .order_by(RecurringOccurrence.due_date)
        ).all()
    )


def _offered_on(
    session: Session, recurring_id: int, dates: list[Date]
) -> list[RecurringOccurrence]:
    """The offered occurrences for exactly these dates.

    Raises:
        ValidationError: any date was never offered — already answered, already
            charged, or not a due date at all. Answering silently would let the
            caller believe a decision was recorded when none was.
    """
    if not dates:
        return []
    found = list(
        session.exec(
            select(RecurringOccurrence)
            .where(
                RecurringOccurrence.recurring_id == recurring_id,
                RecurringOccurrence.status == OccurrenceStatus.offered,
                RecurringOccurrence.due_date.in_(dates),
            )
            .order_by(RecurringOccurrence.due_date)
        ).all()
    )
    unknown = sorted(set(dates) - {occ.due_date for occ in found})
    if unknown:
        raise ValidationError(
            "these dates are not waiting for an answer: "
            + ", ".join(str(d) for d in unknown)
        )
    return found


def accept_pending_dates(
    session: Session, recurring_id: int, dates: list[Date]
) -> list[RecurringOccurrence]:
    """Charge the offered dates the user ticked, each on its own real date.

    All-or-nothing, unlike the daily run. Per-charge commit (ADR-0036) exists so
    one broken obligation cannot cost the others their day in an unattended
    batch; here the user is watching one obligation and pressed one button, and
    expects every date they ticked to land or none of them to.

    Raises:
        NotFound: the recurring item does not exist.
        ValidationError: any date was not waiting for an answer.
    """
    item = session.get(RecurringItem, recurring_id)
    if item is None:
        raise NotFound(f"recurring item {recurring_id} not found")
    offered = _offered_on(session, recurring_id, dates)
    try:
        accepted = [
            _create_occurrence_tx(session, item, occ.due_date, occ) for occ in offered
        ]
        session.commit()
    except Exception:
        session.rollback()
        raise
    for occ in accepted:
        session.refresh(occ)
    return accepted


def decline_pending_dates(
    session: Session, recurring_id: int, dates: list[Date]
) -> list[RecurringOccurrence]:
    """Close the offered dates the user turned down, for good.

    A declined date is never charged and never offered again: it becomes
    `skipped`, the state the engine already treats as settled.

    Raises:
        NotFound: the recurring item does not exist.
    """
    if session.get(RecurringItem, recurring_id) is None:
        raise NotFound(f"recurring item {recurring_id} not found")
    declined = _offered_on(session, recurring_id, dates)
    for occ in declined:
        occ.status = OccurrenceStatus.skipped
        session.add(occ)
    session.commit()
    return declined


def close_date_of_deleted_charge(tx: Transaction, session: Session) -> None:
    """Settle the due date behind a movement that is about to be deleted.

    Deleting an engine-made charge is how a wrongly charged date is undone
    (AC-20 sends the user here). The money comes back, so the date has to close
    as skipped rather than stay marked charged and pointing at a row that no
    longer exists — otherwise it is consumed forever and no run brings it back
    (ADR-0038). Does NOT commit; `delete_transaction` owns the commit.
    """
    occ = occurrence_of(session, tx)
    if occ is None:
        return
    occ.status = OccurrenceStatus.skipped
    occ.transaction_id = None
    session.add(occ)


def offer_paused_stretch(
    session: Session, item: RecurringItem, today: Date
) -> list[Date]:
    """Offer the dates left behind when a switched-off obligation comes back.

    Resuming must not charge the stretch in one lump — that would turn pausing
    into deferring. It must not write the stretch off either: the engine may
    have been down before the pause, and those dates are money the user still
    owes. The two causes are indistinguishable from here, and the user is the
    only one who can tell them apart, so the dates are offered rather than
    decided (ADR-0037).

    Today itself is left to the daily run, so an obligation resumed today is
    charged today.
    """
    behind = [d for d in _unclaimed_dates(session, item, today) if d < today]
    return _offer(session, item, behind)


def skip(session: Session, recurring_id: int, due_date: Date) -> RecurringOccurrence:
    """Mark (or create) the occurrence for (recurring_id, due_date) as skipped.

    A planned tx already materialized for that occurrence is skipped too, so it
    leaves to_pay. materialize_due will not recreate the date afterwards.

    Raises:
        NotFound: the recurring item does not exist.
        ValidationError: the obligation never falls due on that date, or its
            money already moved — skipping then would leave the obligation
            saying it was not paid while the account says it was. Deleting the
            movement is the way back (ADR-0038).
    """
    item = session.get(RecurringItem, recurring_id)
    if item is None:
        raise NotFound(f"recurring item {recurring_id} not found")
    if not is_due_on(
        item.start_date, item.end_date, item.interval_unit,
        item.interval_count, due_date,
    ):
        raise ValidationError(
            f"{item.name!r} never falls due on {due_date}; there is nothing to skip"
        )
    occ = session.exec(
        select(RecurringOccurrence).where(
            RecurringOccurrence.recurring_id == recurring_id,
            RecurringOccurrence.due_date == due_date,
        )
    ).first()
    if occ is not None and occ.status == OccurrenceStatus.posted:
        raise ValidationError(
            f"the turn of {item.name!r} due on {due_date} was already charged; "
            f"delete that movement to undo it"
        )
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
