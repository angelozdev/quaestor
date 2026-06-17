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
    return fx.tasa_vigente(session, date)  # raises MissingRate if absent


def _registrar(
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
    """Core registration logic shared by registrar_gasto and registrar_ingreso."""
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


def registrar_gasto(
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
    return _registrar(
        session, TxType.expense, account_id, amount, currency, date, payee,
        category_id, notes, source, fx_rate,
    )


def registrar_ingreso(
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
    return _registrar(
        session, TxType.income, account_id, amount, currency, date, payee,
        category_id, notes, source, fx_rate,
    )


def consultar_transaccion(session: Session, tx_id: int) -> Transaction:
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
