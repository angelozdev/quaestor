from tests.support.fx import set_trm as _set_trm


def test_safe_to_spend_endpoint(client, auth):
    _set_trm(client, auth)
    r = client.get("/api/budgets/safe-to-spend", params={"month": "2026-06"}, headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["year_month"] == "2026-06"
    assert {"income_forecast", "committed", "assigned_envelopes", "free", "committed_breakdown"} <= body.keys()
    assert isinstance(body["free"], int)
    assert body["committed_breakdown"] == []


def test_safe_to_spend_without_trm_is_409(client, auth):
    r = client.get("/api/budgets/safe-to-spend", params={"month": "2026-06"}, headers=auth)
    assert r.status_code == 409 and r.json()["error"] == "MissingRate"


def test_safe_to_spend_malformed_month_is_422(client, auth):
    r = client.get("/api/budgets/safe-to-spend", params={"month": "junio"}, headers=auth)
    assert r.status_code == 422


def test_safe_to_spend_requires_auth(client):
    r = client.get("/api/budgets/safe-to-spend", params={"month": "2026-06"})
    assert r.status_code == 401


def _seed_category(engine, name="Food"):
    from quaestor.services import categories
    from sqlmodel import Session
    with Session(engine) as s:
        return categories.create_category(s, name=name).id


def test_list_budgets_endpoint(client, engine, auth):
    cat_id = _seed_category(engine)
    _set_trm(client, auth)
    r = client.get("/api/budgets?month=2026-06", headers=auth)
    assert r.status_code == 200, r.text
    assert any(line["category_id"] == cat_id for line in r.json())


def test_list_budgets_without_trm_is_409(client, engine, auth):
    _seed_category(engine)
    r = client.get("/api/budgets?month=2026-06", headers=auth)
    assert r.status_code == 409 and r.json()["error"] == "MissingRate"


def test_put_budget_assign_is_idempotent(client, engine, auth):
    cat_id = _seed_category(engine)
    _set_trm(client, auth)
    body = {"category_id": cat_id, "year_month": "2026-06", "amount_assigned": 500_000}
    r1 = client.put("/api/budgets", json=body, headers=auth)
    assert r1.status_code == 200, r1.text
    assert r1.json()["assigned"] == 500_000
    body["amount_assigned"] = 700_000
    r2 = client.put("/api/budgets", json=body, headers=auth)
    assert r2.json()["assigned"] == 700_000
