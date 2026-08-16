"""The funds service: what a fund asks, what it holds, and what it refuses."""

from datetime import date

import pytest
from quaestor.db import init_db, make_engine
from quaestor.domain.errors import MissingRate, NotFound, ValidationError
from quaestor.services import categories, funds, fx, planned, recurring, transactions
from quaestor.services import month as month_service
from sqlmodel import Session

from tests.support.query_counter import count_queries

SEEDED_TRM = "4200"
"""The rate a running app always carries — background state, not a subject.

Every fund read demands it on entry (ADR-0031), so a test that is not about
currency starts with one already set. A test that *is* about currency sets its
own, which overwrites this.
"""


@pytest.fixture
def session():
    engine = make_engine(memory=True)
    init_db(engine)
    with Session(engine) as s:
        fx.set_trm(s, SEEDED_TRM)
        yield s


@pytest.fixture
def engine_session():
    engine = make_engine(memory=True)
    init_db(engine)
    with Session(engine) as s:
        fx.set_trm(s, SEEDED_TRM)
        yield engine, s


def _clear_trm(session):
    """Take the app back to a fresh install, before any rate was ever set."""
    from quaestor.domain.models import Settings
    from sqlmodel import select

    for settings in session.exec(select(Settings)).all():
        settings.usd_cop = None
        session.add(settings)
    session.commit()


def _cat_id(cat) -> int:
    """The id, whether the fixture handed back the row or the id itself."""
    return cat.id if hasattr(cat, "id") else cat


def _category(session, name="Seguro", is_income=False):
    return categories.create_category(session, name, is_income=is_income).id


def _spend(session, category_id, amount, on):
    return transactions.record_expense(
        session, _default_account(session), amount, "COP", on, "Gasto", category_id=category_id
    )


def _category_named(session, name):
    """The id of a category this file already created, by name."""
    return next(cat.id for cat in categories.list_categories(session) if cat.name == name)


def _default_account(session):
    from quaestor.services import accounts

    existing = [a for a in accounts.list_accounts(session) if a.name == "Caja"]
    if existing:
        return existing[0].id
    return accounts.create_account(session, "Caja", "debit", "COP", balance=0).id


def _obligation(session, category_id, amount, start, unit="month", count=1, name="SOAT", currency="COP"):
    return recurring.create_recurring(
        session,
        name=name,
        payee=name,
        type="expense",
        mode="manual",
        amount=amount,
        currency=currency,
        category_id=category_id,
        account_id=_account_for(session, currency),
        interval_unit=unit,
        interval_count=count,
        start_date=start,
        declared_on=start,
    )


def _recurring_id(session, name):
    from quaestor.domain.models import RecurringItem
    from sqlmodel import select

    return session.exec(select(RecurringItem).where(RecurringItem.name == name)).first().id


def _post_the_charge(session, name, on, amount=None):
    """Take one obligation's turn all the way to posted, at its real amount.

    The path a real charge takes: the engine materializes the turn at what the
    obligation declared, and the owner confirms it with what the bill actually
    said.
    """
    from quaestor.domain.models import Transaction, TxStatus
    from quaestor.services.occurrences import materialize_due
    from sqlmodel import select

    materialize_due(session, on)
    charge = session.exec(
        select(Transaction).where(
            Transaction.recurring_id == _recurring_id(session, name),
            Transaction.status == TxStatus.planned,
        )
    ).first()
    return planned.confirm_payment(session, charge.id, amount=amount)


def _account_for(session, currency):
    from quaestor.services import accounts

    existing = [a for a in accounts.list_accounts(session) if a.currency == currency]
    if existing:
        return existing[0].id
    return accounts.create_account(session, f"Banco {currency}", "debit", currency, balance=0).id


# ------------------------------------------------------------------- asking


def test_a_fixed_fund_asks_its_amount_from_its_start_month(session):
    cat = _category(session, "Tecnologia")
    fund = funds.create_fund(session, cat, rule="fixed", amount=100_000_00, start_month="2026-11")
    assert funds.fund_status(session, fund.id, "2026-11").asks == 100_000_00


def test_a_fixed_fund_asks_nothing_before_its_start_month(session):
    cat = _category(session, "Tecnologia")
    fund = funds.create_fund(session, cat, rule="fixed", amount=100_000_00, start_month="2026-11")
    assert funds.fund_status(session, fund.id, "2026-09").asks == 0


def test_a_fixed_amount_does_not_move_with_spending(session):
    cat = _category(session, "Restaurantes")
    fund = funds.create_fund(session, cat, rule="fixed", amount=200_000_00, start_month="2026-11")
    _spend(session, cat, 350_000_00, date(2026, 11, 12))
    assert funds.fund_status(session, fund.id, "2026-11").asks == 200_000_00


def test_a_dated_obligation_spreads_over_the_months_that_remain(session):
    cat = _category(session)
    _obligation(session, cat, 447_300_00, date(2027, 5, 2), unit="year")
    fund = funds.create_fund(session, cat, rule="from-recurring", start_month="2026-11")
    status = funds.fund_status(session, fund.id, "2026-11")
    assert status.asks == 74_550_00
    assert status.spreads_over == 6
    assert status.whole_by == "2027-04"


def test_the_ask_recomputes_as_months_pass_and_as_the_fund_fills(session):
    cat = _category(session)
    _obligation(session, cat, 447_300_00, date(2027, 5, 2), unit="year")
    fund = funds.create_fund(session, cat, rule="from-recurring", start_month="2026-11")
    funds.set_fund(session, fund.id, balance=297_300_00)
    assert funds.fund_status(session, fund.id, "2027-01").asks == 37_500_00


def test_the_month_the_charge_lands_does_not_contribute(session):
    cat = _category(session)
    _obligation(session, cat, 447_300_00, date(2027, 5, 2), unit="year")
    fund = funds.create_fund(session, cat, rule="from-recurring", start_month="2026-11")
    funds.set_fund(session, fund.id, balance=447_300_00)
    status = funds.fund_status(session, fund.id, "2027-04")
    assert status.asks == 0
    assert status.on_track is True


def test_every_obligation_in_the_category_is_added_together(session):
    cat = _category(session, "Internet")
    for name, amount in (("Hogar", 85_000_00), ("Datos", 38_900_00), ("Datos Mama", 37_500_00)):
        _obligation(session, cat, amount, date(2026, 1, 5), name=name)
    fund = funds.create_fund(session, cat, rule="from-recurring", start_month="2026-11")
    assert funds.fund_status(session, fund.id, "2026-11").asks == 161_400_00


def test_obligations_of_different_cycles_are_each_brought_to_a_month(session):
    cat = _category(session, "Servicios")
    _obligation(session, cat, 250_000_00, date(2026, 1, 5), name="EPM")
    _obligation(session, cat, 600_000_00, date(2027, 11, 5), unit="year", name="Antivirus")
    fund = funds.create_fund(session, cat, rule="from-recurring", start_month="2026-11")
    assert funds.fund_status(session, fund.id, "2026-11").asks == 300_000_00


