import pytest

from tests.support.fx import set_trm as _set_trm


@pytest.fixture
def two_accounts(client, auth):
    a = client.post("/api/accounts", headers=auth, json={"name": "Cash", "type": "cash", "currency": "COP"}).json()
    b = client.post("/api/accounts", headers=auth, json={"name": "Bank", "type": "debit", "currency": "COP"}).json()
    return a, b


@pytest.fixture
def usd_account(client, auth):
    return client.post("/api/accounts", headers=auth, json={"name": "USD", "type": "debit", "currency": "USD"}).json()


def test_transactions_requires_auth(client):
    assert client.get("/api/transactions").status_code == 401


def test_create_expense_without_trm_decrements_balance_and_omits_cop_equivalent(client, auth, two_accounts):
    cash, _ = two_accounts
    resp = client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "expense",
            "account_id": cash["id"],
            "amount": 1500,
            "currency": "COP",
            "date": "2026-06-17",
            "payee": "Store",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["type"] == "expense" and body["amount"] == 1500
    assert body["cop_equivalent"] is None
    assert "to_base" not in body and "fx_rate" not in body

    acc = client.get(f"/api/accounts/{cash['id']}", headers=auth).json()
    assert acc["balance"] == -1500


def test_create_expense_ignores_legacy_fx_rate_field(client, auth, two_accounts):
    cash, _ = two_accounts
    resp = client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "expense",
            "account_id": cash["id"],
            "amount": 1500,
            "currency": "COP",
            "date": "2026-06-17",
            "payee": "Store",
            "fx_rate": "9999",
        },
    )
    assert resp.status_code == 201
    assert "fx_rate" not in resp.json()


def test_create_income(client, auth, two_accounts):
    _, bank = two_accounts
    resp = client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "income",
            "account_id": bank["id"],
            "amount": 5000,
            "currency": "COP",
            "date": "2026-06-17",
            "payee": "Salary",
        },
    )
    assert resp.status_code == 201
    assert client.get(f"/api/accounts/{bank['id']}", headers=auth).json()["balance"] == 5000


def test_create_with_trm_set_returns_identity_cop_equivalent_for_cop(client, auth, two_accounts):
    cash, _ = two_accounts
    _set_trm(client, auth)
    resp = client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "expense",
            "account_id": cash["id"],
            "amount": 1500,
            "currency": "COP",
            "date": "2026-06-17",
            "payee": "Store",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["cop_equivalent"] == 1500


def test_post_transactions_rejects_transfer_type(client, auth, two_accounts):
    cash, _ = two_accounts
    resp = client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "transfer",
            "account_id": cash["id"],
            "amount": 100,
            "currency": "COP",
            "date": "2026-06-17",
            "payee": "x",
        },
    )
    assert resp.status_code == 422 and resp.json()["error"] == "ValidationError"


def test_list_transactions_without_trm_is_409(client, auth, two_accounts):
    resp = client.get("/api/transactions", headers=auth)
    assert resp.status_code == 409 and resp.json()["error"] == "MissingRate"


def test_get_transaction_without_trm_is_409(client, auth, two_accounts):
    cash, _ = two_accounts
    tx = client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "expense",
            "account_id": cash["id"],
            "amount": 1000,
            "currency": "COP",
            "date": "2026-06-17",
            "payee": "Store",
        },
    ).json()
    resp = client.get(f"/api/transactions/{tx['id']}", headers=auth)
    assert resp.status_code == 409 and resp.json()["error"] == "MissingRate"


def test_usd_cop_equivalent_recomputes_when_trm_changes(client, auth, usd_account):
    tx = client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "expense",
            "account_id": usd_account["id"],
            "amount": 1000,
            "currency": "USD",
            "date": "2026-06-17",
            "payee": "Amazon",
        },
    ).json()
    _set_trm(client, auth, "4000")
    first = client.get(f"/api/transactions/{tx['id']}", headers=auth).json()
    assert first["cop_equivalent"] == 4_000_000
    _set_trm(client, auth, "4100.50")
    second = client.get(f"/api/transactions/{tx['id']}", headers=auth).json()
    assert second["cop_equivalent"] == 4_100_500


