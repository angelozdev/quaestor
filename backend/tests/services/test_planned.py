from datetime import date

import pytest

from quaestor.domain.errors import NotFound, ValidationError
from quaestor.domain.models import AccountType, TxStatus, TxType
from quaestor.services import accounts, planned, transactions


def _acc(session, currency="COP", balance=0):
    return accounts.create_account(session, "Bank", AccountType.debit, currency, balance=balance)


def test_plan_payment_creates_planned_without_balance(session):
    acc = _acc(session, balance=500_000)
    tx = planned.plan_payment(
        session, payee="Friend", amount=80_000, currency="COP",
        due_date=date(2026, 6, 20), account_id=acc.id,
    )
    assert tx.status == TxStatus.planned and tx.type == TxType.expense
    assert tx.recurring_id is None
    assert accounts.get_account(session, acc.id).balance == 500_000  # untouched


def test_plan_payment_rejects_bad_amount(session):
    acc = _acc(session)
    with pytest.raises(ValidationError):
        planned.plan_payment(
            session, payee="x", amount=0, currency="COP",
            due_date=date(2026, 6, 20), account_id=acc.id,
        )


def test_plan_payment_unknown_account(session):
    with pytest.raises(NotFound):
        planned.plan_payment(
            session, payee="x", amount=1000, currency="COP",
            due_date=date(2026, 6, 20), account_id=999,
        )


def test_to_pay_window_orders_and_totals(session):
    acc = _acc(session)
    planned.plan_payment(session, payee="A", amount=10_000, currency="COP",
                         due_date=date(2026, 6, 10), account_id=acc.id)
    planned.plan_payment(session, payee="B", amount=20_000, currency="COP",
                         due_date=date(2026, 6, 5), account_id=acc.id)
    planned.plan_payment(session, payee="C", amount=99_000, currency="COP",
                         due_date=date(2026, 7, 1), account_id=acc.id)  # outside window
    result = planned.to_pay(session, date(2026, 6, 1), date(2026, 6, 30))
    assert [t.payee for t in result["items"]] == ["B", "A"]  # ordered by date
    assert result["total_base"] == 30_000


def test_to_pay_excludes_posted(session):
    acc = _acc(session, balance=1_000_000)
    transactions.record_expense(session, acc.id, 5_000, "COP", date(2026, 6, 10), "Posted")
    planned.plan_payment(session, payee="Planned", amount=7_000, currency="COP",
                         due_date=date(2026, 6, 11), account_id=acc.id)
    result = planned.to_pay(session, date(2026, 6, 1), date(2026, 6, 30))
    assert [t.payee for t in result["items"]] == ["Planned"]
    assert result["total_base"] == 7_000


def test_to_pay_inverted_window_raises(session):
    with pytest.raises(ValidationError):
        planned.to_pay(session, date(2026, 6, 30), date(2026, 6, 1))
