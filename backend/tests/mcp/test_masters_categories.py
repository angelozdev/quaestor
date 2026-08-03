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
    out = masters.create_category(
        session, CreateCategoryInput(name="Groceries", group="Essentials")
    )
    assert "Groceries" in out and "Essentials" in out


def test_create_category_income_flag(session):
    out = masters.create_category(
        session, CreateCategoryInput(name="Salary", is_income=True)
    )
    assert "Salary" in out and "income" in out


def test_create_category_unknown_group_returns_text(session):
    _seed_group(session)
    out = masters.create_category(
        session, CreateCategoryInput(name="X", group="Nonexistent")
    )
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
    assert "Groceries" in out


def test_get_category_returns_card(session):
    g = _seed_group(session)
    categories.create_category(session, "Groceries", group_id=g.id)
    out = masters.get_category(session, GetCategoryInput(category="Groceries"))
    assert "Groceries" in out and "Essentials" in out
