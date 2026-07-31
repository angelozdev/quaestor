def test_fx_requires_auth(client):
    assert client.get("/api/fx").status_code == 401


def test_get_fx_without_trm_is_409(client, auth):
    resp = client.get("/api/fx", headers=auth)
    assert resp.status_code == 409 and resp.json()["error"] == "MissingRate"


def test_set_then_get_trm(client, auth):
    created = client.post("/api/fx", headers=auth, json={"usd_cop": "4000.00"})
    assert created.status_code == 201
    assert float(created.json()["usd_cop"]) == 4000.0
    assert "date" not in created.json()

    got = client.get("/api/fx", headers=auth)
    assert got.status_code == 200
    assert float(got.json()["usd_cop"]) == 4000.0


def test_set_trm_overwrites_last_write_wins(client, auth):
    assert client.post("/api/fx", headers=auth, json={"usd_cop": "4000.00"}).status_code == 201
    assert client.post("/api/fx", headers=auth, json={"usd_cop": "4123.45"}).status_code == 201
    assert float(client.get("/api/fx", headers=auth).json()["usd_cop"]) == 4123.45


def test_set_trm_zero_is_422(client, auth):
    resp = client.post("/api/fx", headers=auth, json={"usd_cop": "0"})
    assert resp.status_code == 422 and resp.json()["error"] == "ValidationError"


def test_set_trm_negative_is_422(client, auth):
    resp = client.post("/api/fx", headers=auth, json={"usd_cop": "-4000"})
    assert resp.status_code == 422 and resp.json()["error"] == "ValidationError"
