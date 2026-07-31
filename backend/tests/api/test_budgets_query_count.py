"""The budgets read-path must be bounded regardless of category/month count.

Red rationale (verified against current code): list_budgets runs
budget_status per category (= _assigned 1 + _spent 2 + _available recursion
~2 per active month), so 15 categories × 3 active months ≈ 150+ queries.
safe_to_spend's _has_envelope adds one query per recurring item / planned tx /
unbudgeted posted tx. Both far exceed the bounds below before the refactor.
"""
from tests.support.query_counter import count_queries


def _seed(client, auth, n_categories=15):
    assert client.post("/api/fx", json={"usd_cop": "4000"}, headers=auth).status_code == 201
    acc = client.post(
        "/api/accounts", json={"name": "Bank", "type": "debit", "currency": "COP"},
        headers=auth,
    ).json()
    for name, tx_type, amount in [("Salary", "income", 2_000_000), ("Rent", "expense", 800_000)]:
        client.post(
            "/api/recurring",
            json={
                "name": name, "type": tx_type, "mode": "manual", "amount": amount,
                "currency": "COP", "account_id": acc["id"], "interval_unit": "month",
                "interval_count": 1, "start_date": "2026-01-01",
            },
            headers=auth,
        )
    for i in range(n_categories):
        cat = client.post(
            "/api/categories", json={"name": f"Cat {i}"}, headers=auth
        ).json()
        for m in ("2026-04", "2026-05", "2026-06"):
            client.put(
                "/api/budgets",
                json={"category_id": cat["id"], "year_month": m, "amount_assigned": 10_000},
                headers=auth,
            )
            client.post(
                "/api/transactions",
                json={
                    "type": "expense", "account_id": acc["id"], "amount": 5_000,
                    "currency": "COP", "date": f"{m}-10", "category_id": cat["id"],
                    "payee": "seed",
                },
                headers=auth,
            )


def test_list_budgets_query_count_is_bounded(client, auth, engine):
    _seed(client, auth, n_categories=15)
    with count_queries(engine) as c:
        r = client.get("/api/budgets", params={"month": "2026-06"}, headers=auth)
    assert r.status_code == 200
    assert c.count <= 15, f"list_budgets issued {c.count} queries"


def test_safe_to_spend_query_count_is_bounded(client, auth, engine):
    _seed(client, auth, n_categories=15)
    with count_queries(engine) as c:
        r = client.get("/api/budgets/safe-to-spend", params={"month": "2026-06"}, headers=auth)
    assert r.status_code == 200
    assert c.count <= 20, f"safe_to_spend issued {c.count} queries"
