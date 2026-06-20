def test_tags_requires_auth(client):
    assert client.get("/api/tags").status_code == 401


def test_tags_crud(client, auth):
    created = client.post("/api/tags", headers=auth, json={"name": "trip"})
    assert created.status_code == 201
    tid = created.json()["id"]

    patched = client.patch(f"/api/tags/{tid}", headers=auth, json={"name": "vacation"})
    assert patched.status_code == 200 and patched.json()["name"] == "vacation"

    assert len(client.get("/api/tags", headers=auth).json()) == 1
    assert client.delete(f"/api/tags/{tid}", headers=auth).status_code == 204
    assert client.get("/api/tags", headers=auth).json() == []


def test_delete_missing_tag_is_404(client, auth):
    resp = client.delete("/api/tags/999", headers=auth)
    assert resp.status_code == 404 and resp.json()["error"] == "NotFound"
