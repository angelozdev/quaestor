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
