import pytest


@pytest.fixture
def two_accounts(client, auth):
    a = client.post(
        "/api/accounts", headers=auth, json={"name": "Cash", "type": "cash", "currency": "COP"}
    ).json()
    b = client.post(
        "/api/accounts", headers=auth, json={"name": "Bank", "type": "debit", "currency": "COP"}
    ).json()
    return a, b


def test_transactions_requires_auth(client):
    assert client.get("/api/transactions").status_code == 401


def test_create_expense_decrements_balance(client, auth, two_accounts):
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
    assert body["type"] == "expense" and body["amount"] == 1500 and body["to_base"] == 1500

    acc = client.get(f"/api/accounts/{cash['id']}", headers=auth).json()
    assert acc["balance"] == -1500


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
    assert body["from_leg"]["transfer_group_id"] == body["to_leg"]["transfer_group_id"]
    assert client.get(f"/api/accounts/{cash['id']}", headers=auth).json()["balance"] == -2000
    assert client.get(f"/api/accounts/{bank['id']}", headers=auth).json()["balance"] == 2000


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
    client.post(
        "/api/transactions",
        headers=auth,
        json={"type": "expense", "account_id": cash["id"], "amount": 100,
              "currency": "COP", "date": "2026-06-01", "payee": "A"},
    )
    client.post(
        "/api/transactions",
        headers=auth,
        json={"type": "income", "account_id": bank["id"], "amount": 200,
              "currency": "COP", "date": "2026-06-20", "payee": "B"},
    )
    all_tx = client.get("/api/transactions", headers=auth).json()
    assert len(all_tx) == 2

    by_account = client.get("/api/transactions", headers=auth, params={"account_id": cash["id"]}).json()
    assert len(by_account) == 1 and by_account[0]["account_id"] == cash["id"]

    by_type = client.get("/api/transactions", headers=auth, params={"type": "income"}).json()
    assert len(by_type) == 1 and by_type[0]["type"] == "income"

    by_range = client.get(
        "/api/transactions", headers=auth, params={"date_from": "2026-06-10", "date_to": "2026-06-30"}
    ).json()
    assert len(by_range) == 1


def test_get_missing_transaction_is_404(client, auth):
    resp = client.get("/api/transactions/999", headers=auth)
    assert resp.status_code == 404 and resp.json()["error"] == "NotFound"


def test_patch_transaction_edits_fields(client, auth, two_accounts):
    cash, _ = two_accounts
    tx = client.post(
        "/api/transactions",
        headers=auth,
        json={"type": "expense", "account_id": cash["id"], "amount": 1000,
              "currency": "COP", "date": "2026-06-17", "payee": "Store"},
    ).json()
    patched = client.patch(
        f"/api/transactions/{tx['id']}", headers=auth, json={"payee": "Super", "notes": "x"}
    )
    assert patched.status_code == 200
    assert patched.json()["payee"] == "Super" and patched.json()["notes"] == "x"


def test_delete_expense_reverses_balance_via_api(client, auth, two_accounts):
    cash, _ = two_accounts
    tx = client.post(
        "/api/transactions",
        headers=auth,
        json={"type": "expense", "account_id": cash["id"], "amount": 1000,
              "currency": "COP", "date": "2026-06-17", "payee": "Store"},
    ).json()
    assert client.get(f"/api/accounts/{cash['id']}", headers=auth).json()["balance"] == -1000
    assert client.delete(f"/api/transactions/{tx['id']}", headers=auth).status_code == 204
    assert client.get(f"/api/accounts/{cash['id']}", headers=auth).json()["balance"] == 0


def test_delete_transfer_leg_via_api_is_422(client, auth, two_accounts):
    cash, bank = two_accounts
    transfer = client.post(
        "/api/transactions/transfer",
        headers=auth,
        json={"from_account_id": cash["id"], "to_account_id": bank["id"],
              "amount": 500, "currency": "COP", "date": "2026-06-17"},
    ).json()
    resp = client.delete(f"/api/transactions/{transfer['from_leg']['id']}", headers=auth)
    assert resp.status_code == 422 and resp.json()["error"] == "ValidationError"