def test_transfer_creates_atomic_pair(client, auth, two_accounts):
    cash, bank = two_accounts
    resp = client.post(
        "/api/transactions/transfer",
        headers=auth,
        json={
            "from_account_id": cash["id"],
            "to_account_id": bank["id"],
            "amount": 2000,
            "currency": "COP",
            "date": "2026-06-17",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["from_leg"]["account_id"] == cash["id"]
    assert body["to_leg"]["account_id"] == bank["id"]
    assert body["from_leg"]["amount"] == 2000 and body["to_leg"]["amount"] == 2000
    assert body["from_leg"]["transfer_group_id"] == body["to_leg"]["transfer_group_id"]
    assert body["from_leg"]["transfer_direction"] == "out"
    assert body["to_leg"]["transfer_direction"] == "in"
    assert client.get(f"/api/accounts/{cash['id']}", headers=auth).json()["balance"] == -2000
    assert client.get(f"/api/accounts/{bank['id']}", headers=auth).json()["balance"] == 2000


def test_transfer_currency_defaults_to_source_account(client, auth, two_accounts):
    cash, bank = two_accounts
    resp = client.post(
        "/api/transactions/transfer",
        headers=auth,
        json={
            "from_account_id": cash["id"],
            "to_account_id": bank["id"],
            "amount": 700,
            "date": "2026-06-17",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["from_leg"]["currency"] == "COP"


def test_cross_currency_transfer_stores_each_legs_own_amount_and_currency(client, auth, two_accounts, usd_account):
    cash, _ = two_accounts
    resp = client.post(
        "/api/transactions/transfer",
        headers=auth,
        json={
            "from_account_id": usd_account["id"],
            "to_account_id": cash["id"],
            "amount": 10_000,
            "amount_received": 41_000_000,
            "date": "2026-06-17",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["from_leg"]["amount"] == 10_000 and body["from_leg"]["currency"] == "USD"
    assert body["to_leg"]["amount"] == 41_000_000 and body["to_leg"]["currency"] == "COP"
    assert body["from_leg"]["transfer_group_id"] == body["to_leg"]["transfer_group_id"]
    assert "fx_rate" not in body["from_leg"] and "fx_rate" not in body["to_leg"]
    assert client.get(f"/api/accounts/{usd_account['id']}", headers=auth).json()["balance"] == -10_000
    assert client.get(f"/api/accounts/{cash['id']}", headers=auth).json()["balance"] == 41_000_000


def test_cross_currency_transfer_without_amount_received_is_422(client, auth, two_accounts, usd_account):
    cash, _ = two_accounts
    resp = client.post(
        "/api/transactions/transfer",
        headers=auth,
        json={
            "from_account_id": usd_account["id"],
            "to_account_id": cash["id"],
            "amount": 10_000,
            "date": "2026-06-17",
        },
    )
    assert resp.status_code == 422 and resp.json()["error"] == "ValidationError"


def test_transfer_non_positive_amounts_are_422(client, auth, two_accounts, usd_account):
    cash, bank = two_accounts
    zero_sent = client.post(
        "/api/transactions/transfer",
        headers=auth,
        json={"from_account_id": cash["id"], "to_account_id": bank["id"], "amount": 0, "date": "2026-06-17"},
    )
    assert zero_sent.status_code == 422 and zero_sent.json()["error"] == "ValidationError"
    zero_received = client.post(
        "/api/transactions/transfer",
        headers=auth,
        json={
            "from_account_id": usd_account["id"],
            "to_account_id": cash["id"],
            "amount": 10_000,
            "amount_received": 0,
            "date": "2026-06-17",
        },
    )
    assert zero_received.status_code == 422 and zero_received.json()["error"] == "ValidationError"


def test_transfer_same_account_is_409(client, auth, two_accounts):
    cash, _ = two_accounts
    resp = client.post(
        "/api/transactions/transfer",
        headers=auth,
        json={
            "from_account_id": cash["id"],
            "to_account_id": cash["id"],
            "amount": 100,
            "currency": "COP",
            "date": "2026-06-17",
        },
    )
    assert resp.status_code == 409 and resp.json()["error"] == "TransferImbalance"


def test_list_transactions_filters(client, auth, two_accounts):
    cash, bank = two_accounts
    _set_trm(client, auth)
    client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "expense",
            "account_id": cash["id"],
            "amount": 100,
            "currency": "COP",
            "date": "2026-06-01",
            "payee": "A",
        },
    )
    client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "income",
            "account_id": bank["id"],
            "amount": 200,
            "currency": "COP",
            "date": "2026-06-20",
            "payee": "B",
        },
    )
    all_tx = client.get("/api/transactions", headers=auth).json()
    assert len(all_tx) == 2
    assert all(t["cop_equivalent"] == t["amount"] for t in all_tx)

    by_account = client.get("/api/transactions", headers=auth, params={"account_id": cash["id"]}).json()
    assert len(by_account) == 1 and by_account[0]["account_id"] == cash["id"]

    by_type = client.get("/api/transactions", headers=auth, params={"type": "income"}).json()
    assert len(by_type) == 1 and by_type[0]["type"] == "income"

    by_range = client.get(
        "/api/transactions", headers=auth, params={"date_from": "2026-06-10", "date_to": "2026-06-30"}
    ).json()
    assert len(by_range) == 1


def test_get_missing_transaction_is_404(client, auth):
    _set_trm(client, auth)
    resp = client.get("/api/transactions/999", headers=auth)
    assert resp.status_code == 404 and resp.json()["error"] == "NotFound"


def test_patch_transaction_edits_fields(client, auth, two_accounts):
    cash, _ = two_accounts
    tx = client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "expense",
            "account_id": cash["id"],
            "amount": 1000,
            "currency": "COP",
            "date": "2026-06-17",
            "payee": "Store",
        },
    ).json()
    patched = client.patch(f"/api/transactions/{tx['id']}", headers=auth, json={"payee": "Super", "notes": "x"})
    assert patched.status_code == 200
    assert patched.json()["payee"] == "Super" and patched.json()["notes"] == "x"


