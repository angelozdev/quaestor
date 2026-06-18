def test_categories_requires_auth(client):
    assert client.get("/api/categories").status_code == 401


def test_categories_crud(client, auth):
    g = client.post("/api/category-groups", headers=auth, json={"name": "Esenciales"})
    gid = g.json()["id"]

    created = client.post(
        "/api/categories",
        headers=auth,
        json={"name": "Mercado", "group_id": gid, "is_income": False},
    )
    assert created.status_code == 201
    cid = created.json()["id"]
    assert created.json()["group_id"] == gid

    got = client.get(f"/api/categories/{cid}", headers=auth)
    assert got.status_code == 200 and got.json()["name"] == "Mercado"

    patched = client.patch(
        f"/api/categories/{cid}", headers=auth, json={"name": "Comida", "exclude_from_budget": True}
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Comida" and patched.json()["exclude_from_budget"] is True

    assert len(client.get("/api/categories", headers=auth).json()) == 1
    assert client.delete(f"/api/categories/{cid}", headers=auth).status_code == 204
    assert client.get("/api/categories", headers=auth).json() == []


def test_create_category_bad_group_is_422(client, auth):
    resp = client.post(
        "/api/categories", headers=auth, json={"name": "X", "group_id": 9999}
    )
    assert resp.status_code == 422 and resp.json()["error"] == "ValidationError"
