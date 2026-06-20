def test_login_cookie_authorizes_same_endpoints_as_bearer(client):
    # Without auth: rejected.
    assert client.get("/api/accounts").status_code == 401

    # Log in with the password -> session cookie persists on the client.
    assert client.post("/api/auth/login", json={"password": "test-password"}).status_code == 200
    assert client.get("/api/auth/me").json() == {"authenticated": True}

    # Cookie alone (no Authorization header) authorizes a full create+read+update+archive.
    acc = client.post(
        "/api/accounts", json={"name": "Cash", "type": "cash", "currency": "COP"}
    )
    assert acc.status_code == 201
    acc_id = acc.json()["id"]
    assert client.get(f"/api/accounts/{acc_id}").status_code == 200
    assert client.patch(f"/api/accounts/{acc_id}", json={"name": "Wallet"}).status_code == 200
    assert client.delete(f"/api/accounts/{acc_id}").status_code == 204

    # After logout the same endpoint is rejected again.
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/accounts").status_code == 401


def test_bearer_full_core_crud(client, auth):
    # accounts
    cash = client.post(
        "/api/accounts", headers=auth, json={"name": "Cash", "type": "cash", "currency": "COP"}
    ).json()
    bank = client.post(
        "/api/accounts", headers=auth, json={"name": "Bank", "type": "debit", "currency": "COP"}
    ).json()

    # category group + category
    group = client.post("/api/category-groups", headers=auth, json={"name": "Essentials"}).json()
    cat = client.post(
        "/api/categories", headers=auth, json={"name": "Food", "group_id": group["id"]}
    ).json()

    # tag
    tag = client.post("/api/tags", headers=auth, json={"name": "groceries"}).json()

    # fx override then expense in COP
    assert client.post(
        "/api/fx", headers=auth, json={"date": "2026-06-17", "usd_cop": "4000"}
    ).status_code == 201

    expense = client.post(
        "/api/transactions",
        headers=auth,
        json={"type": "expense", "account_id": cash["id"], "amount": 1500,
              "currency": "COP", "date": "2026-06-17", "payee": "Store",
              "category_id": cat["id"]},
    ).json()
    assert client.get(f"/api/accounts/{cash['id']}", headers=auth).json()["balance"] == -1500

    # transfer
    client.post(
        "/api/transactions/transfer",
        headers=auth,
        json={"from_account_id": bank["id"], "to_account_id": cash["id"],
              "amount": 1000, "currency": "COP", "date": "2026-06-17"},
    )
    assert client.get(f"/api/accounts/{bank['id']}", headers=auth).json()["balance"] == -1000

    # settings
    assert client.patch(
        "/api/settings", headers=auth, json={"default_source_account_id": bank["id"]}
    ).status_code == 200

    # update + delete the expense, balance returns to the transfer-only state
    client.patch(f"/api/transactions/{expense['id']}", headers=auth, json={"payee": "Super"})
    client.delete(f"/api/transactions/{expense['id']}", headers=auth)
    assert client.get(f"/api/accounts/{cash['id']}", headers=auth).json()["balance"] == 1000

    # tag cleanup hard-deletes
    assert client.delete(f"/api/tags/{tag['id']}", headers=auth).status_code == 204
