from datetime import date, timedelta
from datetime import date as Date
from decimal import Decimal

import pytest
from quaestor.domain.errors import IllegalTransition, NotFound, ValidationError
from quaestor.domain.models import AccountType, IntervalUnit, OccurrenceStatus, RecurringMode, TxStatus, TxType
from quaestor.services import accounts, occurrences, planned, recurring, transactions

from tests.support.categories import a_category
from tests.support.recurring import declare_existing


def _acc(session, currency="COP", balance=0):
    return accounts.create_account(session, "Bank", AccountType.debit, currency, balance=balance)


def test_plan_payment_creates_planned_without_balance(session):
    acc = _acc(session, balance=500_000)
    tx = planned.plan_payment(
        session,
        payee="Friend",
        amount=80_000,
        currency="COP",
        due_date=date(2026, 6, 20),
        account_id=acc.id,
        category_id=a_category(session),
    )
    assert tx.status == TxStatus.planned and tx.type == TxType.expense
    assert tx.recurring_id is None
    assert accounts.get_account(session, acc.id).balance == 500_000  # untouched


def test_plan_payment_rejects_bad_amount(session):
    acc = _acc(session)
    with pytest.raises(ValidationError):
        planned.plan_payment(
            session,
            payee="x",
            amount=0,
            currency="COP",
            due_date=date(2026, 6, 20),
            account_id=acc.id,
            category_id=a_category(session),
        )


def test_plan_payment_unknown_account(session):
    with pytest.raises(NotFound):
        planned.plan_payment(
            session,
            payee="x",
            amount=1000,
            currency="COP",
            due_date=date(2026, 6, 20),
            account_id=999,
            category_id=a_category(session),
        )


def test_plan_payment_currency_mismatch_raises(session):
    acc = accounts.create_account(session, "USD Account", AccountType.debit, "USD", balance=0)
    with pytest.raises(ValidationError):
        planned.plan_payment(
            session,
            payee="x",
            amount=1000,
            currency="COP",
            due_date=date(2026, 6, 20),
            account_id=acc.id,
            category_id=a_category(session),
        )


