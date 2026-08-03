from quaestor.mcp.tools import masters
from quaestor.mcp.tools.masters import (
    CreateTagInput,
    DeleteTagInput,
    UpdateTagInput,
)


def test_create_tag(session):
    out = masters.create_tag(session, CreateTagInput(name="travel"))
    assert out == "Tag 'travel' (id 1)."


def test_create_tag_idempotent_by_name(session):
    masters.create_tag(session, CreateTagInput(name="trip"))
    out = masters.create_tag(session, CreateTagInput(name="trip"))
    assert out == "Tag 'trip' (id 1)."  # same id, no duplicate


def test_create_tag_empty_name_rejected(session):
    out = masters.create_tag(session, CreateTagInput(name="   "))
    assert "Invalid input" in out


def test_update_tag_renames(session):
    masters.create_tag(session, CreateTagInput(name="old"))
    out = masters.update_tag(session, UpdateTagInput(tag="old", name="new"))
    assert out == "Tag 'new' (id 1)."


def test_update_tag_unknown_returns_text(session):
    out = masters.update_tag(session, UpdateTagInput(tag="ghost", name="x"))
    assert "not found" in out


def test_update_tag_duplicate_name_rejected(session):
    masters.create_tag(session, CreateTagInput(name="a"))
    masters.create_tag(session, CreateTagInput(name="b"))
    out = masters.update_tag(session, UpdateTagInput(tag="a", name="b"))
    assert "Invalid input" in out


def test_delete_tag_removes_it(session):
    masters.create_tag(session, CreateTagInput(name="trip"))
    out = masters.delete_tag(session, DeleteTagInput(tag="trip"))
    assert out == "Deleted tag 'trip'."
