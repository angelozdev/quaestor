from datetime import date

import pytest

from quaestor.domain.errors import IllegalTransition, NotFound, ValidationError
from quaestor.domain.models import AccountType, IntervalUnit, OccurrenceStatus, RecurringMode, TxStatus, TxType
from quaestor.services import accounts, planned, recurring, transactions


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


def test_plan_payment_currency_mismatch_raises(session):
    acc = accounts.create_account(session, "USD Account", AccountType.debit, "USD", balance=0)
    with pytest.raises(ValidationError):
        planned.plan_payment(
            session, payee="x", amount=1000, currency="COP",
            due_date=date(2026, 6, 20), account_id=acc.id,
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


def test_confirm_posts_and_moves_balance(session):
    acc = _acc(session, balance=500_000)
    tx = planned.plan_payment(session, payee="Friend", amount=80_000, currency="COP",
                              due_date=date(2026, 6, 20), account_id=acc.id)
    confirmed = planned.confirm_payment(session, tx.id)
    assert confirmed.status == TxStatus.posted
    assert accounts.get_account(session, acc.id).balance == 420_000


def test_confirm_with_adjusted_amount_recomputes_to_base_and_balance(session):
    acc = _acc(session, balance=500_000)
    tx = planned.plan_payment(session, payee="Electric", amount=80_000, currency="COP",
                              due_date=date(2026, 6, 20), account_id=acc.id)
    confirmed = planned.confirm_payment(session, tx.id, amount=95_000, date=date(2026, 6, 22))
    assert confirmed.amount == 95_000 and confirmed.date == date(2026, 6, 22)
    assert confirmed.to_base == 95_000
    assert accounts.get_account(session, acc.id).balance == 405_000


def test_confirm_syncs_manual_occurrence_to_posted(session):
    acc = _acc(session, balance=1_000_000)
    item = recurring.create_recurring(
        session, name="Water", payee="Utility", type=TxType.expense, mode=RecurringMode.manual,
        amount=50_000, currency="COP", category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 6, 5),
    )
    recurring.materialize_due(session, date(2026, 6, 30))
    planned_tx = transactions.list_transactions(session, status="planned")[0]
    planned.confirm_payment(session, planned_tx.id, amount=53_000)
    occ = recurring.list_recurring(session)  # sanity: item still there
    from sqlmodel import select
    from quaestor.domain.models import RecurringOccurrence
    occ_row = session.exec(
        select(RecurringOccurrence).where(RecurringOccurrence.recurring_id == item.id)
    ).first()
    assert occ_row.status == OccurrenceStatus.posted
    assert accounts.get_account(session, acc.id).balance == 947_000


def test_confirm_non_planned_raises_illegal_transition(session):
    acc = _acc(session, balance=500_000)
    tx = transactions.record_expense(session, acc.id, 1000, "COP", date(2026, 6, 1), "x")
    with pytest.raises(IllegalTransition):
        planned.confirm_payment(session, tx.id)


def test_confirm_unknown_tx_raises_not_found(session):
    with pytest.raises(NotFound):
        planned.confirm_payment(session, 999)


def test_post_confirm_hook_runs_in_same_transaction_and_failure_rolls_back(session):
    acc = _acc(session, balance=500_000)
    tx = planned.plan_payment(session, payee="Goal", amount=100_000, currency="COP",
                              due_date=date(2026, 6, 20), account_id=acc.id)

    def boom(t, s):
        raise RuntimeError("hook failed")

    planned.POST_CONFIRM_HOOKS.append(boom)
    try:
        with pytest.raises(RuntimeError):
            planned.confirm_payment(session, tx.id)
    finally:
        planned.POST_CONFIRM_HOOKS.remove(boom)
    # rolled back: still planned, balance untouched
    reloaded = transactions.get_transaction(session, tx.id)
    assert reloaded.status == TxStatus.planned
    assert accounts.get_account(session, acc.id).balance == 500_000