def test_a_drained_fund_raises_its_ask_and_says_it_is_behind(session):
    cat = _category(session)
    _obligation(session, cat, 7_200_000_00, date(2027, 5, 2), unit="year")
    fund = funds.create_fund(session, cat, rule="from-recurring", start_month="2026-11")
    funds.set_fund(session, fund.id, balance=3_600_000_00)
    _spend(session, cat, 3_600_000_00, date(2026, 11, 20))
    status = funds.fund_status(session, fund.id, "2026-11")
    assert status.asks == 1_200_000_00
    assert status.on_track is False


def test_a_fund_that_spent_past_everything_it_had_says_it_is_behind(session):
    cat = _category(session)
    fund = funds.create_fund(session, cat, rule="fixed", amount=300_000_00, start_month="2026-11")
    funds.set_fund(session, fund.id, balance=350_000_00)
    _spend(session, cat, 900_000_00, date(2026, 11, 20))
    assert funds.fund_status(session, fund.id, "2026-11").on_track is False


def test_a_fund_that_spent_every_peso_it_had_and_no_more_is_on_track(session):
    cat = _category(session)
    fund = funds.create_fund(session, cat, rule="fixed", amount=300_000_00, start_month="2026-11")
    funds.set_fund(session, fund.id, balance=350_000_00)
    _spend(session, cat, 650_000_00, date(2026, 11, 20))
    assert funds.fund_status(session, fund.id, "2026-11").on_track is True


def test_a_fund_opening_at_zero_can_still_say_it_is_behind(session):
    cat = _category(session)
    _obligation(session, _cat_id(cat), 8_000_000_00, date(2028, 12, 15), unit="year")
    fund = funds.create_fund(
        session,
        cat,
        rule="from-recurring",
        start_month="2026-11",
    )
    _spend(session, cat, 2_000_000_00, date(2026, 11, 20))
    assert funds.fund_status(session, fund.id, "2026-11").on_track is False


def test_a_fund_that_has_not_started_yet_does_not_swallow_the_spending(session):
    cat = _category(session)
    fund = funds.create_fund(session, cat, rule="fixed", amount=300_000_00, start_month="2027-01")
    _spend(session, cat, 900_000_00, date(2026, 11, 20))
    assert funds.fund_status(session, fund.id, "2026-11").on_track is False


def test_a_charge_still_standing_this_month_is_the_one_the_fund_is_filling(session):
    cat = _category(session)
    _obligation(session, cat, 447_300_00, date(2027, 5, 2), unit="year")
    fund = funds.create_fund(session, cat, rule="from-recurring", start_month="2026-11")
    status = funds.fund_status(session, fund.id, "2027-05")
    assert status.whole_by == "2027-04"
    assert status.holds == 447_300_00
    assert status.asks == 0


def test_a_charge_landing_this_month_that_nothing_saved_for_asks_for_all_of_it(session):
    cat = _category(session)
    _obligation(session, cat, 447_300_00, date(2027, 5, 2), unit="year")
    fund = funds.create_fund(session, cat, rule="from-recurring", start_month="2027-05")
    assert funds.fund_status(session, fund.id, "2027-05").asks == 447_300_00


def test_the_next_cycle_begins_once_the_fund_has_paid(session):
    cat = _category(session)
    _obligation(session, cat, 447_300_00, date(2027, 5, 2), unit="year")
    fund = funds.create_fund(session, cat, rule="from-recurring", start_month="2026-11")
    funds.set_fund(session, fund.id, balance=447_300_00)
    _spend(session, cat, 447_300_00, date(2027, 5, 10))
    status = funds.fund_status(session, fund.id, "2027-05")
    assert status.whole_by == "2028-04"
    assert status.holds == 0


def test_a_skipped_charge_lowers_what_its_fund_asks_that_month(session):
    cat = _category(session, "Internet")
    for name, amount in (("Hogar", 85_000_00), ("Datos", 38_900_00), ("Datos Mama", 37_500_00)):
        _obligation(session, cat, amount, date(2026, 11, 5), name=name)
    fund = funds.create_fund(session, cat, rule="from-recurring", start_month="2026-11")
    recurring.skip_recurring(session, _recurring_id(session, "Datos Mama"), date(2026, 11, 5))
    assert funds.fund_status(session, fund.id, "2026-11").asks == 123_900_00


def test_the_month_after_a_skipped_charge_asks_the_full_amount_again(session):
    cat = _category(session, "Internet")
    _obligation(session, cat, 37_500_00, date(2026, 11, 5), name="Datos Mama")
    fund = funds.create_fund(session, cat, rule="from-recurring", start_month="2026-11")
    recurring.skip_recurring(session, _recurring_id(session, "Datos Mama"), date(2026, 11, 5))
    assert funds.fund_status(session, fund.id, "2026-12").asks == 37_500_00


def test_the_average_divides_by_the_months_the_app_has_data_for(session):
    cat = _category(session, "Servicios")
    _spend(session, cat, 200_000_00, date(2026, 9, 10))
    _spend(session, cat, 100_000_00, date(2026, 10, 10))
    fund = funds.create_fund(session, cat, rule="average", window_months=12, start_month="2026-11")
    status = funds.fund_status(session, fund.id, "2026-11")
    assert status.asks == 150_000_00
    assert status.averaged_over == 2


def test_a_month_inside_the_window_with_no_spending_counts_as_zero(session):
    history = _category(session, "Historia")
    _spend(session, history, 100, date(2026, 6, 10))
    cat = _category(session, "Cursos")
    _spend(session, cat, 300_000_00, date(2026, 9, 10))
    fund = funds.create_fund(session, cat, rule="average", window_months=3, start_month="2026-11")
    status = funds.fund_status(session, fund.id, "2026-11")
    assert status.asks == 100_000_00
    assert status.averaged_over == 3


def test_the_current_month_does_not_average_itself(session):
    history = _category(session, "Historia")
    _spend(session, history, 100, date(2026, 6, 10))
    cat = _category(session, "Mercado")
    _spend(session, cat, 300_000_00, date(2026, 10, 10))
    _spend(session, cat, 900_000_00, date(2026, 11, 10))
    fund = funds.create_fund(session, cat, rule="average", window_months=3, start_month="2026-11")
    assert funds.fund_status(session, fund.id, "2026-11").asks == 100_000_00


def test_a_dollar_obligation_is_asked_for_in_cop(session):
    fx.set_trm(session, "4000")
    cat = _category(session, "Gimnasio")
    _obligation(session, cat, 30_00, date(2026, 1, 5), name="Smart Fit", currency="USD")
    fund = funds.create_fund(session, cat, rule="from-recurring", start_month="2026-11")
    assert funds.fund_status(session, fund.id, "2026-11").asks == 120_000_00


def test_a_fund_cannot_be_read_without_a_rate_even_in_pure_cop(session):
    cat = _category(session, "Tecnologia")
    fund = funds.create_fund(session, cat, rule="fixed", amount=100_000_00, start_month="2026-11")
    _clear_trm(session)
    with pytest.raises(MissingRate):
        funds.fund_status(session, fund.id, "2026-11")


