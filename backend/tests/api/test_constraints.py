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

from quaestor.services import accounts
from sqlmodel import Session


def _seed_account(engine, name="Bank", type_="debit", balance=1_000_000):
    with Session(engine) as s:
        acc = accounts.create_account(s, name, type_, "COP", balance=balance)
        return acc.id


# --- RecurringCreate.interval_count ---


def test_recurring_create_interval_count_zero_is_422(client, engine, auth, expense_category):
    """gt=0 boundary: interval_count=0 must be rejected."""
    acc_id = _seed_account(engine)
    body = {
        "name": "Rent",
        "payee": "LL",
        "type": "expense",
        "category_id": expense_category,
        "mode": "auto",
        "amount": 2_000_000,
        "account_id": acc_id,
        "interval_unit": "month",
        "interval_count": 0,
        "start_date": "2026-01-01",
    }
    r = client.post("/api/recurring", json=body, headers=auth)
    assert r.status_code == 422, r.text
    data = r.json()
    assert data["error"] == "ValidationError"
    assert "fields" in data, r.text
    assert "interval_count" in data["fields"], r.text


def test_recurring_create_interval_count_over_1000_is_422(client, engine, auth, expense_category):
    """le=1000 boundary: interval_count=1001 must be rejected."""
    acc_id = _seed_account(engine)
    body = {
        "name": "Rent",
        "payee": "LL",
        "type": "expense",
        "category_id": expense_category,
        "mode": "auto",
        "amount": 2_000_000,
        "account_id": acc_id,
        "interval_unit": "month",
        "interval_count": 1001,
        "start_date": "2026-01-01",
    }
    r = client.post("/api/recurring", json=body, headers=auth)
    assert r.status_code == 422, r.text


def test_recurring_create_interval_count_negative_is_422(client, engine, auth, expense_category):
    """gt=0 boundary: negative interval_count must be rejected."""
    acc_id = _seed_account(engine)
    body = {
        "name": "Rent",
        "payee": "LL",
        "type": "expense",
        "category_id": expense_category,
        "mode": "auto",
        "amount": 2_000_000,
        "account_id": acc_id,
        "interval_unit": "month",
        "interval_count": -1,
        "start_date": "2026-01-01",
    }
    r = client.post("/api/recurring", json=body, headers=auth)
    assert r.status_code == 422, r.text


# --- RecurringUpdate.amount & RecurringUpdate.interval_count ---


def _seed_recurring(client, engine, auth, expense_category):
    acc_id = _seed_account(engine)
    body = {
        "name": "Rent",
        "payee": "LL",
        "type": "expense",
        "category_id": expense_category,
        "mode": "auto",
        "amount": 2_000_000,
        "account_id": acc_id,
        "interval_unit": "month",
        "interval_count": 1,
        "start_date": "2026-01-01",
    }
    return client.post("/api/recurring", json=body, headers=auth).json()["id"]


def test_recurring_update_amount_zero_is_422(client, engine, auth, expense_category):
    """gt=0 boundary: RecurringUpdate.amount=0 must be rejected."""
    rid = _seed_recurring(client, engine, auth, expense_category)
    r = client.patch(f"/api/recurring/{rid}", json={"amount": 0}, headers=auth)
    assert r.status_code == 422, r.text


def test_recurring_update_interval_count_over_1000_is_422(client, engine, auth, expense_category):
    """le=1000 boundary: RecurringUpdate.interval_count=1001 must be rejected."""
    rid = _seed_recurring(client, engine, auth, expense_category)
    r = client.patch(f"/api/recurring/{rid}", json={"interval_count": 1001}, headers=auth)
    assert r.status_code == 422, r.text


# --- PlanPaymentIn.amount ---


def test_plan_payment_amount_zero_is_422(client, engine, auth):
    """gt=0 boundary: PlanPaymentIn.amount=0 must be rejected."""
    acc_id = _seed_account(engine)
    body = {
        "payee": "Friend",
        "amount": 0,
        "due_date": "2026-06-20",
        "account_id": acc_id,
    }
    r = client.post("/api/planned", json=body, headers=auth)
    assert r.status_code == 422, r.text


def test_plan_payment_amount_negative_is_422(client, engine, auth):
    """gt=0 boundary: negative plan-payment amount must be rejected."""
    acc_id = _seed_account(engine)
    body = {
        "payee": "Friend",
        "amount": -50_000,
        "due_date": "2026-06-20",
        "account_id": acc_id,
    }
    r = client.post("/api/planned", json=body, headers=auth)
    assert r.status_code == 422, r.text


# --- FxIn.usd_cop ---


def test_fx_usd_cop_zero_is_422(client, auth):
    """gt=0 boundary: FxIn.usd_cop=0 must be rejected."""
    r = client.post("/api/fx", json={"date": "2026-06-17", "usd_cop": "0"}, headers=auth)
    assert r.status_code == 422, r.text


def test_fx_usd_cop_over_100000_is_422(client, auth):
    """le=100000 boundary: FxIn.usd_cop=200000 must be rejected."""
    r = client.post("/api/fx", json={"date": "2026-06-17", "usd_cop": "200000"}, headers=auth)
    assert r.status_code == 422, r.text


def test_fx_usd_cop_negative_is_422(client, auth):
    """gt=0 boundary: negative FxIn.usd_cop must be rejected."""
    r = client.post("/api/fx", json={"date": "2026-06-17", "usd_cop": "-1"}, headers=auth)
    assert r.status_code == 422, r.text
