from tests.support.fx import set_trm as _set_trm


def test_reports_endpoint(client, auth, expense_category):
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
            "amount": 50_000,
            "currency": "COP",
            "date": "2026-06-10",
            "payee": "Groceries",
        },
        headers=auth,
    )
    r = client.get("/api/reports", params={"month": "2026-06"}, headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["month"] == "2026-06"
    assert body["expense"] == 50_000
    assert "available" in body and "markdown" in body
    assert body["available"]["year_month"] == "2026-06"
    assert body["drift_mom"] is None


def test_reports_without_trm_is_409(client, auth):
    r = client.get("/api/reports", params={"month": "2026-06"}, headers=auth)
    assert r.status_code == 409 and r.json()["error"] == "MissingRate"


def test_reports_malformed_month_is_422(client, auth):
    r = client.get("/api/reports", params={"month": "2026-6"}, headers=auth)
    assert r.status_code == 422


def test_reports_requires_auth(client):
    assert client.get("/api/reports", params={"month": "2026-06"}).status_code == 401
