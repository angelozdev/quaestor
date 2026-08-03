from datetime import date

import pytest
from quaestor.domain.errors import NotFound, ValidationError
from quaestor.domain.models import (
    AccountType,
    IntervalUnit,
    OccurrenceStatus,
    RecurringMode,
    Source,
    TxType,
)
from quaestor.services import accounts, occurrences, recurring, transactions

from tests.support.categories import a_category
from tests.support.recurring import declare_existing


def _acc(session, currency="COP"):
    return accounts.create_account(session, "Bank", AccountType.debit, currency, balance=0)


def accounts_balance(session, account_id):
    return accounts.get_account(session, account_id).balance


def test_materialize_auto_posts_on_each_due_date(session):
    acc = _acc(session)
    declare_existing(
        session,
        name="Rent",
        payee="Landlord",
        type=TxType.expense,
        mode=RecurringMode.auto,
        amount=2_000_000,
        currency="COP",
        category_id=a_category(session),
        account_id=acc.id,
        interval_unit=IntervalUnit.month,
        interval_count=1,
        start_date=date(2026, 1, 1),
    )
    report = occurrences.materialize_due(session, date(2026, 3, 15))
    assert [o.due_date for o in report.created] == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]
    assert all(o.status == OccurrenceStatus.posted for o in report.created)
    posted = transactions.list_transactions(session, status="posted")
    assert len(posted) == 3 and all(t.recurring_id is not None for t in posted)
    assert accounts_balance(session, acc.id) == -6_000_000


def test_materialize_submonthly_generates_several_in_a_month(session):
    acc = _acc(session)
    declare_existing(
        session,
        name="Allowance",
        payee="Self",
        type=TxType.expense,
        mode=RecurringMode.auto,
        amount=10_000,
        currency="COP",
        category_id=a_category(session),
        account_id=acc.id,
        interval_unit=IntervalUnit.week,
        interval_count=2,
        start_date=date(2026, 1, 1),
    )
    report = occurrences.materialize_due(session, date(2026, 1, 31))
    assert [o.due_date for o in report.created] == [date(2026, 1, 1), date(2026, 1, 15), date(2026, 1, 29)]


def test_materialize_manual_leaves_planned_without_balance(session):
    acc = _acc(session)
    declare_existing(
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
        start_date=date(2026, 1, 5),
    )
    report = occurrences.materialize_due(session, date(2026, 1, 31))
    assert len(report.created) == 1 and report.created[0].status == OccurrenceStatus.planned
    planned = transactions.list_transactions(session, status="planned")
    assert len(planned) == 1 and planned[0].date == date(2026, 1, 5)
    assert accounts_balance(session, acc.id) == 0


def test_materialize_is_idempotent(session):
    acc = _acc(session)
    declare_existing(
        session,
        name="Rent",
        payee="Landlord",
        type=TxType.expense,
        mode=RecurringMode.auto,
        amount=2_000_000,
        currency="COP",
        category_id=a_category(session),
        account_id=acc.id,
        interval_unit=IntervalUnit.month,
        interval_count=1,
        start_date=date(2026, 1, 1),
    )
    first = occurrences.materialize_due(session, date(2026, 2, 15))
    again = occurrences.materialize_due(session, date(2026, 2, 15))
    assert len(first.created) == 2 and again.created == []
    assert len(transactions.list_transactions(session, status="posted")) == 2
    assert accounts_balance(session, acc.id) == -4_000_000


def test_materialize_missed_day_self_heals(session):
    acc = _acc(session)
    declare_existing(
        session,
        name="Rent",
        payee="Landlord",
        type=TxType.expense,
        mode=RecurringMode.auto,
        amount=1_000_000,
        currency="COP",
        category_id=a_category(session),
        account_id=acc.id,
        interval_unit=IntervalUnit.month,
        interval_count=1,
        start_date=date(2026, 1, 1),
    )
    occurrences.materialize_due(session, date(2026, 1, 15))
    report = occurrences.materialize_due(session, date(2026, 3, 15))
    assert [o.due_date for o in report.created] == [date(2026, 2, 1), date(2026, 3, 1)]


