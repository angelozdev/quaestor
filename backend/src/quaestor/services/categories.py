"""Use cases for category groups and categories (ADR-023: group as entity)."""
from __future__ import annotations

from sqlmodel import Session, select

from ..domain.errors import ValidationError
from ..domain.models import Category, CategoryGroup


def crear_grupo(session: Session, name: str, sort_order: int = 0) -> CategoryGroup:
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
    grupo = CategoryGroup(name=name.strip(), sort_order=sort_order)
    session.add(grupo)
    session.commit()
    session.refresh(grupo)
    return grupo


def listar_grupos(
    session: Session, incluir_archivados: bool = False
) -> list[CategoryGroup]:
    """List all category groups ordered by sort_order.

    Args:
        session: Database session.
        incluir_archivados: Whether to include archived groups (default: False).

    Returns:
        List of CategoryGroup objects ordered by sort_order.
    """
    stmt = select(CategoryGroup)
    if not incluir_archivados:
        stmt = stmt.where(CategoryGroup.archived == False)  # noqa: E712
    return list(session.exec(stmt.order_by(CategoryGroup.sort_order)).all())


def crear_categoria(
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


def listar_categorias(
    session: Session, incluir_archivadas: bool = False
) -> list[Category]:
    """List all categories.

    Args:
        session: Database session.
        incluir_archivadas: Whether to include archived categories (default: False).

    Returns:
        List of Category objects.
    """
    stmt = select(Category)
    if not incluir_archivadas:
        stmt = stmt.where(Category.archived == False)  # noqa: E712
    return list(session.exec(stmt).all())
