import pytest

from quaestor.domain.errors import ValidationError
from quaestor.services import categories


def test_create_group_and_linked_category(session):
    group = categories.create_group(session, "Essentials", sort_order=1)
    cat = categories.create_category(session, "Groceries", group_id=group.id)
    assert cat.group_id == group.id
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
    names = [g.name for g in categories.list_groups(session)]
    assert names == ["Essentials", "Entertainment"]


def test_update_group_renames_and_reorders(session):
    g = categories.create_group(session, "Leisure", sort_order=1)
    updated = categories.update_group(session, g.id, name="Entertainment", sort_order=5)
    assert updated.name == "Entertainment" and updated.sort_order == 5


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


def test_get_category_missing_raises(session):
    import pytest

    from quaestor.domain.errors import NotFound

    with pytest.raises(NotFound):
        categories.get_category(session, 999)


def test_update_category_reassigns_group_and_flags(session):
    g = categories.create_group(session, "Essentials")
    cat = categories.create_category(session, "Groceries")
    updated = categories.update_category(
        session, cat.id, name="Food", group_id=g.id, exclude_from_budget=True
    )
    assert updated.name == "Food"
    assert updated.group_id == g.id
    assert updated.exclude_from_budget is True


def test_update_category_can_unassign_group(session):
    g = categories.create_group(session, "Essentials")
    cat = categories.create_category(session, "Groceries", group_id=g.id)
    updated = categories.update_category(session, cat.id, group_id=None)
    assert updated.group_id is None


def test_update_category_bad_group_rejected(session):
    cat = categories.create_category(session, "Groceries")
    import pytest

    from quaestor.domain.errors import ValidationError

    with pytest.raises(ValidationError):
        categories.update_category(session, cat.id, group_id=12345)


def test_archive_category_hides_from_default_list(session):
    cat = categories.create_category(session, "Temp")
    categories.archive_category(session, cat.id)
    assert all(c.id != cat.id for c in categories.list_categories(session))


def test_unarchive_category_clears_flag(session):
    from quaestor.services import categories
    cat = categories.create_category(session, name="Food")
    categories.archive_category(session, cat.id)
    assert categories.unarchive_category(session, cat.id).archived is False


def test_unarchive_group_clears_flag(session):
    from quaestor.services import categories
    g = categories.create_group(session, name="Bills")
    categories.archive_group(session, g.id)
    assert categories.unarchive_group(session, g.id).archived is False
