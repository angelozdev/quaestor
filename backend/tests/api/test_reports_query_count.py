"""The monthly report must be bounded regardless of transaction count.

Red rationale (verified against current code): _envelope_lines runs
budget_status per budget (recursion included: ~9 queries per budget with two
active months), safe_to_spend inside the report repeats the overspend walk,
and _has_envelope fires per item. With 6 budgeted categories over two months
plus goals, the current count lands in the hundreds — far above the bound.

NOTE on the bound: if this fails AFTER the refactor, record the actual count
and set the bound to actual + 2 — it must stay far below the pre-refactor
count (document the observed numbers in the commit message). Goals cost one
query each by design (see spec: known linearities).
"""
from tests.support.query_counter import count_queries


def test_report_query_count_is_bounded(client, auth, engine):
    assert client.post("/api/fx", json={"usd_cop": "4000"}, headers=auth).status_code == 201
    acc = client.post(
        "/api/accounts", json={"name": "Bank", "type": "debit", "currency": "COP"},
        headers=auth,
    ).json()
    savings = client.post(
        "/api/accounts", json={"name": "Savings", "type": "debit", "currency": "COP"},
        headers=auth,
    ).json()
    for g in range(3):
        client.post(
            "/api/goals",
            json={"name": f"Goal {g}", "monthly_amount": 100_000,
                  "savings_account_id": savings["id"]},
            headers=auth,
        )
    cats = [
        client.post("/api/categories", json={"name": f"Cat {i}"}, headers=auth).json()
        for i in range(6)
    ]
    # Budgets across two months -> _envelope_lines + rollover recursion are
    # genuinely exercised pre-refactor (this is what makes the test red).
    for cat in cats:
        for m in ("2026-05", "2026-06"):
            client.put(
                "/api/budgets",
                json={"category_id": cat["id"], "year_month": m, "amount_assigned": 50_000},
                headers=auth,
            )
    for i in range(120):
        month = "2026-05" if i % 2 else "2026-06"
        client.post(
            "/api/transactions",
            json={
                "type": "expense", "account_id": acc["id"], "amount": 1_000,
                "currency": "COP", "date": f"{month}-{1 + (i % 27):02d}",
                "category_id": cats[i % 6]["id"], "payee": "seed",
            },
            headers=auth,
        )
    with count_queries(engine) as c:
        r = client.get("/api/reports", params={"month": "2026-06"}, headers=auth)
    assert r.status_code == 200
    assert c.count <= 25, f"monthly_report issued {c.count} queries"
