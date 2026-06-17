"""Account use cases."""
from __future__ import annotations

from sqlmodel import Session, select

from ..domain.errors import NotFound, ValidationError
from ..domain.models import Account, AccountType
from ..domain.money import is_supported


def crear_cuenta(
    session: Session, name: str, type, currency: str, balance: int = 0
) -> Account:
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


def listar_cuentas(session: Session, incluir_archivadas: bool = False) -> list[Account]:
    """List all accounts.

    By default, archived accounts are excluded. Set incluir_archivadas=True to include them.

    Args:
        session: Database session
        incluir_archivadas: Whether to include archived accounts

    Returns:
        List of Account objects
    """
    stmt = select(Account)
    if not incluir_archivadas:
        stmt = stmt.where(Account.archived == False)  # noqa: E712
    return list(session.exec(stmt).all())


def consultar_cuenta(session: Session, account_id: int) -> Account:
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


def archivar_cuenta(session: Session, account_id: int) -> Account:
    """Archive an account.

    Args:
        session: Database session
        account_id: The account ID to archive

    Returns:
        The archived Account

    Raises:
        NotFound: If account does not exist
    """
    acc = consultar_cuenta(session, account_id)
    acc.archived = True
    session.add(acc)
    session.commit()
    session.refresh(acc)
    return acc
