def test_category_groups_requires_auth(client):
    assert client.get("/api/category-groups").status_code == 401


def test_category_groups_crud(client, auth):
    created = client.post(
        "/api/category-groups", headers=auth, json={"name": "Ocio", "sort_order": 1}
    )
    assert created.status_code == 201
    gid = created.json()["id"]

    patched = client.patch(
        f"/api/category-groups/{gid}", headers=auth, json={"name": "Entretenimiento"}
    )
    assert patched.status_code == 200 and patched.json()["name"] == "Entretenimiento"

    assert len(client.get("/api/category-groups", headers=auth).json()) == 1

    assert client.delete(f"/api/category-groups/{gid}", headers=auth).status_code == 204
    assert client.get("/api/category-groups", headers=auth).json() == []
    assert len(client.get("/api/category-groups?archived=true", headers=auth).json()) == 1


def test_restore_group_endpoint(client, engine, auth):
    from quaestor.services import categories
    from sqlmodel import Session
    with Session(engine) as s:
        g = categories.create_group(s, name="Bills")
        categories.archive_group(s, g.id)
        gid = g.id
    r = client.post(f"/api/category-groups/{gid}/restore", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["archived"] is False
