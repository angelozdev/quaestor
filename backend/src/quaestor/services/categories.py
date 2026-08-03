"""Use cases for category groups and categories (ADR-023: group as entity)."""

from __future__ import annotations

from sqlalchemy import func
from sqlmodel import Session, select

from ..domain.errors import NotFound, ValidationError
from ..domain.models import Category, CategoryGroup, RecurringItem, Transaction, TxType
from ..domain.rules import category_is_income_for


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


def list_groups(session: Session, include_archived: bool = False) -> list[CategoryGroup]:
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


def _by_name(session: Session, name: str, is_income: bool) -> Category | None:
    """The category of that direction holding this name, archived or not.

    Scoped to one direction on purpose (AC-13, owner's decision 2026-08-03): a
    name is unique per direction, not across the app. "Intereses" can be both
    the ones paid to the bank and the ones earned from it, and no list ever
    shows the two together because every offering is already filtered by
    direction.
    """
    folded = name.strip().casefold()
    matches = [
        cat
        for cat in session.exec(select(Category).where(Category.is_income == is_income)).all()
        if cat.name.casefold() == folded
    ]
    # An active match wins: where production carries both (`🛡️ Auto Insurance`),
    # naming the archived one would advise a restore into a name a live category
    # already holds.
    return next((cat for cat in matches if not cat.archived), None) or next(iter(matches), None)