def test_post_confirm_hook_sees_posted_tx(session):
    acc = _acc(session, balance=500_000)
    tx = planned.plan_payment(session, payee="Goal", amount=100_000, currency="COP",
                              due_date=date(2026, 6, 20), account_id=acc.id)
    seen = {}

    def record(t, s):
        seen["status"] = t.status

    planned.register_post_confirm_hook(record)
    try:
        planned.confirm_payment(session, tx.id)
    finally:
        planned.POST_CONFIRM_HOOKS.remove(record)
    assert seen["status"] == TxStatus.posted


def _planned_transfer(session, dst_account_id, amount=100_000, due=date(2026, 6, 20)):
    """Construct a planned transfer row directly (P4 normally creates these)."""
    from quaestor.domain.models import Transaction
    from decimal import Decimal
    tx = Transaction(
        date=due, payee="Savings goal", type=TxType.transfer, status=TxStatus.planned,
        amount=amount, currency="COP", fx_rate=Decimal("1"), to_base=amount,
        account_id=dst_account_id, source="manual",
    )
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx


def test_confirm_planned_transfer_materializes_posted_pair(session):
    from quaestor.services import settings as settings_svc
    src = accounts.create_account(session, "Checking", AccountType.debit, "COP", balance=1_000_000)
    dst = accounts.create_account(session, "Savings", AccountType.savings, "COP", balance=0)
    settings_svc.update_settings(session, default_source_account_id=src.id)
    tx = _planned_transfer(session, dst.id, amount=100_000)
    confirmed = planned.confirm_payment(session, tx.id)
    assert confirmed.status == TxStatus.posted and confirmed.transfer_group_id is not None
    assert accounts.get_account(session, src.id).balance == 900_000
    assert accounts.get_account(session, dst.id).balance == 100_000
    # exactly one posted pair sharing the group
    posted = transactions.list_transactions(session, status="posted", type=TxType.transfer)
    assert len(posted) == 2
    assert posted[0].transfer_group_id == posted[1].transfer_group_id


def test_confirm_planned_transfer_without_default_source_raises(session):
    dst = accounts.create_account(session, "Savings", AccountType.savings, "COP", balance=0)
    tx = _planned_transfer(session, dst.id)
    with pytest.raises(ValidationError):
        planned.confirm_payment(session, tx.id)


def test_skip_payment_cancels_standalone_planned(session):
    acc = _acc(session, balance=500_000)
    tx = planned.plan_payment(session, payee="Friend", amount=80_000, currency="COP",
                              due_date=date(2026, 6, 20), account_id=acc.id)
    skipped = planned.skip_payment(session, tx.id)
    assert skipped.status == TxStatus.skipped
    result = planned.to_pay(session, date(2026, 6, 1), date(2026, 6, 30))
    assert result["items"] == []  # left the queue
    assert accounts.get_account(session, acc.id).balance == 500_000


def test_skip_payment_marks_occurrence_skipped(session):
    acc = _acc(session, balance=1_000_000)
    item = recurring.create_recurring(
        session, name="Water", payee="Utility", type=TxType.expense, mode=RecurringMode.manual,
        amount=50_000, currency="COP", category_id=None, account_id=acc.id,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 6, 5),
    )
    recurring.materialize_due(session, date(2026, 6, 30))
    planned_tx = transactions.list_transactions(session, status="planned")[0]
    planned.skip_payment(session, planned_tx.id)
    from sqlmodel import select
    from quaestor.domain.models import RecurringOccurrence
    occ = session.exec(
        select(RecurringOccurrence).where(RecurringOccurrence.recurring_id == item.id)
    ).first()
    assert occ.status == OccurrenceStatus.skipped


def test_skip_payment_non_planned_raises(session):
    acc = _acc(session, balance=500_000)
    tx = transactions.record_expense(session, acc.id, 1000, "COP", date(2026, 6, 1), "x")
    with pytest.raises(IllegalTransition):
        planned.skip_payment(session, tx.id)