# ------------------------------------------------------------------ holding


def test_an_accumulating_fund_carries_its_balance_into_the_next_month(session):
    cat = _category(session, "Tecnologia")
    fund = funds.create_fund(session, cat, rule="fixed", amount=100_000_00, start_month="2026-11", accumulates=True)
    assert funds.fund_status(session, fund.id, "2026-12").holds == 100_000_00


def test_a_resetting_fund_starts_each_month_fresh(session):
    cat = _category(session, "Restaurantes")
    fund = funds.create_fund(session, cat, rule="fixed", amount=200_000_00, start_month="2026-11", accumulates=False)
    assert funds.fund_status(session, fund.id, "2026-12").holds == 0


def test_an_accumulating_fund_overspent_falls_to_zero_not_below(session):
    cat = _category(session, "Tecnologia")
    fund = funds.create_fund(session, cat, rule="fixed", amount=100_000_00, start_month="2026-11", accumulates=True)
    _spend(session, cat, 400_000_00, date(2026, 11, 12))
    assert funds.fund_status(session, fund.id, "2026-12").holds == 0


def test_the_opening_balance_counts_toward_what_the_fund_still_needs(session):
    cat = _category(session, "Ahorro Viaje")
    _obligation(session, _cat_id(cat), 3_000_000_00, date(2027, 5, 15), unit="year")
    fund = funds.create_fund(
        session,
        cat,
        rule="from-recurring",
        start_month="2026-11",
        opening_balance=1_200_000_00,
    )
    status = funds.fund_status(session, fund.id, "2026-11")
    assert status.holds == 1_200_000_00
    assert status.asks == 300_000_00


def test_a_stated_opening_balance_still_seeds_the_fold_in_a_later_month(session):
    cat = _category(session, "Ahorro Viaje")
    _obligation(session, _cat_id(cat), 3_000_000_00, date(2027, 5, 15), unit="year")
    fund = funds.create_fund(
        session,
        cat,
        rule="from-recurring",
        start_month="2026-11",
        opening_balance=1_200_000_00,
    )
    assert funds.fund_status(session, fund.id, "2026-12").holds == 1_500_000_00


def test_the_fund_never_reads_an_account_balance(session):
    from quaestor.services import accounts

    accounts.create_account(session, "Ahorros", "savings", "COP", balance=9_000_000_00)
    cat = _category(session, "Ahorro Viaje")
    _obligation(session, _cat_id(cat), 3_000_000_00, date(2027, 5, 15), unit="year")
    fund = funds.create_fund(
        session,
        cat,
        rule="from-recurring",
        start_month="2026-11",
        opening_balance=1_200_000_00,
    )
    assert funds.fund_status(session, fund.id, "2026-11").holds == 1_200_000_00


def test_a_fund_saving_toward_a_date_accumulates_without_being_asked(session):
    cat = _category(session, "Ahorro Viaje")
    _obligation(session, _cat_id(cat), 3_000_000_00, date(2027, 5, 15), unit="year")
    fund = funds.create_fund(
        session,
        cat,
        rule="from-recurring",
        start_month="2026-11",
    )
    status = funds.fund_status(session, fund.id, "2026-11")
    assert status.accumulates is True
    assert status.accumulation_is_implied is True


# ------------------------------------------------------ what next month gets


def test_a_fund_reports_what_its_category_spent_that_month(session):
    cat = _category(session, "Tecnologia")
    fund = funds.create_fund(session, cat, rule="fixed", amount=100_000_00, start_month="2026-11")
    _spend(session, cat, 60_000_00, date(2026, 11, 10))
    assert funds.fund_status(session, fund.id, "2026-11").spent == 60_000_00


def test_an_accumulating_fund_carries_what_the_month_did_not_spend(session):
    cat = _category(session, "Tecnologia")
    fund = funds.create_fund(session, cat, rule="fixed", amount=100_000_00, start_month="2026-11")
    _spend(session, cat, 60_000_00, date(2026, 11, 10))
    status = funds.fund_status(session, fund.id, "2026-11")
    assert status.carries == 40_000_00
    assert status.next_month_has == 140_000_00


def test_a_resetting_fund_carries_nothing_and_next_month_only_asks(session):
    cat = _category(session, "Restaurantes")
    fund = funds.create_fund(session, cat, rule="fixed", amount=100_000_00, start_month="2026-11", accumulates=False)
    _spend(session, cat, 60_000_00, date(2026, 11, 10))
    status = funds.fund_status(session, fund.id, "2026-11")
    assert status.carries == 0
    assert status.next_month_has == 100_000_00


def test_the_carry_never_goes_negative_however_far_the_month_overspends(session):
    cat = _category(session, "Tecnologia")
    fund = funds.create_fund(session, cat, rule="fixed", amount=100_000_00, start_month="2026-11")
    _spend(session, cat, 500_000_00, date(2026, 11, 10))
    status = funds.fund_status(session, fund.id, "2026-11")
    assert status.carries == 0
    assert status.next_month_has == 100_000_00


def test_a_dated_fund_asks_next_month_against_what_it_will_hold_by_then(session):
    cat = _category(session, "Ahorro Viaje")
    _obligation(session, _cat_id(cat), 600_000_00, date(2027, 5, 15), unit="year")
    fund = funds.create_fund(
        session,
        cat,
        rule="from-recurring",
        start_month="2026-11",
    )
    status = funds.fund_status(session, fund.id, "2026-11")
    assert status.asks == 100_000_00
    assert status.carries == 100_000_00
    assert status.next_month_has == 200_000_00


def test_an_averaging_fund_looks_ahead_with_the_window_shifted_one_month(session):
    cat = _category(session, "Mercado")
    _spend(session, cat, 300_000_00, date(2026, 8, 10))
    _spend(session, cat, 300_000_00, date(2026, 9, 10))
    _spend(session, cat, 300_000_00, date(2026, 10, 10))
    fund = funds.create_fund(session, cat, rule="average", window_months=3, start_month="2026-11")
    _spend(session, cat, 100_000_00, date(2026, 11, 10))
    status = funds.fund_status(session, fund.id, "2026-11")
    assert status.asks == 300_000_00
    assert status.carries == 200_000_00
    assert status.next_month_has == 433_333_34


def test_a_fund_that_has_not_started_reports_nothing_for_next_month_either(session):
    cat = _category(session, "Seguro")
    fund = funds.create_fund(session, cat, rule="fixed", amount=100_000_00, start_month="2027-01")
    status = funds.fund_status(session, fund.id, "2026-08")
    assert status.carries == 0
    assert status.next_month_has == 0


def test_the_month_before_a_fund_starts_already_reports_what_it_will_have(session):
    cat = _category(session, "Seguro")
    fund = funds.create_fund(session, cat, rule="fixed", amount=100_000_00, start_month="2027-01")
    status = funds.fund_status(session, fund.id, "2026-12")
    assert status.asks == 0
    assert status.carries == 0
    assert status.next_month_has == 100_000_00


