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


from quaestor.domain.models import OccurrenceStatus, Source, TxStatus
from quaestor.services import fx, transactions


def accounts_balance(session, account_id):
    from quaestor.services import accounts
    return accounts.get_account(session, account_id).balance


def test_materialize_auto_posts_on_each_due_date(session):
    acc = _acc(session)
    recurring.create_recurring(
        session, name="Rent", payee="Landlord", type=TxType.expense, mode=RecurringMode.auto,
        amount=2_000_000, currency="COP", category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 1, 1),
    )
    occs = recurring.materialize_due(session, date(2026, 3, 15))
    assert [o.due_date for o in occs] == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]
    assert all(o.status == OccurrenceStatus.posted for o in occs)
    posted = transactions.list_transactions(session, status="posted")
    assert len(posted) == 3 and all(t.recurring_id is not None for t in posted)
    # auto posts on each real date and moves the balance by all three
    assert accounts_balance(session, acc.id) == -6_000_000


def test_materialize_submonthly_generates_several_in_a_month(session):
    acc = _acc(session)
    recurring.create_recurring(
        session, name="Allowance", payee="Self", type=TxType.expense, mode=RecurringMode.auto,
        amount=10_000, currency="COP", category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.week, interval_count=2, start_date=date(2026, 1, 1),
    )
    occs = recurring.materialize_due(session, date(2026, 1, 31))
    assert [o.due_date for o in occs] == [date(2026, 1, 1), date(2026, 1, 15), date(2026, 1, 29)]


def test_materialize_manual_leaves_planned_without_balance(session):
    acc = _acc(session)
    recurring.create_recurring(
        session, name="Water", payee="Utility", type=TxType.expense, mode=RecurringMode.manual,
        amount=50_000, currency="COP", category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 1, 5),
    )
    occs = recurring.materialize_due(session, date(2026, 1, 31))
    assert len(occs) == 1 and occs[0].status == OccurrenceStatus.planned
    planned = transactions.list_transactions(session, status="planned")
    assert len(planned) == 1 and planned[0].date == date(2026, 1, 5)
    assert accounts_balance(session, acc.id) == 0  # planned never moves balance


def test_materialize_is_idempotent(session):
    acc = _acc(session)
    recurring.create_recurring(
        session, name="Rent", payee="Landlord", type=TxType.expense, mode=RecurringMode.auto,
        amount=2_000_000, currency="COP", category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 1, 1),
    )
    first = recurring.materialize_due(session, date(2026, 2, 15))
    again = recurring.materialize_due(session, date(2026, 2, 15))
    assert len(first) == 2 and again == []  # nothing new on the second run
    assert len(transactions.list_transactions(session, status="posted")) == 2
    assert accounts_balance(session, acc.id) == -4_000_000


def test_materialize_missed_day_self_heals(session):
    acc = _acc(session)
    recurring.create_recurring(
        session, name="Rent", payee="Landlord", type=TxType.expense, mode=RecurringMode.auto,
        amount=1_000_000, currency="COP", category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 1, 1),
    )
    recurring.materialize_due(session, date(2026, 1, 15))  # only January materialized
    occs = recurring.materialize_due(session, date(2026, 3, 15))  # catches Feb + Mar
    assert [o.due_date for o in occs] == [date(2026, 2, 1), date(2026, 3, 1)]


def test_materialize_skips_inactive_items(session):
    acc = _acc(session)
    item = recurring.create_recurring(
        session, name="Old", payee="x", type=TxType.expense, mode=RecurringMode.auto,
        amount=1000, currency="COP", category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 1, 1),
    )
    item.active = False
    session.add(item)
    session.commit()
    assert recurring.materialize_due(session, date(2026, 6, 1)) == []
