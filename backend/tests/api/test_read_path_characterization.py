"""Golden outputs for the monthly read-path. These must not change through the
MonthAggregate refactor — they pin observable behavior at the API contract,
including rollover across months (May available rolls into June)."""


def _seed(client, auth):
    acc = client.post(
        "/api/accounts",
        json={"name": "Bank", "type": "debit", "currency": "COP"},
        headers=auth,
    ).json()
    grp = client.post(
        "/api/category-groups", json={"name": "Living"}, headers=auth
    ).json()
    food = client.post(
        "/api/categories", json={"name": "Food", "group_id": grp["id"]}, headers=auth
    ).json()
    rent = client.post(
        "/api/categories", json={"name": "Rent", "group_id": grp["id"]}, headers=auth
    ).json()
    # May: assign 100k to Food, spend 60k -> May available 40k rolls into June.
    client.put(
        "/api/budgets",
        json={"category_id": food["id"], "year_month": "2026-05", "amount_assigned": 100_000},
        headers=auth,
    )
    client.post(
        "/api/transactions",
        json={
            "type": "expense", "account_id": acc["id"], "amount": 60_000,
            "currency": "COP", "date": "2026-05-15", "category_id": food["id"],
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
                "type": "expense", "account_id": acc["id"], "amount": amount,
                "currency": "COP", "date": f"2026-06-{day}", "category_id": cat_id,
                "payee": "seed",
            },
            headers=auth,
        )
    client.post(
        "/api/transactions",
        json={
            "type": "income", "account_id": acc["id"], "amount": 2_000_000,
            "currency": "COP", "date": "2026-06-02", "payee": "Salary",
        },
        headers=auth,
    )
    client.put(
        "/api/budgets",
        json={"category_id": food["id"], "year_month": "2026-06", "amount_assigned": 100_000},
        headers=auth,
    )
    return {"food": food["id"], "rent": rent["id"]}


def test_report_totals_and_sections_are_stable(client, auth):
    _seed(client, auth)
    body = client.get("/api/reports", params={"month": "2026-06"}, headers=auth).json()
    assert body["income"] == 2_000_000
    assert body["expense"] == 880_000
    assert body["net"] == 1_120_000
    by_cat = {c["category"]: c["total"] for c in body["by_category"]}
    assert by_cat == {"Food": 80_000, "Rent": 800_000}
    by_group = {g["group"]: g["total"] for g in body["by_group"]}
    assert by_group == {"Living": 880_000}


def test_safe_to_spend_is_stable(client, auth):
    _seed(client, auth)
    sts = client.get(
        "/api/budgets/safe-to-spend", params={"month": "2026-06"}, headers=auth
    ).json()
    assert sts["year_month"] == "2026-06"
    assert sts["assigned_envelopes"] == 100_000


def test_list_budgets_pins_rollover(client, auth):
    ids = _seed(client, auth)
    lines = client.get(
        "/api/budgets", params={"month": "2026-06"}, headers=auth
    ).json()
    food = next(l for l in lines if l["category_id"] == ids["food"])
    assert food["assigned"] == 100_000
    assert food["spent"] == 80_000
    assert food["rollover_in"] == 40_000  # May: 100k assigned - 60k spent
    assert food["available"] == 60_000    # 40k rollover + 100k - 80k
    assert food["status"] == "under"
