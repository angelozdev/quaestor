from quaestor.mcp.tools import settings as settings_tools
from quaestor.mcp.tools.settings import GetSettingsInput, UpdateSettingsInput
from quaestor.services import accounts


def test_get_settings_default_card(session):
    out = settings_tools.get_settings(session, GetSettingsInput())
    assert "Base currency: COP" in out
    assert "(none)" in out  # default_source_account_id is None initially


def test_update_settings_base_currency(session):
    out = settings_tools.update_settings(
        session, UpdateSettingsInput(base_currency="USD")
    )
    assert "Base currency: USD" in out


def test_update_settings_rejects_unsupported_currency(session):
    out = settings_tools.update_settings(
        session, UpdateSettingsInput(base_currency="XYZ")
    )
    assert "Invalid input" in out


def test_update_settings_default_source_account(session):
    acc = accounts.create_account(session, "Bancolombia", "debit", "COP", balance=0)
    out = settings_tools.update_settings(
        session, UpdateSettingsInput(default_source_account="Bancolombia")
    )
    assert "default source account: 1" in out  # the new account's id


def test_update_settings_unknown_account_returns_text(session):
    out = settings_tools.update_settings(
        session, UpdateSettingsInput(default_source_account="Ghost")
    )
    assert "not found" in out