def test_materialize_skips_inactive_items(session):
    acc = _acc(session)
    item = declare_existing(
        session,
        name="Old",
        payee="x",
        type=TxType.expense,
        mode=RecurringMode.auto,
        amount=1000,
        currency="COP",
        category_id=a_category(session),
        account_id=acc.id,
        interval_unit=IntervalUnit.month,
        interval_count=1,
        start_date=date(2026, 1, 1),
    )
    item.active = False
    session.add(item)
    session.commit()
    assert occurrences.materialize_due(session, date(2026, 6, 1)).created == []


def test_skip_recurring_before_materialization_blocks_it(session):
    acc = _acc(session)
    item = declare_existing(
        session,
        name="Rent",
        payee="Landlord",
        type=TxType.expense,
        mode=RecurringMode.auto,
        amount=1_000_000,
        currency="COP",
        category_id=a_category(session),
        account_id=acc.id,
        interval_unit=IntervalUnit.month,
        interval_count=1,
        start_date=date(2026, 1, 1),
    )
    occ = occurrences.skip(session, item.id, date(2026, 2, 1))
    assert occ.status == OccurrenceStatus.skipped and occ.transaction_id is None
    report = occurrences.materialize_due(session, date(2026, 3, 15))
    assert [o.due_date for o in report.created] == [date(2026, 1, 1), date(2026, 3, 1)]


def test_skip_recurring_after_manual_materialization_skips_the_planned_tx(session):
    acc = _acc(session)
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
        start_date=date(2026, 1, 5),
    )
    occurrences.materialize_due(session, date(2026, 1, 31))
    assert len(transactions.list_transactions(session, status="planned")) == 1
    occ = occurrences.skip(session, item.id, date(2026, 1, 5))
    assert occ.status == OccurrenceStatus.skipped
    assert transactions.list_transactions(session, status="planned") == []
    assert len(transactions.list_transactions(session, status="skipped")) == 1


def test_skip_recurring_unknown_item(session):
    with pytest.raises(NotFound):
        occurrences.skip(session, 999, date(2026, 1, 1))


def _recurring(session, name, account_id, amount, mode=RecurringMode.auto):
    return declare_existing(
        session,
        name=name,
        payee=name,
        type=TxType.expense,
        mode=mode,
        amount=amount,
        currency="COP",
        category_id=a_category(session),
        account_id=account_id,
        interval_unit=IntervalUnit.month,
        interval_count=1,
        start_date=date(2026, 1, 1),
    )


def test_a_broken_obligation_does_not_stop_the_healthy_ones(session):
    good = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    bad = accounts.create_account(session, "Nequi", AccountType.debit, "COP", balance=200_000)
    _recurring(session, "Netflix", good.id, 25_900)
    _recurring(session, "Spotify", bad.id, 15_000)
    accounts.archive_account(session, bad.id)

    report = occurrences.materialize_due(session, date(2026, 1, 31))

    assert [o.due_date for o in report.created] == [date(2026, 1, 1)]
    assert accounts.get_account(session, good.id).balance == 500_000 - 25_900
    assert accounts.get_account(session, bad.id).balance == 200_000


def test_the_failure_names_the_obligation_and_only_that_one(session):
    good = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    bad = accounts.create_account(session, "Nequi", AccountType.debit, "COP", balance=200_000)
    _recurring(session, "Netflix", good.id, 25_900)
    _recurring(session, "Spotify", bad.id, 15_000)
    accounts.archive_account(session, bad.id)

    report = occurrences.materialize_due(session, date(2026, 1, 31))

    reported = [str(f) for f in report.failures]
    assert len(reported) == 1
    assert "Spotify" in reported[0]
    assert not any("Netflix" in message for message in reported)


