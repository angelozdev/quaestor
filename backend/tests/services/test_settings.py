import pytest

from quaestor.domain.errors import ValidationError
from quaestor.domain.models import AccountType
from quaestor.services import accounts, settings


def test_get_settings_returns_singleton(session):
    s = settings.get_settings(session)
    assert s.id == 1
    assert s.base_currency == "COP"


def test_update_settings_sets_default_source_account(session):
    acc = accounts.create_account(session, "Savings", AccountType.savings, "COP")
    s = settings.update_settings(session, default_source_account_id=acc.id)
    assert s.default_source_account_id == acc.id


def test_update_settings_bad_account_rejected(session):
    with pytest.raises(ValidationError):
        settings.update_settings(session, default_source_account_id=4242)


def test_update_settings_bad_currency_rejected(session):
    with pytest.raises(ValidationError):
        settings.update_settings(session, base_currency="EUR")
