def test_safe_to_spend_endpoint(client, auth):
    r = client.get("/api/budgets/safe-to-spend", params={"month": "2026-06"}, headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["year_month"] == "2026-06"
    assert {"income_forecast", "committed", "assigned_envelopes", "free", "committed_breakdown"} <= body.keys()
    assert isinstance(body["free"], int)
    assert body["committed_breakdown"] == []


def test_safe_to_spend_malformed_month_is_422(client, auth):
    r = client.get("/api/budgets/safe-to-spend", params={"month": "junio"}, headers=auth)
    assert r.status_code == 422


def test_safe_to_spend_requires_auth(client):
    r = client.get("/api/budgets/safe-to-spend", params={"month": "2026-06"})
    assert r.status_code == 401