def test_a_failed_charge_leaves_the_date_free_for_the_next_run(session):
    acc = accounts.create_account(session, "Nequi", AccountType.debit, "COP", balance=200_000)
    _recurring(session, "Spotify", acc.id, 15_000)
    accounts.archive_account(session, acc.id)
    occurrences.materialize_due(session, date(2026, 1, 31))

    accounts.unarchive_account(session, acc.id)
    report = occurrences.materialize_due(session, date(2026, 1, 31))

    assert [o.due_date for o in report.created] == [date(2026, 1, 1)]
    assert accounts.get_account(session, acc.id).balance == 200_000 - 15_000


def test_a_failed_charge_writes_no_occurrence(session):
    acc = accounts.create_account(session, "Nequi", AccountType.debit, "COP", balance=200_000)
    item = _recurring(session, "Spotify", acc.id, 15_000)
    accounts.archive_account(session, acc.id)

    occurrences.materialize_due(session, date(2026, 1, 31))

    assert occurrences.existing_due_dates(session, item.id) == set()


def test_one_failure_is_reported_per_obligation_not_per_date(session):
    acc = accounts.create_account(session, "Nequi", AccountType.debit, "COP", balance=200_000)
    _recurring(session, "Spotify", acc.id, 15_000)
    accounts.archive_account(session, acc.id)

    report = occurrences.materialize_due(session, date(2026, 6, 30))

    assert len(report.failures) == 1


def test_an_auto_charge_records_the_engine_as_its_source(session):
    acc = _acc(session)
    declare_existing(
        session,
        name="Rent",
        payee="Landlord",
        type=TxType.expense,
        mode=RecurringMode.auto,
        amount=1_000_000,
        currency="COP",
        category_id=a_category(session),
        account_id=acc.id,
        interval_unit=IntervalUnit.month,
        interval_count=1,
        start_date=date(2026, 1, 1),
    )
    occurrences.materialize_due(session, date(2026, 1, 31))
    tx = transactions.list_transactions(session, status="posted")[0]
    assert tx.source == Source.recurring


def test_a_manual_charge_records_the_engine_as_its_source(session):
    acc = _acc(session)
    declare_existing(
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
        start_date=date(2026, 1, 5),
    )
    occurrences.materialize_due(session, date(2026, 1, 31))
    tx = transactions.list_transactions(session, status="planned")[0]
    assert tx.source == Source.recurring


def test_a_hand_entered_movement_is_not_the_engines(session):
    acc = _acc(session)
    tx = transactions.record_expense(
        session, acc.id, 30_000, "COP", date(2026, 1, 5), "Tienda", category_id=a_category(session, TxType.expense)
    )
    assert tx.source == Source.manual


def _weekly(session, acc_id, start):
    return declare_existing(
        session,
        name="Gimnasio",
        payee="Gimnasio",
        type=TxType.expense,
        mode=RecurringMode.auto,
        amount=8_000,
        currency="COP",
        category_id=a_category(session),
        account_id=acc_id,
        interval_unit=IntervalUnit.week,
        interval_count=1,
        start_date=start,
    )