def test_a_stated_balance_is_what_next_month_builds_on(session):
    cat = _category(session, "Tecnologia")
    fund = funds.create_fund(session, cat, rule="fixed", amount=100_000_00, start_month="2026-11")
    funds.set_fund(session, fund.id, balance=500_000_00)
    status = funds.fund_status(session, fund.id, "2026-11")
    assert status.carries == 600_000_00
    assert status.next_month_has == 700_000_00


def test_a_fund_that_starts_next_month_already_carries_the_balance_it_was_given(session):
    cat = _category(session, "Tecnologia")
    fund = funds.create_fund(
        session, cat, rule="fixed", amount=100_000_00, start_month="2026-12", opening_balance=500_000_00
    )
    status = funds.fund_status(session, fund.id, "2026-11")
    assert status.holds == 0
    assert status.carries == 500_000_00
    assert status.next_month_has == 600_000_00


def test_a_balance_stated_on_a_fund_two_months_out_carries_nothing_yet(session):
    cat = _category(session, "Tecnologia")
    fund = funds.create_fund(session, cat, rule="fixed", amount=100_000_00, start_month="2027-01")
    funds.set_fund(session, fund.id, balance=500_000_00)
    status = funds.fund_status(session, fund.id, "2026-11")
    assert status.carries == 0
    assert status.next_month_has == 0


def test_a_fund_whose_target_falls_next_month_asks_the_whole_thing_and_is_on_track(session):
    cat = _category(session, "Ahorro Viaje")
    _obligation(session, _cat_id(cat), 600_000_00, date(2026, 12, 15), unit="year")
    fund = funds.create_fund(
        session,
        cat,
        rule="from-recurring",
        start_month="2026-11",
    )
    status = funds.fund_status(session, fund.id, "2026-11")
    assert status.asks == 600_000_00
    assert status.on_track is True


# ----------------------------------------------------------------- refusing


def test_a_fund_on_an_income_category_is_refused(session):
    cat = _category(session, "Salario", is_income=True)
    with pytest.raises(ValidationError, match="going out"):
        funds.create_fund(session, cat, rule="fixed", amount=100_000_00, start_month="2026-11")


def test_a_second_fund_on_the_same_category_is_refused_naming_it(session):
    cat = _category(session, "Restaurantes")
    funds.create_fund(session, cat, rule="fixed", amount=200_000_00, start_month="2026-11")
    with pytest.raises(ValidationError, match="Restaurantes"):
        funds.create_fund(session, cat, rule="average", window_months=3, start_month="2026-11")


def test_averaging_a_category_with_no_spending_at_all_is_refused(session):
    cat = _category(session, "Reembolsable")
    with pytest.raises(ValidationError, match="fixed"):
        funds.create_fund(session, cat, rule="average", window_months=3, start_month="2026-11")


def test_spending_only_in_the_month_the_fund_starts_does_not_count_as_history(session):
    cat = _category(session, "Peajes")
    _spend(session, cat, 90_000_00, date(2026, 11, 10))
    with pytest.raises(ValidationError):
        funds.create_fund(session, cat, rule="average", window_months=3, start_month="2026-11")


def test_a_fund_saving_toward_a_date_refuses_to_reset(session):
    cat = _category(session, "Ahorro Viaje")
    with pytest.raises(ValidationError, match="accumulate"):
        funds.create_fund(
            session,
            cat,
            rule="from-recurring",
            start_month="2026-11",
            accumulates=False,
        )


def test_a_category_holding_a_fund_cannot_be_archived(session):
    cat = _category(session)
    funds.create_fund(session, cat, rule="fixed", amount=100_000_00, start_month="2026-11")
    with pytest.raises(ValidationError, match="fund"):
        categories.archive_category(session, cat)


def test_the_category_archives_once_its_fund_is_gone(session):
    cat = _category(session)
    fund = funds.create_fund(session, cat, rule="fixed", amount=100_000_00, start_month="2026-11")
    funds.delete_fund(session, fund.id)
    assert categories.archive_category(session, cat).archived is True


def test_a_fund_that_does_not_exist_is_reported_as_missing(session):
    with pytest.raises(NotFound):
        funds.fund_status(session, 999_999, "2026-11")


# ----------------------------------------------------------- listing, preview


def test_the_app_starts_with_no_funds_at_all(session):
    cat = _category(session, "Internet")
    _obligation(session, cat, 85_000_00, date(2026, 1, 5), name="Hogar")
    assert funds.list_funds(session) == []


def test_a_listed_fund_names_its_category(session):
    cat = _category(session, "Restaurantes")
    funds.create_fund(session, cat, rule="fixed", amount=200_000_00, start_month="2026-11")
    assert [line.name for line in funds.list_funds(session)] == ["Restaurantes"]


def test_an_implausible_target_is_announced_with_its_figure_before_the_fund_exists(session):
    cat = _category(session, "Ahorro Viaje")
    _obligation(session, cat, 10_000_000_00, date(2026, 8, 20), unit="year")
    preview = funds.preview_fund(
        session,
        cat,
        rule="from-recurring",
        start_month="2026-08",
    )
    assert preview.would_ask == 10_000_000_00
    assert preview.warning is not None
    assert funds.list_funds(session) == []


def test_a_reachable_target_is_previewed_without_a_warning(session):
    cat = _category(session, "Ahorro Viaje")
    _obligation(session, cat, 3_000_000_00, date(2027, 8, 20), unit="year")
    preview = funds.preview_fund(
        session,
        cat,
        rule="from-recurring",
        start_month="2026-08",
    )
    assert preview.would_ask == 250_000_00
    assert preview.warning is None


# ------------------------------------------------------------- the read path


def test_a_fund_reading_stays_bounded_no_matter_how_many_months_it_folds(engine_session):
    engine, session = engine_session
    cat = _category(session, "Seguro")
    _obligation(session, cat, 447_300_00, date(2027, 5, 2), unit="year")
    fund = funds.create_fund(session, cat, rule="from-recurring", start_month="2026-01")
    for month in range(1, 13):
        _spend(session, cat, 1_000_00, date(2026, month, 10))
    with count_queries(engine) as counted:
        funds.fund_status(session, fund.id, "2026-12")
    assert counted.count <= 16, f"fund_status issued {counted.count} queries"


# -------------------------------------------------------- the month's number


def _income_obligation(session, category_id, amount, start, unit="month", count=1, name="Empresa", currency="COP"):
    return recurring.create_recurring(
        session,
        name=name,
        payee=name,
        type="income",
        mode="auto",
        amount=amount,
        currency=currency,
        category_id=category_id,
        account_id=_account_for(session, currency),
        interval_unit=unit,
        interval_count=count,
        start_date=start,
        declared_on=start,
    )


def _earn(session, category_id, amount, on, payee="Empresa"):
    return transactions.record_income(
        session, _account_for(session, "COP"), amount, "COP", on, payee, category_id=category_id
    )


def _salario(session):
    cat = _category(session, "Salario", is_income=True)
    _income_obligation(session, cat, 5_000_000_00, date(2026, 1, 5))
    return cat


