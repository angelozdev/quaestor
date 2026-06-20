from quaestor.services import accounts
from sqlmodel import Session


def _seed_account(engine, balance=1_000_000):
    with Session(engine) as s:
        acc = accounts.create_account(s, "Bank", "debit", "COP", balance=balance)
        return acc.id


def test_plan_to_pay_confirm_flow(client, engine, auth):
    acc_id = _seed_account(engine)
    plan = client.post("/api/planned", json={
        "payee": "Friend", "amount": 80_000, "due_date": "2026-06-20", "account_id": acc_id,
    }, headers=auth)
    assert plan.status_code == 201, plan.text
    tx_id = plan.json()["id"]
    assert plan.json()["status"] == "planned"

    queue = client.get("/api/planned/to-pay", params={"since": "2026-06-01", "until": "2026-06-30"}, headers=auth)
    assert queue.status_code == 200
    assert queue.json()["total_base"] == 80_000
    assert [i["id"] for i in queue.json()["items"]] == [tx_id]

    confirm = client.post(f"/api/planned/{tx_id}/confirm", json={"amount": 85_000}, headers=auth)
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "posted" and confirm.json()["amount"] == 85_000


def test_confirm_non_planned_is_409(client, engine, auth):
    acc_id = _seed_account(engine)
    # post a normal expense, then try to confirm it
    plan = client.post("/api/planned", json={
        "payee": "Friend", "amount": 80_000, "due_date": "2026-06-20", "account_id": acc_id,
    }, headers=auth)
    tx_id = plan.json()["id"]
    client.post(f"/api/planned/{tx_id}/confirm", json={}, headers=auth)  # now posted
    again = client.post(f"/api/planned/{tx_id}/confirm", json={}, headers=auth)
    assert again.status_code == 409


def test_skip_planned_payment(client, engine, auth):
    acc_id = _seed_account(engine)
    tx_id = client.post("/api/planned", json={
        "payee": "Friend", "amount": 80_000, "due_date": "2026-06-20", "account_id": acc_id,
    }, headers=auth).json()["id"]
    r = client.post(f"/api/planned/{tx_id}/skip", json={}, headers=auth)
    assert r.status_code == 200 and r.json()["status"] == "skipped"


def test_rollover_admin_endpoint_runs(client, auth):
    r = client.post("/api/rollover", json={"period": "2026-06"}, headers=auth)
    assert r.status_code == 200
    assert r.json()["period"] == "2026-06"
