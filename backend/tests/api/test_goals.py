from datetime import date

from quaestor.services import accounts, goals
from sqlmodel import Session


def test_goals_progress_empty(client, auth):
    r = client.get("/api/goals/progress", headers=auth)
    assert r.status_code == 200
    assert r.json() == []


def test_goals_progress_shape(client, engine, auth):
    with Session(engine) as s:
        acc = accounts.create_account(s, "Savings", "savings", "COP", balance=0)
        goals.create_goal(
            s,
            name="Trip",
            monthly_amount=100_000,
            savings_account_id=acc.id,
            target_amount=1_200_000,
            deadline=date(2026, 12, 31),
        )
    r = client.get("/api/goals/progress", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body) == 1
    g = body[0]
    assert g["name"] == "Trip"
    assert g["type"] == "defined"
    assert g["saved"] == 0
    assert g["target_amount"] == 1_200_000


def test_goals_progress_requires_auth(client):
    assert client.get("/api/goals/progress").status_code == 401


def _seed_savings(engine):
    from quaestor.domain.models import AccountType
    from quaestor.services import accounts
    from sqlmodel import Session

    with Session(engine) as s:
        return accounts.create_account(s, "Savings", AccountType.savings, "COP", balance=0).id


def test_create_list_goal(client, engine, auth):
    sid = _seed_savings(engine)
    body = {"name": "Trip", "monthly_amount": 200_000, "savings_account_id": sid}
    r = client.post("/api/goals", json=body, headers=auth)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "active"
    assert any(g["name"] == "Trip" for g in client.get("/api/goals", headers=auth).json())


def test_patch_goal(client, engine, auth):
    sid = _seed_savings(engine)
    gid = client.post(
        "/api/goals", json={"name": "A", "monthly_amount": 100_000, "savings_account_id": sid}, headers=auth
    ).json()["id"]
    r = client.patch(f"/api/goals/{gid}", json={"monthly_amount": 150_000}, headers=auth)
    assert r.status_code == 200 and r.json()["monthly_amount"] == 150_000


def test_delete_then_restore_goal(client, engine, auth):
    sid = _seed_savings(engine)
    gid = client.post(
        "/api/goals", json={"name": "A", "monthly_amount": 100_000, "savings_account_id": sid}, headers=auth
    ).json()["id"]
    assert client.delete(f"/api/goals/{gid}", headers=auth).status_code == 204
    assert client.post(f"/api/goals/{gid}/restore", headers=auth).json()["status"] == "active"


def test_contribute_requires_default_source_is_422(client, engine, auth):
    sid = _seed_savings(engine)
    gid = client.post(
        "/api/goals", json={"name": "A", "monthly_amount": 100_000, "savings_account_id": sid}, headers=auth
    ).json()["id"]
    # no default source account configured -> 422
    r = client.post(f"/api/goals/{gid}/contribute", json={"amount": 50_000, "date": "2026-06-01"}, headers=auth)
    assert r.status_code == 422


def test_contribute_succeeds_with_default_source(client, engine, auth):
    from quaestor.domain.models import AccountType
    from quaestor.services import accounts, settings
    from sqlmodel import Session

    with Session(engine) as s:
        src = accounts.create_account(s, "Checking", AccountType.savings, "COP", balance=1_000_000)
        sav = accounts.create_account(s, "Savings", AccountType.savings, "COP", balance=0)
        settings.update_settings(s, default_source_account_id=src.id)
        sav_id = sav.id
    gid = client.post(
        "/api/goals", json={"name": "A", "monthly_amount": 100_000, "savings_account_id": sav_id}, headers=auth
    ).json()["id"]
    r = client.post(f"/api/goals/{gid}/contribute", json={"amount": 50_000, "date": "2026-06-01"}, headers=auth)
    assert r.status_code == 201, r.text
    assert r.json()["goal_id"] == gid
