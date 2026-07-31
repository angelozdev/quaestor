"""Shared FX test helper: set the scalar TRM through the REST surface."""


def set_trm(client, auth, rate="4000"):
    """POST /api/fx and assert the 201, so callers start from a set TRM."""
    resp = client.post("/api/fx", headers=auth, json={"usd_cop": rate})
    assert resp.status_code == 201, resp.text
