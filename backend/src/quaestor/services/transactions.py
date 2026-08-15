"""Transaction use cases: register expense/income, transfer, read.

ADR-0031: transactions store only their physical amount + currency. No
rate and no converted amount are ever persisted; COP figures are computed
at read time from the current TRM.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date as Date
from typing import Protocol

from sqlalchemy import delete
from sqlmodel import Session, select

from ..domain.errors import CorrectionNotApplied, NotFound, TransferImbalance, ValidationError
from ..domain.models import (
    Account,
    Meta,
    RecurringItem,
    Source,
    Tag,
    Transaction,
    TransactionTag,
    TransferDirection,
    TxStatus,
    TxType,
)
from ..domain.money import is_supported
from ..domain.rules import delta_balance, leg_delta_balance
from ..domain.sort import Order, SortableColumns, SortField, SortSpec
from . import categories

PRE_DELETE_HOOKS: list[Callable[[Transaction, Session], None]] = []


def register_pre_delete_hook(fn: Callable[[Transaction, Session], None]) -> None:
    """Register a hook fired inside delete_transaction, before the row goes.

    The seam the recurring engine uses to close the due date a deleted charge
    belonged to (ADR-0038), so this module never learns what a recurring item
    is. Wired once in `services/bootstrap.py`.
    """
    PRE_DELETE_HOOKS.append(fn)


def _require_account(session: Session, account_id: int) -> Account:
    """Return the account or raise NotFound/ValidationError if missing or archived."""
    acc = session.get(Account, account_id)
    if acc is None:
        raise NotFound(f"account {account_id} not found")
    if acc.archived:
        raise ValidationError(f"account {account_id} is archived")
    return acc


def require_positive(amount: int) -> None:
    """A movement is worth something or it is not a movement (AC-24)."""
    if amount <= 0:
        raise ValidationError("amount must be > 0")


def refuse_bad_meta(session: Session, tx_type: TxType, meta_id: int | None) -> None:
    """A meta is pointed at by a purchase, and by nothing else (AC-23, AC-25).

    Money coming in is not a purchase, and money moving between the owner's own
    accounts is not either — the card statement payment included. A meta that
    has been cancelled takes no new link.
    """
    if meta_id is None:
        return
    if tx_type is not TxType.expense:
        raise ValidationError("only money going out can be pointed at a meta")
    meta = session.get(Meta, meta_id)
    if meta is None:
        raise NotFound(f"meta {meta_id} not found")
    if meta.closed:
        raise ValidationError(f"the meta {meta.name!r} was closed and takes no new link")
    if meta.archived:
        raise ValidationError(f"the meta {meta.name!r} was cancelled and takes no new link")


def refuse_bad_charge_link(
    session: Session, tx_type: TxType, category_id: int | None, recurring_id: int | None
) -> None:
    """A movement may name the charge it settled, and only one it could have settled.

    The owner pays the insurance from the bank and types it in by hand; naming
    the charge is what closes that cycle, because the amount alone cannot —
    guessing by amount is the very thing ADR-0057 replaces, and it would empty
    the insurance fund the day a fire extinguisher costs the same (AC-5).

    Money coming in settles nothing. A charge that is switched off has no cycle
    left to close. And a charge filed under a different category is refused
    rather than accepted quietly: the screen only ever offers the charges of the
    movement's own category, so a link across categories can only arrive by
    mistake, and it would take the payment out of one category's spending while
    draining a fund in another.
    """
    if recurring_id is None:
        return
    if tx_type is not TxType.expense:
        raise ValidationError("only money going out can settle a repeating charge")
    item = session.get(RecurringItem, recurring_id)
    if item is None:
        raise NotFound(f"repeating charge {recurring_id} not found")
    if not item.active:
        raise ValidationError(f"the charge {item.name!r} is switched off and has no turn left to settle")
    if item.type is not TxType.expense:
        raise ValidationError(f"{item.name!r} is money coming in, so no payment settles it")
    if category_id is not None and item.category_id != category_id:
        raise ValidationError(
            f"{item.name!r} is not filed under this movement's category, "
            f"so this payment cannot be the one that settled it"
        )


def _record(
    session: Session,
    tx_type: TxType,
    account_id: int,
    amount: int,
    currency: str,
    date: Date,
    payee: str,
    category_id: int | None,
    notes: str | None,
    source: str,
    new_category: str | None = None,
    meta_id: int | None = None,
    recurring_id: int | None = None,
) -> Transaction:
    """Core registration logic shared by record_expense and record_income."""
    require_positive(amount)
    if not is_supported(currency):
        raise ValidationError(f"unsupported currency: {currency}")
    acc = _require_account(session, account_id)
    if currency != acc.currency:
        raise ValidationError(f"currency {currency} does not match account currency ({acc.currency})")
    category_id = categories.resolve_for_movement(session, tx_type, category_id, new_category)
    refuse_bad_meta(session, tx_type, meta_id)
    refuse_bad_charge_link(session, tx_type, category_id, recurring_id)
    tx = Transaction(
        date=date,
        payee=payee or "",
        notes=notes,
        type=tx_type,
        status=TxStatus.posted,
        amount=amount,
        currency=currency,
        account_id=account_id,
        category_id=category_id,
        meta_id=meta_id,
        recurring_id=recurring_id,
        source=Source(source),
    )
    acc.balance += delta_balance(tx_type, amount)
    session.add(tx)
    session.add(acc)
    session.commit()
    session.refresh(tx)
    return tx


def record_expense(
    session: Session,
    account_id: int,
    amount: int,
    currency: str,
    date: Date,
    payee: str,
    category_id: int | None = None,
    notes: str | None = None,
    source: str = "manual",
    new_category: str | None = None,
    meta_id: int | None = None,
    recurring_id: int | None = None,
) -> Transaction:
    """Register an expense transaction and decrement the account balance.

    Works without any TRM set (AC-1): nothing about conversion is recorded.

    Args:
        session: Database session.
        account_id: The account to debit.
        amount: Positive integer cents in the account's currency.
        currency: Must match the account's currency.
        date: Transaction date.
        payee: Name of the payee.
        category_id: An existing expense category. Required unless
            `new_category` is given (ADR-0042).
        notes: Optional free-text notes.
        source: Origin of the transaction ("manual", "agent", or "import").
        new_category: Name of an expense category to create and file this
            expense under, in the same action.
        meta_id: The meta this purchase was for, named once on the day it
            happens (ADR-0046). Optional, and the ordinary case is None.
        recurring_id: The repeating charge this payment settled, named by the
            owner when he pays outside «Por pagar» (ADR-0057). Optional; without
            it the payment settles nothing, because the amount alone never
            decides.

    Returns:
        The persisted Transaction.

    Raises:
        ValidationError: Invalid amount, currency mismatch, or any refusal from
            `categories.resolve_for_movement` — no category, both categories,
            a name already taken, or a category missing, archived or of the
            wrong direction.
        NotFound: Account does not exist.
    """
    return _record(
        session,
        TxType.expense,
        account_id,
        amount,
        currency,
        date,
        payee,
        category_id,
        notes,
        source,
        new_category,
        meta_id,
        recurring_id,
    )


def record_income(
    session: Session,
    account_id: int,
    amount: int,
    currency: str,
    date: Date,
    payee: str,
    category_id: int | None = None,
    notes: str | None = None,
    source: str = "manual",
    new_category: str | None = None,
    meta_id: int | None = None,
    recurring_id: int | None = None,
) -> Transaction:
    """Register an income transaction and increment the account balance.

    Works without any TRM set (AC-1): nothing about conversion is recorded.

    Args:
        session: Database session.
        account_id: The account to credit.
        amount: Positive integer cents in the account's currency.
        currency: Must match the account's currency.
        date: Transaction date.
        payee: Name of the income source.
        category_id: An existing income category. Required unless
            `new_category` is given (ADR-0042).
        notes: Optional free-text notes.
        source: Origin of the transaction ("manual", "agent", or "import").
        new_category: Name of an income category to create and file this
            income under, in the same action.
        meta_id: Refused for income, the way `refuse_bad_meta` has always
            refused it.
        recurring_id: Refused for income. It is accepted as an argument so the
            refusal happens rather than the link being dropped in silence —
            money coming in settles nothing (AC-5).

    Returns:
        The persisted Transaction.

    Raises:
        ValidationError: Invalid amount, currency mismatch, a meta or a charge
            named by money coming in, or any refusal from
            `categories.resolve_for_movement` — no category, both categories,
            a name already taken, or a category missing, archived or of the
            wrong direction.
        NotFound: Account does not exist.
    """
    return _record(
        session,
        TxType.income,
        account_id,
        amount,
        currency,
        date,
        payee,
        category_id,
        notes,
        source,
        new_category,
        meta_id,
        recurring_id,
    )


def get_transaction(session: Session, tx_id: int) -> Transaction:
    """Fetch a transaction by ID.

    Args:
        session: Database session.
        tx_id: Transaction primary key.

    Returns:
        The Transaction.

    Raises:
        NotFound: If no transaction exists with the given ID.
    """
    tx = session.get(Transaction, tx_id)
    if tx is None:
        raise NotFound(f"transaction {tx_id} not found")
    return tx


def transfer(
    session: Session,
    from_account_id: int,
    to_account_id: int,
    amount: int,
    currency: str | None = None,
    date: Date | None = None,
    notes: str | None = None,
    source: str = "manual",
    amount_received: int | None = None,
    category_id: int | None = None,
) -> tuple[Transaction, Transaction]:
    """Create a transfer between two accounts as two linked Transaction rows.

    Each leg stores its own physical amount in its account's currency
    (ADR-0031); no rate is stored — the effective rate is implicit in the
    ratio and any pair of positive amounts is accepted (AC-8). Both legs
    share one transfer_group_id; balances move by each leg's own amount,
    atomically — on any error the session is rolled back and re-raised.

    Args:
        session: Database session.
        from_account_id: Account debited (source).
        to_account_id: Account credited (destination).
        amount: Positive integer cents SENT, in the source account's currency.
        currency: Sent currency; None defaults to the source account's
            currency, otherwise it must match it.
        date: Transaction date.
        notes: Optional free-text notes.
        source: Origin of the transaction ("manual", "agent", or "import").
        amount_received: Positive integer cents RECEIVED, in the destination
            account's currency. Required when the two accounts' currencies
            differ; defaults to `amount` when they match.
        category_id: Accepted only as `None`. A transfer carries no category
            (ADR-0042); the parameter exists so attaching one is refused here
            rather than silently ignored.

    Returns:
        Tuple (leg_from, leg_to) — the two persisted Transaction rows.

    Raises:
        ValidationError: Non-positive amount, currency mismatch, a
            cross-currency transfer missing the received amount, or a category.
        TransferImbalance: from_account_id == to_account_id.
        NotFound: Either account does not exist.
    """
    categories.resolve_for_movement(session, TxType.transfer, category_id)
    require_positive(amount)
    if amount_received is not None and amount_received <= 0:
        raise ValidationError("amount_received must be > 0")
    if from_account_id == to_account_id:
        raise TransferImbalance("source and destination cannot be the same account")
    src = _require_account(session, from_account_id)
    dst = _require_account(session, to_account_id)
    sent_currency = currency if currency is not None else src.currency
    if not is_supported(sent_currency):
        raise ValidationError(f"unsupported currency: {sent_currency}")
    if sent_currency != src.currency:
        raise ValidationError(f"currency {sent_currency} does not match source account currency ({src.currency})")
    cross_currency = src.currency != dst.currency
    if cross_currency and amount_received is None:
        raise ValidationError("amount_received is required when the accounts use different currencies")
    received = amount_received if amount_received is not None else amount
    group = uuid.uuid4().hex
    payee = notes or "transfer"
    leg_from = Transaction(
        date=date,
        payee=payee,
        notes=notes,
        type=TxType.transfer,
        status=TxStatus.posted,
        amount=amount,
        currency=src.currency,
        account_id=from_account_id,
        transfer_group_id=group,
        transfer_direction=TransferDirection.out,
        source=Source(source),
    )
    leg_to = Transaction(
        date=date,
        payee=payee,
        notes=notes,
        type=TxType.transfer,
        status=TxStatus.posted,
        amount=received,
        currency=dst.currency,
        account_id=to_account_id,
        transfer_group_id=group,
        transfer_direction=TransferDirection.in_,
        source=Source(source),
    )
    try:
        src.balance -= amount
        dst.balance += received
        session.add_all([leg_from, leg_to, src, dst])
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(leg_from)
    session.refresh(leg_to)
    return (leg_from, leg_to)


_TRANSACTION_SORTABLE: SortableColumns = {
    "date": Transaction.date,
    "created_at": Transaction.created_at,
}


def list_transactions(
    session: Session,
    account_id: int | None = None,
    category_id: int | None = None,
    tag: str | None = None,
    type=None,
    status=None,
    transfer_group_id: str | None = None,
    date_from: Date | None = None,
    date_to: Date | None = None,
    *,
    sort: SortField = "date",
    order: Order = "desc",
) -> list[Transaction]:
    """List transactions with optional filters, ordered by `date DESC, id DESC`.

    The default puts the most recent transaction date first, matching how the
    user reviews activity on `/transactions` ("qué pasó más reciente"). With
    no `status` filter, both `posted` and `planned` rows are returned —
    planned txs surface at their due-date position so upcoming obligations
    are visible. Pass `sort="created_at"` to fall back to creation-time
    order (rare; mainly for audit / debugging).

    Args:
        session: Database session.
        account_id: Filter by account.
        category_id: Filter by category.
        tag: Filter by tag name (exact match).
        type: Filter by TxType (or a value coercible to TxType).
        status: Filter by TxStatus (or a value coercible to TxStatus).
        transfer_group_id: Filter to the legs of one transfer.
        date_from: Include transactions on or after this date.
        date_to: Include transactions on or before this date.
        sort: Primary sort field. One of `SortField`.
        order: Sort direction. One of `Order`.

    Returns:
        List of Transaction rows in deterministic order
        (primary field, then `id` as tiebreaker in the same direction).
    """
    stmt = select(Transaction)
    if account_id is not None:
        stmt = stmt.where(Transaction.account_id == account_id)
    if category_id is not None:
        stmt = stmt.where(Transaction.category_id == category_id)
    if type is not None:
        stmt = stmt.where(Transaction.type == TxType(type))
    if status is not None:
        stmt = stmt.where(Transaction.status == TxStatus(status))
    if transfer_group_id is not None:
        stmt = stmt.where(Transaction.transfer_group_id == transfer_group_id)
    if date_from is not None:
        stmt = stmt.where(Transaction.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.date <= date_to)
    if tag is not None:
        stmt = (
            stmt.join(TransactionTag, TransactionTag.transaction_id == Transaction.id)  # type: ignore[arg-type]
            .join(Tag, Tag.id == TransactionTag.tag_id)  # type: ignore[arg-type]
            .where(Tag.name == tag)
        )
    spec = SortSpec(field=sort, order=order)
    primary, secondary = spec.resolve(_TRANSACTION_SORTABLE, Transaction.id)
    return list(session.exec(stmt.order_by(primary, secondary)).all())


_UNSET = object()


def update_transaction(
    session: Session,
    tx_id: int,
    payee=None,
    notes=_UNSET,
    category_id=_UNSET,
    date=None,
    meta_id=_UNSET,
    recurring_id=_UNSET,
) -> Transaction:
    """Edit balance-safe fields of a transaction (payee, notes, category_id, date).

    Amount/account/currency/type are immutable here, so no balance ever moves.
    `notes` uses the _UNSET sentinel to allow setting it to None; `category_id`
    keeps the sentinel to mean "leave it alone", but passing None no longer
    clears it — the rule holds for the life of the movement, not only at the
    moment it is created (ADR-0042).

    Raises:
        NotFound: If the transaction does not exist.
        ValidationError: Any refusal from `categories.resolve_for_movement` —
            clearing an expense's or income's category, giving one to a
            transfer, or a category missing, archived or of the wrong direction.
            Also every refusal about the meta this purchase is pointed at —
            money coming in, money moving between the owner's own accounts, or
            a meta that was cancelled. Passing None here DOES clear it: unlinking
            is a real act, and the category's fund takes the purchase back the
            moment it happens (AC-28). Every refusal about the charge this
            payment settled applies the same way, and clearing it hands the
            cycle back to the charge's fund (ADR-0057, AC-5).
    """
    tx = get_transaction(session, tx_id)
    if payee is not None:
        tx.payee = payee
    if notes is not _UNSET:
        tx.notes = notes
    if date is not None:
        tx.date = date
    if category_id is not _UNSET:
        tx.category_id = categories.resolve_for_movement(session, tx.type, category_id)
    if meta_id is not _UNSET:
        refuse_bad_meta(session, tx.type, meta_id)
        tx.meta_id = meta_id
    if recurring_id is not _UNSET:
        refuse_bad_charge_link(session, tx.type, tx.category_id, recurring_id)
        tx.recurring_id = recurring_id
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx


def _posted_effect(tx: Transaction) -> int:
    """What this row currently does to its account — zero until it is posted."""
    return _delta_balance_of(tx) if tx.status == TxStatus.posted else 0


def _effects(rows: list[Transaction]) -> dict[int, int]:
    """Account id -> what these rows together do to it right now."""
    effects: dict[int, int] = {}
    for tx in rows:
        effects[tx.account_id] = effects.get(tx.account_id, 0) + _posted_effect(tx)
    return effects


def _stored_balances(session: Session, account_ids: set[int]) -> dict[int, int]:
    """Balances read from the database, never from the session's own copies.

    Selecting the column rather than the entity is what makes the proof in
    `_restate` real: an entity query answers from the identity map, so it would
    return the value the code just assigned and confirm nothing (ADR-0051)."""
    session.flush()
    return dict(session.exec(select(Account.id, Account.balance).where(Account.id.in_(account_ids))).all())


def _restate(session: Session, rows: list[Transaction], mutate: Callable[[], None]) -> None:
    """Apply `mutate` to `rows` and move every balance it displaces, or nothing.

    The net movement of an account is what the rows do to it after the mutation
    minus what they did before, which is a reversal and a re-application in one
    subtraction. Both balances are then re-read from the database and each must
    have moved by exactly that figure; anything else — including a write that
    never persisted — rolls the whole correction back (ADR-0051).

    The starting balances are never questioned, only their movement, so an
    account that already disagrees with the sum of its movements disagrees by
    exactly as much afterwards.

    Raises:
        CorrectionNotApplied: a balance did not move as the correction declared.
    """
    was = _effects(rows)
    try:
        mutate()
        now = _effects(rows)
        expected = {
            account_id: now.get(account_id, 0) - was.get(account_id, 0) for account_id in was.keys() | now.keys()
        }
        before = _stored_balances(session, set(expected))
        for account_id, delta in expected.items():
            account = session.get(Account, account_id)
            if account is None:
                raise NotFound(f"account {account_id} not found")
            account.balance += delta
            session.add(account)
        for tx in rows:
            session.add(tx)
        after = _stored_balances(session, set(expected))
        for account_id, delta in expected.items():
            moved = after[account_id] - before[account_id]
            if moved != delta:
                raise CorrectionNotApplied(f"account {account_id} moved {moved} where the correction declared {delta}")
        session.commit()
    except Exception:
        session.rollback()
        raise


class Retargetable(Protocol):
    """A row that names an account and carries a figure stated in one currency.

    A posted movement, a planned one and a recurring rule all answer the same
    question when they are pointed at an account in another currency, so one
    function answers it for the three of them rather than three that agree by
    accident (ADR-0051, ADR-0052).
    """

    account_id: int
    amount: int
    currency: str


def retarget(session: Session, row: Retargetable, account_id: int, amount: int | None) -> bool:
    """Point `row` at another account and say whether `amount` was consumed doing it.

    A destination in another currency cannot hold the old figure, so the amount
    must be restated in it: the app offers the conversion where the owner can see
    it and never applies one of its own here (ADR-0051). That case consumes
    `amount` and returns True.

    A destination in the same currency can hold the old figure, so it is left
    alone and False is returned: an amount the caller carries is still its to
    apply, and both correcting and confirming take it as the real amount.

    Raises:
        NotFound: the account does not exist.
        ValidationError: the account is archived, or the amount is missing or
            not positive when the currency changes.
    """
    account = _require_account(session, account_id)
    crosses = account.currency != row.currency
    if crosses:
        if amount is None:
            raise ValidationError(f"moving to {account.currency} needs the amount in {account.currency}")
        require_positive(amount)
        row.amount = amount
        row.currency = account.currency
    row.account_id = account_id
    return crosses


def move_to_account(session: Session, tx_id: int, *, account_id: int, amount: int | None = None) -> Transaction:
    """Move a movement to the account it really came out of, or went into.

    The account it left gets back exactly what it gave up, and the destination
    gives up what the movement is worth there. Nothing else about the movement
    changes: it keeps its date, payee, category, tags, meta and the recurring
    due date it hangs from — which is what deleting and recreating cannot do
    (ADR-0038, ADR-0051). A leg of a transfer moves on its own; its counterpart
    is left alone.

    `amount` is the real figure and is stated in the destination's currency. It
    is required when that currency differs, since the old figure cannot survive
    the change, and optional when it does not — the account and the real amount
    are corrected in one act, exactly as confirming a payment does (AC-2, AC-7).

    Raises:
        NotFound: no such transaction, or no such account.
        ValidationError: the destination is archived, or the amount is missing
            when the currency changes, or not positive.
        TransferImbalance: the destination is where this transfer's other leg
            already sits, or the move would leave the pair's two halves
            carrying different figures inside one currency.
        CorrectionNotApplied: a balance did not move as declared.
    """
    tx = get_transaction(session, tx_id)
    _refuse_transfer_collision(session, tx, account_id)
    if amount is not None:
        require_positive(amount)

    def restate() -> None:
        if not retarget(session, tx, account_id, amount) and amount is not None:
            tx.amount = amount
        _refuse_unequal_halves(session, tx)

    _restate(session, [tx], restate)
    session.refresh(tx)
    return tx


def _refuse_transfer_collision(session: Session, tx: Transaction, account_id: int) -> None:
    """A transfer's two sides cannot sit on one account: that is not a transfer.

    `TransferImbalance` is the class `transfer` already raises for the same
    refusal at creation time, so a pair that cannot exist is named the same way
    whether it is being made or being corrected (AC-22).
    """
    if tx.type != TxType.transfer or tx.transfer_group_id is None:
        return
    if any(member.account_id == account_id for member in _group_members(session, tx)):
        raise TransferImbalance("source and destination cannot be the same account")


def _refuse_unequal_halves(session: Session, leg: Transaction) -> None:
    """In one currency a transfer's two halves are one number (AC-11).

    Read from the pair as it stands rather than from what a caller asked for,
    so the one rule covers both ways the halves can come to disagree: both
    figures restated at once, and a single leg retargeted into the currency the
    other half already holds. Money never appears or disappears between them.

    A movement that is not a leg of a pair has no halves and is left alone.

    Raises:
        TransferImbalance: two different figures inside one currency.
    """
    if leg.type != TxType.transfer or leg.transfer_group_id is None:
        return
    out_side, in_side = _transfer_sides(session, leg)
    if out_side.currency == in_side.currency and out_side.amount != in_side.amount:
        raise TransferImbalance("the two sides of a transfer in one currency carry the same amount")


def correct_amount(session: Session, tx_id: int, *, amount: int) -> Transaction:
    """Restate what a movement is worth. Its account keeps its own currency.

    The balance moves by the difference alone, and the movement stays the same
    movement — the correction that today costs it its identity, its category,
    its tags and its meta, because deleting and recreating is the only way to
    make it (ADR-0051).

    A transfer is refused here: its two sides answer to each other, so what it
    moved is restated through `correct_transfer` and never one side at a time
    (AC-11).

    Raises:
        NotFound: no such transaction.
        ValidationError: the amount is not positive, or the movement is a
            transfer.
        CorrectionNotApplied: the balance did not move as declared.
    """
    tx = get_transaction(session, tx_id)
    if tx.type == TxType.transfer:
        raise ValidationError("a transfer is restated on both of its sides at once")
    require_positive(amount)

    def restate() -> None:
        tx.amount = amount

    _restate(session, [tx], restate)
    session.refresh(tx)
    return tx


def _transfer_sides(session: Session, leg: Transaction) -> tuple[Transaction, Transaction]:
    """The (sent, received) sides of the pair this leg belongs to."""
    if leg.type != TxType.transfer or leg.transfer_group_id is None:
        raise ValidationError(f"transaction {leg.id} is not part of a transfer")
    sides = {member.transfer_direction: member for member in (leg, *_group_members(session, leg))}
    out_side, in_side = sides.get(TransferDirection.out), sides.get(TransferDirection.in_)
    if out_side is None or in_side is None:
        raise ValidationError(f"transfer {leg.transfer_group_id} does not have both of its sides")
    return out_side, in_side


def correct_transfer(session: Session, tx_id: int, *, sent: int, received: int) -> Transaction:
    """Restate what a transfer moved, on both of its sides at once.

    In one currency the two sides are one number, so they are stated as one and
    disagreeing is refused — money never appears or disappears between the halves
    of a transfer that never left its currency. Across currencies they are
    genuinely two numbers, since the rate the bank used is not the app's, and
    each side takes its own (AC-11, AC-12).

    Raises:
        NotFound: no such transaction.
        ValidationError: not a transfer, a side missing, or a figure that is not
            positive.
        TransferImbalance: two different figures inside one currency.
        CorrectionNotApplied: a balance did not move as declared.
    """
    leg = get_transaction(session, tx_id)
    out_side, in_side = _transfer_sides(session, leg)
    require_positive(sent)
    require_positive(received)

    def restate() -> None:
        out_side.amount = sent
        in_side.amount = received
        _refuse_unequal_halves(session, leg)

    _restate(session, [out_side, in_side], restate)
    session.refresh(leg)
    return leg


def _delete_tag_links(session: Session, tx_ids: list[int]) -> None:
    session.exec(delete(TransactionTag).where(TransactionTag.transaction_id.in_(tx_ids)))


def _delta_balance_of(tx: Transaction) -> int:
    if tx.type != TxType.transfer:
        return delta_balance(tx.type, tx.amount)
    try:
        return leg_delta_balance(tx.transfer_direction, tx.amount)
    except ValueError as exc:
        raise ValidationError(f"transfer leg {tx.id} has no stored direction; cannot reverse safely") from exc


def _reverse_balance(session: Session, tx: Transaction) -> None:
    delta = _delta_balance_of(tx)
    acc = session.get(Account, tx.account_id)
    if acc is not None:
        acc.balance -= delta
        session.add(acc)


def _group_members(session: Session, leg: Transaction) -> list[Transaction]:
    """The other legs sharing this transfer's group."""
    return [
        member
        for member in session.exec(
            select(Transaction).where(Transaction.transfer_group_id == leg.transfer_group_id)
        ).all()
        if member.id != leg.id
    ]