def test_delete_expense_reverses_balance_via_api(client, auth, two_accounts):
    cash, _ = two_accounts
    tx = client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "expense",
            "account_id": cash["id"],
            "amount": 1000,
            "currency": "COP",
            "date": "2026-06-17",
            "payee": "Store",
        },
    ).json()
    assert client.get(f"/api/accounts/{cash['id']}", headers=auth).json()["balance"] == -1000
    assert client.delete(f"/api/transactions/{tx['id']}", headers=auth).status_code == 204
    assert client.get(f"/api/accounts/{cash['id']}", headers=auth).json()["balance"] == 0


def test_delete_transfer_leg_via_api_deletes_pair_and_restores_balances(client, auth, two_accounts):
    cash, bank = two_accounts
    _set_trm(client, auth)
    transfer = client.post(
        "/api/transactions/transfer",
        headers=auth,
        json={
            "from_account_id": cash["id"],
            "to_account_id": bank["id"],
            "amount": 500,
            "currency": "COP",
            "date": "2026-06-17",
        },
    ).json()
    resp = client.delete(f"/api/transactions/{transfer['from_leg']['id']}", headers=auth)
    assert resp.status_code == 204
    assert client.get(f"/api/accounts/{cash['id']}", headers=auth).json()["balance"] == 0
    assert client.get(f"/api/accounts/{bank['id']}", headers=auth).json()["balance"] == 0
    remaining = client.get("/api/transactions", headers=auth).json()
    assert remaining == []


def test_create_transaction_with_tags_round_trips(client, auth, two_accounts):
    cash, _ = two_accounts
    resp = client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "expense",
            "account_id": cash["id"],
            "amount": 1000,
            "currency": "COP",
            "date": "2026-06-17",
            "payee": "Store",
            "tags": ["viaje", "comida"],
        },
    )
    assert resp.status_code == 201
    assert resp.json()["tags"] == ["comida", "viaje"]


def test_create_transaction_without_tags_defaults_to_empty(client, auth, two_accounts):
    cash, _ = two_accounts
    resp = client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "expense",
            "account_id": cash["id"],
            "amount": 1000,
            "currency": "COP",
            "date": "2026-06-17",
            "payee": "Store",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["tags"] == []


def test_patch_transaction_tags_is_a_replace_set(client, auth, two_accounts):
    cash, _ = two_accounts
    tx = client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "expense",
            "account_id": cash["id"],
            "amount": 1000,
            "currency": "COP",
            "date": "2026-06-17",
            "payee": "Store",
            "tags": ["viaje"],
        },
    ).json()
    patched = client.patch(
        f"/api/transactions/{tx['id']}",
        headers=auth,
        json={"tags": ["comida", "reembolso"]},
    )
    assert patched.status_code == 200
    assert patched.json()["tags"] == ["comida", "reembolso"]


def test_patch_without_tags_leaves_them_untouched(client, auth, two_accounts):
    cash, _ = two_accounts
    tx = client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "expense",
            "account_id": cash["id"],
            "amount": 1000,
            "currency": "COP",
            "date": "2026-06-17",
            "payee": "Store",
            "tags": ["viaje"],
        },
    ).json()
    patched = client.patch(f"/api/transactions/{tx['id']}", headers=auth, json={"payee": "Super"})
    assert patched.status_code == 200
    assert patched.json()["tags"] == ["viaje"]


