def test_settings_requires_auth(client):
    assert client.get("/api/settings").status_code == 401


def test_get_and_patch_settings(client, auth):
    got = client.get("/api/settings", headers=auth)
    assert got.status_code == 200 and got.json()["base_currency"] == "COP"

    acc = client.post(
        "/api/accounts",
        headers=auth,
        json={"name": "Savings", "type": "savings", "currency": "COP"},
    ).json()

    patched = client.patch("/api/settings", headers=auth, json={"default_source_account_id": acc["id"]})
    assert patched.status_code == 200
    assert patched.json()["default_source_account_id"] == acc["id"]


def test_patch_settings_bad_account_is_422(client, auth):
    resp = client.patch("/api/settings", headers=auth, json={"default_source_account_id": 9999})
    assert resp.status_code == 422 and resp.json()["error"] == "ValidationError"
