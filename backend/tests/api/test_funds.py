"""The /funds door: it translates and delegates, and decides nothing.

Every refusal asserted here is raised by `services.funds` — the router is only
asked to carry it out as an HTTP status (ADR-0043/0044, feature 003 AC-28).
"""

from tests.support.fx import set_trm as _set_trm


def _category(client, auth, name="Restaurantes", is_income=False):
    return client.post(
        "/api/categories",
        json={"name": name, "is_income": is_income},
        headers=auth,
    ).json()["id"]


def _fixed_fund(client, auth, category_id, amount=20_000_000, start="2026-11"):
    return client.post(
        "/api/funds",
        json={"category_id": category_id, "rule": "fixed", "amount": amount, "start_month": start},
        headers=auth,
    )


def test_creating_a_fund_returns_the_stored_rule(client, auth):
    category = _category(client, auth)
    resp = _fixed_fund(client, auth, category)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["category_id"] == category
    assert body["rule"] == "fixed"
    assert body["amount"] == 20_000_000
    assert body["accumulates"] is True


def test_the_list_names_the_category_the_fund_covers(client, auth):
    category = _category(client, auth)
    _fixed_fund(client, auth, category)
    rows = client.get("/api/funds", headers=auth).json()
    assert [(r["name"], r["rule"], r["start_month"]) for r in rows] == [("Restaurantes", "fixed", "2026-11")]


def test_a_fund_on_an_income_category_is_refused_by_the_service(client, auth):
    salary = _category(client, auth, "Salario", is_income=True)
    resp = _fixed_fund(client, auth, salary)
    assert resp.status_code == 422, resp.text
    assert "going out" in resp.json()["detail"]


def test_a_second_fund_on_the_same_category_is_refused(client, auth):
    category = _category(client, auth)
    _fixed_fund(client, auth, category)
    resp = _fixed_fund(client, auth, category)
    assert resp.status_code == 422, resp.text
    assert "already has a fund" in resp.json()["detail"]


def test_the_preview_warns_before_the_fund_exists(client, auth):
    _set_trm(client, auth)
    category = _category(client, auth)
    resp = client.post(
        "/api/funds/preview",
        json={
            "category_id": category,
            "rule": "target-by-date",
            "target_amount": 300_000_000,
            "target_month": "2026-11",
            "start_month": "2026-11",
        },
        headers=auth,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["would_ask"] == 300_000_000
    assert "leaves no month to save in" in body["warning"]
    assert client.get("/api/funds", headers=auth).json() == []


def test_the_status_of_one_fund_is_read_per_month(client, auth):
    _set_trm(client, auth)
    category = _category(client, auth)
    fund = _fixed_fund(client, auth, category).json()
    resp = client.get(f"/api/funds/{fund['id']}/status", params={"month": "2026-11"}, headers=auth)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["asks"] == 20_000_000
    assert body["name"] == "Restaurantes"
    assert body["year_month"] == "2026-11"


def test_the_money_available_opens_into_a_breakdown_that_adds_up(client, auth):
    _set_trm(client, auth)
    category = _category(client, auth)
    _fixed_fund(client, auth, category)
    body = client.get("/api/funds/available", params={"month": "2026-11"}, headers=auth).json()
    assert [line["name"] for line in body["funds"]] == ["Restaurantes"]
    asked = sum(line["asks"] for line in body["funds"])
    assert body["income"] - asked - body["uncovered"] == body["free"]


def test_the_rates_are_their_own_door(client, auth):
    _set_trm(client, auth)
    body = client.get("/api/funds/rates", params={"month": "2026-11"}, headers=auth).json()
    assert body["earning"] - body["cost"] == body["margin"]


def test_reading_the_number_without_a_rate_is_409(client, auth):
    resp = client.get("/api/funds/available", params={"month": "2026-11"}, headers=auth)
    assert resp.status_code == 409 and resp.json()["error"] == "MissingRate"


def test_a_malformed_month_is_422(client, auth):
    _set_trm(client, auth)
    assert client.get("/api/funds/available", params={"month": "2026-6"}, headers=auth).status_code == 422


def test_changing_a_fund_records_what_the_owner_says_it_holds(client, auth):
    _set_trm(client, auth)
    category = _category(client, auth)
    fund = _fixed_fund(client, auth, category).json()
    assert client.patch(f"/api/funds/{fund['id']}", json={"balance": 5_000_000}, headers=auth).status_code == 200
    status = client.get(f"/api/funds/{fund['id']}/status", params={"month": "2026-11"}, headers=auth).json()
    assert status["holds"] == 5_000_000


def test_deleting_a_fund_leaves_none_and_is_not_found_twice(client, auth):
    category = _category(client, auth)
    fund = _fixed_fund(client, auth, category).json()
    assert client.delete(f"/api/funds/{fund['id']}", headers=auth).status_code == 204
    assert client.get("/api/funds", headers=auth).json() == []
    assert client.delete(f"/api/funds/{fund['id']}", headers=auth).status_code == 404


def test_every_fund_door_requires_auth(client):
    assert client.get("/api/funds").status_code == 401
    assert client.get("/api/funds/available", params={"month": "2026-11"}).status_code == 401
    assert client.get("/api/funds/rates", params={"month": "2026-11"}).status_code == 401
    assert client.post("/api/funds", json={}).status_code == 401
    assert client.delete("/api/funds/1").status_code == 401
