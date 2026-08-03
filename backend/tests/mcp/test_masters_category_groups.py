from quaestor.mcp.tools import masters
from quaestor.mcp.tools.masters import (
    ArchiveCategoryGroupInput,
    CreateCategoryGroupInput,
    RestoreCategoryGroupInput,
    UpdateCategoryGroupInput,
)
from quaestor.services import categories


def test_create_group(session):
    out = masters.create_category_group(
        session, CreateCategoryGroupInput(name="Essentials", sort_order=2)
    )
    assert "Essentials" in out and "id=" in out


def test_create_group_empty_name_rejected(session):
    out = masters.create_category_group(
        session, CreateCategoryGroupInput(name="   ")
    )
    assert "Invalid input" in out


def test_update_group_renames(session):
    categories.create_group(session, "Old")
    out = masters.update_category_group(
        session, UpdateCategoryGroupInput(group="Old", name="New")
    )
    assert "New" in out


def test_update_group_unknown_returns_text(session):
    out = masters.update_category_group(
        session, UpdateCategoryGroupInput(group="Ghost")
    )
    assert "not found" in out


def test_archive_group(session):
    categories.create_group(session, "Essentials")
    out = masters.archive_category_group(
        session, ArchiveCategoryGroupInput(group="Essentials")
    )
    assert "archived" in out


def test_restore_group(session):
    categories.create_group(session, "Essentials")
    masters.archive_category_group(
        session, ArchiveCategoryGroupInput(group="Essentials")
    )
    out = masters.restore_category_group(
        session, RestoreCategoryGroupInput(group="Essentials")
    )
    assert "Essentials" in out and "restored" in out
