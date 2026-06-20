def test_reports_endpoint(client, auth):
    acc = client.post(
        "/api/accounts",
        json={"name": "Bank", "type": "debit", "currency": "COP"},
        headers=auth,
    ).json()
    client.post(
        "/api/transactions",
        json={
            "type": "expense", "account_id": acc["id"], "amount": 50_000,
            "currency": "COP", "date": "2026-06-10", "payee": "Groceries",
        },
        headers=auth,
    )
    r = client.get("/api/reports", params={"month": "2026-06"}, headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["month"] == "2026-06"
    assert body["expense"] == 50_000
    assert "safe_to_spend" in body and "markdown" in body
    assert body["safe_to_spend"]["year_month"] == "2026-06"
    assert body["drift_mom"] is None  # cold start: no previous month


def test_reports_malformed_month_is_422(client, auth):
    r = client.get("/api/reports", params={"month": "2026-6"}, headers=auth)
    assert r.status_code == 422


def test_reports_requires_auth(client):
    assert client.get("/api/reports", params={"month": "2026-06"}).status_code == 401
