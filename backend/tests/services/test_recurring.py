from datetime import date

import pytest
from quaestor.domain.errors import NotFound, ValidationError
from quaestor.domain.models import (
    Account,
    AccountType,
    IntervalUnit,
    RecurringItem,
    RecurringMode,
    Transaction,
    TxType,
)
from quaestor.services import accounts, occurrences, recurring, transactions
from sqlalchemy import event

from tests.support.categories import a_category
from tests.support.recurring import declare_existing


def _acc(session, currency="COP"):
    return accounts.create_account(session, "Bank", AccountType.debit, currency, balance=0)


def test_create_recurring_defaults_active(session):
    acc = _acc(session)
    item = declare_existing(
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
    assert item.id is not None and item.active is True
    assert item.interval_unit == IntervalUnit.month


def test_create_recurring_rejects_transfer_type(session):
    acc = _acc(session)
    with pytest.raises(ValidationError):
        declare_existing(
            session,
            name="X",
            payee="Y",
            type=TxType.transfer,
            mode=RecurringMode.auto,
            amount=1000,
            currency="COP",
            category_id=a_category(session),
            account_id=acc.id,
            interval_unit=IntervalUnit.month,
            interval_count=1,
            start_date=date(2026, 1, 1),
        )


def test_create_recurring_rejects_bad_interval_count(session):
    acc = _acc(session)
    with pytest.raises(ValidationError):
        declare_existing(
            session,
            name="X",
            payee="Y",
            type=TxType.expense,
            mode=RecurringMode.auto,
            amount=1000,
            currency="COP",
            category_id=a_category(session),
            account_id=acc.id,
            interval_unit=IntervalUnit.month,
            interval_count=0,
            start_date=date(2026, 1, 1),
        )


def test_create_recurring_rejects_non_positive_amount(session):
    acc = _acc(session)
    with pytest.raises(ValidationError):
        declare_existing(
            session,
            name="X",
            payee="Y",
            type=TxType.expense,
            mode=RecurringMode.auto,
            amount=0,
            currency="COP",
            category_id=a_category(session),
            account_id=acc.id,
            interval_unit=IntervalUnit.month,
            interval_count=1,
            start_date=date(2026, 1, 1),
        )


def test_create_recurring_rejects_end_before_start(session):
    acc = _acc(session)
    with pytest.raises(ValidationError):
        declare_existing(
            session,
            name="X",
            payee="Y",
            type=TxType.expense,
            mode=RecurringMode.auto,
            amount=1000,
            currency="COP",
            category_id=a_category(session),
            account_id=acc.id,
            interval_unit=IntervalUnit.month,
            interval_count=1,
            start_date=date(2026, 5, 1),
            end_date=date(2026, 1, 1),
        )


def test_create_recurring_unknown_account(session):
    with pytest.raises(NotFound):
        declare_existing(
            session,
            name="X",
            payee="Y",
            type=TxType.expense,
            mode=RecurringMode.auto,
            amount=1000,
            currency="COP",
            category_id=a_category(session),
            account_id=999,
            interval_unit=IntervalUnit.month,
            interval_count=1,
            start_date=date(2026, 1, 1),
        )


def test_create_recurring_currency_mismatch_raises(session):
    acc = accounts.create_account(session, "USD Account", AccountType.debit, "USD", balance=0)
    with pytest.raises(ValidationError):
        declare_existing(
            session,
            name="X",
            payee="Y",
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


def test_list_recurring_filters_by_active(session):
    acc = _acc(session)
    a = declare_existing(
        session,
        name="A",
        payee="p",
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
    b = declare_existing(
        session,
        name="B",
        payee="p",
        type=TxType.expense,
        mode=RecurringMode.manual,
        amount=1000,
        currency="COP",
        category_id=a_category(session),
        account_id=acc.id,
        interval_unit=IntervalUnit.week,
        interval_count=2,
        start_date=date(2026, 1, 1),
    )
    b.active = False
    session.add(b)
    session.commit()
    assert {i.id for i in recurring.list_recurring(session)} == {a.id, b.id}
    assert {i.id for i in recurring.list_recurring(session, active=True)} == {a.id}
    assert {i.id for i in recurring.list_recurring(session, active=False)} == {b.id}


def test_update_recurring_changes_amount_and_payee(session):
    acc = _acc(session)
    item = declare_existing(
        session,
        name="Rent",
        payee="LL",
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
    updated = recurring.update_recurring(session, item.id, amount=2_500_000, payee="New LL")
    assert updated.amount == 2_500_000 and updated.payee == "New LL"
    assert updated.currency == "COP"  # unchanged


def test_update_recurring_rejects_bad_interval(session):
    acc = _acc(session)
    item = declare_existing(
        session,
        name="X",
        payee="",
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
    with pytest.raises(ValidationError):
        recurring.update_recurring(session, item.id, interval_count=0)


def _netflix_on(session, account_id, amount=2_590_000, start=date(2026, 1, 1), mode=RecurringMode.auto):
    return declare_existing(
        session,
        name="Netflix",
        payee="Netflix",
        type=TxType.expense,
        mode=mode,
        amount=amount,
        currency="COP",
        category_id=a_category(session),
        account_id=account_id,
        interval_unit=IntervalUnit.month,
        interval_count=1,
        start_date=start,
    )


def test_a_turn_already_on_the_board_is_restated_one_at_a_time(session):
    """The route out of a turn left in the old currency (ADR-0052, feature 012).

    A manual charge puts its turn on the to-pay board before the money moves.
    Moving the obligation leaves that turn alone — it is a movement of its own by
    then — so `move_to_account` is what restates it, and nothing else does.
    """
    cop = accounts.create_account(session, "COP acct", AccountType.debit, "COP", balance=0)
    usd = accounts.create_account(session, "USD acct", AccountType.debit, "USD", balance=0)
    item = _netflix_on(session, cop.id, mode=RecurringMode.manual)
    january = occurrences.materialize_due(session, date(2026, 1, 1)).created[0]

    recurring.update_recurring(session, item.id, account_id=usd.id, amount=2935, currency="USD")
    waiting = session.get(Transaction, january.transaction_id)
    assert (waiting.currency, waiting.amount, waiting.account_id) == ("COP", 2_590_000, cop.id)

    corrected = transactions.move_to_account(session, waiting.id, account_id=usd.id, amount=2935)

    assert (corrected.currency, corrected.amount, corrected.account_id) == ("USD", 2935, usd.id)
    assert (session.get(Account, cop.id).balance, session.get(Account, usd.id).balance) == (0, 0)


def test_moving_a_charge_to_another_currency_needs_the_amount_restated_in_it(session):
    cop = accounts.create_account(session, "COP acct", AccountType.debit, "COP", balance=0)
    usd = accounts.create_account(session, "USD acct", AccountType.debit, "USD", balance=0)
    item = _netflix_on(session, cop.id)

    with pytest.raises(ValidationError, match="must be stated in USD"):
        recurring.update_recurring(session, item.id, account_id=usd.id)


def test_a_charge_that_waits_for_approval_keeps_its_price_across_the_move(session):
    """The price is the merchant's; only a self-paying charge has to follow its account (ADR-0053)."""
    cop = accounts.create_account(session, "COP acct", AccountType.debit, "COP", balance=0)
    usd = accounts.create_account(session, "USD acct", AccountType.debit, "USD", balance=0)
    item = _netflix_on(session, cop.id, mode=RecurringMode.manual)

    moved = recurring.update_recurring(session, item.id, account_id=usd.id)

    assert (moved.account_id, moved.currency, moved.amount) == (usd.id, "COP", 2_590_000)


def test_a_charge_moved_to_another_currency_is_stated_in_that_currency(session):
    cop = accounts.create_account(session, "COP acct", AccountType.debit, "COP", balance=0)
    usd = accounts.create_account(session, "USD acct", AccountType.debit, "USD", balance=0)
    item = _netflix_on(session, cop.id)

    moved = recurring.update_recurring(session, item.id, account_id=usd.id, amount=2935, currency="USD")

    assert (moved.account_id, moved.currency, moved.amount) == (usd.id, "USD", 2935)


def test_a_charge_that_stays_in_its_currency_still_moves_without_an_amount(session):
    first = accounts.create_account(session, "Nu", AccountType.debit, "COP", balance=0)
    second = accounts.create_account(session, "Bancolombia", AccountType.debit, "COP", balance=0)
    item = _netflix_on(session, first.id)

    moved = recurring.update_recurring(session, item.id, account_id=second.id)

    assert (moved.account_id, moved.currency, moved.amount) == (second.id, "COP", 2_590_000)


def test_future_turns_of_a_moved_charge_are_charged_in_the_new_currency(session):
    cop = accounts.create_account(session, "COP acct", AccountType.debit, "COP", balance=0)
    usd = accounts.create_account(session, "USD acct", AccountType.debit, "USD", balance=0)
    item = _netflix_on(session, cop.id)

    recurring.update_recurring(session, item.id, account_id=usd.id, amount=2935, currency="USD")
    created = occurrences.materialize_due(session, date(2026, 1, 1)).created

    charged = [session.get(Transaction, occ.transaction_id) for occ in created]
    assert [(tx.currency, tx.amount, tx.account_id) for tx in charged] == [("USD", 2935, usd.id)]


def test_a_turn_already_charged_keeps_the_currency_it_was_written_with(session):
    cop = accounts.create_account(session, "COP acct", AccountType.debit, "COP", balance=0)
    usd = accounts.create_account(session, "USD acct", AccountType.debit, "USD", balance=0)
    item = _netflix_on(session, cop.id)
    january = occurrences.materialize_due(session, date(2026, 1, 1)).created[0]

    recurring.update_recurring(session, item.id, account_id=usd.id, amount=2935, currency="USD")
    february = occurrences.materialize_due(session, date(2026, 2, 1)).created[0]

    already = session.get(Transaction, january.transaction_id)
    later = session.get(Transaction, february.transaction_id)
    assert (already.currency, already.amount, already.account_id) == ("COP", 2_590_000, cop.id)
    assert (later.currency, later.amount, later.account_id) == ("USD", 2935, usd.id)


def test_update_recurring_not_found(session):
    with pytest.raises(NotFound):
        recurring.update_recurring(session, 999, amount=1)


def test_deactivate_then_restore_recurring(session):
    acc = _acc(session)
    item = declare_existing(
        session,
        name="Rent",
        payee="",
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
    assert recurring.deactivate_recurring(session, item.id).active is False
    assert recurring.list_recurring(session, active=True) == []
    assert recurring.restore_recurring(session, item.id).active is True
    assert len(recurring.list_recurring(session, active=True)) == 1


def test_deactivate_recurring_not_found(session):
    with pytest.raises(NotFound):
        recurring.deactivate_recurring(session, 999)


def _income(session, acc_id, mode, **kw):
    return declare_existing(
        session,
        name="Salario",
        payee="Empresa",
        type=TxType.income,
        mode=mode,
        amount=4_500_000,
        currency="COP",
        category_id=a_category(session, TxType.income),
        account_id=acc_id,
        interval_unit=IntervalUnit.month,
        interval_count=1,
        start_date=date(2026, 1, 1),
        **kw,
    )


def test_a_repeating_income_that_waits_for_approval_is_refused(session):
    acc = _acc(session)
    with pytest.raises(ValidationError):
        _income(session, acc.id, RecurringMode.manual)


def test_a_repeating_income_that_pays_itself_is_accepted(session):
    acc = _acc(session)
    assert _income(session, acc.id, RecurringMode.auto).mode == RecurringMode.auto


def test_an_income_cannot_be_edited_into_waiting_for_approval(session):
    acc = _acc(session)
    item = _income(session, acc.id, RecurringMode.auto)
    with pytest.raises(ValidationError):
        recurring.update_recurring(session, item.id, mode=RecurringMode.manual)


def test_an_expense_may_still_wait_for_approval(session):
    acc = _acc(session)
    item = declare_existing(
        session,
        name="Arriendo",
        payee="Dueño",
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
    assert item.mode == RecurringMode.manual


def _ending(session, acc_id, end_date):
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
        start_date=date(2026, 1, 1),
        end_date=end_date,
    )


def test_an_obligation_past_its_end_date_leaves_the_live_list(session):
    acc = _acc(session)
    _ending(session, acc.id, date(2026, 1, 15))
    today = date(2026, 2, 1)

    assert recurring.list_recurring(session, active=True, today=today) == []
    assert [i.name for i in recurring.list_recurring(session, active=False, today=today)] == ["Gimnasio"]


def test_an_obligation_ending_today_is_still_live(session):
    acc = _acc(session)
    _ending(session, acc.id, date(2026, 1, 15))
    today = date(2026, 1, 15)

    assert [i.name for i in recurring.list_recurring(session, active=True, today=today)] == ["Gimnasio"]


def test_extending_the_end_date_brings_it_back(session):
    acc = _acc(session)
    item = _ending(session, acc.id, date(2026, 1, 15))
    today = date(2026, 2, 1)
    assert recurring.list_recurring(session, active=True, today=today) == []

    recurring.update_recurring(session, item.id, end_date=date(2026, 3, 1))

    assert [i.name for i in recurring.list_recurring(session, active=True, today=today)] == ["Gimnasio"]


def test_the_user_switching_it_off_stays_distinguishable_from_it_ending(session):
    acc = _acc(session)
    ended = _ending(session, acc.id, date(2026, 1, 15))
    off = declare_existing(
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
        start_date=date(2026, 1, 1),
    )
    recurring.deactivate_recurring(session, off.id)

    assert session.get(RecurringItem, ended.id).active is True
    assert session.get(RecurringItem, off.id).active is False


def _priced(session, account_id, *, amount, currency, name="Hevy Pro"):
    return declare_existing(
        session,
        name=name,
        payee=name,
        type=TxType.expense,
        mode=RecurringMode.manual,
        amount=amount,
        currency=currency,
        category_id=a_category(session),
        account_id=account_id,
        interval_unit=IntervalUnit.month,
        interval_count=1,
        start_date=date(2026, 1, 1),
    )


def _charge(session, account_id, *, amount, currency, recurring_id=None):
    tx = transactions.record_expense(
        session,
        account_id=account_id,
        amount=amount,
        currency=currency,
        date=date(2026, 7, 10),
        payee="Hevy Pro",
        category_id=a_category(session),
    )
    tx.recurring_id = recurring_id
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx


def test_a_charge_carries_the_price_of_the_rule_that_made_it(session):
    dolarapp = _acc(session, "USD")
    rule = _priced(session, dolarapp.id, amount=40_000_000, currency="COP")
    tx = _charge(session, dolarapp.id, amount=10_200, currency="USD", recurring_id=rule.id)

    assert recurring.prices_by_transaction(session, [tx]) == {tx.id: (40_000_000, "COP")}


def test_a_charge_whose_rule_agrees_with_it_carries_no_price(session):
    dolarapp = _acc(session, "USD")
    rule = _priced(session, dolarapp.id, amount=4_000, currency="USD", name="Opal")
    tx = _charge(session, dolarapp.id, amount=4_000, currency="USD", recurring_id=rule.id)

    assert recurring.prices_by_transaction(session, [tx]) == {}


def test_a_movement_that_came_from_no_rule_carries_no_price(session):
    dolarapp = _acc(session, "USD")
    tx = _charge(session, dolarapp.id, amount=2_500, currency="USD")

    assert recurring.prices_by_transaction(session, [tx]) == {}


def test_a_charge_from_a_rule_that_was_switched_off_carries_no_price(session):
    dolarapp = _acc(session, "USD")
    rule = _priced(session, dolarapp.id, amount=40_000_000, currency="COP")
    tx = _charge(session, dolarapp.id, amount=10_200, currency="USD", recurring_id=rule.id)
    recurring.deactivate_recurring(session, rule.id)

    assert recurring.prices_by_transaction(session, [tx]) == {}


def test_an_obligation_may_end_on_the_day_it_starts(session):
    """Only an end date *before* the start is refused (007 AC-18, 013 AC-16).

    Ending on the start date is how a single charge is declared: the end date is
    itself a due date, so that one turn still falls due.
    """
    acc = _acc(session)
    item = declare_existing(
        session,
        name="Hevy Pro",
        payee="Hevy Pro",
        type=TxType.expense,
        mode=RecurringMode.manual,
        amount=9_990_000,
        currency="COP",
        category_id=a_category(session),
        account_id=acc.id,
        interval_unit=IntervalUnit.year,
        interval_count=1,
        start_date=date(2026, 7, 15),
        end_date=date(2026, 7, 15),
    )

    created = occurrences.materialize_due(session, date(2026, 7, 15)).created

    assert item.end_date == item.start_date
    assert [occ.due_date for occ in created] == [date(2026, 7, 15)]


def test_an_edit_may_end_an_obligation_on_the_day_it_starts(session):
    """The same boundary on the editing door (007 AC-18, "the same rules hold when editing")."""
    acc = _acc(session)
    item = _netflix_on(session, acc.id)

    ended = recurring.update_recurring(session, item.id, end_date=item.start_date)

    assert ended.end_date == ended.start_date
    with pytest.raises(ValidationError):
        recurring.update_recurring(session, item.id, end_date=date(2025, 12, 31))


def test_the_price_an_edit_refuses_starts_at_zero_and_not_above_it(session):
    """Editing refuses a price of zero or below, and nothing above it (007 AC-18)."""
    acc = _acc(session)
    item = _netflix_on(session, acc.id)

    assert recurring.update_recurring(session, item.id, amount=1).amount == 1
    with pytest.raises(ValidationError):
        recurring.update_recurring(session, item.id, amount=0)


def test_the_cadence_can_be_edited_down_to_every_single_period(session):
    """Editing the cadence takes from the next due date onward (007 AC-14), and
    only a cadence below one period is refused (007 AC-18)."""
    acc = _acc(session)
    item = declare_existing(
        session,
        name="Smart Fit",
        payee="Smart Fit",
        type=TxType.expense,
        mode=RecurringMode.auto,
        amount=12_000_000,
        currency="COP",
        category_id=a_category(session),
        account_id=acc.id,
        interval_unit=IntervalUnit.month,
        interval_count=3,
        start_date=date(2026, 1, 1),
    )

    assert recurring.update_recurring(session, item.id, interval_count=1).interval_count == 1
    created = occurrences.materialize_due(session, date(2026, 3, 1)).created

    assert [occ.due_date for occ in created] == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]
    with pytest.raises(ValidationError):
        recurring.update_recurring(session, item.id, interval_count=0)


def test_an_edit_that_resubmits_the_same_start_date_offers_nothing(session):
    """Passed dates are offered when the start is *moved back* (007 AC-12).

    A form that sends every field back sends the start date unchanged too, so
    an ordinary price edit must not put the obligation's own turns up for a
    decision — that would take them off the engine's hands and out of to-pay.
    """
    acc = _acc(session)
    item = _netflix_on(session, acc.id, mode=RecurringMode.manual)

    recurring.update_recurring(
        session,
        item.id,
        amount=2_900_000,
        start_date=item.start_date,
        today=date(2026, 6, 1),
    )
    created = occurrences.materialize_due(session, date(2026, 6, 1)).created

    assert occurrences.pending_dates(session, item.id) == []
    assert len(created) == 6


def test_a_whole_page_of_charges_costs_one_read_of_the_rules(session):
    """A page of charges must not turn into one query per row (ADR-0028)."""
    dolarapp = _acc(session, "USD")
    rule = _priced(session, dolarapp.id, amount=40_000_000, currency="COP")
    txs = [
        _charge(session, dolarapp.id, amount=cents, currency="USD", recurring_id=rule.id)
        for cents in (10_200, 9_900, 10_050)
    ]
    reads = []

    def count(conn, cursor, statement, *rest):
        if "recurring_item" in statement.lower():
            reads.append(statement)

    engine = session.get_bind()
    event.listen(engine, "before_cursor_execute", count)
    try:
        prices = recurring.prices_by_transaction(session, txs)
    finally:
        event.remove(engine, "before_cursor_execute", count)

    assert prices == {tx.id: (40_000_000, "COP") for tx in txs}
    assert len(reads) == 1, f"a page of {len(txs)} charges read the rules {len(reads)} times"
