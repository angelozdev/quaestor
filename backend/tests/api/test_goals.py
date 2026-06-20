from datetime import date

from sqlmodel import Session

from quaestor.services import accounts, goals


def test_goals_progress_empty(client, auth):
    r = client.get("/api/goals/progress", headers=auth)
    assert r.status_code == 200
    assert r.json() == []


def test_goals_progress_shape(client, engine, auth):
    with Session(engine) as s:
        acc = accounts.create_account(s, "Savings", "savings", "COP", balance=0)
        goals.create_goal(
            s, name="Trip", monthly_amount=100_000, savings_account_id=acc.id,
            target_amount=1_200_000, deadline=date(2026, 12, 31),
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