def test_an_income_category_with_nothing_recorded_counts_what_it_promises(session):
    _salario(session)
    assert month_service.available(session, "2026-11").income == 5_000_000_00


def test_what_arrived_replaces_what_the_category_promised(session):
    cat = _salario(session)
    _earn(session, cat, 4_200_000_00, date(2026, 11, 20))
    assert month_service.available(session, "2026-11").income == 4_200_000_00


def test_a_category_stops_guessing_for_every_obligation_it_holds(session):
    """The declared boundary of ADR-0044: per category, never per obligation."""
    cat = _salario(session)
    _income_obligation(session, cat, 2_000_000_00, date(2026, 1, 5), name="Socio")
    assert month_service.available(session, "2026-11").income == 7_000_000_00
    _earn(session, cat, 4_200_000_00, date(2026, 11, 20))
    assert month_service.available(session, "2026-11").income == 4_200_000_00


def test_money_with_no_obligation_behind_it_counts_from_the_moment_it_is_recorded(session):
    cat = _category(session, "Rendimientos", is_income=True)
    _earn(session, cat, 250_000_00, date(2026, 11, 10), payee="Banco")
    assert month_service.available(session, "2026-11").income == 250_000_00


def test_a_quarterly_income_counts_nothing_until_the_month_it_is_due(session):
    cat = _category(session, "Bonos", is_income=True)
    _income_obligation(session, cat, 3_000_000_00, date(2026, 9, 30), count=3, name="Bono")
    assert month_service.available(session, "2026-08").free == 0
    assert month_service.available(session, "2026-09").free == 3_000_000_00


def test_only_the_excess_past_a_fund_leaves_the_money_available(session):
    _salario(session)
    cat = _category(session, "Restaurantes")
    funds.create_fund(session, cat, rule="fixed", amount=200_000_00, start_month="2026-11")
    _spend(session, cat, 350_000_00, date(2026, 11, 12))
    view = month_service.available(session, "2026-11")
    assert view.uncovered == 150_000_00
    assert view.free == 4_650_000_00


def test_spending_no_fund_covers_comes_straight_out_of_the_money_available(session):
    _salario(session)
    loose = _category(session, "Transporte")
    _spend(session, loose, 150_000_00, date(2026, 11, 12))
    assert month_service.available(session, "2026-11").free == 4_850_000_00


def test_an_obligation_no_fund_covers_is_uncovered_too(session):
    _salario(session)
    cat = _category(session, "Arriendo")
    _obligation(session, cat, 1_000_000_00, date(2026, 1, 5), name="Arrendador")
    view = month_service.available(session, "2026-11")
    assert view.uncovered == 1_000_000_00
    assert view.free == 4_000_000_00


def test_a_charge_that_posts_above_its_promise_costs_the_month_what_it_really_was(session):
    _salario(session)
    cat = _category(session, "Servicios")
    _obligation(session, cat, 200_000_00, date(2026, 11, 5), name="EPM")
    _post_the_charge(session, "EPM", date(2026, 11, 12), amount=250_000_00)
    view = month_service.available(session, "2026-11")
    assert view.uncovered == 250_000_00
    assert view.free == 4_750_000_00


def test_a_charge_that_posts_below_its_promise_gives_the_difference_back(session):
    _salario(session)
    cat = _category(session, "Servicios")
    _obligation(session, cat, 200_000_00, date(2026, 11, 5), name="EPM")
    _post_the_charge(session, "EPM", date(2026, 11, 12), amount=150_000_00)
    view = month_service.available(session, "2026-11")
    assert view.uncovered == 150_000_00
    assert view.free == 4_850_000_00


def test_an_obligation_switched_off_after_paying_still_costs_the_month(session):
    _salario(session)
    cat = _category(session, "Servicios")
    _obligation(session, cat, 200_000_00, date(2026, 11, 5), name="EPM")
    _post_the_charge(session, "EPM", date(2026, 11, 12))
    recurring.deactivate_recurring(session, _recurring_id(session, "EPM"))
    view = month_service.available(session, "2026-11")
    assert view.uncovered == 200_000_00
    assert view.free == 4_800_000_00


def test_a_charge_still_ahead_keeps_counting_what_it_promised(session):
    _salario(session)
    cat = _category(session, "Servicios")
    _obligation(session, cat, 200_000_00, date(2026, 11, 5), name="EPM")
    view = month_service.available(session, "2026-11")
    assert view.uncovered == 200_000_00
    assert view.free == 4_800_000_00


def test_a_posted_charge_is_counted_once_not_twice(session):
    _salario(session)
    cat = _category(session, "Servicios")
    _obligation(session, cat, 200_000_00, date(2026, 11, 5), name="EPM")
    _post_the_charge(session, "EPM", date(2026, 11, 12))
    view = month_service.available(session, "2026-11")
    assert view.uncovered == 200_000_00


def test_only_the_turn_that_posted_stops_being_promised(session):
    from quaestor.domain.models import IntervalUnit
    from quaestor.domain.recurrence import due_dates

    _salario(session)
    cat = _category(session, "Servicios")
    _obligation(session, cat, 100_000_00, date(2026, 11, 3), unit="week", count=1, name="Aseo")
    _post_the_charge(session, "Aseo", date(2026, 11, 3), amount=120_000_00)
    turns = len(due_dates(date(2026, 11, 3), None, IntervalUnit.week, 1, date(2026, 11, 1), date(2026, 11, 30)))
    assert turns > 1
    assert month_service.available(session, "2026-11").uncovered == 120_000_00 + (turns - 1) * 100_000_00


def test_the_breakdown_names_every_fund_and_adds_up_exactly(session):
    _salario(session)
    restaurantes = _category(session, "Restaurantes")
    mercado = _category(session, "Mercado")
    funds.create_fund(session, restaurantes, rule="fixed", amount=200_000_00, start_month="2026-11")
    funds.create_fund(session, mercado, rule="fixed", amount=300_000_00, start_month="2026-11")
    _spend(session, _category(session, "Transporte"), 150_000_00, date(2026, 11, 12))
    view = month_service.available(session, "2026-11")
    assert {line.name: line.asks for line in view.funds} == {"Restaurantes": 200_000_00, "Mercado": 300_000_00}
    assert view.income - sum(line.asks for line in view.funds) - view.uncovered == view.free
    assert view.free == 4_350_000_00


def test_a_fund_asking_nothing_this_month_is_still_named(session):
    cat = _category(session, "Seguro")
    funds.create_fund(session, cat, rule="fixed", amount=100_000_00, start_month="2027-01")
    view = month_service.available(session, "2026-11")
    assert [(line.name, line.asks) for line in view.funds] == [("Seguro", 0)]


def test_the_money_available_cannot_be_read_without_a_rate_even_in_pure_cop(session):
    _category(session, "Gimnasio")
    _clear_trm(session)
    with pytest.raises(MissingRate):
        month_service.available(session, "2026-11")


