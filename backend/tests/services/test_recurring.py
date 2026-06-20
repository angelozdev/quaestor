from datetime import date

import pytest

from quaestor.domain.errors import NotFound, ValidationError
from quaestor.domain.models import AccountType, IntervalUnit, RecurringMode, TxType
from quaestor.services import accounts, recurring


def _acc(session, currency="COP"):
    return accounts.create_account(session, "Bank", AccountType.debit, currency, balance=0)


def test_create_recurring_defaults_active(session):
    acc = _acc(session)
    item = recurring.create_recurring(
        session, name="Rent", payee="Landlord", type=TxType.expense,
        mode=RecurringMode.auto, amount=2_000_000, currency="COP",
        category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 1, 1),
    )
    assert item.id is not None and item.active is True
    assert item.interval_unit == IntervalUnit.month


def test_create_recurring_rejects_transfer_type(session):
    acc = _acc(session)
    with pytest.raises(ValidationError):
        recurring.create_recurring(
            session, name="X", payee="Y", type=TxType.transfer, mode=RecurringMode.auto,
            amount=1000, currency="COP", category_id=None, account_id=acc.id,
            interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 1, 1),
        )


def test_create_recurring_rejects_bad_interval_count(session):
    acc = _acc(session)
    with pytest.raises(ValidationError):
        recurring.create_recurring(
            session, name="X", payee="Y", type=TxType.expense, mode=RecurringMode.auto,
            amount=1000, currency="COP", category_id=None, account_id=acc.id,
            interval_unit=IntervalUnit.month, interval_count=0, start_date=date(2026, 1, 1),
        )


def test_create_recurring_rejects_non_positive_amount(session):
    acc = _acc(session)
    with pytest.raises(ValidationError):
        recurring.create_recurring(
            session, name="X", payee="Y", type=TxType.expense, mode=RecurringMode.auto,
            amount=0, currency="COP", category_id=None, account_id=acc.id,
            interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 1, 1),
        )


def test_create_recurring_rejects_end_before_start(session):
    acc = _acc(session)
    with pytest.raises(ValidationError):
        recurring.create_recurring(
            session, name="X", payee="Y", type=TxType.expense, mode=RecurringMode.auto,
            amount=1000, currency="COP", category_id=None, account_id=acc.id,
            interval_unit=IntervalUnit.month, interval_count=1,
            start_date=date(2026, 5, 1), end_date=date(2026, 1, 1),
        )


def test_create_recurring_unknown_account(session):
    with pytest.raises(NotFound):
        recurring.create_recurring(
            session, name="X", payee="Y", type=TxType.expense, mode=RecurringMode.auto,
            amount=1000, currency="COP", category_id=None, account_id=999,
            interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 1, 1),
        )


def test_list_recurring_filters_by_active(session):
    acc = _acc(session)
    a = recurring.create_recurring(
        session, name="A", payee="p", type=TxType.expense, mode=RecurringMode.auto,
        amount=1000, currency="COP", category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 1, 1),
    )
    b = recurring.create_recurring(
        session, name="B", payee="p", type=TxType.income, mode=RecurringMode.manual,
        amount=1000, currency="COP", category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.week, interval_count=2, start_date=date(2026, 1, 1),
    )
    b.active = False
    session.add(b)
    session.commit()
    assert {i.id for i in recurring.list_recurring(session)} == {a.id, b.id}
    assert {i.id for i in recurring.list_recurring(session, active=True)} == {a.id}
    assert {i.id for i in recurring.list_recurring(session, active=False)} == {b.id}
