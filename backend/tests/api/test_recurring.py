from quaestor.domain.models import Transaction
from quaestor.services import accounts
from sqlmodel import Session

from tests.support.fx import set_trm as _set_trm


def _seed_account(engine):
    with Session(engine) as s:
        acc = accounts.create_account(s, "Bank", "debit", "COP", balance=1_000_000)
        return acc.id


def test_create_and_list_recurring(client, engine, auth, expense_category):
    acc_id = _seed_account(engine)
    body = {
        "name": "Rent",
        "payee": "Landlord",
        "type": "expense",
        "category_id": expense_category,
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


def test_skip_recurring_occurrence(client, engine, auth, expense_category):
    acc_id = _seed_account(engine)
    body = {
        "name": "Water",
        "payee": "Utility",
        "type": "expense",
        "category_id": expense_category,
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


def _seed_recurring(client, engine, auth, expense_category):
    acc_id = _seed_account(engine)
    body = {
        "name": "Rent",
        "payee": "LL",
        "type": "expense",
        "category_id": expense_category,
        "mode": "auto",
        "amount": 2_000_000,
        "account_id": acc_id,
        "interval_unit": "month",
        "interval_count": 1,
        "start_date": "2026-01-01",
    }
    return client.post("/api/recurring", json=body, headers=auth).json()["id"]


def test_patch_recurring(client, engine, auth, expense_category):
    rid = _seed_recurring(client, engine, auth, expense_category)
    r = client.patch(f"/api/recurring/{rid}", json={"amount": 2_500_000, "payee": "New"}, headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["amount"] == 2_500_000 and r.json()["payee"] == "New"


def test_delete_recurring_is_soft(client, engine, auth, expense_category):
    rid = _seed_recurring(client, engine, auth, expense_category)
    assert client.delete(f"/api/recurring/{rid}", headers=auth).status_code == 204
    # gone from active list, present when listing inactive
    assert client.get("/api/recurring?active=true", headers=auth).json() == []
    inactive = client.get("/api/recurring?active=false", headers=auth).json()
    assert [i["id"] for i in inactive] == [rid]


def test_patch_recurring_across_currencies_needs_the_amount_restated(client, engine, auth, expense_category):
    rid = _seed_recurring(client, engine, auth, expense_category)
    with Session(engine) as s:
        usd = accounts.create_account(s, "DolarApp", "debit", "USD", balance=0).id

    r = client.patch(f"/api/recurring/{rid}", json={"account_id": usd}, headers=auth)

    assert r.status_code == 422, r.text
    assert "must be stated in USD" in r.json()["detail"]


def test_patch_recurring_across_currencies_restates_the_charge(client, engine, auth, expense_category):
    rid = _seed_recurring(client, engine, auth, expense_category)
    with Session(engine) as s:
        usd = accounts.create_account(s, "DolarApp", "debit", "USD", balance=0).id

    r = client.patch(
        f"/api/recurring/{rid}",
        json={"account_id": usd, "amount": 2935, "currency": "USD"},
        headers=auth,
    )

    assert r.status_code == 200, r.text
    assert (r.json()["currency"], r.json()["amount"], r.json()["account_id"]) == ("USD", 2935, usd)


def test_restore_recurring(client, engine, auth, expense_category):
    rid = _seed_recurring(client, engine, auth, expense_category)
    client.delete(f"/api/recurring/{rid}", headers=auth)
    r = client.post(f"/api/recurring/{rid}/restore", headers=auth)
    assert r.status_code == 200 and r.json()["active"] is True


def _charge_from_a_peso_rule_on_a_dollar_account(client, engine, auth, expense_category):
    """Hevy Pro: priced in pesos, waiting, paid from an account holding dollars."""
    _set_trm(client, auth)
    with Session(engine) as s:
        usd = accounts.create_account(s, "DolarApp", "debit", "USD", balance=100_000).id
    rid = client.post(
        "/api/recurring",
        json={
            "name": "Hevy Pro",
            "payee": "Hevy",
            "type": "expense",
            "category_id": expense_category,
            "mode": "manual",
            "amount": 9_990_000,
            "currency": "COP",
            "account_id": usd,
            "interval_unit": "year",
            "interval_count": 1,
            "start_date": "2026-01-01",
        },
        headers=auth,
    ).json()["id"]
    posted = client.post(
        "/api/transactions",
        json={
            "type": "expense",
            "category_id": expense_category,
            "account_id": usd,
            "amount": 3_210,
            "currency": "USD",
            "date": "2026-07-12",
            "payee": "Hevy",
        },
        headers=auth,
    )
    assert posted.status_code == 201, posted.text
    tx = posted.json()
    with Session(engine) as s:
        row = s.get(Transaction, tx["id"])
        row.recurring_id = rid
        s.add(row)
        s.commit()
    return rid, tx["id"]


def test_a_charge_reports_the_price_its_rule_holds(client, engine, auth, expense_category):
    """AC-21 reaches the wire, not just the service."""
    _, tx_id = _charge_from_a_peso_rule_on_a_dollar_account(client, engine, auth, expense_category)

    got = client.get(f"/api/transactions/{tx_id}", headers=auth)
    assert got.status_code == 200, got.text
    row = got.json()

    assert (row["amount"], row["currency"]) == (3_210, "USD")
    assert (row["rule_amount"], row["rule_currency"]) == (9_990_000, "COP")


def test_the_listing_reports_it_too(client, engine, auth, expense_category):
    _, tx_id = _charge_from_a_peso_rule_on_a_dollar_account(client, engine, auth, expense_category)

    row = next(t for t in client.get("/api/transactions", headers=auth).json() if t["id"] == tx_id)

    assert (row["rule_amount"], row["rule_currency"]) == (9_990_000, "COP")


def test_a_charge_from_a_rule_switched_off_reports_no_price(client, engine, auth, expense_category):
    rid, tx_id = _charge_from_a_peso_rule_on_a_dollar_account(client, engine, auth, expense_category)
    client.delete(f"/api/recurring/{rid}", headers=auth)

    row = client.get(f"/api/transactions/{tx_id}", headers=auth).json()

    assert (row["rule_amount"], row["rule_currency"]) == (None, None)
