"""POST /transactions/{id}/correction — the four body shapes over the wire.

The service layer is covered by the acceptance suite, which binds below the
router. This file is the missing half: it exercises the dispatch the browser
actually reaches, with a real session and a real CSRF token, for every body the
edit dialog can produce — a move alone, a figure alone, both together in one
currency, both together across currencies, and a transfer's two sides.

Two transfer fixtures, because a pair's currencies decide what its halves may
say: `a_transfer` never leaves pesos, and `a_crossing_transfer` is production's
own US$1.556,04 → $5.000.000, whose legs can be moved into and out of a shared
currency (AC-11, AC-13).

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
def prestamos(client, auth):
    return _account(client, auth, "Prestamos a terceros", "COP")


@pytest.fixture
def trm(client, auth):
    """Production's rate, 3142 — reading a movement back needs one set (ADR-0031)."""
    assert client.post("/api/fx", headers=auth, json={"usd_cop": 3142}).status_code == 201


@pytest.fixture
def a_transfer(client, auth, trm, nu, rappi):
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


@pytest.fixture
def dolarapp_invest(client, auth):
    return _account(client, auth, "DolarApp Invest", "USD")


@pytest.fixture
def a_crossing_transfer(client, auth, trm, dolarapp, prestamos):
    """US$1.556,04 out of DolarApp, $5.000.000 into Prestamos a terceros.

    Production's own pair, the one whose sending side the dialog offers to move
    into pesos at the TRM.
    """
    resp = client.post(
        "/api/transactions/transfer",
        headers=auth,
        json={
            "from_account_id": dolarapp["id"],
            "to_account_id": prestamos["id"],
            "amount": 155_604,
            "currency": "USD",
            "amount_received": 500_000_000,
            "date": "2026-08-10",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _correct(client, auth, tx_id: int, body: dict):
    return client.post(f"/api/transactions/{tx_id}/correction", headers=auth, json=body)


def _balance(client, auth, account: dict) -> int:
    return client.get(f"/api/accounts/{account['id']}", headers=auth).json()["balance"]


def _amount(client, auth, leg: dict) -> int:
    return client.get(f"/api/transactions/{leg['id']}", headers=auth).json()["amount"]


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


def test_a_leg_moved_into_the_other_halfs_currency_cannot_conjure_money(
    client, auth, nu, dolarapp, prestamos, a_crossing_transfer
):
    """The TRM figure the dialog offers for this move would break the pair (AC-11).

    US$1.556,04 converted at 3142 is $4.889.078, and the other half already
    reads $5.000.000: taking it would put $110.922 into Prestamos that never
    left anywhere.
    """
    leg = a_crossing_transfer["from_leg"]

    resp = _correct(client, auth, leg["id"], {"account_id": nu["id"], "amount": 488_907_768})

    assert resp.status_code == 409, resp.text
    assert resp.json()["error"] == "TransferImbalance"
    assert _amount(client, auth, leg) == 155_604
    assert _balance(client, auth, dolarapp) == -155_604
    assert _balance(client, auth, nu) == 0
    assert _balance(client, auth, prestamos) == 500_000_000


def test_a_leg_moved_into_the_other_halfs_currency_takes_the_counterparts_figure(
    client, auth, nu, dolarapp, prestamos, a_crossing_transfer
):
    leg = a_crossing_transfer["from_leg"]

    resp = _correct(client, auth, leg["id"], {"account_id": nu["id"], "amount": 500_000_000})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["account_id"] == nu["id"]
    assert body["amount"] == 500_000_000
    assert body["currency"] == "COP"
    assert _balance(client, auth, dolarapp) == 0
    assert _balance(client, auth, nu) == -500_000_000
    assert _balance(client, auth, prestamos) == 500_000_000


def test_a_leg_moving_into_a_currency_the_pair_does_not_share_takes_the_conversion(
    client, auth, nu, rappi, dolarapp, a_transfer
):
    """AC-13's case: the halves are free to differ once they stop sharing a currency."""
    resp = _correct(client, auth, a_transfer["from_leg"]["id"], {"account_id": dolarapp["id"], "amount": 15_913})

    assert resp.status_code == 200, resp.text
    assert resp.json()["currency"] == "USD"
    assert _amount(client, auth, a_transfer["to_leg"]) == 50_000_000
    assert _balance(client, auth, nu) == 0
    assert _balance(client, auth, dolarapp) == -15_913
    assert _balance(client, auth, rappi) == 50_000_000


def test_a_leg_keeping_its_own_currency_inside_a_crossing_pair_needs_no_figure(
    client, auth, dolarapp, dolarapp_invest, prestamos, a_crossing_transfer
):
    resp = _correct(client, auth, a_crossing_transfer["from_leg"]["id"], {"account_id": dolarapp_invest["id"]})

    assert resp.status_code == 200, resp.text
    assert resp.json()["amount"] == 155_604
    assert _balance(client, auth, dolarapp) == 0
    assert _balance(client, auth, dolarapp_invest) == -155_604
    assert _balance(client, auth, prestamos) == 500_000_000


def test_a_leg_moving_into_another_currency_still_needs_the_figure(
    client, auth, dolarapp, dolarapp_invest, prestamos, a_crossing_transfer
):
    resp = _correct(client, auth, a_crossing_transfer["to_leg"]["id"], {"account_id": dolarapp_invest["id"]})

    assert resp.status_code == 422, resp.text
    assert "USD" in resp.json()["detail"]
    assert _balance(client, auth, prestamos) == 500_000_000
    assert _balance(client, auth, dolarapp_invest) == 0


def test_a_leg_move_that_restates_only_one_half_of_a_one_currency_pair_is_refused(
    client, auth, nu, rappi, prestamos, a_transfer
):
    resp = _correct(client, auth, a_transfer["from_leg"]["id"], {"account_id": prestamos["id"], "amount": 52_000_000})

    assert resp.status_code == 409, resp.text
    assert resp.json()["error"] == "TransferImbalance"
    assert _balance(client, auth, nu) == -50_000_000
    assert _balance(client, auth, rappi) == 50_000_000
    assert _balance(client, auth, prestamos) == 0


def test_a_crossing_transfer_is_restated_with_two_genuinely_different_figures(
    client, auth, dolarapp, prestamos, a_crossing_transfer
):
    resp = _correct(client, auth, a_crossing_transfer["from_leg"]["id"], {"sent": 160_000, "received": 505_000_000})

    assert resp.status_code == 200, resp.text
    assert resp.json()["amount"] == 160_000
    assert _amount(client, auth, a_crossing_transfer["to_leg"]) == 505_000_000
    assert _balance(client, auth, dolarapp) == -160_000
    assert _balance(client, auth, prestamos) == 505_000_000


@pytest.mark.parametrize("extra", ["account_id", "amount"])
def test_a_transfers_two_figures_are_not_corrected_beside_a_leg_of_its_own(
    client, auth, nu, dolarapp, prestamos, a_crossing_transfer, extra
):
    """The account used to be dropped without a word; the most dangerous write says so."""
    leg = a_crossing_transfer["from_leg"]
    body = {"sent": 160_000, "received": 505_000_000, extra: nu["id"] if extra == "account_id" else 160_000}

    resp = _correct(client, auth, leg["id"], body)

    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"] == "a transfer's two figures are corrected on their own, not beside a leg's account"
    assert _amount(client, auth, leg) == 155_604
    assert _balance(client, auth, dolarapp) == -155_604
    assert _balance(client, auth, nu) == 0
    assert _balance(client, auth, prestamos) == 500_000_000


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
