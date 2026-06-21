import pytest

from quaestor.domain.errors import NotFound, ValidationError
from quaestor.domain.models import AccountType
from quaestor.services import accounts


def test_create_and_get_account(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP")
    assert acc.id is not None
    assert accounts.get_account(session, acc.id).name == "Bancolombia"


def test_create_account_accepts_string_type(session):
    acc = accounts.create_account(session, "Tarjeta", "credit", "COP", balance=-50000)
    assert acc.type == AccountType.credit
    assert acc.balance == -50000


def test_create_account_rejects_currency(session):
    with pytest.raises(ValidationError):
        accounts.create_account(session, "X", AccountType.cash, "EUR")


def test_create_account_rejects_empty_name(session):
    with pytest.raises(ValidationError):
        accounts.create_account(session, "  ", AccountType.cash, "COP")


def test_list_excludes_archived_by_default(session):
    a = accounts.create_account(session, "A", AccountType.debit, "COP")
    accounts.create_account(session, "B", AccountType.debit, "COP")
    accounts.archive_account(session, a.id)
    activas = accounts.list_accounts(session)
    assert {c.name for c in activas} == {"B"}
    todas = accounts.list_accounts(session, include_archived=True)
    assert {c.name for c in todas} == {"A", "B"}


def test_get_nonexistent(session):
    with pytest.raises(NotFound):
        accounts.get_account(session, 999)


def test_update_account_renames_and_retypes(session):
    acc = accounts.create_account(session, "Cash", AccountType.cash, "COP")
    updated = accounts.update_account(session, acc.id, name="Wallet", type=AccountType.debit)
    assert updated.name == "Wallet"
    assert updated.type == AccountType.debit


def test_update_account_empty_name_rejected(session):
    acc = accounts.create_account(session, "Cash", AccountType.cash, "COP")
    with pytest.raises(ValidationError):
        accounts.update_account(session, acc.id, name="  ")


def test_update_account_missing_id_raises(session):
    with pytest.raises(NotFound):
        accounts.update_account(session, 999, name="X")


def test_unarchive_account_clears_flag(session):
    acc = accounts.create_account(session, "Bank", "debit", "COP", balance=0)
    accounts.archive_account(session, acc.id)
    restored = accounts.unarchive_account(session, acc.id)
    assert restored.archived is False


def test_unarchive_active_account_is_noop(session):
    acc = accounts.create_account(session, "Bank", "debit", "COP", balance=0)
    restored = accounts.unarchive_account(session, acc.id)
    assert restored.archived is False
