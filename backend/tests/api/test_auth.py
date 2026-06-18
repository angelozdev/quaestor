def test_me_unauthenticated_is_false(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json() == {"authenticated": False}


def test_me_with_bearer_is_true(client, auth):
    resp = client.get("/api/auth/me", headers=auth)
    assert resp.status_code == 200
    assert resp.json() == {"authenticated": True}


def test_bad_bearer_is_unauthorized_on_me(client):
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 200
    assert resp.json() == {"authenticated": False}


def test_login_wrong_password_is_401(client):
    resp = client.post("/api/auth/login", json={"password": "nope"})
    assert resp.status_code == 401
    assert resp.json()["error"] == "Unauthorized"


def test_login_then_cookie_authenticates(client):
    login = client.post("/api/auth/login", json={"password": "test-password"})
    assert login.status_code == 200
    assert login.json() == {"ok": True}
    # The TestClient persists the session cookie across calls.
    me = client.get("/api/auth/me")
    assert me.json() == {"authenticated": True}


def test_logout_clears_session(client):
    client.post("/api/auth/login", json={"password": "test-password"})
    out = client.post("/api/auth/logout")
    assert out.status_code == 200
    assert out.json() == {"ok": True}
    assert client.get("/api/auth/me").json() == {"authenticated": False}
