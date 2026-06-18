"""Use cases for category groups and categories (ADR-023: group as entity)."""
from __future__ import annotations

from sqlmodel import Session, select

from ..domain.errors import NotFound, ValidationError
from ..domain.models import Category, CategoryGroup


def create_group(session: Session, name: str, sort_order: int = 0) -> CategoryGroup:
    """Create a new category group.

    Args:
        session: Database session.
        name: Name of the group (required, non-empty).
        sort_order: Order for display (default: 0).

    Returns:
        The created CategoryGroup.

    Raises:
        ValidationError: If name is empty or whitespace-only.
    """
    if not name or not name.strip():
        raise ValidationError("group name is required")
    group = CategoryGroup(name=name.strip(), sort_order=sort_order)
    session.add(group)
    session.commit()
    session.refresh(group)
    return group


def list_groups(
    session: Session, include_archived: bool = False
) -> list[CategoryGroup]:
    """List all category groups ordered by sort_order.

    Args:
        session: Database session.
        include_archived: Whether to include archived groups (default: False).

    Returns:
        List of CategoryGroup objects ordered by sort_order.
    """
    stmt = select(CategoryGroup)
    if not include_archived:
        stmt = stmt.where(CategoryGroup.archived == False)  # noqa: E712
    return list(session.exec(stmt.order_by(CategoryGroup.sort_order)).all())


def create_category(
    session: Session,
    name: str,
    group_id: int | None = None,
    is_income: bool = False,
    exclude_from_budget: bool = False,
    exclude_from_totals: bool = False,
) -> Category:
    """Create a new category.

    Args:
        session: Database session.
        name: Name of the category (required, non-empty).
        group_id: Optional group ID. Must exist if provided.
        is_income: Whether this is an income category (default: False).
        exclude_from_budget: Whether to exclude from budget calculations (default: False).
        exclude_from_totals: Whether to exclude from totals (default: False).

    Returns:
        The created Category.

    Raises:
        ValidationError: If name is empty, whitespace-only, or group_id is invalid.
    """
    if not name or not name.strip():
        raise ValidationError("category name is required")
    if group_id is not None and session.get(CategoryGroup, group_id) is None:
        raise ValidationError(f"group {group_id} does not exist")
    cat = Category(
        name=name.strip(),
        group_id=group_id,
        is_income=is_income,
        exclude_from_budget=exclude_from_budget,
        exclude_from_totals=exclude_from_totals,
    )
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return cat


def list_categories(
    session: Session, include_archived: bool = False
) -> list[Category]:
    """List all categories.

    Args:
        session: Database session.
        include_archived: Whether to include archived categories (default: False).

    Returns:
        List of Category objects.
    """
    stmt = select(Category)
    if not include_archived:
        stmt = stmt.where(Category.archived == False)  # noqa: E712
    return list(session.exec(stmt).all())


def update_group(
    session: Session, group_id: int, name=None, sort_order=None
) -> CategoryGroup:
    """Update a category group's name and/or sort_order.

    Raises:
        NotFound: If the group does not exist.
        ValidationError: If name is provided but empty.
    """
    group = session.get(CategoryGroup, group_id)
    if group is None:
        raise NotFound(f"group {group_id} not found")
    if name is not None:
        if not name.strip():
            raise ValidationError("group name is required")
        group.name = name.strip()
    if sort_order is not None:
        group.sort_order = sort_order
    session.add(group)
    session.commit()
    session.refresh(group)
    return group


def archive_group(session: Session, group_id: int) -> CategoryGroup:
    """Archive a category group.

    Raises:
        NotFound: If the group does not exist.
    """
    group = session.get(CategoryGroup, group_id)
    if group is None:
        raise NotFound(f"group {group_id} not found")
    group.archived = True
    session.add(group)
    session.commit()
    session.refresh(group)
    return group
