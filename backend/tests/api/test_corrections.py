"""POST /transactions/{id}/correction — the four body shapes over the wire.

The service layer is covered by the acceptance suite, which binds below the
router. This file is the missing half: it exercises the dispatch the browser
actually reaches, with a real session and a real CSRF token, for every body the
edit dialog can produce — a move alone, a figure alone, both together in one
currency, both together across currencies, and a transfer's two sides.

Nothing here rebuilds a balance from the sum of its movements: every balance
assertion is a figure the test itself put there (ADR-0051).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _account(client, auth, name: str, currency: str) -> dict:
    resp = client.post(
        "/api/accounts",
        headers=auth,
        json={"name": name, "type": "debit", "currency": currency},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def nu(client, auth):
    return _account(client, auth, "Nu Debito", "COP")


@pytest.fixture
def rappi(client, auth):
    return _account(client, auth, "RappiCard", "COP")


@pytest.fixture
def dolarapp(client, auth):
    return _account(client, auth, "DolarApp", "USD")


@pytest.fixture
def an_expense(client, auth, nu, expense_category):
    """$93.558 paid to Tigo out of Nu Debito, filed and tagged."""
    resp = client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "expense",
            "category_id": expense_category,
            "account_id": nu["id"],
            "amount": 9_355_800,
            "currency": "COP",
            "date": "2026-08-10",
            "payee": "Tigo",
            "tags": ["hogar"],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def a_transfer(client, auth, nu, rappi):
    resp = client.post(
        "/api/transactions/transfer",
        headers=auth,
        json={
            "from_account_id": nu["id"],
            "to_account_id": rappi["id"],
            "amount": 50_000_000,
            "currency": "COP",
            "date": "2026-08-10",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _correct(client, auth, tx_id: int, body: dict):
    return client.post(f"/api/transactions/{tx_id}/correction", headers=auth, json=body)


def _balance(client, auth, account: dict) -> int:
    return client.get(f"/api/accounts/{account['id']}", headers=auth).json()["balance"]


def test_move_alone_gives_the_money_back_and_charges_the_other_account(client, auth, nu, rappi, an_expense):
    resp = _correct(client, auth, an_expense["id"], {"account_id": rappi["id"]})

    assert resp.status_code == 200, resp.text
    assert resp.json()["account_id"] == rappi["id"]
    assert resp.json()["amount"] == 9_355_800
    assert _balance(client, auth, nu) == 0
    assert _balance(client, auth, rappi) == -9_355_800


def test_amount_alone_moves_the_balance_by_the_difference(client, auth, nu, an_expense):
    resp = _correct(client, auth, an_expense["id"], {"amount": 9_520_000})

    assert resp.status_code == 200, resp.text
    assert resp.json()["amount"] == 9_520_000
    assert _balance(client, auth, nu) == -9_520_000


def test_account_and_amount_together_in_one_currency(client, auth, nu, rappi, an_expense):
    """The exact body the edit dialog sends when both controls were touched."""
    resp = _correct(client, auth, an_expense["id"], {"account_id": rappi["id"], "amount": 42_000_000})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["account_id"] == rappi["id"]
    assert body["amount"] == 42_000_000
    assert body["currency"] == "COP"
    assert _balance(client, auth, nu) == 0
    assert _balance(client, auth, rappi) == -42_000_000


def test_account_and_amount_together_across_currencies(client, auth, nu, dolarapp, an_expense):
    resp = _correct(client, auth, an_expense["id"], {"account_id": dolarapp["id"], "amount": 10_000})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["account_id"] == dolarapp["id"]
    assert body["amount"] == 10_000
    assert body["currency"] == "USD"
    assert _balance(client, auth, nu) == 0
    assert _balance(client, auth, dolarapp) == -10_000


def test_moving_across_currencies_without_the_amount_is_refused(client, auth, nu, dolarapp, an_expense):
    resp = _correct(client, auth, an_expense["id"], {"account_id": dolarapp["id"]})

    assert resp.status_code == 422, resp.text
    assert "USD" in resp.json()["detail"]
    assert _balance(client, auth, nu) == -9_355_800
    assert _balance(client, auth, dolarapp) == 0


def test_a_correction_keeps_everything_it_did_not_name(client, auth, rappi, an_expense, expense_category):
    resp = _correct(client, auth, an_expense["id"], {"account_id": rappi["id"], "amount": 42_000_000})

    body = resp.json()
    assert body["id"] == an_expense["id"]
    assert body["date"] == an_expense["date"]
    assert body["payee"] == "Tigo"
    assert body["category_id"] == expense_category
    assert body["tags"] == ["hogar"]


def test_a_transfer_is_restated_on_both_of_its_sides(client, auth, nu, rappi, a_transfer):
    leg = a_transfer["from_leg"]

    resp = _correct(client, auth, leg["id"], {"sent": 52_000_000, "received": 52_000_000})

    assert resp.status_code == 200, resp.text
    assert resp.json()["amount"] == 52_000_000
    assert _balance(client, auth, nu) == -52_000_000
    assert _balance(client, auth, rappi) == 52_000_000


def test_a_transfer_in_one_currency_refuses_two_different_figures(client, auth, nu, rappi, a_transfer):
    resp = _correct(client, auth, a_transfer["from_leg"]["id"], {"sent": 52_000_000, "received": 51_000_000})

    assert resp.status_code == 409, resp.text
    assert resp.json()["error"] == "TransferImbalance"
    assert _balance(client, auth, nu) == -50_000_000
    assert _balance(client, auth, rappi) == 50_000_000


@pytest.mark.parametrize("body", [{"sent": 52_000_000}, {"received": 52_000_000}])
def test_a_transfer_states_both_of_its_figures_or_neither(client, auth, a_transfer, body):
    resp = _correct(client, auth, a_transfer["from_leg"]["id"], body)

    assert resp.status_code == 422, resp.text
    assert "sent" in resp.json()["detail"]


def test_one_side_of_a_transfer_cannot_be_restated_alone(client, auth, a_transfer):
    resp = _correct(client, auth, a_transfer["from_leg"]["id"], {"amount": 52_000_000})

    assert resp.status_code == 422, resp.text
    assert "both of its sides" in resp.json()["detail"]


def test_a_transfer_leg_moves_on_its_own(client, auth, nu, rappi, a_transfer, expense_category):
    third = _account(client, auth, "Prestamos", "COP")

    resp = _correct(client, auth, a_transfer["from_leg"]["id"], {"account_id": third["id"]})

    assert resp.status_code == 200, resp.text
    assert resp.json()["account_id"] == third["id"]
    assert _balance(client, auth, nu) == 0
    assert _balance(client, auth, third) == -50_000_000


def test_a_leg_cannot_move_onto_the_account_its_counterpart_uses(client, auth, nu, rappi, a_transfer):
    resp = _correct(client, auth, a_transfer["from_leg"]["id"], {"account_id": rappi["id"]})

    assert resp.status_code == 409, resp.text
    assert resp.json()["error"] == "TransferImbalance"
    assert _balance(client, auth, nu) == -50_000_000
    assert _balance(client, auth, rappi) == 50_000_000


def test_a_body_naming_neither_an_account_nor_an_amount_is_refused(client, auth, nu, an_expense):
    resp = _correct(client, auth, an_expense["id"], {})

    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"] == "a correction states an account, an amount, or both"
    assert _balance(client, auth, nu) == -9_355_800


@pytest.mark.parametrize("amount", [0, -1])
def test_a_correction_never_leaves_a_movement_worth_nothing_or_less(client, auth, nu, an_expense, amount):
    resp = _correct(client, auth, an_expense["id"], {"amount": amount})

    assert resp.status_code == 422, resp.text
    assert _balance(client, auth, nu) == -9_355_800


@pytest.mark.parametrize("amount", [0, -1])
def test_a_move_carrying_a_worthless_figure_is_refused(client, auth, nu, rappi, an_expense, amount):
    resp = _correct(client, auth, an_expense["id"], {"account_id": rappi["id"], "amount": amount})

    assert resp.status_code == 422, resp.text
    assert _balance(client, auth, nu) == -9_355_800
    assert _balance(client, auth, rappi) == 0


def test_a_correction_pointing_at_an_account_that_does_not_exist_is_refused(client, auth, nu, an_expense):
    resp = _correct(client, auth, an_expense["id"], {"account_id": 9_999})

    assert resp.status_code == 404, resp.text
    assert _balance(client, auth, nu) == -9_355_800


def test_an_archived_account_takes_nothing_new(client, auth, nu, rappi, an_expense):
    assert client.delete(f"/api/accounts/{rappi['id']}", headers=auth).status_code == 204

    resp = _correct(client, auth, an_expense["id"], {"account_id": rappi["id"]})

    assert resp.status_code == 422, resp.text
    assert "archived" in resp.json()["detail"]
    assert _balance(client, auth, nu) == -9_355_800


def test_correcting_a_movement_that_does_not_exist_is_refused(client, auth, nu):
    assert _correct(client, auth, 9_999, {"amount": 100}).status_code == 404


def test_a_correction_cannot_be_made_without_credentials(client, an_expense):
    resp = client.post(f"/api/transactions/{an_expense['id']}/correction", json={"amount": 100})

    assert resp.status_code == 401


def test_a_correction_cannot_be_made_without_the_csrf_token(client, auth, an_expense):
    fresh = TestClient(client.app)

    resp = fresh.post(f"/api/transactions/{an_expense['id']}/correction", headers=auth, json={"amount": 100})

    assert resp.status_code == 403
