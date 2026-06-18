def test_app_serves_openapi(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"] == "Quaestor API"


def test_unknown_path_is_404_not_crash(client):
    assert client.get("/api/does-not-exist").status_code == 404