def _fire_pre_delete(session: Session, rows: list[Transaction]) -> None:
    """Let every registered hook settle what hangs off these rows.

    Fired from `delete_transaction` rather than from one of the two deletion
    paths, so a transfer pair cannot slip past a hook that a single row runs.
    A hook that fails takes its own partial writes with it, so the caller never
    inherits a half-settled session.
    """
    try:
        for tx in rows:
            for hook in PRE_DELETE_HOOKS:
                hook(tx, session)
    except Exception:
        session.rollback()
        raise


def _delete_transfer_pair(session: Session, leg: Transaction) -> None:
    if leg.transfer_group_id is None:
        raise ValidationError(f"transfer {leg.id} has no transfer group; cannot delete its pair")
    legs = session.exec(select(Transaction).where(Transaction.transfer_group_id == leg.transfer_group_id)).all()
    try:
        for member in legs:
            _reverse_balance(session, member)
        _delete_tag_links(session, [member.id for member in legs])
        for member in legs:
            session.delete(member)
        session.commit()
    except Exception:
        session.rollback()
        raise


def _delete_single(session: Session, tx: Transaction) -> None:
    try:
        if tx.status == TxStatus.posted:
            _reverse_balance(session, tx)
        _delete_tag_links(session, [tx.id])
        session.delete(tx)
        session.commit()
    except Exception:
        session.rollback()
        raise


def delete_transaction(session: Session, tx_id: int) -> None:
    """Delete a transaction, reversing its posted balance effect.

    A transfer leg that belongs to a group deletes its whole pair: both legs'
    balances are reversed per their stored direction and both rows plus their
    tag links are removed atomically (ADR-0032) — a half-deleted transfer can
    never exist. A group-less transfer deletes as a single row, and moves no
    balance unless it was already posted.

    Raises:
        NotFound: If the transaction does not exist.
        ValidationError: If a posted transfer leg carries no stored direction.
    """
    tx = get_transaction(session, tx_id)
    if tx.type == TxType.transfer and tx.transfer_group_id is not None:
        _fire_pre_delete(session, [tx, *_group_members(session, tx)])
        _delete_transfer_pair(session, tx)
        return
    _fire_pre_delete(session, [tx])
    _delete_single(session, tx)
