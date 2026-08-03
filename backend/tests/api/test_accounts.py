def test_accounts_requires_auth(client):
    assert client.get("/api/accounts").status_code == 401


def test_accounts_crud_happy_path(client, auth):
    created = client.post(
        "/api/accounts",
        headers=auth,
        json={"name": "Cash", "type": "cash", "currency": "COP", "balance": 0},
    )
    assert created.status_code == 201
    acc = created.json()
    assert acc["name"] == "Cash" and acc["type"] == "cash" and acc["archived"] is False
    acc_id = acc["id"]

    got = client.get(f"/api/accounts/{acc_id}", headers=auth)
    assert got.status_code == 200 and got.json()["id"] == acc_id

    patched = client.patch(f"/api/accounts/{acc_id}", headers=auth, json={"name": "Wallet"})
    assert patched.status_code == 200 and patched.json()["name"] == "Wallet"

    listed = client.get("/api/accounts", headers=auth)
    assert listed.status_code == 200 and len(listed.json()) == 1

    archived = client.delete(f"/api/accounts/{acc_id}", headers=auth)
    assert archived.status_code == 204
    assert client.get("/api/accounts", headers=auth).json() == []
    assert len(client.get("/api/accounts?archived=true", headers=auth).json()) == 1


def test_get_missing_account_is_404(client, auth):
    resp = client.get("/api/accounts/999", headers=auth)
    assert resp.status_code == 404 and resp.json()["error"] == "NotFound"


def test_create_account_bad_currency_is_422(client, auth):
    resp = client.post(
        "/api/accounts",
        headers=auth,
        json={"name": "X", "type": "cash", "currency": "EUR"},
    )
    assert resp.status_code == 422 and resp.json()["error"] == "ValidationError"


def test_restore_account_endpoint(client, engine, auth):
    from quaestor.services import accounts
    from sqlmodel import Session

    with Session(engine) as s:
        acc = accounts.create_account(s, "Bank", "debit", "COP", balance=0)
        accounts.archive_account(s, acc.id)
        acc_id = acc.id
    r = client.post(f"/api/accounts/{acc_id}/restore", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["archived"] is False
