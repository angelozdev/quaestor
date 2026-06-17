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