def test_patch_tags_to_empty_removes_them_all(client, auth, two_accounts):
    cash, _ = two_accounts
    tx = client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "expense",
            "account_id": cash["id"],
            "amount": 1000,
            "currency": "COP",
            "date": "2026-06-17",
            "payee": "Store",
            "tags": ["viaje"],
        },
    ).json()
    patched = client.patch(f"/api/transactions/{tx['id']}", headers=auth, json={"tags": []})
    assert patched.status_code == 200
    assert patched.json()["tags"] == []


def test_list_and_get_include_tags(client, auth, two_accounts):
    cash, _ = two_accounts
    _set_trm(client, auth)
    tagged = client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "expense",
            "account_id": cash["id"],
            "amount": 1000,
            "currency": "COP",
            "date": "2026-06-17",
            "payee": "Store",
            "tags": ["viaje"],
        },
    ).json()
    client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "expense",
            "account_id": cash["id"],
            "amount": 2000,
            "currency": "COP",
            "date": "2026-06-18",
            "payee": "Other",
        },
    )
    listed = client.get("/api/transactions", headers=auth).json()
    by_payee = {row["payee"]: row["tags"] for row in listed}
    assert by_payee == {"Store": ["viaje"], "Other": []}
    got = client.get(f"/api/transactions/{tagged['id']}", headers=auth).json()
    assert got["tags"] == ["viaje"]


def test_list_endpoint_default_orders_by_date_desc(client, auth, two_accounts):
    """Default endpoint order: newest date first, regardless of insertion order."""
    cash, _ = two_accounts
    _set_trm(client, auth)
    client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "expense",
            "account_id": cash["id"],
            "amount": 100,
            "currency": "COP",
            "date": "2026-06-15",
            "payee": "mid",
        },
    )
    client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "expense",
            "account_id": cash["id"],
            "amount": 200,
            "currency": "COP",
            "date": "2026-06-01",
            "payee": "old",
        },
    )
    client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "expense",
            "account_id": cash["id"],
            "amount": 300,
            "currency": "COP",
            "date": "2026-07-01",
            "payee": "new",
        },
    )
    body = client.get("/api/transactions", headers=auth).json()
    assert [t["payee"] for t in body] == ["new", "mid", "old"]


def test_list_endpoint_sort_date_asc_orders_chronologically(client, auth, two_accounts):
    cash, _ = two_accounts
    _set_trm(client, auth)
    for payee, date in [("mid", "2026-06-15"), ("old", "2026-06-01"), ("new", "2026-07-01")]:
        client.post(
            "/api/transactions",
            headers=auth,
            json={
                "type": "expense",
                "account_id": cash["id"],
                "amount": 100,
                "currency": "COP",
                "date": date,
                "payee": payee,
            },
        )
    body = client.get("/api/transactions", headers=auth, params={"sort": "date", "order": "asc"}).json()
    assert [t["payee"] for t in body] == ["old", "mid", "new"]


def test_list_endpoint_invalid_sort_returns_422(client, auth):
    resp = client.get("/api/transactions", headers=auth, params={"sort": "amount"})
    assert resp.status_code == 422
    assert "sort" in resp.text.lower()


def test_list_endpoint_default_includes_planned_at_due_date(client, auth, two_accounts):
    """No status filter = both posted and planned, in date-DESC order.

    Planned tx with due-date 15-jun surfaces between a 1-jul posted and
    a 1-jun posted in the API response.
    """
    cash, _ = two_accounts
    _set_trm(client, auth)
    client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "expense",
            "account_id": cash["id"],
            "amount": 100,
            "currency": "COP",
            "date": "2026-06-01",
            "payee": "old",
        },
    )
    client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "expense",
            "account_id": cash["id"],
            "amount": 300,
            "currency": "COP",
            "date": "2026-07-01",
            "payee": "new",
        },
    )
    plan = client.post(
        "/api/planned",
        headers=auth,
        json={
            "payee": "Rent",
            "amount": 500_000,
            "due_date": "2026-06-15",
            "account_id": cash["id"],
        },
    )
    assert plan.status_code == 201, plan.text
    body = client.get("/api/transactions", headers=auth).json()
    assert [t["payee"] for t in body] == ["new", "Rent", "old"]
