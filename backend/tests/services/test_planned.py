from datetime import date, timedelta
from datetime import date as Date

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


def test_to_pay_includes_overdue_before_since(session):
    """Bug reproduction (2026-07-02): an overdue item with date < since
    must appear in the overdue bucket when retrospective=False
    (the default). Pre-fix, the service filtered with date_from=since
    and the item was silently dropped."""
    a = accounts.create_account(session, "Bank", AccountType.debit, "COP", balance=10_000_000)
    past = date.today() - timedelta(days=10)  # overdue, well before `since`
    planned.plan_payment(
        session, payee="Tigo", amount=8_500_00, currency="COP",
        due_date=past, account_id=a.id,
    )
    queue = planned.to_pay(
        session,
        since=date.today() + timedelta(days=5),
        until=date.today() + timedelta(days=10),
    )
    assert [t.payee for t in queue.overdue] == ["Tigo"]
    assert queue.upcoming == []


def test_to_pay_overdue_excludes_items_on_or_after_today(session):
    """Items dated today or later are 'upcoming', not 'overdue'."""
    a = accounts.create_account(session, "Bank", AccountType.debit, "COP", balance=10_000_000)
    today = date.today()
    planned.plan_payment(
        session, payee="TodayItem", amount=50_000, currency="COP",
        due_date=today, account_id=a.id,
    )
    queue = planned.to_pay(session, since=today, until=today + timedelta(days=30))
    assert queue.overdue == []
    assert [t.payee for t in queue.upcoming] == ["TodayItem"]


def test_to_pay_overdue_excludes_items_after_until(session):
    """An overdue item dated after `until` is out of scope for the
    caller's window. The service must not surface it."""
    a = accounts.create_account(session, "Bank", AccountType.debit, "COP", balance=10_000_000)
    future = date.today() + timedelta(days=5)
    planned.plan_payment(
        session, payee="Future", amount=100_000, currency="COP",
        due_date=future, account_id=a.id,
    )
    queue = planned.to_pay(
        session, since=date.today(), until=date.today() + timedelta(days=2),
    )
    assert queue.overdue == []
    assert queue.upcoming == []  # future item is past `until`


def test_to_pay_upcoming_respects_since_floor(session):
    """`since` is a floor for the upcoming bucket. An item dated
    between `since` and today is overdue (and appears in the overdue
    bucket), not upcoming."""
    a = accounts.create_account(session, "Bank", AccountType.debit, "COP", balance=10_000_000)
    three_days_ago = date.today() - timedelta(days=3)
    planned.plan_payment(
        session, payee="PastButAfterSince", amount=75_000, currency="COP",
        due_date=three_days_ago, account_id=a.id,
    )
    queue = planned.to_pay(
        session, since=three_days_ago, until=date.today() + timedelta(days=10),
    )
    assert [t.payee for t in queue.overdue] == ["PastButAfterSince"]
    assert queue.upcoming == []


def test_to_pay_retrospective_true_omits_overdue_bucket(session):
    """Retrospective view (used by the monthly report): items overdue
    from before the window are not surfaced."""
    a = accounts.create_account(session, "Bank", AccountType.debit, "COP", balance=10_000_000)
    far_past = date.today() - timedelta(days=60)
    in_window = date.today() + timedelta(days=5)
    planned.plan_payment(
        session, payee="PriorOverdue", amount=100_000, currency="COP",
        due_date=far_past, account_id=a.id,
    )
    planned.plan_payment(
        session, payee="InWindow", amount=200_000, currency="COP",
        due_date=in_window, account_id=a.id,
    )
    queue = planned.to_pay(
        session,
        since=date.today(),
        until=date.today() + timedelta(days=30),
        retrospective=True,
    )
    assert queue.overdue == []  # PriorOverdue is filtered out
    assert [t.payee for t in queue.upcoming] == ["InWindow"]


def test_to_pay_today_param_is_respected_for_determinism(session):
    """The `today` kwarg makes the boundary deterministic for tests.
    Passing today=2026-07-15, an item due 2026-07-14 is overdue."""
    a = accounts.create_account(session, "Bank", AccountType.debit, "COP", balance=10_000_000)
    fixed_today = Date(2026, 7, 15)
    planned.plan_payment(
        session, payee="Yesterday", amount=10_000, currency="COP",
        due_date=Date(2026, 7, 14), account_id=a.id,
    )
    queue = planned.to_pay(
        session,
        since=Date(2026, 7, 1),
        until=Date(2026, 7, 31),
        today=fixed_today,
    )
    assert [t.payee for t in queue.overdue] == ["Yesterday"]


def test_to_pay_window_entirely_historical_with_retrospective_returns_empty(session):
    """A retrospective call for a window entirely in the past: both
    buckets are empty (the upcoming floor is past the cap, and the
    overdue bucket is opt-out)."""
    a = accounts.create_account(session, "Bank", AccountType.debit, "COP", balance=10_000_000)
    past = date.today() - timedelta(days=60)
    planned.plan_payment(
        session, payee="WayBefore", amount=10_000, currency="COP",
        due_date=past, account_id=a.id,
    )
    queue = planned.to_pay(
        session,
        since=Date(2024, 1, 1),
        until=Date(2024, 12, 31),
        retrospective=True,
        today=Date(2026, 7, 1),
    )
    assert queue.overdue == []
    assert queue.upcoming == []


