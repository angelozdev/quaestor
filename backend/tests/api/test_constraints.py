"""Backend tests asserting Pydantic v2 gt/le constraints reject malformed input.

Constraints under test (see src/quaestor/api/schemas.py):
  - RecurringCreate.interval_count: gt=0, le=1000
  - RecurringUpdate.amount: gt=0
  - RecurringUpdate.interval_count: gt=0, le=1000
  - PlanPaymentIn.amount: gt=0
  - GoalCreate.monthly_amount: gt=0
  - GoalCreate.target_amount: gt=0
  - GoalUpdate.monthly_amount: gt=0
  - GoalContributeIn.amount: gt=0
  - FxIn.usd_cop: gt=0, le=100000
"""
from quaestor.domain.models import AccountType
from quaestor.services import accounts
from sqlmodel import Session


def _seed_account(engine, name="Bank", type_="debit", balance=1_000_000):
    with Session(engine) as s:
        acc = accounts.create_account(s, name, type_, "COP", balance=balance)
        return acc.id


def _seed_savings_account(engine, name="Savings"):
    with Session(engine) as s:
        acc = accounts.create_account(s, name, AccountType.savings, "COP", balance=0)
        return acc.id


# --- RecurringCreate.interval_count ---

def test_recurring_create_interval_count_zero_is_422(client, engine, auth):
    """gt=0 boundary: interval_count=0 must be rejected."""
    acc_id = _seed_account(engine)
    body = {
        "name": "Rent", "payee": "LL", "type": "expense", "mode": "auto",
        "amount": 2_000_000, "account_id": acc_id, "interval_unit": "month",
        "interval_count": 0, "start_date": "2026-01-01",
    }
    r = client.post("/api/recurring", json=body, headers=auth)
    assert r.status_code == 422, r.text
    data = r.json()
    assert data["error"] == "ValidationError"
    assert "fields" in data, r.text
    assert "interval_count" in data["fields"], r.text


def test_recurring_create_interval_count_over_1000_is_422(client, engine, auth):
    """le=1000 boundary: interval_count=1001 must be rejected."""
    acc_id = _seed_account(engine)
    body = {
        "name": "Rent", "payee": "LL", "type": "expense", "mode": "auto",
        "amount": 2_000_000, "account_id": acc_id, "interval_unit": "month",
        "interval_count": 1001, "start_date": "2026-01-01",
    }
    r = client.post("/api/recurring", json=body, headers=auth)
    assert r.status_code == 422, r.text


def test_recurring_create_interval_count_negative_is_422(client, engine, auth):
    """gt=0 boundary: negative interval_count must be rejected."""
    acc_id = _seed_account(engine)
    body = {
        "name": "Rent", "payee": "LL", "type": "expense", "mode": "auto",
        "amount": 2_000_000, "account_id": acc_id, "interval_unit": "month",
        "interval_count": -1, "start_date": "2026-01-01",
    }
    r = client.post("/api/recurring", json=body, headers=auth)
    assert r.status_code == 422, r.text


# --- RecurringUpdate.amount & RecurringUpdate.interval_count ---

def _seed_recurring(client, engine, auth):
    acc_id = _seed_account(engine)
    body = {
        "name": "Rent", "payee": "LL", "type": "expense", "mode": "auto",
        "amount": 2_000_000, "account_id": acc_id, "interval_unit": "month",
        "interval_count": 1, "start_date": "2026-01-01",
    }
    return client.post("/api/recurring", json=body, headers=auth).json()["id"]


def test_recurring_update_amount_zero_is_422(client, engine, auth):
    """gt=0 boundary: RecurringUpdate.amount=0 must be rejected."""
    rid = _seed_recurring(client, engine, auth)
    r = client.patch(f"/api/recurring/{rid}", json={"amount": 0}, headers=auth)
    assert r.status_code == 422, r.text


def test_recurring_update_interval_count_over_1000_is_422(client, engine, auth):
    """le=1000 boundary: RecurringUpdate.interval_count=1001 must be rejected."""
    rid = _seed_recurring(client, engine, auth)
    r = client.patch(f"/api/recurring/{rid}", json={"interval_count": 1001}, headers=auth)
    assert r.status_code == 422, r.text


# --- PlanPaymentIn.amount ---

