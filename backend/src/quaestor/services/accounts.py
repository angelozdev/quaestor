"""Account use cases."""

from __future__ import annotations

from sqlmodel import Session, select

from ..domain.errors import NotFound, ValidationError
from ..domain.models import Account, AccountType
from ..domain.money import is_supported


def create_account(session: Session, name: str, type, currency: str, balance: int = 0) -> Account:
    """Create a new account with the given parameters.

    Validates that the account name is not empty and the currency is supported.

    Args:
        session: Database session
        name: Account name
        type: Account type (AccountType enum or string)
        currency: Currency code
        balance: Initial balance (default 0)

    Returns:
        The created Account

    Raises:
        ValidationError: If name is empty or currency is not supported
    """
    if not name or not name.strip():
        raise ValidationError("account name is required")
    if not is_supported(currency):
        raise ValidationError(f"unsupported currency: {currency}")
    acc = Account(
        name=name.strip(),
        type=AccountType(type),
        currency=currency,
        balance=balance,
    )
    session.add(acc)
    session.commit()
    session.refresh(acc)
    return acc


def list_accounts(session: Session, include_archived: bool = False) -> list[Account]:
    """List all accounts.

    By default, archived accounts are excluded. Set include_archived=True to include them.

    Args:
        session: Database session
        include_archived: Whether to include archived accounts

    Returns:
        List of Account objects
    """
    stmt = select(Account)
    if not include_archived:
        stmt = stmt.where(Account.archived == False)  # noqa: E712
    return list(session.exec(stmt).all())


def get_account(session: Session, account_id: int) -> Account:
    """Get an account by ID.

    Args:
        session: Database session
        account_id: The account ID

    Returns:
        The Account

    Raises:
        NotFound: If account does not exist
    """
    acc = session.get(Account, account_id)
    if acc is None:
        raise NotFound(f"account {account_id} not found")
    return acc


def archive_account(session: Session, account_id: int) -> Account:
    """Archive an account.

    Args:
        session: Database session
        account_id: The account ID to archive

    Returns:
        The archived Account

    Raises:
        NotFound: If account does not exist
    """
    acc = get_account(session, account_id)
    acc.archived = True
    session.add(acc)
    session.commit()
    session.refresh(acc)
    return acc


def unarchive_account(session: Session, account_id: int) -> Account:
    """Re-activate an archived account. Idempotent no-op if already active.

    Args:
        session: Database session
        account_id: The account ID to restore

    Returns:
        The restored Account

    Raises:
        NotFound: If account does not exist
    """
    acc = get_account(session, account_id)
    acc.archived = False
    session.add(acc)
    session.commit()
    session.refresh(acc)
    return acc


def update_account(session: Session, account_id: int, name=None, type=None) -> Account:
    """Update an account's name and/or type. None leaves a field unchanged.

    Raises:
        NotFound: If the account does not exist.
        ValidationError: If name is provided but empty.
    """
    acc = get_account(session, account_id)
    if name is not None:
        if not name.strip():
            raise ValidationError("account name is required")
        acc.name = name.strip()
    if type is not None:
        acc.type = AccountType(type)
    session.add(acc)
    session.commit()
    session.refresh(acc)
    return acc