def test_to_pay_inverted_window_raises(session):
    """Existing test, kept verbatim: the inverted-window guard."""
    with pytest.raises(ValidationError, match="inverted"):
        planned.to_pay(session, date(2026, 6, 30), date(2026, 6, 1))


def test_to_pay_excludes_posted_from_both_buckets(session):
    """Existing test, updated: 'posted' is excluded from BOTH the
    overdue and the upcoming bucket (a posted tx is not pending)."""
    a = accounts.create_account(session, "Bank", AccountType.debit, "COP", balance=10_000_000)
    past = date.today() - timedelta(days=10)
    tx = planned.plan_payment(
        session, payee="WillBeConfirmed", amount=50_000, currency="COP",
        due_date=past, account_id=a.id,
    )
    planned.confirm_payment(session, tx.id)
    queue = planned.to_pay(
        session,
        since=date.today() - timedelta(days=30),
        until=date.today() + timedelta(days=30),
    )
    assert queue.overdue == []
    assert queue.upcoming == []


def test_to_pay_excludes_skipped_from_both_buckets(session):
    """Lock the 'skipped' exclusion invariant at the service layer.

    `to_pay` filters by `status="planned"` at the SQL boundary, so any
    non-planned status (posted, skipped, future variants) is excluded
    from BOTH buckets. The 'posted' case is locked by
    `test_to_pay_excludes_posted_from_both_buckets` above; this test
    locks the 'skipped' case so a future refactor that accidentally
    relaxes the status filter (e.g. `status != "posted"` only) is caught
    by CI before it ships.
    """
    a = accounts.create_account(session, "Bank", AccountType.debit, "COP", balance=10_000_000)
    past = date.today() - timedelta(days=10)
    tx = planned.plan_payment(
        session, payee="WillBeSkipped", amount=50_000, currency="COP",
        due_date=past, account_id=a.id,
    )
    planned.skip_payment(session, tx.id)
    queue = planned.to_pay(
        session,
        since=date.today() - timedelta(days=30),
        until=date.today() + timedelta(days=30),
    )
    assert queue.overdue == []
    assert queue.upcoming == []


def test_confirm_posts_and_moves_balance(session):
    acc = _acc(session, balance=500_000)
    tx = planned.plan_payment(session, payee="Friend", amount=80_000, currency="COP",
                              due_date=date(2026, 6, 20), account_id=acc.id)
    confirmed = planned.confirm_payment(session, tx.id)
    assert confirmed.status == TxStatus.posted
    assert accounts.get_account(session, acc.id).balance == 420_000


def test_confirm_with_adjusted_amount_moves_balance(session):
    acc = _acc(session, balance=500_000)
    tx = planned.plan_payment(session, payee="Electric", amount=80_000, currency="COP",
                              due_date=date(2026, 6, 20), account_id=acc.id)
    confirmed = planned.confirm_payment(session, tx.id, amount=95_000, date=date(2026, 6, 22))
    assert confirmed.amount == 95_000 and confirmed.date == date(2026, 6, 22)
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


def test_confirm_planned_transfer_stores_both_leg_directions(session):
    from quaestor.domain.models import TransferDirection
    from quaestor.services import settings as settings_svc
    src = accounts.create_account(session, "Checking", AccountType.debit, "COP", balance=1_000_000)
    dst = accounts.create_account(session, "Savings", AccountType.savings, "COP", balance=0)
    settings_svc.update_settings(session, default_source_account_id=src.id)
    tx = _planned_transfer(session, dst.id, amount=100_000)
    confirmed = planned.confirm_payment(session, tx.id)
    legs = transactions.list_transactions(session, status="posted", type=TxType.transfer)
    by_account = {leg.account_id: leg.transfer_direction for leg in legs}
    assert by_account[src.id] == TransferDirection.out
    assert by_account[dst.id] == TransferDirection.in_
    assert confirmed.transfer_direction == TransferDirection.in_


def test_confirmed_planned_transfer_deletes_as_a_pair(session):
    from quaestor.services import settings as settings_svc
    src = accounts.create_account(session, "Checking", AccountType.debit, "COP", balance=1_000_000)
    dst = accounts.create_account(session, "Savings", AccountType.savings, "COP", balance=0)
    settings_svc.update_settings(session, default_source_account_id=src.id)
    tx = _planned_transfer(session, dst.id, amount=100_000)
    confirmed = planned.confirm_payment(session, tx.id)
    transactions.delete_transaction(session, confirmed.id)
    assert transactions.list_transactions(session, type=TxType.transfer) == []
    assert accounts.get_account(session, src.id).balance == 1_000_000
    assert accounts.get_account(session, dst.id).balance == 0


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
    assert result.is_empty  # left the queue
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
