from quaestor.services import accounts
from sqlmodel import Session


def _seed_account(engine):
    with Session(engine) as s:
        acc = accounts.create_account(s, "Bank", "debit", "COP", balance=1_000_000)
        return acc.id


def test_create_and_list_recurring(client, engine, auth):
    acc_id = _seed_account(engine)
    body = {
        "name": "Rent", "payee": "Landlord", "type": "expense", "mode": "auto",
        "amount": 2_000_000, "account_id": acc_id, "interval_unit": "month",
        "interval_count": 1, "start_date": "2026-01-01",
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
        "name": "X", "payee": "Y", "type": "transfer", "mode": "auto",
        "amount": 1000, "account_id": acc_id, "interval_unit": "month",
        "interval_count": 1, "start_date": "2026-01-01",
    }
    r = client.post("/api/recurring", json=body, headers=auth)
    assert r.status_code == 422


def test_skip_recurring_occurrence(client, engine, auth):
    acc_id = _seed_account(engine)
    body = {
        "name": "Water", "payee": "Utility", "type": "expense", "mode": "manual",
        "amount": 50_000, "account_id": acc_id, "interval_unit": "month",
        "interval_count": 1, "start_date": "2026-01-05",
    }
    rec_id = client.post("/api/recurring", json=body, headers=auth).json()["id"]
    r = client.post(f"/api/recurring/{rec_id}/skip", json={"due_date": "2026-01-05"}, headers=auth)
    assert r.status_code == 200
    assert r.json()["status"] == "skipped"


def test_recurring_requires_auth(client):
    assert client.get("/api/recurring").status_code == 401
