def test_fx_requires_auth(client):
    assert client.get("/api/fx").status_code == 401


def test_get_fx_without_rate_is_409(client, auth):
    resp = client.get("/api/fx", headers=auth, params={"date": "2026-06-17"})
    assert resp.status_code == 409 and resp.json()["error"] == "MissingRate"


def test_set_then_get_fx(client, auth):
    created = client.post(
        "/api/fx", headers=auth, json={"date": "2026-06-17", "usd_cop": "4000.00"}
    )
    assert created.status_code == 201
    assert created.json()["date"] == "2026-06-17"

    got = client.get("/api/fx", headers=auth, params={"date": "2026-06-18"})
    assert got.status_code == 200
    # most recent rate on or before the queried date
    assert float(got.json()["usd_cop"]) == 4000.0


def test_set_fx_non_positive_is_422(client, auth):
    resp = client.post(
        "/api/fx", headers=auth, json={"date": "2026-06-17", "usd_cop": "0"}
    )
    assert resp.status_code == 422 and resp.json()["error"] == "ValidationError"
