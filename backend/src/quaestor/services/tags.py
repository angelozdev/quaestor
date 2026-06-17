"""Tags and tagging use cases (m2m relationship)."""
from __future__ import annotations

from sqlmodel import Session, select

from ..domain.errors import NotFound, ValidationError
from ..domain.models import Tag, Transaction, TransactionTag


def _get_or_create_tag(session: Session, name: str) -> Tag:
    """Get existing tag by name or create a new one.

    Args:
        session: Database session
        name: Tag name

    Returns:
        The Tag (existing or newly created)

    Raises:
        ValidationError: If name is empty after stripping whitespace
    """
    name = name.strip()
    if not name:
        raise ValidationError("tag name is required")
    existing = session.exec(select(Tag).where(Tag.name == name)).first()
    if existing is not None:
        return existing
    tag = Tag(name=name)
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag


def create_tag(session: Session, name: str) -> Tag:
    """Create or retrieve an idempotent tag by name.

    If a tag with the same name already exists, returns the existing tag.
    Otherwise creates and returns a new tag.

    Args:
        session: Database session
        name: Tag name

    Returns:
        The Tag (existing or newly created)

    Raises:
        ValidationError: If name is empty after stripping whitespace
    """
    return _get_or_create_tag(session, name)


def list_tags(session: Session) -> list[Tag]:
    """List all tags ordered by name.

    Args:
        session: Database session

    Returns:
        List of Tag objects sorted by name
    """
    return list(session.exec(select(Tag).order_by(Tag.name)).all())


def tag_transaction(session: Session, tx_id: int, tags: list[str]) -> Transaction:
    """Tag a transaction with the given tag names.

    Creates any missing tags and links them to the transaction.
    Does not create duplicate links (idempotent).

    Args:
        session: Database session
        tx_id: Transaction ID
        tags: List of tag names to apply

    Returns:
        The updated Transaction

    Raises:
        NotFound: If transaction does not exist
    """
    tx = session.get(Transaction, tx_id)
    if tx is None:
        raise NotFound(f"transaction {tx_id} not found")
    for name in tags:
        tag = _get_or_create_tag(session, name)
        link = session.get(TransactionTag, (tx_id, tag.id))
        if link is None:
            session.add(TransactionTag(transaction_id=tx_id, tag_id=tag.id))
    session.commit()
    session.refresh(tx)
    return tx
