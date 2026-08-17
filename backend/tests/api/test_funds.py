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


def _charge_due(client, auth, category_id, amount, on):
    """One yearly obligation, so a fund reading its category has a date."""
    account = client.post(
        "/api/accounts",
        json={"name": "Banco", "type": "debit", "currency": "COP"},
        headers=auth,
    ).json()["id"]
    return client.post(
        "/api/recurring",
        json={
            "name": "Cobro",
            "payee": "Cobro",
            "type": "expense",
            "mode": "manual",
            "amount": amount,
            "currency": "COP",
            "category_id": category_id,
            "account_id": account,
            "interval_unit": "year",
            "interval_count": 1,
            "start_date": on,
        },
        headers=auth,
    )


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
    _charge_due(client, auth, category, 300_000_000, "2026-11-20")
    resp = client.post(
        "/api/funds/preview",
        json={
            "category_id": category,
            "rule": "from-recurring",
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


def _charge_every(client, auth, category_id, *, unit="year", count=1, start="2027-07-05", name="Seguro"):
    account = client.post(
        "/api/accounts",
        json={"name": f"Banco {name}", "type": "debit", "currency": "COP"},
        headers=auth,
    ).json()["id"]
    return client.post(
        "/api/recurring",
        json={
            "name": name,
            "payee": name,
            "type": "expense",
            "mode": "manual",
            "amount": 110_000_000,
            "currency": "COP",
            "category_id": category_id,
            "account_id": account,
            "interval_unit": unit,
            "interval_count": count,
            "start_date": start,
        },
        headers=auth,
    ).json()["id"]


def test_the_charge_list_says_which_may_be_saved_for_and_why_not(client, auth):
    """AC-2: where the box is not offered, the row explains it in one line."""
    _set_trm(client, auth)
    category = _category(client, auth, "Carro")
    spreadable = _charge_every(client, auth, category)
    monthly = _charge_every(client, auth, category, unit="month", start="2026-09-05", name="Netflix")

    rows = client.get("/api/funds/charges", params={"month": "2026-08"}, headers=auth).json()

    by_id = {row["recurring_id"]: row for row in rows}
    assert by_id[spreadable]["can_be_marked"] is True
    assert by_id[spreadable]["why_not"] is None
    assert by_id[monthly]["can_be_marked"] is False
    assert "whole month" in by_id[monthly]["why_not"]


def test_marking_a_charge_creates_its_fund_and_marking_it_twice_is_refused(client, auth):
    """AC-1 through the door, and AC-10's fourth refusal behind it."""
    _set_trm(client, auth)
    category = _category(client, auth, "Carro")
    charge = _charge_every(client, auth, category)

    created = client.post(f"/api/funds/charges/{charge}", params={"month": "2026-08"}, headers=auth)
    assert created.status_code == 201
    assert created.json()["rule"] == "from-recurring"
    assert created.json()["start_month"] == "2026-08"

    again = client.post(f"/api/funds/charges/{charge}", params={"month": "2026-08"}, headers=auth)
    assert again.status_code == 422

    listed = client.get("/api/funds", headers=auth).json()
    assert [row["name"] for row in listed] == ["Seguro"]


def test_the_turns_door_offers_the_open_ones_of_one_charge(client, auth):
    """AC-5's second question, asked only once a charge has been chosen."""
    _set_trm(client, auth)
    category = _category(client, auth, "Carro")
    charge = _charge_every(client, auth, category, unit="month", start="2026-01-05", name="Club")

    offered = client.get(f"/api/funds/charges/{charge}/turns", headers=auth)

    assert offered.status_code == 200
    assert len(offered.json()) >= 2
    assert offered.json() == sorted(offered.json())


def test_asking_what_an_edit_would_cost_the_fund_before_saving_it(client, auth):
    """AC-8's fifth door: the screen says what is about to happen, in one step."""
    _set_trm(client, auth)
    category = _category(client, auth, "Carro")
    charge = _charge_every(client, auth, category)
    client.post(f"/api/funds/charges/{charge}", params={"month": "2026-08"}, headers=auth)

    kept = client.post(
        f"/api/funds/charges/{charge}/edit-cost",
        json={"month": "2026-08", "interval_unit": "year", "interval_count": 1},
        headers=auth,
    )
    lost = client.post(
        f"/api/funds/charges/{charge}/edit-cost",
        json={"month": "2026-08", "interval_unit": "month", "interval_count": 1},
        headers=auth,
    )

    assert kept.json()["would_lose_its_fund"] is False
    assert lost.json()["would_lose_its_fund"] is True


def test_unmarking_a_charge_removes_its_fund_and_says_nothing_the_second_time(client, auth):
    """AC-4: unmarking is idempotent, which is what lets AC-8's doors all close alike."""
    _set_trm(client, auth)
    category = _category(client, auth, "Carro")
    charge = _charge_every(client, auth, category)
    client.post(f"/api/funds/charges/{charge}", params={"month": "2026-08"}, headers=auth)

    assert client.delete(f"/api/funds/charges/{charge}", headers=auth).status_code == 204
    assert client.get("/api/funds", headers=auth).json() == []
    assert client.delete(f"/api/funds/charges/{charge}", headers=auth).status_code == 204


def test_every_charge_door_requires_auth(client):
    assert client.get("/api/funds/charges", params={"month": "2026-08"}).status_code == 401
    assert client.post("/api/funds/charges/1", params={"month": "2026-08"}).status_code == 401
    assert client.get("/api/funds/charges/1/turns").status_code == 401
    assert client.post("/api/funds/charges/1/edit-cost", json={"month": "2026-08"}).status_code == 401
    assert client.delete("/api/funds/charges/1").status_code == 401