def test_the_earning_rate_smooths_a_quarterly_income_across_its_cycle(session):
    _salario(session)
    bonos = _category(session, "Bonos", is_income=True)
    _income_obligation(session, bonos, 3_000_000_00, date(2026, 9, 30), count=3, name="Bono")
    assert month_service.rates(session, "2026-08").earning == 6_000_000_00
    assert month_service.rates(session, "2026-09").earning == 6_000_000_00


def test_the_rate_and_the_balance_differ_when_a_quarterly_income_has_not_landed(session):
    _salario(session)
    bonos = _category(session, "Bonos", is_income=True)
    _income_obligation(session, bonos, 3_000_000_00, date(2026, 9, 30), count=3, name="Bono")
    assert month_service.rates(session, "2026-08").earning == 6_000_000_00
    assert month_service.available(session, "2026-08").free == 5_000_000_00


def test_the_cost_rate_is_every_fund_ask_plus_the_obligations_no_fund_covers(session):
    restaurantes = _category(session, "Restaurantes")
    funds.create_fund(session, restaurantes, rule="fixed", amount=200_000_00, start_month="2026-11")
    arriendo = _category(session, "Arriendo")
    _obligation(session, arriendo, 1_000_000_00, date(2026, 1, 5), name="Arrendador")
    assert month_service.rates(session, "2026-11").cost == 1_200_000_00


def test_an_obligation_a_fund_covers_is_not_counted_in_the_cost_rate_twice(session):
    cat = _category(session, "Internet")
    _obligation(session, cat, 85_000_00, date(2026, 1, 5), name="Internet Hogar")
    funds.create_fund(session, cat, rule="from-recurring", start_month="2026-11")
    assert month_service.rates(session, "2026-11").cost == 85_000_00


def test_the_margin_is_what_the_earning_rate_leaves_after_the_cost_rate(session):
    _salario(session)
    cat = _category(session, "Restaurantes")
    funds.create_fund(session, cat, rule="fixed", amount=200_000_00, start_month="2026-11")
    rates = month_service.rates(session, "2026-11")
    assert (rates.earning, rates.cost, rates.margin) == (5_000_000_00, 200_000_00, 4_800_000_00)


def test_the_month_number_reads_the_month_asked_about_not_a_stored_one(session):
    cat = _salario(session)
    _income_obligation(session, cat, 2_000_000_00, date(2026, 1, 5), name="Socio")
    month_service.available(session, "2026-09")
    recurring.deactivate_recurring(session, _recurring_id(session, "Socio"))
    assert month_service.available(session, "2026-09").income == 5_000_000_00


def test_the_month_number_stays_bounded_however_many_funds_it_walks(engine_session):
    engine, session = engine_session
    _salario(session)
    for index in range(6):
        cat = _category(session, f"Fondo {index}")
        funds.create_fund(session, cat, rule="fixed", amount=100_000_00, start_month="2026-01")
        _spend(session, cat, 10_000_00, date(2026, 6, 10))
    with count_queries(engine) as counted:
        month_service.available(session, "2026-11")
    assert counted.count <= 16, f"available issued {counted.count} queries"


# ---------------------------------------------- boundaries the mutation sweep found


def test_a_fixed_fund_with_no_amount_at_all_is_refused(session):
    cat = _category(session, "Tecnologia")
    with pytest.raises(ValidationError, match="above zero"):
        funds.create_fund(session, cat, rule="fixed", start_month="2026-11")


def test_a_fixed_fund_asking_exactly_zero_is_refused(session):
    cat = _category(session, "Tecnologia")
    with pytest.raises(ValidationError, match="above zero"):
        funds.create_fund(session, cat, rule="fixed", amount=0, start_month="2026-11")


def test_a_fixed_fund_may_ask_a_single_centavo(session):
    cat = _category(session, "Tecnologia")
    fund = funds.create_fund(session, cat, rule="fixed", amount=1, start_month="2026-11")
    assert funds.fund_status(session, fund.id, "2026-11").asks == 1


def test_an_average_fund_with_no_window_at_all_is_refused(session):
    cat = _category(session, "Mercado")
    _spend(session, cat, 100_000_00, date(2026, 10, 5))
    with pytest.raises(ValidationError, match="at least one month"):
        funds.create_fund(session, cat, rule="average", start_month="2026-11")


def test_an_average_fund_with_a_window_of_zero_months_is_refused(session):
    cat = _category(session, "Mercado")
    _spend(session, cat, 100_000_00, date(2026, 10, 5))
    with pytest.raises(ValidationError, match="at least one month"):
        funds.create_fund(session, cat, rule="average", window_months=0, start_month="2026-11")


def test_an_average_fund_may_look_back_a_single_month(session):
    cat = _category(session, "Mercado")
    _spend(session, cat, 100_000_00, date(2026, 10, 5))
    fund = funds.create_fund(session, cat, rule="average", window_months=1, start_month="2026-11")
    status = funds.fund_status(session, fund.id, "2026-11")
    assert status.asks == 100_000_00
    assert status.averaged_over == 1


def test_a_fund_saving_toward_a_date_may_target_a_single_centavo(session):
    cat = _category(session, "Ahorro Viaje")
    _obligation(session, _cat_id(cat), 1, date(2027, 5, 15), unit="year")
    fund = funds.create_fund(session, cat, rule="from-recurring", start_month="2026-11")
    assert funds.fund_status(session, fund.id, "2026-11").asks == 1


def test_a_fund_already_holding_more_than_its_target_asks_for_nothing(session):
    cat = _category(session, "Ahorro Viaje")
    _obligation(session, _cat_id(cat), 1_000_000_00, date(2027, 5, 15), unit="year")
    fund = funds.create_fund(
        session,
        cat,
        rule="from-recurring",
        start_month="2026-11",
        opening_balance=1_500_000_00,
    )
    assert funds.fund_status(session, fund.id, "2026-11").asks == 0


def test_a_fund_holds_nothing_in_a_month_before_it_starts(session):
    cat = _category(session, "Tecnologia")
    fund = funds.create_fund(
        session, cat, rule="fixed", amount=100_000_00, start_month="2026-11", opening_balance=500_000_00
    )
    status = funds.fund_status(session, fund.id, "2026-09")
    assert status.asks == 0
    assert status.holds == 0


def test_spending_on_the_very_first_day_of_the_start_month_is_not_history(session):
    """`before the start month` is strict — the start month itself is not history."""
    cat = _category(session, "Peajes")
    _spend(session, cat, 90_000_00, date(2026, 11, 1))
    with pytest.raises(ValidationError, match="fixed"):
        funds.create_fund(session, cat, rule="average", window_months=3, start_month="2026-11")


def test_a_target_the_month_after_the_start_is_warned_about_too(session):
    cat = _category(session, "Ahorro Viaje")
    _obligation(session, cat, 1_000_000_00, date(2026, 12, 20), unit="year")
    preview = funds.preview_fund(
        session,
        cat,
        rule="from-recurring",
        start_month="2026-11",
    )
    assert preview.would_ask == 1_000_000_00
    assert preview.warning is not None


