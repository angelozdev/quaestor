"""Golden outputs for the monthly read-path. These must not change through the
MonthAggregate refactor — they pin observable behavior at the API contract,
including rollover across months (May available rolls into June)."""

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
    # May: assign 100k to Food, spend 60k -> May available 40k rolls into June.
    client.put(
        "/api/budgets",
        json={"category_id": food["id"], "year_month": "2026-05", "amount_assigned": 100_000},
        headers=auth,
    )
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
    # June: expenses + income + Food budget.
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
    client.put(
        "/api/budgets",
        json={"category_id": food["id"], "year_month": "2026-06", "amount_assigned": 100_000},
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


def test_safe_to_spend_is_stable(client, auth, expense_category, income_category):
    _seed(client, auth, expense_category, income_category)
    sts = client.get("/api/budgets/safe-to-spend", params={"month": "2026-06"}, headers=auth).json()
    assert sts["year_month"] == "2026-06"
    assert sts["assigned_envelopes"] == 100_000


def test_list_budgets_pins_rollover(client, auth, expense_category, income_category):
    ids = _seed(client, auth, expense_category, income_category)
    lines = client.get("/api/budgets", params={"month": "2026-06"}, headers=auth).json()
    food = next(row for row in lines if row["category_id"] == ids["food"])
    assert food["assigned"] == 100_000
    assert food["spent"] == 80_000
    assert food["rollover_in"] == 40_000  # May: 100k assigned - 60k spent
    assert food["available"] == 60_000  # 40k rollover + 100k - 80k
    assert food["status"] == "under"


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
