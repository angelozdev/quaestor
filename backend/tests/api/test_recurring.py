from quaestor.services import accounts
from sqlmodel import Session


def _seed_account(engine):
    with Session(engine) as s:
        acc = accounts.create_account(s, "Bank", "debit", "COP", balance=1_000_000)
        return acc.id


def test_create_and_list_recurring(client, engine, auth):
    acc_id = _seed_account(engine)
    body = {
        "name": "Rent",
        "payee": "Landlord",
        "type": "expense",
        "mode": "auto",
        "amount": 2_000_000,
        "account_id": acc_id,
        "interval_unit": "month",
        "interval_count": 1,
        "start_date": "2026-01-01",
    }
    r = client.post("/api/recurring", json=body, headers=auth)
    assert r.status_code == 201, r.text
    assert r.json()["active"] is True

    r2 = client.get("/api/recurring", headers=auth)
    assert r2.status_code == 200
    assert [i["name"] for i in r2.json()] == ["Rent"]


def test_create_recurring_transfer_type_is_422(client, engine, auth):
    acc_id = _seed_account(engine)
    body = {
        "name": "X",
        "payee": "Y",
        "type": "transfer",
        "mode": "auto",
        "amount": 1000,
        "account_id": acc_id,
        "interval_unit": "month",
        "interval_count": 1,
        "start_date": "2026-01-01",
    }
    r = client.post("/api/recurring", json=body, headers=auth)
    assert r.status_code == 422


def test_skip_recurring_occurrence(client, engine, auth):
    acc_id = _seed_account(engine)
    body = {
        "name": "Water",
        "payee": "Utility",
        "type": "expense",
        "mode": "manual",
        "amount": 50_000,
        "account_id": acc_id,
        "interval_unit": "month",
        "interval_count": 1,
        "start_date": "2026-01-05",
    }
    rec_id = client.post("/api/recurring", json=body, headers=auth).json()["id"]
    r = client.post(f"/api/recurring/{rec_id}/skip", json={"due_date": "2026-01-05"}, headers=auth)
    assert r.status_code == 200
    assert r.json()["status"] == "skipped"


def test_recurring_requires_auth(client):
    assert client.get("/api/recurring").status_code == 401


def _seed_recurring(client, engine, auth):
    acc_id = _seed_account(engine)
    body = {
        "name": "Rent",
        "payee": "LL",
        "type": "expense",
        "mode": "auto",
        "amount": 2_000_000,
        "account_id": acc_id,
        "interval_unit": "month",
        "interval_count": 1,
        "start_date": "2026-01-01",
    }
    return client.post("/api/recurring", json=body, headers=auth).json()["id"]


def test_patch_recurring(client, engine, auth):
    rid = _seed_recurring(client, engine, auth)
    r = client.patch(f"/api/recurring/{rid}", json={"amount": 2_500_000, "payee": "New"}, headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["amount"] == 2_500_000 and r.json()["payee"] == "New"


def test_delete_recurring_is_soft(client, engine, auth):
    rid = _seed_recurring(client, engine, auth)
    assert client.delete(f"/api/recurring/{rid}", headers=auth).status_code == 204
    # gone from active list, present when listing inactive
    assert client.get("/api/recurring?active=true", headers=auth).json() == []
    inactive = client.get("/api/recurring?active=false", headers=auth).json()
    assert [i["id"] for i in inactive] == [rid]


def test_restore_recurring(client, engine, auth):
    rid = _seed_recurring(client, engine, auth)
    client.delete(f"/api/recurring/{rid}", headers=auth)
    r = client.post(f"/api/recurring/{rid}/restore", headers=auth)
    assert r.status_code == 200 and r.json()["active"] is True
