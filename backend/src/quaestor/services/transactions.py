"""Transaction use cases: register expense/income, transfer, read."""
from __future__ import annotations

import uuid
from datetime import date as Date
from decimal import Decimal

from sqlmodel import Session, select

from ..domain.errors import NotFound, TransferImbalance, ValidationError
from ..domain.models import (
    Account,
    Category,
    Tag,
    Transaction,
    TransactionTag,
    TxStatus,
    TxType,
    Source,
)
from ..domain.money import BASE_CURRENCY, is_supported, to_base_cents
from ..domain.rules import delta_balance, transfer_deltas
from . import fx


def _require_account(session: Session, account_id: int) -> Account:
    """Return the account or raise NotFound/ValidationError if missing or archived."""
    acc = session.get(Account, account_id)
    if acc is None:
        raise NotFound(f"account {account_id} not found")
    if acc.archived:
        raise ValidationError(f"account {account_id} is archived")
    return acc


def _resolve_fx(session: Session, currency: str, date: Date, fx_rate) -> Decimal:
    """Return the FX rate to use for this transaction.

    COP transactions always get rate 1. Non-COP transactions use the explicit
    fx_rate if provided, otherwise look up the most recent rate via fx.tasa_vigente
    (which raises MissingRate if none is found).
    """
    if currency == BASE_CURRENCY:
        return Decimal("1")
    if fx_rate is not None:
        return Decimal(str(fx_rate))
    return fx.get_current_rate(session, date)  # raises MissingRate if absent


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
    fx_rate,
) -> Transaction:
    """Core registration logic shared by record_expense and record_income."""
    if amount <= 0:
        raise ValidationError("amount must be > 0")
    if not is_supported(currency):
        raise ValidationError(f"unsupported currency: {currency}")
    acc = _require_account(session, account_id)
    if currency != acc.currency:
        raise ValidationError(
            f"currency {currency} does not match account currency ({acc.currency})"
        )
    if category_id is not None:
        cat = session.get(Category, category_id)
        if cat is None:
            raise ValidationError(f"category {category_id} not found")
        if cat.archived:
            raise ValidationError(f"category {category_id} is archived")
    rate = _resolve_fx(session, currency, date, fx_rate)
    tx = Transaction(
        date=date,
        payee=payee or "",
        notes=notes,
        type=tx_type,
        status=TxStatus.posted,
        amount=amount,
        currency=currency,
        fx_rate=rate,
        to_base=to_base_cents(amount, rate),
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
    fx_rate=None,
) -> Transaction:
    """Register an expense transaction and decrement the account balance.

    Args:
        session: Database session.
        account_id: The account to debit.
        amount: Positive integer cents in the account's currency.
        currency: Must match the account's currency.
        date: Transaction date (used for FX lookup if needed).
        payee: Name of the payee.
        category_id: Optional category.
        notes: Optional free-text notes.
        source: Origin of the transaction ("manual", "agent", or "import").
        fx_rate: Explicit FX rate (skips lookup). Required for non-COP accounts
                 when no rate has been set for the date.

    Returns:
        The persisted Transaction.

    Raises:
        ValidationError: Invalid amount, currency mismatch, or unknown category.
        NotFound: Account does not exist.
        MissingRate: Non-COP account with no rate available and no explicit fx_rate.
    """
    return _record(
        session, TxType.expense, account_id, amount, currency, date, payee,
        category_id, notes, source, fx_rate,
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
    fx_rate=None,
) -> Transaction:
    """Register an income transaction and increment the account balance.

    Args:
        session: Database session.
        account_id: The account to credit.
        amount: Positive integer cents in the account's currency.
        currency: Must match the account's currency.
        date: Transaction date (used for FX lookup if needed).
        payee: Name of the income source.
        category_id: Optional category.
        notes: Optional free-text notes.
        source: Origin of the transaction ("manual", "agent", or "import").
        fx_rate: Explicit FX rate (skips lookup). Required for non-COP accounts
                 when no rate has been set for the date.

    Returns:
        The persisted Transaction.

    Raises:
        ValidationError: Invalid amount, currency mismatch, or unknown category.
        NotFound: Account does not exist.
        MissingRate: Non-COP account with no rate available and no explicit fx_rate.
    """
    return _record(
        session, TxType.income, account_id, amount, currency, date, payee,
        category_id, notes, source, fx_rate,
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
    currency: str,
    date: Date,
    notes: str | None = None,
    source: str = "manual",
    fx_rate=None,
) -> tuple[Transaction, Transaction]:
    """Create a transfer between two accounts as two linked Transaction rows.

    Both legs share the same transfer_group_id. Balances are updated atomically;
    on any error the session is rolled back and the exception re-raised.

    Args:
        session: Database session.
        from_account_id: Account debited (source).
        to_account_id: Account credited (destination).
        amount: Positive integer cents in the given currency.
        currency: Must match both accounts' currency.
        date: Transaction date (used for FX lookup if needed).
        notes: Optional free-text notes.
        source: Origin of the transaction ("manual", "agent", or "import").
        fx_rate: Explicit FX rate (skips lookup). Required for non-COP accounts
                 when no rate has been set for the date.

    Returns:
        Tuple (leg_from, leg_to) — the two persisted Transaction rows.

    Raises:
        ValidationError: Invalid amount, currency mismatch, or same-account transfer.
        TransferImbalance: from_account_id == to_account_id.
        NotFound: Either account does not exist.
        MissingRate: Non-COP account with no rate available and no explicit fx_rate.
    """
    if amount <= 0:
        raise ValidationError("amount must be > 0")
    if from_account_id == to_account_id:
        raise TransferImbalance("source and destination cannot be the same account")
    if not is_supported(currency):
        raise ValidationError(f"unsupported currency: {currency}")
    src = _require_account(session, from_account_id)
    dst = _require_account(session, to_account_id)
    if currency != src.currency or currency != dst.currency:
        raise ValidationError(
            "P0 transfer: both accounts must use the transfer currency"
        )
    rate = _resolve_fx(session, currency, date, fx_rate)
    to_base = to_base_cents(amount, rate)
    group = uuid.uuid4().hex
    d_from, d_to = transfer_deltas(amount)
    payee = notes or "transfer"
    leg_from = Transaction(
        date=date,
        payee=payee,
        notes=notes,
        type=TxType.transfer,
        status=TxStatus.posted,
        amount=amount,
        currency=currency,
        fx_rate=rate,
        to_base=to_base,
        account_id=from_account_id,
        transfer_group_id=group,
        source=Source(source),
    )
    leg_to = Transaction(
        date=date,
        payee=payee,
        notes=notes,
        type=TxType.transfer,
        status=TxStatus.posted,
        amount=amount,
        currency=currency,
        fx_rate=rate,
        to_base=to_base,
        account_id=to_account_id,
        transfer_group_id=group,
        source=Source(source),
    )
    try:
        src.balance += d_from
        dst.balance += d_to
        session.add_all([leg_from, leg_to, src, dst])
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(leg_from)
    session.refresh(leg_to)
    return (leg_from, leg_to)


