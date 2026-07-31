from datetime import date

from quaestor.mcp.tools import transactions as tx_tools
from quaestor.mcp.tools.transactions import (
    GetTransactionInput, UpdateTransactionInput, DeleteTransactionInput,
)
from quaestor.services import accounts, fx, transactions as tx_service


def _seed(session):
    fx.set_trm(session, "4000")
    return accounts.create_account(session, "Bancolombia", "debit", "COP", balance=10_000_000)


def test_get_transaction_returns_card(session):
    _seed(session)
    tx = tx_service.record_expense(
        session, account_id=1, amount=5_000_000, currency="COP",
        date=date(2026, 6, 18), payee="Lunch",
    )
    out = tx_tools.get_transaction(session, GetTransactionInput(tx_id=tx.id))
    assert "Lunch" in out and "50000.00 COP" in out
    assert f"id={tx.id}" in out


def test_get_transaction_without_trm_returns_missing_rate_text(session):
    accounts.create_account(session, "Bancolombia", "debit", "COP", balance=10_000_000)
    tx = tx_service.record_expense(
        session, account_id=1, amount=5_000_000, currency="COP",
        date=date(2026, 6, 18), payee="Lunch",
    )
    out = tx_tools.get_transaction(session, GetTransactionInput(tx_id=tx.id))
    assert "No TRM is set" in out
    assert "set_fx_rate" in out


def test_get_transaction_unknown_returns_text(session):
    out = tx_tools.get_transaction(session, GetTransactionInput(tx_id=999))
    assert "not found" in out


def test_update_transaction_changes_payee_and_notes(session):
    _seed(session)
    tx = tx_service.record_expense(
        session, account_id=1, amount=5_000_000, currency="COP",
        date=date(2026, 6, 18), payee="Lunch",
    )
    out = tx_tools.update_transaction(
        session, UpdateTransactionInput(
            tx_id=tx.id, payee="Brunch", notes="with friends"
        )
    )
    assert "Brunch" in out
    refreshed = tx_service.get_transaction(session, tx.id)
    assert refreshed.payee == "Brunch"
    assert refreshed.notes == "with friends"


def test_update_transaction_can_clear_notes_with_empty_string(session):
    _seed(session)
    tx = tx_service.record_expense(
        session, account_id=1, amount=5_000_000, currency="COP",
        date=date(2026, 6, 18), payee="Lunch", notes="note",
    )
    tx_tools.update_transaction(
        session, UpdateTransactionInput(tx_id=tx.id, clear_notes=True)
    )
    assert tx_service.get_transaction(session, tx.id).notes is None


def test_delete_transaction_reverses_balance(session):
    _seed(session)
    tx = tx_service.record_expense(
        session, account_id=1, amount=5_000_000, currency="COP",
        date=date(2026, 6, 18), payee="Lunch",
    )
    out = tx_tools.delete_transaction(session, DeleteTransactionInput(tx_id=tx.id))
    assert "Deleted" in out
    # account balance back to original
    assert accounts.get_account(session, 1).balance == 10_000_000