from quaestor.services import accounts
from sqlmodel import Session

from tests.support.fx import set_trm as _set_trm


def _seed_account(engine, balance=1_000_000, currency="COP", name="Bank"):
    with Session(engine) as s:
        acc = accounts.create_account(s, name, "debit", currency, balance=balance)
        return acc.id


def test_plan_without_trm_then_to_pay_confirm_flow(client, engine, auth):
    acc_id = _seed_account(engine)
    plan = client.post("/api/planned", json={
        "payee": "Friend", "amount": 80_000, "due_date": "2026-12-15", "account_id": acc_id,
    }, headers=auth)
    assert plan.status_code == 201, plan.text
    tx_id = plan.json()["id"]
    assert plan.json()["status"] == "planned"
    assert plan.json()["cop_equivalent"] is None

    _set_trm(client, auth)
    queue = client.get("/api/planned/to-pay", params={"since": "2026-12-01", "until": "2026-12-31"}, headers=auth)
    assert queue.status_code == 200
    assert queue.json()["total_base"] == 80_000
    assert [i["id"] for i in queue.json()["upcoming"]] == [tx_id]

    confirm = client.post(f"/api/planned/{tx_id}/confirm", json={"amount": 85_000}, headers=auth)
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "posted" and confirm.json()["amount"] == 85_000


def test_to_pay_without_trm_is_409(client, auth):
    resp = client.get(
        "/api/planned/to-pay", params={"since": "2026-12-01", "until": "2026-12-31"}, headers=auth
    )
    assert resp.status_code == 409 and resp.json()["error"] == "MissingRate"


def test_to_pay_total_base_converts_usd_items_at_current_trm(client, engine, auth):
    cop_acc = _seed_account(engine, name="Bank COP")
    usd_acc = _seed_account(engine, currency="USD", name="Bank USD")
    client.post("/api/planned", json={
        "payee": "Rent", "amount": 500_000, "due_date": "2026-12-10", "account_id": cop_acc,
    }, headers=auth)
    client.post("/api/planned", json={
        "payee": "SaaS", "amount": 1_000, "currency": "USD",
        "due_date": "2026-12-20", "account_id": usd_acc,
    }, headers=auth)
    _set_trm(client, auth, "4000")
    first = client.get(
        "/api/planned/to-pay", params={"since": "2026-12-01", "until": "2026-12-31"}, headers=auth
    ).json()
    assert first["total_base"] == 500_000 + 4_000_000
    usd_item = next(i for i in first["upcoming"] if i["payee"] == "SaaS")
    assert usd_item["cop_equivalent"] == 4_000_000
    _set_trm(client, auth, "4500")
    second = client.get(
        "/api/planned/to-pay", params={"since": "2026-12-01", "until": "2026-12-31"}, headers=auth
    ).json()
    assert second["total_base"] == 500_000 + 4_500_000


def test_confirm_non_planned_is_409(client, engine, auth):
    acc_id = _seed_account(engine)
    plan = client.post("/api/planned", json={
        "payee": "Friend", "amount": 80_000, "due_date": "2026-06-20", "account_id": acc_id,
    }, headers=auth)
    tx_id = plan.json()["id"]
    client.post(f"/api/planned/{tx_id}/confirm", json={}, headers=auth)
    again = client.post(f"/api/planned/{tx_id}/confirm", json={}, headers=auth)
    assert again.status_code == 409


def test_skip_planned_payment_works_without_trm(client, engine, auth):
    acc_id = _seed_account(engine)
    tx_id = client.post("/api/planned", json={
        "payee": "Friend", "amount": 80_000, "due_date": "2026-06-20", "account_id": acc_id,
    }, headers=auth).json()["id"]
    r = client.post(f"/api/planned/{tx_id}/skip", json={}, headers=auth)
    assert r.status_code == 200 and r.json()["status"] == "skipped"


def test_restore_skipped_payment_returns_it_to_planned(client, engine, auth):
    acc_id = _seed_account(engine)
    tx_id = client.post("/api/planned", json={
        "payee": "Claro", "amount": 85_000, "due_date": "2026-06-20", "account_id": acc_id,
    }, headers=auth).json()["id"]
    client.post(f"/api/planned/{tx_id}/skip", json={}, headers=auth)
    r = client.post(f"/api/planned/{tx_id}/restore", json={}, headers=auth)
    assert r.status_code == 200 and r.json()["status"] == "planned"
    assert r.json()["amount"] == 85_000


def test_restore_non_skipped_payment_is_409(client, engine, auth):
    acc_id = _seed_account(engine)
    tx_id = client.post("/api/planned", json={
        "payee": "Claro", "amount": 85_000, "due_date": "2026-06-20", "account_id": acc_id,
    }, headers=auth).json()["id"]
    r = client.post(f"/api/planned/{tx_id}/restore", json={}, headers=auth)
    assert r.status_code == 409


def test_rollover_admin_endpoint_runs(client, auth):
    r = client.post("/api/rollover", json={"period": "2026-06"}, headers=auth)
    assert r.status_code == 200
    assert r.json()["period"] == "2026-06"


def test_to_pay_response_includes_overdue_before_since(client, auth):
    """Bug reproduction at the HTTP layer: an overdue item with
    date < since appears in `overdue` (not silently dropped)."""
    from datetime import date as Date
    from datetime import timedelta

    _set_trm(client, auth)
    resp = client.post(
        "/api/accounts",
        headers=auth,
        json={"name": "Bank", "type": "debit", "currency": "COP"},
    )
    account_id = resp.json()["id"]
    due = (Date.today() - timedelta(days=10)).isoformat()
    client.post(
        "/api/planned",
        headers=auth,
        json={
            "payee": "Tigo",
            "amount": 8_500_00,
            "account_id": account_id,
            "currency": "COP",
            "due_date": due,
        },
    )
    since = (Date.today() + timedelta(days=5)).isoformat()
    until = (Date.today() + timedelta(days=10)).isoformat()
    body = client.get(
        f"/api/planned/to-pay?since={since}&until={until}",
        headers=auth,
    ).json()
    assert any(t["payee"] == "Tigo" for t in body["overdue"])
    assert body["upcoming"] == []


def test_to_pay_response_has_overdue_and_upcoming_keys(client, auth):
    """Wire format: the response has both `overdue` and `upcoming` keys."""
    _set_trm(client, auth)
    body = client.get(
        "/api/planned/to-pay?since=2026-01-01&until=2026-12-31",
        headers=auth,
    ).json()
    assert "overdue" in body
    assert "upcoming" in body
    assert "total_base" in body
