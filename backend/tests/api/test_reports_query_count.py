"""The monthly report must be bounded regardless of transaction count.

The report folds the month once over `MonthAggregate` (ADR-0028) and reads
the money available from that same fold, so its cost is fixed by the read
path rather than by how much the month holds: 120 movements across two
months cost what 12 would.

25 is a ceiling with room in it, not a measurement — the assertion is `<=`.
Feature 003 budgeted +2 statements on the month load (plan D4); a change
that pushes the report past this ceiling has broken that budget and wants
explaining, not a bigger number.
"""

from tests.support.query_counter import count_queries


def test_report_query_count_is_bounded(client, auth, engine, expense_category):
    assert client.post("/api/fx", json={"usd_cop": "4000"}, headers=auth).status_code == 201
    acc = client.post(
        "/api/accounts",
        json={"name": "Bank", "type": "debit", "currency": "COP"},
        headers=auth,
    ).json()
    cats = [client.post("/api/categories", json={"name": f"Cat {i}"}, headers=auth).json() for i in range(6)]
    for i in range(120):
        month = "2026-05" if i % 2 else "2026-06"
        client.post(
            "/api/transactions",
            json={
                "type": "expense",
                "category_id": cats[i % 6]["id"],
                "account_id": acc["id"],
                "amount": 1_000,
                "currency": "COP",
                "date": f"{month}-{1 + (i % 27):02d}",
                "payee": "seed",
            },
            headers=auth,
        )
    with count_queries(engine) as c:
        r = client.get("/api/reports", params={"month": "2026-06"}, headers=auth)
    assert r.status_code == 200
    assert c.count <= 25, f"monthly_report issued {c.count} queries"