def test_plan_payment_amount_zero_is_422(client, engine, auth):
    """gt=0 boundary: PlanPaymentIn.amount=0 must be rejected."""
    acc_id = _seed_account(engine)
    body = {
        "payee": "Friend", "amount": 0, "due_date": "2026-06-20", "account_id": acc_id,
    }
    r = client.post("/api/planned", json=body, headers=auth)
    assert r.status_code == 422, r.text


def test_plan_payment_amount_negative_is_422(client, engine, auth):
    """gt=0 boundary: negative plan-payment amount must be rejected."""
    acc_id = _seed_account(engine)
    body = {
        "payee": "Friend", "amount": -50_000, "due_date": "2026-06-20", "account_id": acc_id,
    }
    r = client.post("/api/planned", json=body, headers=auth)
    assert r.status_code == 422, r.text


# --- GoalCreate ---

def test_goal_create_monthly_amount_zero_is_422(client, engine, auth):
    """gt=0 boundary: GoalCreate.monthly_amount=0 must be rejected."""
    sid = _seed_savings_account(engine)
    body = {"name": "Trip", "monthly_amount": 0, "savings_account_id": sid}
    r = client.post("/api/goals", json=body, headers=auth)
    assert r.status_code == 422, r.text


def test_goal_create_target_amount_negative_is_422(client, engine, auth):
    """Optional gt=0: GoalCreate.target_amount=-1 must be rejected."""
    sid = _seed_savings_account(engine)
    body = {
        "name": "Trip", "monthly_amount": 100_000, "savings_account_id": sid,
        "target_amount": -1,
    }
    r = client.post("/api/goals", json=body, headers=auth)
    assert r.status_code == 422, r.text


# --- GoalUpdate ---

def _seed_goal(client, engine, auth):
    sid = _seed_savings_account(engine)
    return client.post(
        "/api/goals",
        json={"name": "A", "monthly_amount": 100_000, "savings_account_id": sid},
        headers=auth,
    ).json()["id"]


def test_goal_update_monthly_amount_zero_is_422(client, engine, auth):
    """gt=0 boundary: GoalUpdate.monthly_amount=0 must be rejected."""
    gid = _seed_goal(client, engine, auth)
    r = client.patch(f"/api/goals/{gid}", json={"monthly_amount": 0}, headers=auth)
    assert r.status_code == 422, r.text


# --- GoalContributeIn ---

def test_goal_contribute_amount_zero_is_422(client, engine, auth):
    """gt=0 boundary: GoalContributeIn.amount=0 must be rejected.

    The contribute endpoint also requires a configured default source account;
    pre-seed it so the request reaches schema validation (not service-level 422).
    """
    sid = _seed_savings_account(engine)
    with Session(engine) as s:
        src = accounts.create_account(s, "Source", AccountType.savings, "COP", balance=1_000_000)
        from quaestor.services import settings
        settings.update_settings(s, default_source_account_id=src.id)
    gid = client.post(
        "/api/goals",
        json={"name": "A", "monthly_amount": 100_000, "savings_account_id": sid},
        headers=auth,
    ).json()["id"]
    r = client.post(
        f"/api/goals/{gid}/contribute",
        json={"amount": 0, "date": "2026-06-01"},
        headers=auth,
    )
    assert r.status_code == 422, r.text


# --- FxIn.usd_cop ---

def test_fx_usd_cop_zero_is_422(client, auth):
    """gt=0 boundary: FxIn.usd_cop=0 must be rejected."""
    r = client.post("/api/fx", json={"date": "2026-06-17", "usd_cop": "0"}, headers=auth)
    assert r.status_code == 422, r.text


def test_fx_usd_cop_over_100000_is_422(client, auth):
    """le=100000 boundary: FxIn.usd_cop=200000 must be rejected."""
    r = client.post(
        "/api/fx", json={"date": "2026-06-17", "usd_cop": "200000"}, headers=auth
    )
    assert r.status_code == 422, r.text


def test_fx_usd_cop_negative_is_422(client, auth):
    """gt=0 boundary: negative FxIn.usd_cop must be rejected."""
    r = client.post(
        "/api/fx", json={"date": "2026-06-17", "usd_cop": "-1"}, headers=auth
    )
    assert r.status_code == 422, r.text
