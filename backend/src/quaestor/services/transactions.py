"""Transaction use cases: register expense/income, transfer, read.

ADR-0031: transactions store only their physical amount + currency. No
rate and no converted amount are ever persisted; COP figures are computed
at read time from the current TRM.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date as Date

from sqlalchemy import delete
from sqlmodel import Session, select

from ..domain.errors import NotFound, TransferImbalance, ValidationError
from ..domain.models import (
    Account,
    Category,
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
) -> Transaction:
    """Core registration logic shared by record_expense and record_income."""
    if amount <= 0:
        raise ValidationError("amount must be > 0")
    if not is_supported(currency):
        raise ValidationError(f"unsupported currency: {currency}")
    acc = _require_account(session, account_id)
    if currency != acc.currency:
        raise ValidationError(f"currency {currency} does not match account currency ({acc.currency})")
    if category_id is not None:
        cat = session.get(Category, category_id)
        if cat is None:
            raise ValidationError(f"category {category_id} not found")
        if cat.archived:
            raise ValidationError(f"category {category_id} is archived")
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
        category_id: Optional category.
        notes: Optional free-text notes.
        source: Origin of the transaction ("manual", "agent", or "import").

    Returns:
        The persisted Transaction.

    Raises:
        ValidationError: Invalid amount, currency mismatch, or unknown category.
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
        category_id: Optional category.
        notes: Optional free-text notes.
        source: Origin of the transaction ("manual", "agent", or "import").

    Returns:
        The persisted Transaction.

    Raises:
        ValidationError: Invalid amount, currency mismatch, or unknown category.
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

    Returns:
        Tuple (leg_from, leg_to) — the two persisted Transaction rows.

    Raises:
        ValidationError: Non-positive amount, currency mismatch, or a
            cross-currency transfer missing the received amount.
        TransferImbalance: from_account_id == to_account_id.
        NotFound: Either account does not exist.
    """
    if amount <= 0:
        raise ValidationError("amount must be > 0")
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
) -> Transaction:
    """Edit balance-safe fields of a transaction (payee, notes, category_id, date).

    Amount/account/currency/type are immutable here, so no balance ever moves.
    `notes`/`category_id` use the _UNSET sentinel to allow setting them to None.

    Raises:
        NotFound: If the transaction does not exist.
        ValidationError: A non-None category_id that is missing or archived.
    """
    tx = get_transaction(session, tx_id)
    if payee is not None:
        tx.payee = payee
    if notes is not _UNSET:
        tx.notes = notes
    if date is not None:
        tx.date = date
    if category_id is not _UNSET:
        if category_id is not None:
            cat = session.get(Category, category_id)
            if cat is None:
                raise ValidationError(f"category {category_id} not found")
            if cat.archived:
                raise ValidationError(f"category {category_id} is archived")
        tx.category_id = category_id
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx


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
    never exist. A group-less transfer is a proposed goal contribution whose
    second leg is only born at confirm time; it deletes as a single row, and
    moves no balance unless it was already posted.

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