def test_to_pay_includes_overdue_before_since(session):
    """Bug reproduction (2026-07-02): an overdue item with date < since
    must appear in the overdue bucket when retrospective=False
    (the default). Pre-fix, the service filtered with date_from=since
    and the item was silently dropped."""
    a = accounts.create_account(session, "Bank", AccountType.debit, "COP", balance=10_000_000)
    past = date.today() - timedelta(days=10)  # overdue, well before `since`
    planned.plan_payment(
        session,
        payee="Tigo",
        amount=8_500_00,
        currency="COP",
        due_date=past,
        account_id=a.id,
        category_id=a_category(session),
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
        session,
        payee="TodayItem",
        amount=50_000,
        currency="COP",
        due_date=today,
        account_id=a.id,
        category_id=a_category(session),
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
        session,
        payee="Future",
        amount=100_000,
        currency="COP",
        due_date=future,
        account_id=a.id,
        category_id=a_category(session),
    )
    queue = planned.to_pay(
        session,
        since=date.today(),
        until=date.today() + timedelta(days=2),
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
        session,
        payee="PastButAfterSince",
        amount=75_000,
        currency="COP",
        due_date=three_days_ago,
        account_id=a.id,
        category_id=a_category(session),
    )
    queue = planned.to_pay(
        session,
        since=three_days_ago,
        until=date.today() + timedelta(days=10),
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
        session,
        payee="PriorOverdue",
        amount=100_000,
        currency="COP",
        due_date=far_past,
        account_id=a.id,
        category_id=a_category(session),
    )
    planned.plan_payment(
        session,
        payee="InWindow",
        amount=200_000,
        currency="COP",
        due_date=in_window,
        account_id=a.id,
        category_id=a_category(session),
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
        session,
        payee="Yesterday",
        amount=10_000,
        currency="COP",
        due_date=Date(2026, 7, 14),
        account_id=a.id,
        category_id=a_category(session),
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
        session,
        payee="WayBefore",
        amount=10_000,
        currency="COP",
        due_date=past,
        account_id=a.id,
        category_id=a_category(session),
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


def test_to_pay_accepts_a_single_day_window(session):
    """`since == until` is a one-day window, not an inverted one: it is
    accepted, and an item due that day is upcoming rather than overdue."""
    a = _acc(session, balance=10_000_000)
    day = Date(2026, 7, 10)
    planned.plan_payment(
        session,
        payee="Agua",
        amount=30_000,
        currency="COP",
        due_date=day,
        account_id=a.id,
        category_id=a_category(session),
    )
    queue = planned.to_pay(session, since=day, until=day, today=day)
    assert queue.overdue == []
    assert [t.payee for t in queue.upcoming] == ["Agua"]


def test_to_pay_overdue_is_capped_by_until_on_a_past_window(session):
    """`until` caps the overdue bucket even when the whole window is in
    the past: something that fell due between `until` and today is out of
    scope for the window the caller asked about."""
    a = _acc(session, balance=10_000_000)
    planned.plan_payment(
        session,
        payee="InWindow",
        amount=10_000,
        currency="COP",
        due_date=Date(2026, 7, 5),
        account_id=a.id,
        category_id=a_category(session),
    )
    planned.plan_payment(
        session,
        payee="AfterUntil",
        amount=20_000,
        currency="COP",
        due_date=Date(2026, 7, 15),
        account_id=a.id,
        category_id=a_category(session),
    )
    queue = planned.to_pay(
        session,
        since=Date(2026, 7, 1),
        until=Date(2026, 7, 10),
        today=Date(2026, 7, 20),
    )
    assert [t.payee for t in queue.overdue] == ["InWindow"]
    assert queue.upcoming == []


def test_to_pay_excludes_posted_from_both_buckets(session):
    """Existing test, updated: 'posted' is excluded from BOTH the
    overdue and the upcoming bucket (a posted tx is not pending)."""
    a = accounts.create_account(session, "Bank", AccountType.debit, "COP", balance=10_000_000)
    past = date.today() - timedelta(days=10)
    tx = planned.plan_payment(
        session,
        payee="WillBeConfirmed",
        amount=50_000,
        currency="COP",
        due_date=past,
        account_id=a.id,
        category_id=a_category(session),
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
        session,
        payee="WillBeSkipped",
        amount=50_000,
        currency="COP",
        due_date=past,
        account_id=a.id,
        category_id=a_category(session),
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
    tx = planned.plan_payment(
        session,
        payee="Friend",
        amount=80_000,
        currency="COP",
        due_date=date(2026, 6, 20),
        account_id=acc.id,
        category_id=a_category(session),
    )
    confirmed = planned.confirm_payment(session, tx.id)
    assert confirmed.status == TxStatus.posted
    assert accounts.get_account(session, acc.id).balance == 420_000


def test_confirm_with_adjusted_amount_moves_balance(session):
    acc = _acc(session, balance=500_000)
    tx = planned.plan_payment(
        session,
        payee="Electric",
        amount=80_000,
        currency="COP",
        due_date=date(2026, 6, 20),
        account_id=acc.id,
        category_id=a_category(session),
    )
    confirmed = planned.confirm_payment(session, tx.id, amount=95_000, date=date(2026, 6, 22))
    assert confirmed.amount == 95_000 and confirmed.date == date(2026, 6, 22)
    assert accounts.get_account(session, acc.id).balance == 405_000


def test_confirm_syncs_manual_occurrence_to_posted(session):
    acc = _acc(session, balance=1_000_000)
    item = declare_existing(
        session,
        name="Water",
        payee="Utility",
        type=TxType.expense,
        mode=RecurringMode.manual,
        amount=50_000,
        currency="COP",
        category_id=a_category(session),
        account_id=acc.id,
        interval_unit=IntervalUnit.month,
        interval_count=1,
        start_date=date(2026, 6, 5),
    )
    occurrences.materialize_due(session, date(2026, 6, 30))
    planned_tx = transactions.list_transactions(session, status="planned")[0]
    planned.confirm_payment(session, planned_tx.id, amount=53_000)
    recurring.list_recurring(session)  # sanity: item still there
    from quaestor.domain.models import RecurringOccurrence
    from sqlmodel import select

    occ_row = session.exec(select(RecurringOccurrence).where(RecurringOccurrence.recurring_id == item.id)).first()
    assert occ_row.status == OccurrenceStatus.posted
    assert accounts.get_account(session, acc.id).balance == 947_000


def test_confirm_non_planned_raises_illegal_transition(session):
    acc = _acc(session, balance=500_000)
    tx = transactions.record_expense(
        session, acc.id, 1000, "COP", date(2026, 6, 1), "x", category_id=a_category(session, TxType.expense)
    )
    with pytest.raises(IllegalTransition):
        planned.confirm_payment(session, tx.id)


def test_confirm_unknown_tx_raises_not_found(session):
    with pytest.raises(NotFound):
        planned.confirm_payment(session, 999)


def test_post_confirm_hook_runs_in_same_transaction_and_failure_rolls_back(session):
    acc = _acc(session, balance=500_000)
    tx = planned.plan_payment(
        session,
        payee="Goal",
        amount=100_000,
        currency="COP",
        due_date=date(2026, 6, 20),
        account_id=acc.id,
        category_id=a_category(session),
    )

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
    tx = planned.plan_payment(
        session,
        payee="Goal",
        amount=100_000,
        currency="COP",
        due_date=date(2026, 6, 20),
        account_id=acc.id,
        category_id=a_category(session),
    )
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
    from decimal import Decimal

    from quaestor.domain.models import Transaction

    tx = Transaction(
        date=due,
        payee="Savings goal",
        type=TxType.transfer,
        status=TxStatus.planned,
        amount=amount,
        currency="COP",
        fx_rate=Decimal("1"),
        to_base=amount,
        account_id=dst_account_id,
        source="manual",
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


def _confirmable_transfer(session, dst_currency="COP", src_currency="COP", amount=100_000):
    from quaestor.services import settings as settings_svc

    src = accounts.create_account(session, "Checking", AccountType.debit, src_currency, balance=1_000_000)
    dst = accounts.create_account(session, "Savings", AccountType.savings, dst_currency, balance=0)
    settings_svc.update_settings(session, default_source_account_id=src.id)
    return src, dst, _planned_transfer(session, dst.id, amount=amount)


def test_confirm_planned_transfer_accepts_a_one_cent_amount(session):
    src, dst, tx = _confirmable_transfer(session, amount=1)
    confirmed = planned.confirm_payment(session, tx.id)
    assert confirmed.status == TxStatus.posted
    assert accounts.get_account(session, src.id).balance == 999_999
    assert accounts.get_account(session, dst.id).balance == 1


def test_confirm_planned_transfer_rejects_a_zero_amount(session):
    src, dst, tx = _confirmable_transfer(session)
    with pytest.raises(ValidationError):
        planned.confirm_payment(session, tx.id, amount=0)
    assert accounts.get_account(session, src.id).balance == 1_000_000
    assert accounts.get_account(session, dst.id).balance == 0


def test_confirm_planned_transfer_rejects_a_source_currency_mismatch(session):
    _src, _dst, tx = _confirmable_transfer(session, src_currency="USD")
    with pytest.raises(ValidationError):
        planned.confirm_payment(session, tx.id)


def test_confirm_planned_transfer_rejects_a_destination_currency_mismatch(session):
    _src, _dst, tx = _confirmable_transfer(session, dst_currency="USD")
    with pytest.raises(ValidationError):
        planned.confirm_payment(session, tx.id)


def test_confirm_planned_transfer_without_default_source_raises(session):
    dst = accounts.create_account(session, "Savings", AccountType.savings, "COP", balance=0)
    tx = _planned_transfer(session, dst.id)
    with pytest.raises(ValidationError):
        planned.confirm_payment(session, tx.id)


def test_skip_payment_cancels_standalone_planned(session):
    acc = _acc(session, balance=500_000)
    tx = planned.plan_payment(
        session,
        payee="Friend",
        amount=80_000,
        currency="COP",
        due_date=date(2026, 6, 20),
        account_id=acc.id,
        category_id=a_category(session),
    )
    skipped = planned.skip_payment(session, tx.id)
    assert skipped.status == TxStatus.skipped
    result = planned.to_pay(session, date(2026, 6, 1), date(2026, 6, 30))
    assert result.is_empty  # left the queue
    assert accounts.get_account(session, acc.id).balance == 500_000


def test_skip_payment_marks_occurrence_skipped(session):
    acc = _acc(session, balance=1_000_000)
    item = declare_existing(
        session,
        name="Water",
        payee="Utility",
        type=TxType.expense,
        mode=RecurringMode.manual,
        amount=50_000,
        currency="COP",
        category_id=a_category(session),
        account_id=acc.id,
        interval_unit=IntervalUnit.month,
        interval_count=1,
        start_date=date(2026, 6, 5),
    )
    occurrences.materialize_due(session, date(2026, 6, 30))
    planned_tx = transactions.list_transactions(session, status="planned")[0]
    planned.skip_payment(session, planned_tx.id)
    from quaestor.domain.models import RecurringOccurrence
    from sqlmodel import select

    occ = session.exec(select(RecurringOccurrence).where(RecurringOccurrence.recurring_id == item.id)).first()
    assert occ.status == OccurrenceStatus.skipped


def test_skip_payment_non_planned_raises(session):
    acc = _acc(session, balance=500_000)
    tx = transactions.record_expense(
        session, acc.id, 1000, "COP", date(2026, 6, 1), "x", category_id=a_category(session, TxType.expense)
    )
    with pytest.raises(IllegalTransition):
        planned.skip_payment(session, tx.id)


def test_restore_payment_returns_skipped_to_the_queue(session):
    acc = _acc(session, balance=500_000)
    tx = planned.plan_payment(
        session,
        payee="Claro",
        amount=85_000,
        currency="COP",
        due_date=date(2026, 6, 20),
        account_id=acc.id,
        category_id=a_category(session),
    )
    planned.skip_payment(session, tx.id)
    restored = planned.restore_payment(session, tx.id)
    assert restored.status == TxStatus.planned
    assert restored.amount == 85_000 and restored.date == date(2026, 6, 20)
    result = planned.to_pay(session, date(2026, 6, 1), date(2026, 6, 30), today=date(2026, 6, 1))
    assert [t.payee for t in result.all_items()] == ["Claro"]


def test_restore_payment_moves_no_balance(session):
    acc = _acc(session, balance=500_000)
    tx = planned.plan_payment(
        session,
        payee="Claro",
        amount=85_000,
        currency="COP",
        due_date=date(2026, 6, 20),
        account_id=acc.id,
        category_id=a_category(session),
    )
    planned.skip_payment(session, tx.id)
    planned.restore_payment(session, tx.id)
    assert accounts.get_account(session, acc.id).balance == 500_000


def _occurrence_for_recurring(session, recurring_id):
    from quaestor.domain.models import RecurringOccurrence
    from sqlmodel import select

    return session.exec(select(RecurringOccurrence).where(RecurringOccurrence.recurring_id == recurring_id)).first()


def _occurrence_count(session, recurring_id) -> int:
    from quaestor.domain.models import RecurringOccurrence
    from sqlmodel import select

    return len(session.exec(select(RecurringOccurrence).where(RecurringOccurrence.recurring_id == recurring_id)).all())


def test_restore_payment_returns_occurrence_to_planned(session):
    acc = _acc(session, balance=1_000_000)
    item = declare_existing(
        session,
        name="Water",
        payee="Utility",
        type=TxType.expense,
        mode=RecurringMode.manual,
        amount=50_000,
        currency="COP",
        category_id=a_category(session),
        account_id=acc.id,
        interval_unit=IntervalUnit.month,
        interval_count=1,
        start_date=date(2026, 6, 5),
    )
    occurrences.materialize_due(session, date(2026, 6, 30))
    planned_tx = transactions.list_transactions(session, status="planned")[0]
    planned.skip_payment(session, planned_tx.id)
    planned.restore_payment(session, planned_tx.id)
    assert _occurrence_for_recurring(session, item.id).status == OccurrenceStatus.planned


def test_restore_payment_then_materialize_does_not_duplicate(session):
    acc = _acc(session, balance=1_000_000)
    item = declare_existing(
        session,
        name="Water",
        payee="Utility",
        type=TxType.expense,
        mode=RecurringMode.manual,
        amount=50_000,
        currency="COP",
        category_id=a_category(session),
        account_id=acc.id,
        interval_unit=IntervalUnit.month,
        interval_count=1,
        start_date=date(2026, 6, 5),
    )
    occurrences.materialize_due(session, date(2026, 6, 30))
    planned_tx = transactions.list_transactions(session, status="planned")[0]
    planned.skip_payment(session, planned_tx.id)
    planned.restore_payment(session, planned_tx.id)
    assert occurrences.materialize_due(session, date(2026, 6, 30)).created == []
    assert len(transactions.list_transactions(session, status="planned")) == 1
    assert _occurrence_count(session, item.id) == 1


def test_restored_payment_can_be_confirmed(session):
    acc = _acc(session, balance=500_000)
    tx = planned.plan_payment(
        session,
        payee="Claro",
        amount=85_000,
        currency="COP",
        due_date=date(2026, 6, 20),
        account_id=acc.id,
        category_id=a_category(session),
    )
    planned.skip_payment(session, tx.id)
    planned.restore_payment(session, tx.id)
    posted = planned.confirm_payment(session, tx.id)
    assert posted.status == TxStatus.posted
    assert accounts.get_account(session, acc.id).balance == 415_000


@pytest.mark.parametrize("status", ["planned", "posted"])
def test_restore_payment_non_skipped_raises(session, status):
    acc = _acc(session, balance=500_000)
    if status == "planned":
        tx = planned.plan_payment(
            session,
            payee="Claro",
            amount=85_000,
            currency="COP",
            due_date=date(2026, 6, 20),
            account_id=acc.id,
            category_id=a_category(session),
        )
    else:
        tx = transactions.record_expense(
            session, acc.id, 1000, "COP", date(2026, 6, 1), "x", category_id=a_category(session, TxType.expense)
        )
    with pytest.raises(IllegalTransition):
        planned.restore_payment(session, tx.id)


def test_restore_payment_unknown_raises(session):
    with pytest.raises(NotFound):
        planned.restore_payment(session, 999)


def _planned_income(session, account_id, amount=5_000_000, due=date(2026, 6, 20)):
    """A planned income row — expected money in, not an obligation."""
    from quaestor.domain.models import Transaction

    tx = Transaction(
        date=due,
        payee="Empleador",
        type=TxType.income,
        status=TxStatus.planned,
        amount=amount,
        currency="COP",
        fx_rate=Decimal("1"),
        to_base=amount,
        account_id=account_id,
        source="manual",
        category_id=a_category(session, TxType.income),
    )
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx


def test_to_pay_excludes_upcoming_planned_income(session):
    acc = _acc(session, balance=500_000)
    _planned_income(session, acc.id, due=date(2026, 6, 20))
    planned.plan_payment(
        session,
        payee="Claro",
        amount=85_000,
        currency="COP",
        due_date=date(2026, 6, 21),
        account_id=acc.id,
        category_id=a_category(session),
    )
    queue = planned.to_pay(session, date(2026, 6, 1), date(2026, 6, 30), today=date(2026, 6, 1))
    assert [t.payee for t in queue.all_items()] == ["Claro"]
    assert queue.total_cop_cents(Decimal("4100")) == 85_000


def test_to_pay_excludes_overdue_planned_income(session):
    acc = _acc(session, balance=500_000)
    _planned_income(session, acc.id, due=date(2026, 6, 5))
    planned.plan_payment(
        session,
        payee="Claro",
        amount=85_000,
        currency="COP",
        due_date=date(2026, 6, 6),
        account_id=acc.id,
        category_id=a_category(session),
    )
    queue = planned.to_pay(session, date(2026, 6, 1), date(2026, 6, 30), today=date(2026, 6, 10))
    assert [t.payee for t in queue.overdue] == ["Claro"]
    assert queue.upcoming == []


def test_to_pay_excludes_an_overdue_planned_income(session):
    from quaestor.domain.models import Transaction

    acc = _acc(session, balance=500_000)
    session.add(
        Transaction(
            date=date(2026, 6, 5),
            payee="Empleador",
            type=TxType.income,
            status=TxStatus.planned,
            amount=5_000_000,
            currency="COP",
            account_id=acc.id,
            category_id=a_category(session, TxType.income),
        )
    )
    session.commit()
    assert transactions.list_transactions(session, status="planned")
    queue = planned.to_pay(session, date(2026, 6, 1), date(2026, 6, 30), today=date(2026, 6, 10))
    assert queue.is_empty
    assert queue.total_cop_cents(Decimal("4100")) == 0


def test_to_pay_keeps_expenses_and_transfers(session):
    acc = _acc(session, balance=500_000)
    dst = accounts.create_account(session, "Savings", AccountType.savings, "COP", balance=0)
    planned.plan_payment(
        session,
        payee="Claro",
        amount=85_000,
        currency="COP",
        due_date=date(2026, 6, 20),
        account_id=acc.id,
        category_id=a_category(session),
    )
    _planned_transfer(session, dst.id, amount=200_000, due=date(2026, 6, 21))
    queue = planned.to_pay(session, date(2026, 6, 1), date(2026, 6, 30), today=date(2026, 6, 1))
    assert {t.type for t in queue.all_items()} == {TxType.expense, TxType.transfer}
    assert queue.total_cop_cents(Decimal("4100")) == 285_000
