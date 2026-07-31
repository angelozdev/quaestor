from datetime import date
from decimal import Decimal

import pytest

from quaestor.domain.errors import NotFound
from quaestor.domain.models import Account, AccountType, Transaction, TxType
from quaestor.services import tags


def _make_transaction(session):
    acc = Account(name="A", type=AccountType.debit, currency="COP")
    session.add(acc)
    session.commit()
    session.refresh(acc)
    tx = Transaction(
        date=date(2026, 6, 1), payee="Test", type=TxType.expense,
        amount=1000, currency="COP",
        account_id=acc.id,
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


def test_delete_tag_removes_links(session):
    from quaestor.domain.models import TransactionTag
    from quaestor.services import accounts, transactions
    from quaestor.domain.models import AccountType
    from datetime import date

    acc = accounts.create_account(session, "Cash", AccountType.cash, "COP")
    tx = transactions.record_expense(session, acc.id, 1000, "COP", date(2026, 6, 17), "Shop")
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
