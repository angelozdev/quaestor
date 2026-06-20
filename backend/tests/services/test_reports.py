from datetime import date

import pytest

from quaestor.domain.errors import ValidationError
from quaestor.domain.models import AccountType, TxType
from quaestor.domain.rules import month_bounds
from quaestor.services import accounts, categories, reports, transactions


def _acc(session, currency="COP", balance=100_000_000):
    return accounts.create_account(session, f"Acc {currency}", AccountType.debit, currency, balance=balance)


def _cat(session, name="Food", **kw):
    return categories.create_category(session, name=name, **kw)


def test_validate_month_rejects_malformed(session):
    with pytest.raises(ValidationError):
        reports._validate_month("2026-13")
    with pytest.raises(ValidationError):
        reports._validate_month("June")
    reports._validate_month("2026-06")  # no raise


def test_totals_posted_only_excludes_planned_and_transfer(session):
    from quaestor.services import planned
    acc = _acc(session)
    acc2 = _acc(session, currency="COP")
    cat = _cat(session)
    transactions.record_expense(session, acc.id, 30_000, "COP", date(2026, 6, 5), "groceries", category_id=cat.id)
    transactions.record_income(session, acc.id, 80_000, "COP", date(2026, 6, 1), "salary", category_id=cat.id)
    transactions.transfer(session, acc.id, acc2.id, 10_000, "COP", date(2026, 6, 6))  # excluded
    planned.plan_payment(session, payee="rent", amount=50_000, currency="COP",
                         account_id=acc.id, due_date=date(2026, 6, 10), category_id=cat.id)  # planned, excluded
    start, end = month_bounds("2026-06")
    income, expense, net = reports._totals(session, start, end)
    assert income == 80_000
    assert expense == 30_000
    assert net == 50_000


def test_totals_respect_exclude_from_totals(session):
    acc = _acc(session)
    normal = _cat(session, name="Food")
    excluded = _cat(session, name="Reimbursable", exclude_from_totals=True)
    transactions.record_expense(session, acc.id, 30_000, "COP", date(2026, 6, 5), "x", category_id=normal.id)
    transactions.record_expense(session, acc.id, 99_000, "COP", date(2026, 6, 7), "reimb", category_id=excluded.id)
    start, end = month_bounds("2026-06")
    _, expense, _ = reports._totals(session, start, end)
    assert expense == 30_000


def test_usd_share(session):
    acc_cop = _acc(session, currency="COP")
    acc_usd = _acc(session, currency="USD")
    from quaestor.services import fx
    fx.set_fx_rate(session, date(2026, 6, 1), 4000)
    cat = _cat(session)
    transactions.record_expense(session, acc_cop.id, 300_000, "COP", date(2026, 6, 5), "cop", category_id=cat.id)
    # 25 USD * 4000 = 100_000 COP cents to_base
    transactions.record_expense(session, acc_usd.id, 25, "USD", date(2026, 6, 6), "usd", category_id=cat.id)
    start, end = month_bounds("2026-06")
    expenses = reports._posted_for_totals(session, TxType.expense, start, end)
    expense_total = sum(t.to_base for t in expenses)
    assert expense_total == 400_000
    assert reports._usd_share(expenses, expense_total) == pytest.approx(0.25)


def test_usd_share_zero_when_no_expense(session):
    assert reports._usd_share([], 0) == 0.0
