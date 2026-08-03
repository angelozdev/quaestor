from datetime import date

import pytest
from quaestor.domain.errors import ValidationError
from quaestor.domain.models import Category, IntervalUnit, RecurringMode, TxType
from quaestor.services import accounts, categories, recurring, transactions


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
        session,
        "Transfers",
        is_income=False,
        exclude_from_budget=True,
        exclude_from_totals=True,
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
    updated = categories.update_category(session, cat.id, name="Food", group_id=g.id, exclude_from_budget=True)
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


def test_a_category_in_use_cannot_change_direction(session):
    """Flipping is_income would make every movement filed under it contradict
    its own type — the condition ADR-0042 exists to remove."""
    acc = accounts.create_account(session, "Bank", "debit", "COP", balance=100_000)
    comida = categories.create_category(session, "Comida")
    transactions.record_expense(session, acc.id, 20_000, "COP", date(2026, 8, 3), "Exito", category_id=comida.id)

    with pytest.raises(ValidationError) as refusal:
        categories.update_category(session, comida.id, is_income=True)

    assert "Comida" in str(refusal.value)
    assert categories.get_category(session, comida.id).is_income is False


def test_a_category_no_movement_uses_can_still_change_direction(session):
    unused = categories.create_category(session, "Rendimientos")
    flipped = categories.update_category(session, unused.id, is_income=True)
    assert flipped.is_income is True


def test_a_recurring_item_also_pins_its_category_direction(session):
    acc = accounts.create_account(session, "Bank", "debit", "COP", balance=0)
    servicios = categories.create_category(session, "Servicios")
    recurring.create_recurring(
        session,
        name="Internet",
        payee="Hogar",
        type=TxType.expense,
        mode=RecurringMode.auto,
        amount=85_000,
        currency="COP",
        category_id=servicios.id,
        account_id=acc.id,
        interval_unit=IntervalUnit.month,
        interval_count=1,
        start_date=date(2026, 8, 1),
    )

    with pytest.raises(ValidationError):
        categories.update_category(session, servicios.id, is_income=True)


def test_renaming_a_category_in_use_is_still_allowed(session):
    acc = accounts.create_account(session, "Bank", "debit", "COP", balance=100_000)
    comida = categories.create_category(session, "Comida")
    transactions.record_expense(session, acc.id, 20_000, "COP", date(2026, 8, 3), "Exito", category_id=comida.id)

    renamed = categories.update_category(session, comida.id, name="Alimentación")
    assert renamed.name == "Alimentación"


def test_a_name_an_active_category_holds_is_refused_anywhere(session):
    """AC-13 covers the whole app, not only the movement form."""
    categories.create_category(session, "Vuelos")

    with pytest.raises(ValidationError) as refusal:
        categories.create_category(session, "vuelos")

    assert "already exists" in str(refusal.value)
    assert [c.name for c in categories.list_categories(session)] == ["Vuelos"]


def test_a_name_an_archived_category_holds_offers_to_restore_it(session):
    archived = categories.create_category(session, "Vuelos")
    categories.archive_category(session, archived.id)

    with pytest.raises(ValidationError) as refusal:
        categories.create_category(session, "Vuelos")

    assert "restore" in str(refusal.value).lower()
    assert "Vuelos" in str(refusal.value)


def test_the_same_name_in_the_other_direction_is_allowed(session):
    """A name is unique per direction, not across the app (AC-13).

    "Intereses" is both what the bank charges and what it pays; no offering
    ever shows the two together, because every one is filtered by direction.
    """
    paid = categories.create_category(session, "Intereses")
    earned = categories.create_category(session, "Intereses", is_income=True)

    assert paid.id != earned.id
    assert [c.name for c in categories.list_categories(session, is_income=False)] == ["Intereses"]
    assert [c.name for c in categories.list_categories(session, is_income=True)] == ["Intereses"]


def test_the_same_name_in_the_same_direction_is_still_refused(session):
    categories.create_category(session, "Bonos", is_income=True)

    with pytest.raises(ValidationError) as refusal:
        categories.create_category(session, "bonos", is_income=True)

    assert "income category" in str(refusal.value)


def test_an_archived_match_of_the_other_direction_does_not_block(session):
    archived = categories.create_category(session, "Ajuste")
    categories.archive_category(session, archived.id)

    created = categories.create_category(session, "Ajuste", is_income=True)
    assert created.is_income is True


def _same_name_pair(session, name="Auto Insurance"):
    """Production's shape: one archived and one active, same name, same direction.

    Built with the model rather than the service, because `create_category`
    refuses to make this pair now — production has carried it since before the
    rule existed (`acs.md` AC-13).
    """
    archived = Category(name=name, is_income=False, archived=True)
    active = Category(name=name, is_income=False, archived=False)
    session.add_all([archived, active])
    session.commit()
    session.refresh(archived)
    session.refresh(active)
    return archived, active


def test_an_active_match_is_named_even_when_an_archived_one_shares_the_name(session):
    """The archived branch must not win over an active one — its advice would be
    to restore a category whose name is already taken by a live one."""
    _same_name_pair(session)

    with pytest.raises(ValidationError) as refusal:
        categories.create_category(session, "auto insurance")

    assert "already exists" in str(refusal.value)
    assert "restore" not in str(refusal.value).lower()


def test_restoring_into_a_name_an_active_category_holds_is_refused(session):
    archived, _active = _same_name_pair(session)

    with pytest.raises(ValidationError) as refusal:
        categories.unarchive_category(session, archived.id)

    assert "Auto Insurance" in str(refusal.value)
    active_names = [c.name for c in categories.list_categories(session, is_income=False)]
    assert active_names.count("Auto Insurance") == 1


def test_restoring_a_category_whose_name_is_free_still_works(session):
    cat = categories.create_category(session, "Suscripciones")
    categories.archive_category(session, cat.id)

    restored = categories.unarchive_category(session, cat.id)
    assert restored.archived is False