def list_transactions(
    session: Session,
    account_id: int | None = None,
    category_id: int | None = None,
    tag: str | None = None,
    type=None,
    status=None,
    date_from: Date | None = None,
    date_to: Date | None = None,
) -> list[Transaction]:
    """List transactions with optional filters, ordered by date ascending.

    Args:
        session: Database session.
        account_id: Filter by account.
        category_id: Filter by category.
        tag: Filter by tag name (exact match).
        type: Filter by TxType (or a value coercible to TxType).
        status: Filter by TxStatus (or a value coercible to TxStatus).
        date_from: Include transactions on or after this date.
        date_to: Include transactions on or before this date.

    Returns:
        List of Transaction rows ordered by date ascending.
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
    return list(session.exec(stmt.order_by(Transaction.date)).all())


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


def delete_transaction(session: Session, tx_id: int) -> None:
    """Delete a transaction, reversing its posted balance effect.

    Transfers are not deletable in P1 (no stored leg direction to reverse safely).

    Raises:
        NotFound: If the transaction does not exist.
        ValidationError: If the transaction is a transfer leg.
    """
    tx = get_transaction(session, tx_id)
    if tx.type == TxType.transfer:
        raise ValidationError("deleting transfers is not supported in P1")
    try:
        if tx.status == TxStatus.posted:
            acc = session.get(Account, tx.account_id)
            if acc is not None:
                acc.balance -= delta_balance(tx.type, tx.amount)
                session.add(acc)
        links = session.exec(
            select(TransactionTag).where(TransactionTag.transaction_id == tx_id)
        ).all()
        for link in links:
            session.delete(link)
        session.delete(tx)
        session.commit()
    except Exception:
        session.rollback()
        raise
