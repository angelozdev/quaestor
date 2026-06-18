import pytest

from quaestor.domain.errors import ValidationError
from quaestor.services import categories


def test_create_group_and_linked_category(session):
    grupo = categories.create_group(session, "Essentials", sort_order=1)
    cat = categories.create_category(session, "Groceries", group_id=grupo.id)
    assert cat.group_id == grupo.id
    assert cat.is_income is False


def test_category_without_group_is_valid(session):
    cat = categories.create_category(session, "No group")
    assert cat.group_id is None


def test_category_with_nonexistent_group_fails(session):
    with pytest.raises(ValidationError):
        categories.create_category(session, "X", group_id=999)


def test_category_flags(session):
    cat = categories.create_category(
        session, "Transfers", is_income=False,
        exclude_from_budget=True, exclude_from_totals=True,
    )
    assert cat.exclude_from_budget is True
    assert cat.exclude_from_totals is True


def test_list_groups_ordered(session):
    categories.create_group(session, "Entertainment", sort_order=2)
    categories.create_group(session, "Essentials", sort_order=1)
    nombres = [g.name for g in categories.list_groups(session)]
    assert nombres == ["Essentials", "Entertainment"]


def test_update_group_renames_and_reorders(session):
    g = categories.create_group(session, "Ocio", sort_order=1)
    updated = categories.update_group(session, g.id, name="Entretenimiento", sort_order=5)
    assert updated.name == "Entretenimiento" and updated.sort_order == 5


def test_update_group_missing_raises(session):
    import pytest

    from quaestor.domain.errors import NotFound

    with pytest.raises(NotFound):
        categories.update_group(session, 999, name="X")


def test_archive_group_hides_from_default_list(session):
    g = categories.create_group(session, "Temp")
    categories.archive_group(session, g.id)
    assert all(x.id != g.id for x in categories.list_groups(session))
    assert any(x.id == g.id for x in categories.list_groups(session, include_archived=True))
