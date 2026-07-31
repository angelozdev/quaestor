"""Tags and tagging use cases (m2m relationship)."""
from __future__ import annotations

from sqlalchemy import delete
from sqlmodel import Session, select

from ..domain.errors import NotFound, ValidationError
from ..domain.models import Tag, Transaction, TransactionTag


def _require_tx(session: Session, tx_id: int) -> Transaction:
    tx = session.get(Transaction, tx_id)
    if tx is None:
        raise NotFound(f"transaction {tx_id} not found")
    return tx


def _stripped(names: list[str]) -> list[str]:
    cleaned = [name.strip() for name in names]
    if any(not name for name in cleaned):
        raise ValidationError("tag name is required")
    return cleaned


def _resolve_tags(session: Session, names: list[str]) -> dict[str, Tag]:
    """Map each name to its Tag, creating the missing ones. Never commits."""
    if not names:
        return {}
    found = session.exec(select(Tag).where(Tag.name.in_(names))).all()  # type: ignore[attr-defined]
    by_name = {tag.name: tag for tag in found}
    missing = [Tag(name=name) for name in dict.fromkeys(names) if name not in by_name]
    if missing:
        session.add_all(missing)
        session.flush()
        by_name.update({tag.name: tag for tag in missing})
    return by_name


def _link_tags(session: Session, tx_id: int, names: list[str]) -> None:
    by_name = _resolve_tags(session, names)
    linked = {
        link.tag_id
        for link in session.exec(
            select(TransactionTag).where(TransactionTag.transaction_id == tx_id)
        ).all()
    }
    session.add_all(
        [
            TransactionTag(transaction_id=tx_id, tag_id=tag.id)
            for tag in by_name.values()
            if tag.id not in linked
        ]
    )


def _unlink_tags(session: Session, tx_id: int, names: list[str]) -> None:
    if not names:
        return
    stale = session.exec(select(Tag.id).where(Tag.name.in_(names))).all()  # type: ignore[attr-defined]
    if not stale:
        return
    session.exec(
        delete(TransactionTag).where(
            TransactionTag.transaction_id == tx_id,
            TransactionTag.tag_id.in_(stale),  # type: ignore[attr-defined]
        )
    )


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
    tag = _resolve_tags(session, _stripped([name]))[name.strip()]
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
    tx = _require_tx(session, tx_id)
    _link_tags(session, tx_id, _stripped(tags))
    session.commit()
    session.refresh(tx)
    return tx


def untag_transaction(session: Session, tx_id: int, tags: list[str]) -> Transaction:
    """Remove the given tag names from a transaction.

    Idempotent: an absent tag is a no-op, and other transactions' links
    are never touched.

    Args:
        session: Database session
        tx_id: Transaction ID
        tags: List of tag names to remove

    Returns:
        The updated Transaction

    Raises:
        NotFound: If transaction does not exist
    """
    tx = _require_tx(session, tx_id)
    _unlink_tags(session, tx_id, [name.strip() for name in tags])
    session.commit()
    session.refresh(tx)
    return tx


def set_transaction_tags(session: Session, tx_id: int, tags: list[str]) -> list[str]:
    """Replace a transaction's tag set with exactly the given names.

    Missing names are created and linked, current names not in the list are
    unlinked, all in one commit. An empty list clears all tags.

    Args:
        session: Database session
        tx_id: Transaction ID
        tags: The full desired tag set

    Returns:
        The resulting tag names, sorted

    Raises:
        NotFound: If transaction does not exist
        ValidationError: If a name is empty after stripping whitespace
    """
    _require_tx(session, tx_id)
    desired = _stripped(tags)
    current = tag_names_by_transaction(session, [tx_id])[tx_id]
    _link_tags(session, tx_id, [n for n in desired if n not in current])
    _unlink_tags(session, tx_id, [n for n in current if n not in desired])
    session.commit()
    return sorted(set(desired))


def tag_names_by_transaction(
    session: Session, tx_ids: list[int]
) -> dict[int, list[str]]:
    """Map each transaction id to its sorted tag names, in one query.

    Args:
        session: Database session
        tx_ids: Transaction IDs to look up

    Returns:
        Dict with one entry per requested id ([] when untagged)
    """
    names: dict[int, list[str]] = {tx_id: [] for tx_id in tx_ids}
    if not tx_ids:
        return names
    rows = session.exec(
        select(TransactionTag.transaction_id, Tag.name)
        .join(Tag, Tag.id == TransactionTag.tag_id)  # type: ignore[arg-type]
        .where(TransactionTag.transaction_id.in_(tx_ids))  # type: ignore[attr-defined]
    ).all()
    for tx_id, name in rows:
        names[tx_id].append(name)
    for values in names.values():
        values.sort()
    return names


def update_tag(session: Session, tag_id: int, name: str) -> Tag:
    """Rename a tag.

    Raises:
        NotFound: If the tag does not exist.
        ValidationError: Empty name, or a name already used by another tag.
    """
    tag = session.get(Tag, tag_id)
    if tag is None:
        raise NotFound(f"tag {tag_id} not found")
    name = name.strip()
    if not name:
        raise ValidationError("tag name is required")
    clash = session.exec(select(Tag).where(Tag.name == name)).first()
    if clash is not None and clash.id != tag_id:
        raise ValidationError(f"tag '{name}' already exists")
    tag.name = name
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag


def delete_tag(session: Session, tag_id: int) -> None:
    """Hard-delete a tag and its transaction links.

    Raises:
        NotFound: If the tag does not exist.
    """
    tag = session.get(Tag, tag_id)
    if tag is None:
        raise NotFound(f"tag {tag_id} not found")
    session.exec(delete(TransactionTag).where(TransactionTag.tag_id == tag_id))
    session.delete(tag)
    session.commit()