def test_resuming_does_not_charge_the_paused_stretch(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = _weekly(session, acc.id, date(2026, 1, 1))
    occurrences.materialize_due(session, date(2026, 1, 1))
    recurring.deactivate_recurring(session, item.id)

    recurring.restore_recurring(session, item.id, today=date(2026, 1, 22))
    occurrences.materialize_due(session, date(2026, 1, 22))

    charged = [o.due_date for o in _live_occurrences(session, item.id)]
    assert charged == [date(2026, 1, 1), date(2026, 1, 22)]
    assert accounts.get_account(session, acc.id).balance == 500_000 - 2 * 8_000


def test_the_obligation_carries_on_normally_after_resuming(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = _weekly(session, acc.id, date(2026, 1, 1))
    occurrences.materialize_due(session, date(2026, 1, 1))
    recurring.deactivate_recurring(session, item.id)
    recurring.restore_recurring(session, item.id, today=date(2026, 1, 22))

    occurrences.materialize_due(session, date(2026, 1, 29))

    charged = [o.due_date for o in _live_occurrences(session, item.id)]
    assert charged == [date(2026, 1, 1), date(2026, 1, 22), date(2026, 1, 29)]


def test_the_dates_left_behind_by_a_pause_are_offered_not_written_off(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = _weekly(session, acc.id, date(2026, 1, 1))
    occurrences.materialize_due(session, date(2026, 1, 1))
    recurring.deactivate_recurring(session, item.id)

    recurring.restore_recurring(session, item.id, today=date(2026, 1, 22))

    assert occurrences.pending_dates(session, item.id) == [
        date(2026, 1, 8),
        date(2026, 1, 15),
    ]
    assert accounts.get_account(session, acc.id).balance == 500_000 - 8_000


def test_restoring_something_already_live_closes_nothing(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = _weekly(session, acc.id, date(2026, 1, 1))

    recurring.restore_recurring(session, item.id, today=date(2026, 1, 22))
    occurrences.materialize_due(session, date(2026, 1, 22))

    charged = [o.due_date for o in _live_occurrences(session, item.id)]
    assert charged == [date(2026, 1, 1), date(2026, 1, 8), date(2026, 1, 15), date(2026, 1, 22)]


def test_an_ended_obligation_still_gets_the_date_the_engine_missed(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    declare_existing(
        session,
        name="Gimnasio",
        payee="Gimnasio",
        type=TxType.expense,
        mode=RecurringMode.auto,
        amount=8_000,
        currency="COP",
        category_id=a_category(session),
        account_id=acc.id,
        interval_unit=IntervalUnit.week,
        interval_count=1,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 15),
    )

    report = occurrences.materialize_due(session, date(2026, 2, 1))

    assert [o.due_date for o in report.created] == [
        date(2026, 1, 1),
        date(2026, 1, 8),
        date(2026, 1, 15),
    ]
    assert recurring.list_recurring(session, active=True, today=date(2026, 2, 1)) == []


def _all_occurrences(session, recurring_id):
    from quaestor.domain.models import RecurringOccurrence
    from sqlmodel import select

    return list(
        session.exec(
            select(RecurringOccurrence)
            .where(RecurringOccurrence.recurring_id == recurring_id)
            .order_by(RecurringOccurrence.due_date)
        ).all()
    )


def _live_occurrences(session, recurring_id):
    live = (OccurrenceStatus.posted, OccurrenceStatus.planned)
    return [o for o in _all_occurrences(session, recurring_id) if o.status in live]


def test_skipping_a_date_already_charged_is_refused(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = _weekly(session, acc.id, date(2026, 1, 1))
    occurrences.materialize_due(session, date(2026, 1, 1))

    with pytest.raises(ValidationError) as caught:
        occurrences.skip(session, item.id, date(2026, 1, 1))

    assert "charged" in str(caught.value).lower()


def test_the_refused_skip_leaves_the_money_and_the_record_alone(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = _weekly(session, acc.id, date(2026, 1, 1))
    occurrences.materialize_due(session, date(2026, 1, 1))

    with pytest.raises(ValidationError):
        occurrences.skip(session, item.id, date(2026, 1, 1))

    assert accounts.get_account(session, acc.id).balance == 500_000 - 8_000
    assert _all_occurrences(session, item.id)[0].status == OccurrenceStatus.posted


def test_a_turn_waiting_for_approval_can_still_be_skipped(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = declare_existing(
        session,
        name="Arriendo",
        payee="Arriendo",
        type=TxType.expense,
        mode=RecurringMode.manual,
        amount=1_800_000,
        currency="COP",
        category_id=a_category(session),
        account_id=acc.id,
        interval_unit=IntervalUnit.month,
        interval_count=1,
        start_date=date(2026, 1, 1),
    )
    occurrences.materialize_due(session, date(2026, 1, 1))

    occ = occurrences.skip(session, item.id, date(2026, 1, 1))

    assert occ.status == OccurrenceStatus.skipped


def test_a_date_the_obligation_never_falls_on_cannot_be_skipped(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = _weekly(session, acc.id, date(2026, 1, 1))

    with pytest.raises(ValidationError):
        occurrences.skip(session, item.id, date(2026, 1, 4))


def test_the_refused_skip_records_nothing(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = _weekly(session, acc.id, date(2026, 1, 1))

    with pytest.raises(ValidationError):
        occurrences.skip(session, item.id, date(2026, 1, 4))

    assert _all_occurrences(session, item.id) == []


def test_a_real_future_due_date_can_still_be_skipped(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = _weekly(session, acc.id, date(2026, 1, 1))

    occ = occurrences.skip(session, item.id, date(2026, 1, 8))

    assert occ.status == OccurrenceStatus.skipped


def test_deleting_an_engine_charge_returns_the_money_and_closes_the_date(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = _weekly(session, acc.id, date(2026, 1, 1))
    occurrences.materialize_due(session, date(2026, 1, 1))
    tx = transactions.list_transactions(session, status="posted")[0]

    transactions.delete_transaction(session, tx.id)

    assert accounts.get_account(session, acc.id).balance == 500_000
    occ = _all_occurrences(session, item.id)[0]
    assert occ.status == OccurrenceStatus.skipped
    assert occ.transaction_id is None


def test_a_later_run_does_not_charge_the_deleted_date_again(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = _weekly(session, acc.id, date(2026, 1, 1))
    occurrences.materialize_due(session, date(2026, 1, 1))
    tx = transactions.list_transactions(session, status="posted")[0]
    transactions.delete_transaction(session, tx.id)

    occurrences.materialize_due(session, date(2026, 1, 1))

    assert _live_occurrences(session, item.id) == []
    assert accounts.get_account(session, acc.id).balance == 500_000


def test_the_dates_after_a_deleted_charge_are_unaffected(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = _weekly(session, acc.id, date(2026, 1, 1))
    occurrences.materialize_due(session, date(2026, 1, 1))
    tx = transactions.list_transactions(session, status="posted")[0]
    transactions.delete_transaction(session, tx.id)

    occurrences.materialize_due(session, date(2026, 1, 8))

    assert [o.due_date for o in _live_occurrences(session, item.id)] == [date(2026, 1, 8)]


def test_deleting_a_hand_entered_movement_touches_no_occurrence(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = _weekly(session, acc.id, date(2026, 1, 1))
    occurrences.materialize_due(session, date(2026, 1, 1))
    loose = transactions.record_expense(
        session, acc.id, 30_000, "COP", date(2026, 1, 3), "Tienda", category_id=a_category(session, TxType.expense)
    )

    transactions.delete_transaction(session, loose.id)

    assert _all_occurrences(session, item.id)[0].status == OccurrenceStatus.posted


def _declared_late(session, acc_id, declared_on):
    """Weekly Netflix whose start is three weeks behind the day it was declared."""
    return recurring.create_recurring(
        session,
        name="Netflix",
        payee="Netflix",
        type=TxType.expense,
        mode=RecurringMode.auto,
        amount=25_900,
        currency="COP",
        category_id=a_category(session),
        account_id=acc_id,
        interval_unit=IntervalUnit.week,
        interval_count=1,
        start_date=date(2026, 1, 1),
        declared_on=declared_on,
    )


def test_declaring_with_a_start_already_behind_offers_and_charges_nothing(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = _declared_late(session, acc.id, declared_on=date(2026, 1, 22))

    assert occurrences.pending_dates(session, item.id) == [
        date(2026, 1, 1),
        date(2026, 1, 8),
        date(2026, 1, 15),
        date(2026, 1, 22),
    ]
    assert _live_occurrences(session, item.id) == []
    assert accounts.get_account(session, acc.id).balance == 500_000


def test_an_obligation_declared_before_its_start_offers_nothing(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = _declared_late(session, acc.id, declared_on=date(2026, 1, 1))

    assert occurrences.pending_dates(session, item.id) == []


def test_only_the_accepted_dates_become_charges(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = _declared_late(session, acc.id, declared_on=date(2026, 1, 22))
    offered = occurrences.pending_dates(session, item.id)

    occurrences.accept_pending_dates(session, item.id, offered[:2])

    assert len(_live_occurrences(session, item.id)) == 2
    assert accounts.get_account(session, acc.id).balance == 500_000 - 2 * 25_900


def test_an_accepted_date_keeps_its_own_real_date(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = _declared_late(session, acc.id, declared_on=date(2026, 1, 22))

    occurrences.accept_pending_dates(session, item.id, occurrences.pending_dates(session, item.id))

    assert [o.due_date for o in _live_occurrences(session, item.id)] == [
        date(2026, 1, 1),
        date(2026, 1, 8),
        date(2026, 1, 15),
        date(2026, 1, 22),
    ]
    assert [t.date for t in transactions.list_transactions(session, status="posted")] != []


def test_declined_dates_are_never_charged_and_never_offered_again(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = _declared_late(session, acc.id, declared_on=date(2026, 1, 22))

    occurrences.decline_pending_dates(session, item.id, occurrences.pending_dates(session, item.id))
    occurrences.materialize_due(session, date(2026, 1, 22))

    assert _live_occurrences(session, item.id) == []
    assert accounts.get_account(session, acc.id).balance == 500_000
    assert occurrences.pending_dates(session, item.id) == []


def test_declining_every_date_leaves_the_obligation_live_from_its_next_date(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = _declared_late(session, acc.id, declared_on=date(2026, 1, 22))
    occurrences.decline_pending_dates(session, item.id, occurrences.pending_dates(session, item.id))

    occurrences.materialize_due(session, date(2026, 1, 29))

    assert [o.due_date for o in _live_occurrences(session, item.id)] == [date(2026, 1, 29)]


def test_an_offered_date_is_not_charged_by_the_daily_run(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = _declared_late(session, acc.id, declared_on=date(2026, 1, 22))

    occurrences.materialize_due(session, date(2026, 1, 22))

    assert _live_occurrences(session, item.id) == []
    assert len(occurrences.pending_dates(session, item.id)) == 4


def test_moving_the_start_date_back_offers_the_dates_it_opens(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = declare_existing(
        session,
        name="Netflix",
        payee="Netflix",
        type=TxType.expense,
        mode=RecurringMode.auto,
        amount=25_900,
        currency="COP",
        category_id=a_category(session),
        account_id=acc.id,
        interval_unit=IntervalUnit.week,
        interval_count=1,
        start_date=date(2026, 1, 22),
    )
    occurrences.materialize_due(session, date(2026, 1, 22))

    recurring.update_recurring(session, item.id, start_date=date(2026, 1, 1), today=date(2026, 1, 22))

    assert occurrences.pending_dates(session, item.id) == [
        date(2026, 1, 1),
        date(2026, 1, 8),
        date(2026, 1, 15),
    ]
    assert len(_live_occurrences(session, item.id)) == 1


def test_skipping_an_already_skipped_date_changes_nothing(session):
    """The guard on the linked movement only ever sees a planned or a skipped
    one — AC-20 refuses a charged date before it gets here — so re-skipping is
    a no-op rather than a second downgrade."""
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = declare_existing(
        session,
        name="Arriendo",
        payee="Arriendo",
        type=TxType.expense,
        mode=RecurringMode.manual,
        amount=1_800_000,
        currency="COP",
        category_id=a_category(session),
        account_id=acc.id,
        interval_unit=IntervalUnit.month,
        interval_count=1,
        start_date=date(2026, 1, 1),
    )
    occurrences.materialize_due(session, date(2026, 1, 1))
    first = occurrences.skip(session, item.id, date(2026, 1, 1))

    again = occurrences.skip(session, item.id, date(2026, 1, 1))

    assert again.id == first.id
    assert again.status == OccurrenceStatus.skipped
    assert transactions.list_transactions(session, status="planned") == []
    assert len(transactions.list_transactions(session, status="skipped")) == 1
    assert accounts.get_account(session, acc.id).balance == 500_000


def test_deleting_a_transfer_leg_also_settles_any_due_date_behind_it(session):
    """The seam fires from `delete_transaction`, not from one deletion path.

    A recurring item can never be a transfer today, so this is not reachable
    through the engine — but the hook must not depend on which branch the
    delete takes, or the next feature that pairs rows inherits a silent hole.
    """
    from quaestor.domain.models import RecurringOccurrence
    from quaestor.services import occurrences as occ_svc

    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    dst = accounts.create_account(session, "Ahorros", AccountType.savings, "COP", balance=0)
    out_leg, _ = transactions.transfer(session, acc.id, dst.id, 50_000, "COP", date(2026, 1, 1))

    item = _weekly(session, acc.id, date(2026, 1, 1))
    session.add(
        RecurringOccurrence(
            recurring_id=item.id,
            due_date=date(2026, 1, 1),
            status=OccurrenceStatus.posted,
            transaction_id=out_leg.id,
        )
    )
    session.commit()

    transactions.delete_transaction(session, out_leg.id)

    settled = _all_occurrences(session, item.id)[0]
    assert settled.status == OccurrenceStatus.skipped
    assert settled.transaction_id is None
    assert occ_svc.pending_dates(session, item.id) == []


def test_answering_a_date_that_was_never_offered_is_refused(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = _declared_late(session, acc.id, declared_on=date(2026, 1, 22))

    with pytest.raises(ValidationError) as caught:
        occurrences.accept_pending_dates(session, item.id, [date(2026, 3, 4)])

    assert "2026-03-04" in str(caught.value)
    assert len(occurrences.pending_dates(session, item.id)) == 4


def test_declining_a_date_that_was_never_offered_is_refused(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = _declared_late(session, acc.id, declared_on=date(2026, 1, 22))

    with pytest.raises(ValidationError):
        occurrences.decline_pending_dates(session, item.id, [date(2026, 3, 4)])

    assert len(occurrences.pending_dates(session, item.id)) == 4


def test_dates_missed_to_downtime_survive_a_pause_that_follows(session):
    """The engine was down, then the user paused and resumed the same day.

    Resuming cannot tell which dates the outage lost and which the pause
    consumed, so it decides neither: both are offered. Before this, the pause
    wrote all of them off — 16.000 COP the user still owed, gone silently.
    """
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = _weekly(session, acc.id, date(2026, 1, 1))
    occurrences.materialize_due(session, date(2026, 1, 1))

    recurring.deactivate_recurring(session, item.id)
    recurring.restore_recurring(session, item.id, today=date(2026, 1, 22))

    assert occurrences.pending_dates(session, item.id) == [
        date(2026, 1, 8),
        date(2026, 1, 15),
    ]
    assert accounts.get_account(session, acc.id).balance == 500_000 - 8_000


def test_the_user_can_still_write_off_the_stretch_they_paused(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = _weekly(session, acc.id, date(2026, 1, 1))
    occurrences.materialize_due(session, date(2026, 1, 1))
    recurring.deactivate_recurring(session, item.id)
    recurring.restore_recurring(session, item.id, today=date(2026, 1, 22))

    occurrences.decline_pending_dates(session, item.id, occurrences.pending_dates(session, item.id))
    occurrences.materialize_due(session, date(2026, 1, 22))

    assert [o.due_date for o in _live_occurrences(session, item.id)] == [
        date(2026, 1, 1),
        date(2026, 1, 22),
    ]
    assert accounts.get_account(session, acc.id).balance == 500_000 - 2 * 8_000


def test_the_user_can_claim_back_what_the_outage_lost(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = _weekly(session, acc.id, date(2026, 1, 1))
    occurrences.materialize_due(session, date(2026, 1, 1))
    recurring.deactivate_recurring(session, item.id)
    recurring.restore_recurring(session, item.id, today=date(2026, 1, 22))

    occurrences.accept_pending_dates(session, item.id, occurrences.pending_dates(session, item.id))

    assert accounts.get_account(session, acc.id).balance == 500_000 - 3 * 8_000


def test_a_start_date_far_enough_back_to_flood_the_dialog_is_refused(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)

    with pytest.raises(ValidationError) as caught:
        recurring.create_recurring(
            session,
            name="Almuerzo",
            payee="Almuerzo",
            type=TxType.expense,
            mode=RecurringMode.auto,
            amount=8_000,
            currency="COP",
            category_id=a_category(session),
            account_id=acc.id,
            interval_unit=IntervalUnit.day,
            interval_count=1,
            start_date=date(2016, 1, 1),
            declared_on=date(2026, 1, 1),
        )

    message = str(caught.value)
    assert "3654" in message
    assert "60" in message


def test_the_refused_declaration_leaves_nothing_behind(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)

    with pytest.raises(ValidationError):
        recurring.create_recurring(
            session,
            name="Almuerzo",
            payee="Almuerzo",
            type=TxType.expense,
            mode=RecurringMode.auto,
            amount=8_000,
            currency="COP",
            category_id=a_category(session),
            account_id=acc.id,
            interval_unit=IntervalUnit.day,
            interval_count=1,
            start_date=date(2016, 1, 1),
            declared_on=date(2026, 1, 1),
        )

    assert recurring.list_recurring(session) == []
    assert accounts.get_account(session, acc.id).balance == 500_000


def test_a_long_but_answerable_history_is_still_allowed(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=5_000_000)

    item = recurring.create_recurring(
        session,
        name="Netflix",
        payee="Netflix",
        type=TxType.expense,
        mode=RecurringMode.auto,
        amount=25_900,
        currency="COP",
        category_id=a_category(session),
        account_id=acc.id,
        interval_unit=IntervalUnit.month,
        interval_count=1,
        start_date=date(2021, 2, 1),
        declared_on=date(2026, 1, 1),
    )

    assert len(occurrences.pending_dates(session, item.id)) == 60


def test_moving_the_start_back_too_far_is_refused_too(session):
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = declare_existing(
        session,
        name="Almuerzo",
        payee="Almuerzo",
        type=TxType.expense,
        mode=RecurringMode.auto,
        amount=8_000,
        currency="COP",
        category_id=a_category(session),
        account_id=acc.id,
        interval_unit=IntervalUnit.day,
        interval_count=1,
        start_date=date(2026, 1, 1),
    )

    with pytest.raises(ValidationError):
        recurring.update_recurring(session, item.id, start_date=date(2016, 1, 1), today=date(2026, 1, 1))


def test_accepting_dates_is_all_or_nothing(session, monkeypatch):
    """A button the user pressed either records every date or none of them.

    Per-charge commit (ADR-0036) is for the unattended daily run, where one
    broken obligation must not cost the others their day. Here the user is
    watching one obligation and pressed one button.
    """
    acc = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=500_000)
    item = _declared_late(session, acc.id, declared_on=date(2026, 1, 22))
    offered = occurrences.pending_dates(session, item.id)

    real = occurrences._create_occurrence_tx
    calls = {"n": 0}

    def explode_on_the_third(session_, item_, due_date, occ=None):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("the third one fails")
        return real(session_, item_, due_date, occ)

    monkeypatch.setattr(occurrences, "_create_occurrence_tx", explode_on_the_third)

    with pytest.raises(RuntimeError):
        occurrences.accept_pending_dates(session, item.id, offered)

    assert accounts.get_account(session, acc.id).balance == 500_000
    assert _live_occurrences(session, item.id) == []
    assert len(occurrences.pending_dates(session, item.id)) == 4