def test_a_planned_payment_no_fund_covers_leaves_the_money_available(session):
    salario = _salario(session)
    assert salario is not None
    cat = _category(session, "Impuestos")
    before = month_service.available(session, "2026-11")
    planned.plan_payment(
        session,
        payee="DIAN",
        amount=300_000_00,
        currency="COP",
        due_date=date(2026, 11, 20),
        account_id=_default_account(session),
        category_id=cat,
    )
    after = month_service.available(session, "2026-11")
    assert after.uncovered == before.uncovered + 300_000_00
    assert after.free == before.free - 300_000_00


def test_a_planned_payment_a_fund_already_covers_is_not_counted_twice(session):
    _salario(session)
    cat = _category(session, "Impuestos")
    funds.create_fund(session, cat, rule="fixed", amount=300_000_00, start_month="2026-11")
    before = month_service.available(session, "2026-11")
    planned.plan_payment(
        session,
        payee="DIAN",
        amount=300_000_00,
        currency="COP",
        due_date=date(2026, 11, 20),
        account_id=_default_account(session),
        category_id=cat,
    )
    after = month_service.available(session, "2026-11")
    assert after.uncovered == before.uncovered
    assert after.free == before.free


# ------------------------------------------- mutants the sweep left standing


def test_a_fund_holds_nothing_before_its_start_month(session):
    """The fold's early return is an answer, not a placeholder."""
    cat = _category(session, "Tecnologia")
    fund = funds.create_fund(session, cat, rule="fixed", amount=100_000_00, start_month="2026-11")
    status = funds.fund_status(session, fund.id, "2026-09")
    assert status.holds == 0
    assert status.asks == 0


def test_spending_before_a_fund_starts_is_uncovered_in_full(session):
    """A fund that has not started yet holds nothing to absorb the spending."""
    cat = _category(session, "Tecnologia")
    funds.create_fund(session, cat, rule="fixed", amount=100_000_00, start_month="2026-12")
    _spend(session, cat, 50_000_00, date(2026, 11, 10))
    assert month_service.available(session, "2026-11").uncovered == 50_000_00


def test_a_target_fund_that_already_holds_its_target_asks_nothing(session):
    cat = _category(session, "Viaje")
    _obligation(session, _cat_id(cat), 1_000_000_00, date(2027, 6, 15), unit="year")
    fund = funds.create_fund(
        session,
        cat,
        rule="from-recurring",
        start_month="2026-11",
        opening_balance=1_000_000_00,
    )
    assert funds.fund_status(session, fund.id, "2026-11").asks == 0


def test_the_average_rule_reads_only_months_completed_before_it_starts(session):
    """Spending on the first day of the start month is not spending before it."""
    cat = _category(session, "Servicios")
    _spend(session, cat, 300_000_00, date(2026, 11, 1))
    with pytest.raises(ValidationError, match="nothing has ever been spent"):
        funds.create_fund(session, cat, rule="average", window_months=12, start_month="2026-11")


@pytest.mark.parametrize("amount", [None, 0])
def test_a_fixed_fund_refuses_an_amount_that_is_not_above_zero(session, amount):
    cat = _category(session, f"Tecnologia {amount}")
    with pytest.raises(ValidationError, match="above zero"):
        funds.create_fund(session, cat, rule="fixed", amount=amount, start_month="2026-11")


@pytest.mark.parametrize("amount", [1, 2])
def test_a_fixed_fund_takes_the_smallest_amount_above_zero(session, amount):
    cat = _category(session, f"Tecnologia {amount}")
    fund = funds.create_fund(session, cat, rule="fixed", amount=amount, start_month="2026-11")
    assert funds.fund_status(session, fund.id, "2026-11").asks == amount


@pytest.mark.parametrize("window", [None, 0])
def test_an_average_fund_refuses_a_window_below_one_month(session, window):
    cat = _category(session, f"Servicios {window}")
    _spend(session, cat, 300_000_00, date(2026, 10, 5))
    with pytest.raises(ValidationError, match="at least one month"):
        funds.create_fund(session, cat, rule="average", window_months=window, start_month="2026-11")


def test_an_average_fund_takes_a_window_of_one_month(session):
    cat = _category(session, "Servicios uno")
    _spend(session, cat, 300_000_00, date(2026, 10, 5))
    fund = funds.create_fund(session, cat, rule="average", window_months=1, start_month="2026-11")
    assert funds.fund_status(session, fund.id, "2026-11").asks == 300_000_00


@pytest.mark.parametrize("target", [1, 2])
def test_a_target_fund_takes_the_smallest_target_above_zero(session, target):
    cat = _category(session, f"Viaje {target}")
    _obligation(session, _cat_id(cat), target, date(2027, 6, 15), unit="year")
    fund = funds.create_fund(session, cat, rule="from-recurring", start_month="2026-11")
    assert funds.fund_status(session, fund.id, "2026-11").asks == 1


def _preview_against_a_charge_in(session, charge):
    cat = _category(session, f"Viaje {charge:%Y%m}")
    _obligation(session, cat, 600_000_00, charge, unit="year", name=f"Viaje {charge:%Y%m}")
    return funds.preview_fund(session, cat, rule="from-recurring", start_month="2026-11")


def test_a_charge_two_months_out_is_the_first_that_is_not_warned_about(session):
    """Two months out is the least runway that leaves a month to save in.

    A charge in December has to be whole by the end of November (AC-6), so a
    fund starting in November has November and nothing else — the same single
    month the warning exists to announce.
    """
    warned, spread = (
        _preview_against_a_charge_in(session, charge) for charge in (date(2026, 12, 20), date(2027, 1, 20))
    )
    assert warned.warning is not None and warned.would_ask == 600_000_00
    assert spread.warning is None and spread.would_ask == 300_000_00


def test_a_turn_on_the_last_day_of_the_month_moves_the_fund_to_the_next_cycle(session):
    """A settled turn is done: the fund fills for the next one, not for it again."""
    cat = _category(session, "Arriendo")
    _obligation(session, cat, 200_000_00, date(2026, 11, 30), name="Arriendo")
    fund = funds.create_fund(session, cat, rule="from-recurring", start_month="2026-11")
    _spend(session, cat, 200_000_00, date(2026, 11, 30))
    assert funds.fund_status(session, fund.id, "2026-11").whole_by == "2026-11"


def test_everything_no_fund_covers_lands_in_one_term(session):
    """Loose spending, an obligation, a planned payment and an overspend, added once each."""
    account = _default_account(session)
    salary = _category(session, "Sueldo", is_income=True)
    transactions.record_income(session, account, 10_000_000_00, "COP", date(2026, 11, 1), "Sueldo", category_id=salary)
    _spend(session, _category(session, "Regalos"), 100_000_00, date(2026, 11, 3))
    _obligation(session, _category(session, "Gimnasio"), 200_000_00, date(2026, 11, 15), name="Gym")
    planned.plan_payment(
        session,
        payee="Hotel",
        amount=400_000_00,
        currency="COP",
        due_date=date(2026, 11, 20),
        account_id=account,
        category_id=_category(session, "Viajes"),
    )
    mercado = _category(session, "Mercado")
    funds.create_fund(session, mercado, rule="fixed", amount=50_000_00, start_month="2026-11")
    _spend(session, mercado, 850_000_00, date(2026, 11, 6))

    available = month_service.available(session, "2026-11")
    assert available.uncovered == 100_000_00 + 200_000_00 + 400_000_00 + 800_000_00


