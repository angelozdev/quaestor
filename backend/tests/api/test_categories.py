def test_categories_requires_auth(client):
    assert client.get("/api/categories").status_code == 401


def test_categories_crud(client, auth):
    g = client.post("/api/category-groups", headers=auth, json={"name": "Essentials"})
    gid = g.json()["id"]

    created = client.post(
        "/api/categories",
        headers=auth,
        json={"name": "Groceries", "group_id": gid, "is_income": False},
    )
    assert created.status_code == 201
    cid = created.json()["id"]
    assert created.json()["group_id"] == gid

    got = client.get(f"/api/categories/{cid}", headers=auth)
    assert got.status_code == 200 and got.json()["name"] == "Groceries"

    patched = client.patch(f"/api/categories/{cid}", headers=auth, json={"name": "Food", "exclude_from_budget": True})
    assert patched.status_code == 200
    assert patched.json()["name"] == "Food" and patched.json()["exclude_from_budget"] is True

    assert len(client.get("/api/categories", headers=auth).json()) == 1
    assert client.delete(f"/api/categories/{cid}", headers=auth).status_code == 204
    assert client.get("/api/categories", headers=auth).json() == []


def test_create_category_bad_group_is_422(client, auth):
    resp = client.post("/api/categories", headers=auth, json={"name": "X", "group_id": 9999})
    assert resp.status_code == 422 and resp.json()["error"] == "ValidationError"


def test_restore_category_endpoint(client, engine, auth):
    from quaestor.services import categories
    from sqlmodel import Session

    with Session(engine) as s:
        cat = categories.create_category(s, name="Food")
        categories.archive_category(s, cat.id)
        cat_id = cat.id
    r = client.post(f"/api/categories/{cat_id}/restore", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["archived"] is False


def test_list_categories_filters_by_direction(client, auth):
    client.post("/api/categories", headers=auth, json={"name": "Restaurantes"})
    client.post("/api/categories", headers=auth, json={"name": "Salario", "is_income": True})

    offered_for_income = client.get("/api/categories?is_income=true", headers=auth).json()
    offered_for_expense = client.get("/api/categories?is_income=false", headers=auth).json()

    assert [c["name"] for c in offered_for_income] == ["Salario"]
    assert [c["name"] for c in offered_for_expense] == ["Restaurantes"]
    assert len(client.get("/api/categories", headers=auth).json()) == 2


def test_list_categories_direction_filter_excludes_archived_like_the_plain_list(client, engine, auth):
    from quaestor.services import categories
    from sqlmodel import Session

    with Session(engine) as s:
        categories.archive_category(s, categories.create_category(s, name="Suscripciones").id)

    assert client.get("/api/categories?is_income=false", headers=auth).json() == []


def test_creating_a_category_whose_name_is_taken_is_422(client, auth):
    client.post("/api/categories", headers=auth, json={"name": "Vuelos"})

    resp = client.post("/api/categories", headers=auth, json={"name": "vuelos"})

    assert resp.status_code == 422
    assert "already exists" in resp.json()["detail"]
    assert len(client.get("/api/categories", headers=auth).json()) == 1


def test_a_category_can_be_created_marked_as_one_where_spending_is_saving(client, auth):
    """AC-41 over the wire: the field existed everywhere but here, so it was dropped."""
    created = client.post("/api/categories", headers=auth, json={"name": "Inversion", "counts_as_saving": True})

    assert created.status_code == 201
    assert created.json()["counts_as_saving"] is True
    assert client.get("/api/categories", headers=auth).json()[0]["counts_as_saving"] is True


def test_a_category_is_not_saving_unless_it_says_so(client, auth):
    created = client.post("/api/categories", headers=auth, json={"name": "Restaurantes"})

    assert created.json()["counts_as_saving"] is False


def test_the_mark_can_be_put_on_a_category_that_already_exists(client, auth):
    category_id = client.post("/api/categories", headers=auth, json={"name": "Inversion"}).json()["id"]

    changed = client.patch(f"/api/categories/{category_id}", headers=auth, json={"counts_as_saving": True})

    assert changed.json()["counts_as_saving"] is True
    assert (
        client.patch(f"/api/categories/{category_id}", headers=auth, json={"counts_as_saving": False}).json()[
            "counts_as_saving"
        ]
        is False
    )
