from datetime import date

import pytest
from quaestor.domain.errors import NotFound
from quaestor.domain.models import Account, AccountType, Transaction, TxType
from quaestor.services import tags

from tests.support.categories import a_category


def _make_transaction(session):
    acc = Account(name="A", type=AccountType.debit, currency="COP")
    session.add(acc)
    session.commit()
    session.refresh(acc)
    tx = Transaction(
        date=date(2026, 6, 1),
        payee="Test",
        type=TxType.expense,
        amount=1000,
        currency="COP",
        account_id=acc.id,
        category_id=a_category(session, TxType.expense),
    )
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx


def test_create_tag_is_idempotent(session):
    t1 = tags.create_tag(session, "trip")
    t2 = tags.create_tag(session, "trip")
    assert t1.id == t2.id
    assert len(tags.list_tags(session)) == 1


def test_tag_creates_missing_and_no_duplicates(session):
    tx = _make_transaction(session)
    tags.tag_transaction(session, tx.id, ["trip", "japan"])
    tags.tag_transaction(session, tx.id, ["trip"])  # already exists -> no duplicate link
    names = {t.name for t in tags.list_tags(session)}
    assert names == {"trip", "japan"}


def test_tag_nonexistent_transaction(session):
    with pytest.raises(NotFound):
        tags.tag_transaction(session, 999, ["x"])


def test_update_tag_renames(session):
    t = tags.create_tag(session, "trip")
    updated = tags.update_tag(session, t.id, "vacation")
    assert updated.name == "vacation"


def test_update_tag_to_existing_name_rejected(session):
    tags.create_tag(session, "trip")
    other = tags.create_tag(session, "food")
    import pytest
    from quaestor.domain.errors import ValidationError

    with pytest.raises(ValidationError):
        tags.update_tag(session, other.id, "trip")


def test_update_tag_to_its_own_current_name_is_allowed(session):
    t = tags.create_tag(session, "trip")
    updated = tags.update_tag(session, t.id, "trip")
    assert updated.id == t.id and updated.name == "trip"


def test_delete_tag_removes_links(session):
    from datetime import date

    from quaestor.domain.models import AccountType, TransactionTag
    from quaestor.services import accounts, transactions

    acc = accounts.create_account(session, "Cash", AccountType.cash, "COP")
    tx = transactions.record_expense(
        session, acc.id, 1000, "COP", date(2026, 6, 17), "Shop", category_id=a_category(session, TxType.expense)
    )
    tags.tag_transaction(session, tx.id, ["trip"])
    t = tags.list_tags(session)[0]
    tags.delete_tag(session, t.id)
    assert tags.list_tags(session) == []
    assert session.get(TransactionTag, (tx.id, t.id)) is None


def test_delete_tag_missing_raises(session):
    import pytest
    from quaestor.domain.errors import NotFound

    with pytest.raises(NotFound):
        tags.delete_tag(session, 999)


def _names(session, tx_id):
    from quaestor.domain.models import Tag, TransactionTag
    from sqlmodel import select

    rows = session.exec(
        select(Tag.name)
        .join(TransactionTag, TransactionTag.tag_id == Tag.id)
        .where(TransactionTag.transaction_id == tx_id)
    ).all()
    return sorted(rows)


def test_untag_removes_only_the_named_links(session):
    tx = _make_transaction(session)
    tags.tag_transaction(session, tx.id, ["trip", "food"])
    tags.untag_transaction(session, tx.id, ["trip"])
    assert _names(session, tx.id) == ["food"]


def test_untag_absent_tag_is_a_noop(session):
    tx = _make_transaction(session)
    tags.tag_transaction(session, tx.id, ["trip"])
    tags.untag_transaction(session, tx.id, ["ghost"])
    assert _names(session, tx.id) == ["trip"]


def test_untag_is_idempotent(session):
    tx = _make_transaction(session)
    tags.tag_transaction(session, tx.id, ["trip"])
    tags.untag_transaction(session, tx.id, ["trip"])
    tags.untag_transaction(session, tx.id, ["trip"])
    assert _names(session, tx.id) == []


def test_untag_missing_transaction_raises(session):
    with pytest.raises(NotFound):
        tags.untag_transaction(session, 999, ["trip"])


def test_untag_leaves_other_transactions_links(session):
    first = _make_transaction(session)
    second = Transaction(
        date=first.date,
        payee="Other",
        type=TxType.expense,
        amount=500,
        currency="COP",
        account_id=first.account_id,
        category_id=a_category(session, TxType.expense),
    )
    session.add(second)
    session.commit()
    session.refresh(second)
    tags.tag_transaction(session, first.id, ["trip"])
    tags.tag_transaction(session, second.id, ["trip"])
    tags.untag_transaction(session, first.id, ["trip"])
    assert _names(session, first.id) == []
    assert _names(session, second.id) == ["trip"]


def test_set_transaction_tags_replaces_the_set(session):
    tx = _make_transaction(session)
    tags.tag_transaction(session, tx.id, ["trip", "food"])
    tags.set_transaction_tags(session, tx.id, ["food", "work"])
    assert _names(session, tx.id) == ["food", "work"]


def test_set_transaction_tags_empty_list_clears_all(session):
    tx = _make_transaction(session)
    tags.tag_transaction(session, tx.id, ["trip"])
    tags.set_transaction_tags(session, tx.id, [])
    assert _names(session, tx.id) == []


def test_set_transaction_tags_missing_transaction_raises(session):
    with pytest.raises(NotFound):
        tags.set_transaction_tags(session, 999, ["trip"])


def test_tag_names_by_transaction_maps_each_id(session):
    first = _make_transaction(session)
    second = Transaction(
        date=first.date,
        payee="Other",
        type=TxType.expense,
        amount=500,
        currency="COP",
        account_id=first.account_id,
        category_id=a_category(session, TxType.expense),
    )
    session.add(second)
    session.commit()
    session.refresh(second)
    tags.tag_transaction(session, first.id, ["trip", "food"])
    names = tags.tag_names_by_transaction(session, [first.id, second.id])
    assert names == {first.id: ["food", "trip"], second.id: []}
    assert tags.tag_names_by_transaction(session, []) == {}