# -------------------------------------- a fund lives exactly as long as its charge


def _marked(session, name="Seguro", amount=1_100_000_00, start=date(2027, 7, 5), unit="year", count=1):
    """A charge that leaves months free, and the fund marking it produced."""
    category = _category(session, "Carro")
    _obligation(session, category, amount, start, unit=unit, count=count, name=name)
    charge_id = _recurring_id(session, name)
    return charge_id, funds.mark_charge(session, charge_id, "2026-08")


def test_a_payment_that_settles_a_marked_charge_leaves_the_month_once(session):
    """AC-9 stated as the month's own arithmetic, which nothing was asserting.

    Eight tests hold the aggregate's half — the payment does not drain its
    category's fund. What the *month* does with the same payment was held by
    none: `_uncovered_posted` skips it because its charge carries a fund, and
    deleting that skip left 1213 tests green. So the peso would leave twice,
    once as the fund's ask and once as spending nothing covers.

    The assertion is the promise itself rather than a figure: whatever the fund
    still asks plus whatever the month could not cover adds to the payment, and
    to nothing more.
    """
    charge_id, _ = _marked(session)
    transactions.record_expense(
        session,
        _default_account(session),
        1_100_000_00,
        "COP",
        date(2026, 8, 20),
        "Seguros Bolívar",
        category_id=_category_named(session, "Carro"),
        recurring_id=charge_id,
    )

    month = month_service.available(session, "2026-08")

    assert month.uncovered + sum(line.asks_cop for line in month.funds) == 1_100_000_00


def test_a_marked_charge_is_not_owed_again_in_the_month_it_lands(session):
    """The obligation half of the same exclusion, also asserted by nothing.

    A charge that carries a fund is already being asked for by that fund, month
    after month. `_uncovered` skips it so the month does not *also* count the
    whole amount as a bill falling due — and until this feature it skipped by
    category, which is why the skip now has to name the charge.
    """
    charge_id, _ = _marked(session)
    lands_in = "2027-07"

    with_a_fund = month_service.available(session, lands_in).uncovered
    funds.unmark_charge(session, charge_id)
    without_one = month_service.available(session, lands_in).uncovered

    assert with_a_fund == 0
    assert without_one == 1_100_000_00


def test_a_fund_is_not_dropped_in_the_month_its_charge_finally_arrives(session):
    """The month a charge lands is the month the fund existed for.

    `mark_charge` refuses a charge landing this very month — there is nothing
    left to spread. Reusing that same answer to decide whether an existing fund
    may *stay* would delete it the moment it succeeds, in the month it hands
    over what it spent a year collecting. The two questions are asked at
    different moments and only one of them is about timing.
    """
    charge_id, _ = _marked(session, start=date(2027, 7, 5))
    _obligation(session, _category_named(session, "Carro"), 900_000_00, date(2027, 7, 5), unit="year", name="SOAT")
    fresh = _recurring_id(session, "SOAT")

    with pytest.raises(ValidationError, match="mark it once it has been paid"):
        funds.mark_charge(session, fresh, "2027-07")

    dropped = funds.unmark_if_it_can_no_longer_be_saved_for(session, charge_id, "2027-07")

    assert dropped is False
    assert funds.fund_for_charge(session, charge_id) is not None


def test_a_charge_edited_into_a_monthly_rhythm_loses_its_fund(session):
    charge_id, _ = _marked(session)

    recurring.update_recurring(session, charge_id, interval_unit="month", interval_count=1, today=date(2026, 8, 15))

    assert funds.fund_for_charge(session, charge_id) is None


def test_the_screen_can_ask_what_an_edit_would_cost_before_saving_it(session):
    """The warning AC-8 wants is asked of the same rule the removal uses."""
    charge_id, _ = _marked(session)

    assert funds.would_lose_its_fund(session, charge_id, "2026-08", interval_unit="month", interval_count=1)
    assert not funds.would_lose_its_fund(session, charge_id, "2026-08", interval_unit="month", interval_count=6)
    assert funds.fund_for_charge(session, charge_id) is not None


def test_asking_what_an_edit_would_cost_says_no_when_nothing_is_marked(session):
    category = _category(session, "Carro")
    _obligation(session, category, 1_100_000_00, date(2027, 7, 5), unit="year", name="Seguro")

    assert not funds.would_lose_its_fund(
        session, _recurring_id(session, "Seguro"), "2026-08", interval_unit="month", interval_count=1
    )


def test_switching_a_charge_off_takes_its_fund_and_switching_it_back_on_does_not_return_it(session):
    charge_id, _ = _marked(session)

    recurring.deactivate_recurring(session, charge_id)
    assert funds.fund_for_charge(session, charge_id) is None

    recurring.restore_recurring(session, charge_id, today=date(2026, 8, 15))
    assert funds.fund_for_charge(session, charge_id) is None


def test_a_category_saving_for_a_charge_names_it_when_it_refuses_to_be_archived(session):
    charge_id, _ = _marked(session)
    category = _category_named(session, "Carro")

    with pytest.raises(ValidationError) as refusal:
        categories.archive_category(session, category)

    assert "Seguro" in str(refusal.value)
    assert funds.fund_for_charge(session, charge_id) is not None


def test_once_the_charge_is_unmarked_the_category_archives(session):
    charge_id, _ = _marked(session)
    category = _category_named(session, "Carro")

    funds.unmark_charge(session, charge_id)
    categories.archive_category(session, category)

    assert categories.get_category(session, category).archived


def test_a_marked_charge_is_not_counted_twice_by_the_monthly_rate(session):
    """The defect the migration rehearsal caught, before it reached real data.

    `month_rates` adds every obligation's monthly share to the cost, skipping
    the ones a fund already covers. It skipped them by *category*, which stopped
    being enough the moment a fund could hang off one charge: the charge's own
    fund asked for it, and the loop asked for it again. Against a restored copy
    of production the two yearly car charges moved the cost by exactly their two
    monthly shares — 58.333.334 + 3.727.500.
    """
    charge_id, _ = _marked(session)
    before = month_service.rates(session, "2026-08").cost

    funds.unmark_charge(session, charge_id)
    unfunded = month_service.rates(session, "2026-08").cost
    funds.mark_charge(session, charge_id, "2026-08")
    after = month_service.rates(session, "2026-08").cost

    assert before == after
    monthly_share_of_a_yearly_charge = 1_100_000_00 // 12 + 1
    spread_over_the_months_left = 1_100_000_00 // 11
    assert unfunded - after == monthly_share_of_a_yearly_charge - spread_over_the_months_left
