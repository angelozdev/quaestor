from quaestor.domain.models import Category
from quaestor.mcp.tools import masters
from quaestor.mcp.tools.masters import (
    ArchiveCategoryInput,
    CreateCategoryInput,
    GetCategoryInput,
    RestoreCategoryInput,
    UpdateCategoryInput,
)
from quaestor.services import categories


def _seed_group(session):
    return categories.create_group(session, "Essentials")


def test_create_category_with_group_returns_card(session):
    _seed_group(session)
    out = masters.create_category(session, CreateCategoryInput(name="Groceries", group="Essentials"))
    assert "Groceries" in out and "Essentials" in out


def test_create_category_income_flag(session):
    out = masters.create_category(session, CreateCategoryInput(name="Salary", is_income=True))
    assert "Salary" in out and "income" in out


def test_create_category_unknown_group_returns_text(session):
    _seed_group(session)
    out = masters.create_category(session, CreateCategoryInput(name="X", group="Nonexistent"))
    assert "not found" in out


def test_update_category_renames_and_regroups(session):
    _seed_group(session)
    categories.create_group(session, "Discretionary")
    categories.create_category(session, "Fun")
    out = masters.update_category(
        session, UpdateCategoryInput(category="Fun", name="Entertainment", group="Discretionary")
    )
    assert "Entertainment" in out and "Discretionary" in out


def test_update_category_unknown_returns_text(session):
    out = masters.update_category(session, UpdateCategoryInput(category="Ghost"))
    assert "not found" in out


def test_archive_and_restore_category_roundtrip(session):
    _seed_group(session)
    categories.create_category(session, "Groceries")
    out = masters.archive_category(session, ArchiveCategoryInput(category="Groceries"))
    assert "archived" in out
    out = masters.restore_category(session, RestoreCategoryInput(category="Groceries"))
    assert "Groceries" in out and "not found" not in out


def test_get_category_returns_card(session):
    g = _seed_group(session)
    categories.create_category(session, "Groceries", group_id=g.id)
    out = masters.get_category(session, GetCategoryInput(category="Groceries"))
    assert "Groceries" in out and "Essentials" in out


def test_the_assistant_can_actually_restore_an_archived_category(session):
    """AC-10 through the assistant, not through the service the handler calls.

    The name resolver listed active categories only, so the one tool whose whole
    job is an archived category could never find one.
    """
    cat = categories.create_category(session, "Suscripciones")
    masters.archive_category(session, ArchiveCategoryInput(category="Suscripciones"))

    out = masters.restore_category(session, RestoreCategoryInput(category="Suscripciones"))

    assert "not found" not in out
    session.refresh(cat)
    assert cat.archived is False


def test_the_advice_the_assistant_gives_is_an_action_the_assistant_can_take(session):
    """AC-13 offers a restore when the name matches an archived category. Taking
    that offer through the same door must work, or the advice is a dead end."""
    categories.archive_category(session, categories.create_category(session, "Vuelos").id)

    refusal = masters.create_category(session, CreateCategoryInput(name="Vuelos"))
    assert "restore it instead" in refusal

    out = masters.restore_category(session, RestoreCategoryInput(category="Vuelos"))
    assert "not found" not in out
    assert [c.name for c in categories.list_categories(session)] == ["Vuelos"]


def test_the_assistant_refuses_to_restore_into_a_name_an_active_category_holds(session):
    """N7's guard at the MCP door: production's `🛡️ Auto Insurance` pair.

    The resolver saw only the active row, so `unarchive_category` was handed a
    category that was not archived, skipped the guard, and reported success for
    a restore that never happened.
    """
    archived = Category(name="Auto Insurance", is_income=False, archived=True)
    active = Category(name="Auto Insurance", is_income=False, archived=False)
    session.add_all([archived, active])
    session.commit()
    session.refresh(archived)

    out = masters.restore_category(session, RestoreCategoryInput(category="Auto Insurance"))

    assert "already named" in out
    session.refresh(archived)
    assert archived.archived is True
