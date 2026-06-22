from datetime import date

from quaestor.mcp.tools import masters
from quaestor.mcp.tools.masters import (
    CreateAccountInput, UpdateAccountInput, ArchiveAccountInput,
    RestoreAccountInput, GetAccountInput,
)
from quaestor.services import accounts


def test_create_account_returns_card(session):
    out = masters.create_account(
        session, CreateAccountInput(name="Nequi", type="debit", currency="COP")
    )
    assert "Nequi" in out and "debit" in out
    assert "id=" in out


def test_create_account_rejects_empty_name(session):
    out = masters.create_account(
        session, CreateAccountInput(name="   ", type="debit")
    )
    assert "Invalid input" in out


def test_create_account_rejects_unsupported_currency(session):
    out = masters.create_account(
        session, CreateAccountInput(name="X", type="debit", currency="XYZ")
    )
    assert "Invalid input" in out


def test_update_account_renames_and_changes_type(session):
    acc = accounts.create_account(session, "Old", "debit", "COP", balance=0)
    out = masters.update_account(
        session, UpdateAccountInput(account="Old", name="New", type="savings")
    )
    assert "New" in out
    refreshed = accounts.get_account(session, acc.id)
    assert refreshed.name == "New"
    assert refreshed.type.value == "savings"


def test_update_account_unknown_name_returns_text(session):
    out = masters.update_account(
        session, UpdateAccountInput(account="Ghost", name="Whatever")
    )
    assert "not found" in out


def test_archive_account_soft_deletes(session, seeded):
    out = masters.archive_account(
        session, ArchiveAccountInput(account=seeded["account"].name)
    )
    assert "Bancolombia" in out and "archived" in out
    listed = accounts.list_accounts(session)  # default excludes archived
    assert listed == []


def test_archive_account_already_archived_is_idempotent(session, seeded):
    masters.archive_account(session, ArchiveAccountInput(account="Bancolombia"))
    out = masters.archive_account(session, ArchiveAccountInput(account="Bancolombia"))
    assert "Bancolombia" in out and "archived" in out


def test_restore_account(session, seeded):
    masters.archive_account(session, ArchiveAccountInput(account="Bancolombia"))
    out = masters.restore_account(session, RestoreAccountInput(account="Bancolombia"))
    assert "Bancolombia" in out and "restored" in out
    assert len(accounts.list_accounts(session)) == 1


def test_get_account_returns_card(session, seeded):
    out = masters.get_account(session, GetAccountInput(account="Bancolombia"))
    assert "Bancolombia" in out and "100000.00 COP" in out
