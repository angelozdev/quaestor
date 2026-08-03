from datetime import date

from quaestor.mcp.tools import transactions as tx_tools
from quaestor.mcp.tools.transactions import (
    DeleteTransactionInput,
    GetTransactionInput,
    UpdateTransactionInput,
)
from quaestor.services import accounts, fx
from quaestor.services import tags as tags_service
from quaestor.services import transactions as tx_service


def _seed(session):
    fx.set_trm(session, "4000")
    return accounts.create_account(session, "Bancolombia", "debit", "COP", balance=10_000_000)


def test_get_transaction_returns_card(session):
    _seed(session)
    tx = tx_service.record_expense(
        session,
        account_id=1,
        amount=5_000_000,
        currency="COP",
        date=date(2026, 6, 18),
        payee="Lunch",
    )
    out = tx_tools.get_transaction(session, GetTransactionInput(tx_id=tx.id))
    assert "Lunch" in out and "50000.00 COP" in out
    assert f"id={tx.id}" in out


def test_get_transaction_without_trm_returns_missing_rate_text(session):
    accounts.create_account(session, "Bancolombia", "debit", "COP", balance=10_000_000)
    tx = tx_service.record_expense(
        session,
        account_id=1,
        amount=5_000_000,
        currency="COP",
        date=date(2026, 6, 18),
        payee="Lunch",
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
        session,
        account_id=1,
        amount=5_000_000,
        currency="COP",
        date=date(2026, 6, 18),
        payee="Lunch",
    )
    out = tx_tools.update_transaction(
        session, UpdateTransactionInput(tx_id=tx.id, payee="Brunch", notes="with friends")
    )
    assert "Brunch" in out
    refreshed = tx_service.get_transaction(session, tx.id)
    assert refreshed.payee == "Brunch"
    assert refreshed.notes == "with friends"


def test_update_transaction_can_clear_notes_with_empty_string(session):
    _seed(session)
    tx = tx_service.record_expense(
        session,
        account_id=1,
        amount=5_000_000,
        currency="COP",
        date=date(2026, 6, 18),
        payee="Lunch",
        notes="note",
    )
    tx_tools.update_transaction(session, UpdateTransactionInput(tx_id=tx.id, clear_notes=True))
    assert tx_service.get_transaction(session, tx.id).notes is None


def test_update_transaction_add_tags_links_them(session):
    _seed(session)
    tx = tx_service.record_expense(
        session,
        account_id=1,
        amount=5_000_000,
        currency="COP",
        date=date(2026, 6, 18),
        payee="Lunch",
    )
    tx_tools.update_transaction(session, UpdateTransactionInput(tx_id=tx.id, add_tags=["viaje", "comida"]))
    assert tags_service.tag_names_by_transaction(session, [tx.id]) == {tx.id: ["comida", "viaje"]}


def test_update_transaction_remove_tags_unlinks_them(session):
    _seed(session)
    tx = tx_service.record_expense(
        session,
        account_id=1,
        amount=5_000_000,
        currency="COP",
        date=date(2026, 6, 18),
        payee="Lunch",
    )
    tags_service.tag_transaction(session, tx.id, ["viaje", "comida"])
    tx_tools.update_transaction(session, UpdateTransactionInput(tx_id=tx.id, remove_tags=["viaje"]))
    assert tags_service.tag_names_by_transaction(session, [tx.id]) == {tx.id: ["comida"]}


def test_update_transaction_remove_absent_tag_is_a_noop(session):
    _seed(session)
    tx = tx_service.record_expense(
        session,
        account_id=1,
        amount=5_000_000,
        currency="COP",
        date=date(2026, 6, 18),
        payee="Lunch",
    )
    tags_service.tag_transaction(session, tx.id, ["viaje"])
    out = tx_tools.update_transaction(session, UpdateTransactionInput(tx_id=tx.id, remove_tags=["ghost"]))
    assert "Lunch" in out
    assert tags_service.tag_names_by_transaction(session, [tx.id]) == {tx.id: ["viaje"]}


def test_delete_transaction_reverses_balance(session):
    _seed(session)
    tx = tx_service.record_expense(
        session,
        account_id=1,
        amount=5_000_000,
        currency="COP",
        date=date(2026, 6, 18),
        payee="Lunch",
    )
    out = tx_tools.delete_transaction(session, DeleteTransactionInput(tx_id=tx.id))
    assert "Deleted" in out
    # account balance back to original
    assert accounts.get_account(session, 1).balance == 10_000_000


def test_delete_transfer_leg_deletes_pair_and_restores_both_balances(session):
    _seed(session)
    accounts.create_account(session, "Nequi", "debit", "COP", balance=200_000)
    leg_from, leg_to = tx_service.transfer(session, 1, 2, 100_000, "COP", date(2026, 6, 18))
    out = tx_tools.delete_transaction(session, DeleteTransactionInput(tx_id=leg_to.id))
    assert "Deleted" in out
    assert accounts.get_account(session, 1).balance == 10_000_000
    assert accounts.get_account(session, 2).balance == 200_000
    assert "not found" in tx_tools.get_transaction(session, GetTransactionInput(tx_id=leg_from.id))
