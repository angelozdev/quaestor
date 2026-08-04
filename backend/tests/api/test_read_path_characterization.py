"""Golden outputs for the monthly read-path, pinned at the API contract.

The envelope goldens they opened with are gone with the envelope; what a
category carries forward is now a fund's fold, characterised in
`tests/services/test_funds.py`."""

from tests.support.fx import set_trm as _set_trm


def _seed(client, auth, expense_category, income_category):
    _set_trm(client, auth)
    acc = client.post(
        "/api/accounts",
        json={"name": "Bank", "type": "debit", "currency": "COP"},
        headers=auth,
    ).json()
    grp = client.post("/api/category-groups", json={"name": "Living"}, headers=auth).json()
    food = client.post("/api/categories", json={"name": "Food", "group_id": grp["id"]}, headers=auth).json()
    rent = client.post("/api/categories", json={"name": "Rent", "group_id": grp["id"]}, headers=auth).json()
    # May: spend 60k on Food, so the month before the report is not empty.
    client.post(
        "/api/transactions",
        json={
            "type": "expense",
            "account_id": acc["id"],
            "amount": 60_000,
            "currency": "COP",
            "date": "2026-05-15",
            "category_id": food["id"],
            "payee": "seed",
        },
        headers=auth,
    )
    # June: expenses + income.
    for cat_id, amount, day in [
        (food["id"], 50_000, "05"),
        (food["id"], 30_000, "12"),
        (rent["id"], 800_000, "01"),
    ]:
        client.post(
            "/api/transactions",
            json={
                "type": "expense",
                "category_id": cat_id,
                "account_id": acc["id"],
                "amount": amount,
                "currency": "COP",
                "date": f"2026-06-{day}",
                "payee": "seed",
            },
            headers=auth,
        )
    client.post(
        "/api/transactions",
        json={
            "type": "income",
            "category_id": income_category,
            "account_id": acc["id"],
            "amount": 2_000_000,
            "currency": "COP",
            "date": "2026-06-02",
            "payee": "Salary",
        },
        headers=auth,
    )
    return {"food": food["id"], "rent": rent["id"]}


def test_report_totals_and_sections_are_stable(client, auth, expense_category, income_category):
    _seed(client, auth, expense_category, income_category)
    body = client.get("/api/reports", params={"month": "2026-06"}, headers=auth).json()
    assert body["income"] == 2_000_000
    assert body["expense"] == 880_000
    assert body["net"] == 1_120_000
    by_cat = {c["category"]: c["total"] for c in body["by_category"]}
    assert by_cat == {"Food": 80_000, "Rent": 800_000}
    by_group = {g["group"]: g["total"] for g in body["by_group"]}
    assert by_group == {"Living": 880_000}


def test_the_closing_line_is_stable(client, auth, expense_category, income_category):
    _seed(client, auth, expense_category, income_category)
    body = client.get("/api/reports", params={"month": "2026-06"}, headers=auth).json()
    available = body["available"]
    assert available["year_month"] == "2026-06"
    assert available["income"] == 2_000_000
    assert available["funds"] == []
    assert available["uncovered"] == 880_000  # no fund covers any of it
    assert available["free"] == 1_120_000


def test_transaction_wire_format_pins_cop_equivalent_and_drops_frozen_fx_fields(client, auth, expense_category):
    _set_trm(client, auth)
    acc = client.post(
        "/api/accounts",
        json={"name": "Bank", "type": "debit", "currency": "COP"},
        headers=auth,
    ).json()
    client.post(
        "/api/transactions",
        json={
            "type": "expense",
            "category_id": expense_category,
            "account_id": acc["id"],
            "amount": 60_000,
            "currency": "COP",
            "date": "2026-06-15",
            "payee": "seed",
        },
        headers=auth,
    )
    row = client.get("/api/transactions", headers=auth).json()[0]
    assert set(row) == {
        "id",
        "date",
        "payee",
        "notes",
        "type",
        "status",
        "amount",
        "currency",
        "cop_equivalent",
        "account_id",
        "category_id",
        "transfer_group_id",
        "transfer_direction",
        "source",
        "created_at",
        "tags",
    }
    assert row["cop_equivalent"] == 60_000


def test_report_totals_convert_usd_at_the_current_trm_not_a_frozen_rate(client, auth, expense_category):
    _set_trm(client, auth, "4000")
    acc = client.post(
        "/api/accounts",
        json={"name": "USD Bank", "type": "debit", "currency": "USD"},
        headers=auth,
    ).json()
    client.post(
        "/api/transactions",
        json={
            "type": "expense",
            "category_id": expense_category,
            "account_id": acc["id"],
            "amount": 1_000,
            "currency": "USD",
            "date": "2026-06-10",
            "payee": "Amazon",
        },
        headers=auth,
    )
    at_4000 = client.get("/api/reports", params={"month": "2026-06"}, headers=auth).json()
    assert at_4000["expense"] == 4_000_000
    _set_trm(client, auth, "4500")
    at_4500 = client.get("/api/reports", params={"month": "2026-06"}, headers=auth).json()
    assert at_4500["expense"] == 4_500_000