def _refuse_name_already_held(session: Session, name: str, is_income: bool) -> None:
    """Two categories of the same direction with the same name are
    indistinguishable in every list that offers them.

    The rule holds wherever a category is created — the movement form, the
    Categorías screen, the API and the assistant (AC-13). An archived match is
    refused with an offer to restore it, because creating a second one leaves
    the owner with the pair production already carries in `🛡️ Auto Insurance`.
    """
    held = _by_name(session, name, is_income)
    if held is None:
        return
    direction = "income" if is_income else "expense"
    if held.archived:
        raise ValidationError(
            f"an archived {direction} category is already named {held.name!r} — "
            f"restore it instead of creating a second one"
        )
    raise ValidationError(f"an {direction} category named {held.name!r} already exists")


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
        ValidationError: If name is empty, whitespace-only, already held by
            another category — archived or not (AC-13) — or group_id is invalid.
    """
    if not name or not name.strip():
        raise ValidationError("category name is required")
    _refuse_name_already_held(session, name, is_income)
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
    session: Session,
    include_archived: bool = False,
    is_income: bool | None = None,
) -> list[Category]:
    """List all categories.

    Args:
        session: Database session.
        include_archived: Whether to include archived categories (default: False).
        is_income: Keep only categories of one direction. `None` (default)
            returns both; `True`/`False` is the offering shown while recording
            money coming in / going out (ADR-0042).

    Returns:
        List of Category objects.
    """
    stmt = select(Category)
    if not include_archived:
        stmt = stmt.where(Category.archived == False)  # noqa: E712
    if is_income is not None:
        stmt = stmt.where(Category.is_income == is_income)
    return list(session.exec(stmt).all())


def update_group(session: Session, group_id: int, name=None, sort_order=None) -> CategoryGroup:
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


_UNSET = object()


def get_category(session: Session, category_id: int) -> Category:
    """Fetch a category by id, or raise NotFound."""
    cat = session.get(Category, category_id)
    if cat is None:
        raise NotFound(f"category {category_id} not found")
    return cat


def _uses_of(session: Session, category_id: int) -> int:
    """How many movements and repeating obligations are filed under it."""
    movements = session.exec(
        select(func.count()).select_from(Transaction).where(Transaction.category_id == category_id)
    ).one()
    obligations = session.exec(
        select(func.count()).select_from(RecurringItem).where(RecurringItem.category_id == category_id)
    ).one()
    return movements + obligations


def _refuse_direction_change_in_use(session: Session, cat: Category) -> None:
    """A category in use cannot change direction (ADR-0042).

    Everything filed under it matched its direction when it was written, so
    flipping the flag would make every one of them contradict its own type —
    the condition the direction rule exists to remove, reintroduced in a single
    edit and invisible afterwards.
    """
    uses = _uses_of(session, cat.id)
    if not uses:
        return
    holds = "movement" if uses == 1 else "movements"
    raise ValidationError(
        f"category {cat.name!r} is already filed on {uses} {holds}, so its direction cannot change — "
        f"create a category of the other direction instead"
    )


def update_category(
    session: Session,
    category_id: int,
    name=None,
    group_id=_UNSET,
    is_income=None,
    exclude_from_budget=None,
    exclude_from_totals=None,
) -> Category:
    """Update a category. `group_id=_UNSET` leaves it unchanged; `group_id=None`
    unassigns the group; a non-None group_id must exist.

    Raises:
        NotFound: If the category does not exist.
        ValidationError: Empty name, a group_id that does not exist, or a
            direction change on a category something is already filed under.
    """
    cat = get_category(session, category_id)
    if is_income is not None and is_income != cat.is_income:
        _refuse_direction_change_in_use(session, cat)
    if name is not None:
        if not name.strip():
            raise ValidationError("category name is required")
        cat.name = name.strip()
    if group_id is not _UNSET:
        if group_id is not None and session.get(CategoryGroup, group_id) is None:
            raise ValidationError(f"group {group_id} does not exist")
        cat.group_id = group_id
    if is_income is not None:
        cat.is_income = is_income
    if exclude_from_budget is not None:
        cat.exclude_from_budget = exclude_from_budget
    if exclude_from_totals is not None:
        cat.exclude_from_totals = exclude_from_totals
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return cat


def archive_category(session: Session, category_id: int) -> Category:
    """Archive a category.

    Raises:
        NotFound: If the category does not exist.
    """
    cat = get_category(session, category_id)
    cat.archived = True
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return cat


def unarchive_category(session: Session, category_id: int) -> Category:
    """Re-activate an archived category. Idempotent no-op if already active.

    Raises:
        NotFound: If the category does not exist.
        ValidationError: An active category of the same direction already holds
            the name. Restoring would produce the duplicate pair AC-13 exists to
            prevent — reachable today on production's `🛡️ Auto Insurance`.
    """
    cat = get_category(session, category_id)
    if cat.archived:
        live = _by_name(session, cat.name, cat.is_income)
        if live is not None and not live.archived and live.id != cat.id:
            direction = "income" if cat.is_income else "expense"
            raise ValidationError(
                f"an active {direction} category is already named {cat.name!r} — "
                f"rename one of the two before restoring this one"
            )
    cat.archived = False
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return cat


def _chosen_for_movement(session: Session, category_id: int, wants_income: bool) -> Category:
    cat = session.get(Category, category_id)
    if cat is None:
        raise ValidationError(f"category {category_id} not found")
    if cat.archived:
        raise ValidationError(f"category {category_id} is archived")
    if cat.is_income != wants_income:
        held = "income" if cat.is_income else "expense"
        needed = "income" if wants_income else "expense"
        raise ValidationError(
            f"category {cat.name!r} is an {held} category, so it does not match the "
            f"direction of the money — this movement needs an {needed} category"
        )
    return cat


def resolve_for_movement(
    session: Session,
    tx_type: TxType,
    category_id: int | None = None,
    new_category: str | None = None,
) -> int | None:
    """The category a movement carries, or the refusal that stops it (ADR-0042).

    The single answer to "which category does this movement carry?", called by
    every write path so the rule has one definition instead of five copies.

    Args:
        session: Database session.
        tx_type: What kind of movement this is. A transfer carries no category.
        category_id: An existing category chosen by the user.
        new_category: A name to create and file this movement under, in the
            same action — mutually exclusive with `category_id`.

    Returns:
        The category id to store; `None` for a transfer.

    Raises:
        ValidationError: A transfer given a category; neither or both of the
            two arguments on an expense or income; a name an active category
            already holds (or an archived one, offering to restore it); a
            category that is missing, archived, or of the wrong direction.
    """
    tx_type = TxType(tx_type)
    if tx_type == TxType.transfer:
        if category_id is not None or new_category is not None:
            raise ValidationError(
                "a transfer carries no category — moving money between your own accounts is neither spending nor income"
            )
        return None
    if category_id is not None and new_category is not None:
        raise ValidationError("choose an existing category or create one, not both")
    wants_income = category_is_income_for(tx_type)
    if new_category is not None:
        return create_category(session, new_category, is_income=wants_income).id
    if category_id is None:
        direction = "income" if wants_income else "expense"
        raise ValidationError(f"category is required: every {direction} must say what it was for")
    return _chosen_for_movement(session, category_id, wants_income).id


def unarchive_group(session: Session, group_id: int) -> CategoryGroup:
    """Re-activate an archived category group. Idempotent no-op if already active.

    Raises:
        NotFound: If the group does not exist.
    """
    group = session.get(CategoryGroup, group_id)
    if group is None:
        raise NotFound(f"group {group_id} not found")
    group.archived = False
    session.add(group)
    session.commit()
    session.refresh(group)
    return group
