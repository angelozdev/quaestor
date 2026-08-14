"""The metas service: what a meta asks, holds, reports and refuses.

Written to close what mutation testing found (Checkpoint 8, feature 009): 50
real survivors in `services.metas`, and one cause behind them — this file did
not exist. The module's only unit pressure arrived through 22 HTTP round-trips
in `tests/api/test_metas.py`, which assert that the wire reaches the rule, and
through 009's acceptance suite, which walks the happy paths the scenarios name.

Each test below names the behaviour a surviving mutant could have changed with
every other test still green.
"""

from datetime import date
from decimal import Decimal

import pytest
from quaestor.domain.errors import ValidationError
from quaestor.domain.models import Account, AccountType, MetaAmendment
from quaestor.services import fx, metas, month, planned, reports, transactions
from quaestor.services.month_aggregate import load_month
from sqlmodel import select

SEEDED_TRM = "4200"
"""The rate a running app always carries — background state, not a subject.

Every meta read demands it on entry (ADR-0031), so a test that is not about
currency starts with one already set.
"""


@pytest.fixture(autouse=True)
def _trm(session):
    fx.set_trm(session, SEEDED_TRM)


def _meta(session, name="Moto", *, amount=1_000_000, today="2026-06", target="2026-12", **spec):
    return metas.create_meta(session, name=name, amount=amount, target_month=target, today=today, **spec)


def _account(session):
    account = Account(name="Caja", type=AccountType.debit, currency="COP")
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def _buy(session, meta, amount, on, category="Compras"):
    return transactions.record_expense(
        session,
        _account(session).id,
        amount,
        "COP",
        on,
        "Compra",
        new_category=category,
        meta_id=meta.id,
    )


def _reported(session, year_month, name):
    found = next((m for m in metas.list_metas(session, year_month) if m.name == name), None)
    assert found is not None, f"the month {year_month} reports no meta named {name!r}"
    return found


def _preview(**spec):
    """A preview always weighs its instalment at the app's one rate (ADR-0031)."""
    return metas.preview_meta(trm=Decimal(SEEDED_TRM), **spec)


def _amendments(session, meta):
    return session.exec(select(MetaAmendment).where(MetaAmendment.meta_id == meta.id)).all()


def test_progress_is_what_it_holds_as_a_percentage_of_what_it_wants(session):
    """AC-5's "60 percent of the way there", asked of the Python.

    The scenario that states it is untagged, so it binds to vitest against a
    fixture — nothing else asks this module what the figure is.
    """
    meta = _meta(session, amount=1_000_000, target="2027-06")
    metas.contribute(session, meta.id, year_month="2026-06", amount=523_076)

    reported = _reported(session, "2026-06", "Moto")
    assert reported.holds == 600_000
    assert reported.progress == 60


def test_the_metas_waiting_on_an_answer_come_first(session):
    """AC-44's order, likewise asserted only against a vitest fixture.

    Two metas want an answer for different reasons — one was bought, one is
    past its month — and one is simply running. The running one has the
    nearest target month, so an order that ignores the grouping puts it in
    the middle and an inverted one puts it first.
    """
    past = _meta(session, "Casa", today="2026-05", target="2026-05")
    bought = _meta(session, "Bici", target="2026-08")
    _meta(session, "Aire", target="2026-07")
    _buy(session, bought, 50_000, date(2026, 6, 10))
    assert past.id is not None

    assert [m.name for m in metas.list_metas(session, "2026-06")] == ["Casa", "Bici", "Aire"]


def test_the_archive_lists_the_newest_cancellation_first(session):
    """The name order and the cancellation order disagree on purpose."""
    aire = _meta(session, "Aire", today="2026-01")
    bici = _meta(session, "Bici", today="2026-01")
    metas.cancel_meta(session, bici.id, year_month="2026-01")
    metas.cancel_meta(session, aire.id, year_month="2026-03")

    assert [m.name for m in metas.list_archived(session)] == ["Aire", "Bici"]


def test_closing_a_bought_meta_takes_it_off_the_live_list_and_records_that_it_was_closed(session):
    """The refusal was pinned when this guard was written; the write was not.

    A close that failed to archive would leave the meta being folded into
    every later month, still charging its instalment, while the button
    appeared to do nothing.
    """
    meta = _meta(session)
    _buy(session, meta, 1_000_000, date(2026, 6, 10))

    closed = metas.close_meta(session, meta.id, year_month="2026-06")

    assert closed.archived is True
    assert closed.closed is True
    assert [m.name for m in metas.list_metas(session, "2026-06")] == []


def test_a_restored_meta_comes_back_running_rather_than_finished(session):
    """Coming back marked closed would mean it could never wait on an answer again."""
    meta = _meta(session)
    metas.cancel_meta(session, meta.id, year_month="2026-06")

    restored = metas.restore_meta(session, meta.id, today="2026-07")

    assert restored.archived is False
    assert restored.closed is False


def test_a_contribution_the_cancellation_never_gave_back_is_not_marked_as_given_back(session):
    """A month can only hand back what it had already been given.

    The fold sums contributions dated at or before the cancellation month, so
    one dated after it was never in the released figure. Marking it would take
    from a month that never got it — 100.000 out of nothing.
    """
    meta = _meta(session, amount=50_000_000)
    metas.contribute(session, meta.id, year_month="2026-08", amount=100_000)
    metas.cancel_meta(session, meta.id, year_month="2026-07")

    metas.restore_meta(session, meta.id, today="2026-08")

    assert [r.returned_month for r in metas.contributions_of(session, meta.id)] == [None]
    assert _reported(session, "2026-08", "Moto").holds == _reported(session, "2026-08", "Moto").asks + 100_000


def test_a_meta_cannot_come_back_in_a_month_behind_the_one_it_left_in(session):
    """Restoring clears the month that released the money.

    Doing it behind the cancellation would leave the months in between holding
    what no month gives back, and the cancellation month with nothing to say.
    """
    meta = _meta(session)
    metas.cancel_meta(session, meta.id, year_month="2026-08")

    with pytest.raises(ValidationError, match="cannot come back"):
        metas.restore_meta(session, meta.id, today="2026-07")


def test_a_second_cancellation_leaves_the_first_ones_give_back_month_alone(session):
    """Each contribution says which cancellation gave it back, not the newest one.

    Overwriting would move June's contribution to August, and the month a
    figure belongs to is the whole of what a stamp is for (AC-27).
    """
    meta = _meta(session)
    metas.contribute(session, meta.id, year_month="2026-06", amount=100_000)
    metas.cancel_meta(session, meta.id, year_month="2026-06")
    metas.restore_meta(session, meta.id, today="2026-07")
    metas.contribute(session, meta.id, year_month="2026-07", amount=100_000)
    metas.cancel_meta(session, meta.id, year_month="2026-08")

    metas.restore_meta(session, meta.id, today="2026-09")

    assert [(r.year_month, r.returned_month) for r in metas.contributions_of(session, meta.id)] == [
        ("2026-06", "2026-06"),
        ("2026-07", "2026-08"),
    ]


def test_a_meta_restored_twice_holds_only_what_the_month_it_came_back_in_put_in(session):
    """Two lives' worth of contributions, both handed back, neither charged again."""
    meta = _meta(session)
    metas.contribute(session, meta.id, year_month="2026-06", amount=100_000)
    metas.cancel_meta(session, meta.id, year_month="2026-06")
    metas.restore_meta(session, meta.id, today="2026-07")
    metas.contribute(session, meta.id, year_month="2026-07", amount=100_000)
    metas.cancel_meta(session, meta.id, year_month="2026-08")
    metas.restore_meta(session, meta.id, today="2026-09")

    came_back = _reported(session, "2026-09", "Moto")

    assert came_back.holds == came_back.asks


def test_editing_one_meta_leaves_another_metas_edit_alone(session):
    moto = _meta(session, "Moto", amount=1_000_000)
    tele = _meta(session, "Tele", amount=2_000_000)
    metas.set_meta(session, tele.id, today="2026-07", amount=2_500_000)

    metas.set_meta(session, moto.id, today="2026-07", amount=1_500_000)

    assert _reported(session, "2026-07", "Moto").amount == 1_500_000
    assert _reported(session, "2026-07", "Tele").amount == 2_500_000


def test_editing_in_one_month_leaves_an_earlier_months_edit_as_it_stood(session):
    """The property ADR-0046 exists for: a past month answers as it stood."""
    moto = _meta(session, amount=1_000_000)
    metas.set_meta(session, moto.id, today="2026-07", amount=1_500_000)

    metas.set_meta(session, moto.id, today="2026-08", amount=2_000_000)

    assert _reported(session, "2026-07", "Moto").amount == 1_500_000
    assert _reported(session, "2026-08", "Moto").amount == 2_000_000


def test_whether_an_edit_changes_anything_is_read_from_this_metas_own_history(session):
    """Two metas are moved to the same amount in the same month.

    Deciding from the wrong meta's history makes the second edit look like a
    no-op and silently write nothing.
    """
    moto = _meta(session, "Moto", amount=1_000_000)
    tele = _meta(session, "Tele", amount=2_000_000)
    metas.set_meta(session, tele.id, today="2026-07", amount=3_000_000)

    metas.set_meta(session, moto.id, today="2026-07", amount=3_000_000)

    assert _reported(session, "2026-07", "Moto").amount == 3_000_000


def test_editing_a_meta_and_editing_it_back_in_the_same_month_returns_it(session):
    """One row per month, and the row is the last thing the owner said."""
    moto = _meta(session, amount=1_000_000)
    metas.set_meta(session, moto.id, today="2026-07", amount=1_500_000)

    metas.set_meta(session, moto.id, today="2026-07", amount=1_000_000)

    assert _reported(session, "2026-07", "Moto").amount == 1_000_000
    assert len(_amendments(session, moto)) == 1


def test_an_edit_made_in_an_earlier_month_is_remembered_by_a_later_one(session):
    """Returning a meta to its original amount is a change, and must be written."""
    moto = _meta(session, amount=1_000_000)
    metas.set_meta(session, moto.id, today="2026-07", amount=1_500_000)

    metas.set_meta(session, moto.id, today="2026-08", amount=1_000_000)

    assert _reported(session, "2026-08", "Moto").amount == 1_000_000


def test_a_new_edit_is_compared_against_the_latest_one_not_the_oldest(session):
    """Three edits, and the third asks for what the second already said.

    Nothing should be written. Both halves of what the meta currently wants
    have to come from the same edit: the amount moves on the first edit and
    the month on the second, so reading either from the oldest row makes the
    third edit look like a change. Reading further back than the history goes
    fails outright.
    """
    moto = _meta(session, amount=1_000_000, target="2026-12")
    metas.set_meta(session, moto.id, today="2026-07", amount=2_000_000, target_month="2026-10")
    metas.set_meta(session, moto.id, today="2026-08", amount=3_000_000, target_month="2026-11")

    metas.set_meta(session, moto.id, today="2026-09", amount=3_000_000, target_month="2026-11")

    reported = _reported(session, "2026-09", "Moto")
    assert (reported.amount, reported.target_month) == (3_000_000, "2026-11")
    assert [(a.year_month, a.amount, a.target_month) for a in _amendments(session, moto)] == [
        ("2026-07", 2_000_000, "2026-10"),
        ("2026-08", 3_000_000, "2026-11"),
    ]


def test_changing_the_month_after_the_amount_keeps_the_amount(session):
    """Two edits in one month, one field each, and neither undoes the other.

    The screen offers *Cambiarle el monto* and *Cambiarle el mes* as separate
    acts, so the owner arrives here by using both. The field left alone has to
    default to what the meta wants now — its own column is the original spec and
    every amendment since has moved past it.
    """
    moto = _meta(session, amount=1_000_000, target="2026-12")
    metas.set_meta(session, moto.id, today="2026-07", amount=2_000_000)

    metas.set_meta(session, moto.id, today="2026-07", target_month="2027-02")

    reported = _reported(session, "2026-07", "Moto")
    assert (reported.amount, reported.target_month) == (2_000_000, "2027-02")


def test_changing_the_amount_after_the_month_keeps_the_month(session):
    """The same pair in the other order."""
    moto = _meta(session, amount=1_000_000, target="2026-12")
    metas.set_meta(session, moto.id, today="2026-07", target_month="2027-02")

    metas.set_meta(session, moto.id, today="2026-07", amount=2_000_000)

    reported = _reported(session, "2026-07", "Moto")
    assert (reported.amount, reported.target_month) == (2_000_000, "2027-02")


def test_renaming_a_meta_leaves_what_it_wants_alone(session):
    """A name is not part of what the meta wants, so it must amend nothing."""
    moto = _meta(session, amount=1_000_000, target="2026-12")
    metas.set_meta(session, moto.id, today="2026-07", amount=2_000_000, target_month="2027-02")

    metas.set_meta(session, moto.id, today="2026-07", name="Moto nueva")

    reported = _reported(session, "2026-07", "Moto nueva")
    assert (reported.amount, reported.target_month) == (2_000_000, "2027-02")
    assert [(a.amount, a.target_month) for a in _amendments(session, moto)] == [(2_000_000, "2027-02")]


def test_a_month_before_the_meta_existed_charges_nothing_for_it(session):
    """`_walk`'s first branch — the whole of it was unreached.

    Asked of the month's arithmetic, not of the screen: the screen leaves the
    meta out of a month it did not exist in, and the sums still have to fold it
    to nothing rather than to a first instalment.
    """
    _meta(session, today="2026-08", target="2026-12")

    agg = load_month(session, "2026-07")
    reported = next(m for m in metas.statuses(agg) if m.name == "Moto")
    assert (reported.asks, reported.holds, reported.progress) == (0, 0, 0)
    assert metas.fold(agg).asks == 0


def test_a_purchase_dated_before_its_meta_existed_costs_the_month_all_of_itself(session):
    """Nothing refuses the link, so the month must still add up over it.

    The meta opened that month with nothing and asked it for nothing, so
    there is nothing for the purchase to net against.
    """
    meta = _meta(session, today="2026-08", target="2026-12")
    _buy(session, meta, 500_000, date(2026, 7, 15))

    assert metas.fold(load_month(session, "2026-07")).uncovered == 500_000


def test_a_meta_never_ends_up_holding_more_than_the_thing_costs(session):
    """The fold's own cap, independent of the one `contribute` applies.

    The owner sets money aside while the target month is far off, then brings
    the month forward. The instalment grows to fill what is missing, and the
    contribution he already made no longer fits beside it.
    """
    meta = _meta(session, amount=1_200_000, stated_opening=300_000)
    metas.contribute(session, meta.id, year_month="2026-06", amount=700_000)

    metas.set_meta(session, meta.id, today="2026-06", target_month="2026-06")

    assert _reported(session, "2026-06", "Moto").holds == 1_200_000


def test_a_contribution_of_one_centavo_is_taken(session):
    meta = _meta(session, amount=1_000_000)

    assert metas.contribute(session, meta.id, year_month="2026-06", amount=1).amount == 1


def test_a_contribution_is_trimmed_to_the_last_centavo_missing(session):
    meta = _meta(session, amount=1_000_000)
    metas.contribute(session, meta.id, year_month="2026-06", amount=857_141)

    assert metas.contribute(session, meta.id, year_month="2026-06", amount=1_000).amount == 1


def test_contributing_to_a_meta_that_needs_nothing_more_is_refused(session):
    """Otherwise the owner is answered yes and a zero-centavo row lands in the history."""
    meta = _meta(session, amount=1_000_000)
    metas.contribute(session, meta.id, year_month="2026-06", amount=857_142)

    with pytest.raises(ValidationError, match="needs nothing more"):
        metas.contribute(session, meta.id, year_month="2026-06", amount=1_000)


def test_a_contribution_of_nothing_is_refused_for_being_nothing(session):
    """The two refusals say different things and the owner must get the right one."""
    meta = _meta(session, amount=1_000_000)

    with pytest.raises(ValidationError, match="above zero"):
        metas.contribute(session, meta.id, year_month="2026-06", amount=0)


def test_a_meta_named_with_nothing_but_spaces_is_refused(session):
    with pytest.raises(ValidationError, match="needs a name"):
        _meta(session, "   ")


def test_a_meta_of_one_centavo_is_allowed(session):
    assert _meta(session, amount=1).amount == 1


def test_lowering_the_amount_by_one_centavo_below_what_it_holds_completes_it(session):
    """Complete means the owner needs no more of it — by any margin at all."""
    meta = _meta(session, amount=1_000_000, target="2026-06")

    metas.set_meta(session, meta.id, today="2026-07", amount=999_999, target_month="2026-07")

    reported = _reported(session, "2026-07", "Moto")
    assert reported.released == 1
    assert reported.complete is True


def test_a_meta_is_not_waiting_on_an_answer_during_its_own_target_month(session):
    """The month the owner planned to buy in is a month he saves in, not one he is nagged in."""
    _meta(session, target="2026-06")

    assert _reported(session, "2026-06", "Moto").waiting is False


def test_a_purchase_reaches_a_foreign_meta_in_the_metas_own_currency(session):
    """AC-26. Every meta in every other test is in pesos, so this branch was never entered.

    100 dollars wanted, 420.000 pesos of it already asked for this month, and a
    420.000-peso purchase — which is 100 dollars at the seeded rate. Converting
    the wrong way would compare pesos against dollar cents and report the whole
    purchase as uncovered.
    """
    meta = _meta(session, amount=10_000, currency="USD")
    _buy(session, meta, 42_000_000, date(2026, 6, 10))

    uncovered = metas.fold(load_month(session, "2026-06")).uncovered
    assert uncovered == (10_000 - 1_429) * 4_200


def test_what_a_meta_would_ask_assumes_it_starts_with_nothing(session):
    """An amount that does not divide evenly is understated by assuming otherwise."""
    assert _preview(amount=1_000_001, target_month="2026-07", today="2026-06", income=0).asks == 500_001


def test_a_meta_is_announced_as_bigger_than_the_month_only_when_it_is(session):
    over = _preview(amount=1_000_000, target_month="2026-07", today="2026-06", income=100_000)
    under = _preview(amount=1_000_000, target_month="2026-07", today="2026-06", income=900_000)

    assert over.over_the_month is True
    assert under.over_the_month is False


def test_a_meta_that_asks_exactly_the_months_income_is_not_over_it(session):
    preview = _preview(amount=1_000_000, target_month="2026-07", today="2026-06", income=500_000)

    assert preview.over_the_month is False


def test_before_any_income_is_recorded_no_meta_is_announced_as_bigger_than_the_month(session):
    """The false alarm the income guard exists to prevent."""
    preview = _preview(amount=1_000_000, target_month="2026-07", today="2026-06", income=0)

    assert preview.over_the_month is False


def test_a_month_earning_one_centavo_still_announces_a_meta_bigger_than_it(session):
    preview = _preview(amount=1_000_000, target_month="2026-07", today="2026-06", income=1)

    assert preview.over_the_month is True


def test_a_dollar_meta_is_weighed_against_the_month_in_pesos(session):
    """AC-45 compares two figures and only one of them was ever pesos.

    A meta held in dollars asks in dollars, and what it costs the month is that
    instalment at the rate (AC-26). The same cents in the two currencies are
    two different claims on the month, and the warning has to tell them apart.
    """
    in_dollars = _preview(
        amount=200_000,
        target_month="2026-07",
        today="2026-06",
        income=100_000_000,
        currency="USD",
    )
    in_pesos = _preview(
        amount=200_000,
        target_month="2026-07",
        today="2026-06",
        income=100_000_000,
        currency="COP",
    )

    assert (in_dollars.over_the_month, in_pesos.over_the_month) == (True, False)


def test_what_a_dollar_meta_would_ask_stays_in_its_own_currency(session):
    """Converting the comparison must not convert the figure the form prints."""
    preview = _preview(
        amount=200_000,
        target_month="2026-07",
        today="2026-06",
        income=100_000_000,
        currency="USD",
    )

    assert preview.asks == 100_000


def test_closing_a_bought_meta_leaves_the_purchase_costing_the_month_it_was_made_in(session):
    """AC-39's own sentence, asked of the month it names rather than the next one.

    Closing releases nothing, so the gap the purchase left keeps costing August
    after the meta is off the screen. Nothing else asks this: AC-39's scenario
    closes in January a purchase made in December, where the meta asks nothing
    and the expense is not that month's, so closing moves no figure there.
    """
    moto = _meta(session, amount=1_000_000, today="2026-06", target="2026-12")
    _buy(session, moto, 1_000_000, date(2026, 8, 10))
    before = metas.fold(load_month(session, "2026-08")).uncovered
    assert before > 0

    metas.close_meta(session, moto.id, year_month="2026-08")

    assert metas.fold(load_month(session, "2026-08")).uncovered == before
    assert [m.name for m in metas.list_metas(session, "2026-08")] == []


def test_a_bought_meta_stops_asking_the_month_after_the_purchase(session):
    """The money went into the thing; asking again would save for it twice.

    The purchase month still asks, because what it asks is part of what covered
    the purchase (AC-12).
    """
    moto = _meta(session, amount=1_000_000, today="2026-06", target="2026-12")
    august = _reported(session, "2026-08", "Moto")
    _buy(session, moto, 1_000_000, date(2026, 8, 10))

    assert _reported(session, "2026-08", "Moto").asks == august.asks
    for later in ("2026-09", "2026-12"):
        after = _reported(session, later, "Moto")
        assert (after.asks, after.holds) == (0, august.holds)


def test_a_contribution_is_trimmed_against_the_amount_the_meta_wants_now(session):
    """AC-14 after AC-11: raising the amount opens the room the raise created.

    Every other read path folds the amendments; the trim was the one that did
    not, so a contribution of what is genuinely missing lost the difference in
    silence.
    """
    moto = _meta(session, amount=1_000_000, today="2026-06", target="2026-12")
    metas.set_meta(session, moto.id, today="2026-06", amount=2_000_000)
    walked = _reported(session, "2026-06", "Moto")

    put_in = metas.contribute(session, moto.id, year_month="2026-06", amount=2_000_000 - walked.holds)

    assert put_in.amount == 2_000_000 - walked.holds
    assert _reported(session, "2026-06", "Moto").holds == 2_000_000


def test_a_closed_meta_is_not_listed_among_the_cancelled_ones(session):
    """AC-29 is about cancelling. A closed meta gave nothing back and is not restorable."""
    moto = _meta(session, amount=1_000_000, today="2026-06", target="2026-12")
    _buy(session, moto, 1_000_000, date(2026, 8, 10))
    metas.close_meta(session, moto.id, year_month="2026-08")

    assert [m.name for m in metas.list_archived(session)] == []


def test_a_closed_meta_cannot_be_brought_back(session):
    """Restoring one would ask the month for an instalment toward a thing already owned."""
    moto = _meta(session, amount=1_000_000, today="2026-06", target="2026-12")
    _buy(session, moto, 1_000_000, date(2026, 8, 10))
    metas.close_meta(session, moto.id, year_month="2026-08")

    with pytest.raises(ValidationError):
        metas.restore_meta(session, moto.id, today="2026-09")


def test_a_preview_counts_what_the_owner_says_he_already_put_by(session):
    """AC-34's own figure, before the meta exists — the form shows this one."""
    preview = _preview(amount=8_000_000, target_month="2026-12", today="2026-08", income=0, stated_opening=3_000_000)

    assert preview.asks == 1_000_000


def test_a_preview_with_nothing_already_put_by_asks_for_the_whole_thing(session):
    preview = _preview(amount=8_000_000, target_month="2026-12", today="2026-08", income=0)

    assert preview.asks == 1_600_000


def test_the_first_purchase_is_the_one_that_stops_the_meta(session):
    """A second linked movement arrives after the meta already finished (AC-28).

    The month a meta stops is the month the thing was bought, and pointing
    another movement at it later — an accessory, a correction — cannot move
    that forward. Read from November, where the fold has seen both: stopping
    at the later one would have let the meta collect two more instalments it
    no longer had a reason to ask for.
    """
    moto = _meta(session, amount=2_000_000, today="2026-06", target="2026-12")
    _buy(session, moto, 500_000, date(2026, 8, 10))
    _buy(session, moto, 500_000, date(2026, 10, 10), category="Accesorios")

    august = _reported(session, "2026-08", "Moto")
    november = _reported(session, "2026-11", "Moto")
    assert (november.asks, november.holds) == (0, august.holds)


def test_a_purchase_owed_but_not_yet_paid_leaves_the_meta_asking(session):
    """AC-43 in its own words: it does not complete, IT KEEPS ASKING.

    Written the other way round first, to kill a mutant that turned
    `posted_only` on. The mutant was right and the test was wrong: netting a
    debt against what the meta holds is the month's arithmetic (AC-12), and
    stopping the meta is a different question that only posted money answers.
    """
    moto = _meta(session, amount=2_000_000, today="2026-06", target="2026-12")
    planned.plan_payment(
        session,
        payee="Compra",
        amount=2_000_000,
        currency="COP",
        due_date=date(2026, 8, 10),
        account_id=_account(session).id,
        category_id=None,
        new_category="Compras",
        meta_id=moto.id,
    )

    september = _reported(session, "2026-09", "Moto")
    assert september.asks > 0
    assert september.complete is False


def test_a_closed_meta_is_still_named_by_the_month_that_pays_for_it(session):
    """It is charged, so it has to be named: a breakdown that hid it would not add up.

    Leaving the metas screen (AC-29) and leaving the month's arithmetic are
    different acts. Closing is only the first.
    """
    moto = _meta(session, amount=1_000_000, today="2026-06", target="2026-12")
    _buy(session, moto, 1_000_000, date(2026, 8, 10))
    agg = load_month(session, "2026-08")
    charged = metas.fold(agg).asks
    assert charged > 0

    metas.close_meta(session, moto.id, year_month="2026-08")

    after = load_month(session, "2026-08")
    assert metas.fold(after).asks == charged
    assert [m.name for m in metas.statuses(after)] == ["Moto"]
    assert [m.name for m in metas.list_metas(session, "2026-08")] == []


def test_a_meta_kept_on_with_a_new_amount_asks_again(session):
    """AC-8's second offer. Stopping is what the purchase said; the owner may say otherwise."""
    moto = _meta(session, amount=1_000_000, today="2026-06", target="2026-12")
    _buy(session, moto, 1_000_000, date(2026, 8, 10))
    held = _reported(session, "2026-08", "Moto").holds

    metas.set_meta(session, moto.id, today="2026-09", amount=2_000_000)

    september = _reported(session, "2026-09", "Moto")
    assert september.asks > 0
    assert september.holds == held + september.asks


def test_a_meta_kept_on_after_its_purchase_stops_reading_as_finished(session):
    """A meta that asks again is running, and the screen has to be told so.

    ADR-0049 decided an amendment resumes the meta and it stays resumed. But
    `complete` was left meaning "a purchase has been linked, ever" — timeless —
    so September reported a meta both finished and asking $200.000. The screen
    reads that one flag for the "cumplida" badge and to swap *Ponerle plata*
    for *Cerrar*, leaving the owner unable to feed a meta the service accepts
    money for.
    """
    moto = _meta(session, amount=1_000_000, today="2026-06", target="2026-12")
    _buy(session, moto, 1_000_000, date(2026, 8, 10))
    assert _reported(session, "2026-08", "Moto").complete is True

    metas.set_meta(session, moto.id, today="2026-09", amount=2_000_000)

    september = _reported(session, "2026-09", "Moto")
    assert september.asks > 0
    assert september.complete is False


def test_a_meta_kept_on_after_its_purchase_can_still_be_closed(session):
    """Narrowing what "complete" means must not strand the meta it narrows.

    Closing asks whether the meta ever finished, which a purchase settles for
    good; only what it asks *now* was ever a month's question. Cancelling is
    already refused to anything bought (AC-39), so a resumed meta answering no
    to both would be un-endable through the app.
    """
    moto = _meta(session, amount=1_000_000, today="2026-06", target="2026-12")
    _buy(session, moto, 1_000_000, date(2026, 8, 10))
    metas.set_meta(session, moto.id, today="2026-09", amount=2_000_000)

    closed = metas.close_meta(session, moto.id, year_month="2026-09")

    assert closed.closed is True


def test_a_meta_kept_on_with_a_new_month_asks_again(session):
    """AC-8's third offer, which has to work the same way as the second."""
    moto = _meta(session, amount=1_000_000, today="2026-06", target="2026-12")
    _buy(session, moto, 500_000, date(2026, 8, 10))

    metas.set_meta(session, moto.id, today="2026-09", target_month="2027-06")

    assert _reported(session, "2026-09", "Moto").asks > 0


def test_a_finished_meta_takes_no_more_money_instead_of_swallowing_it(session):
    """The contribution was accepted, cost the month, and raised nothing."""
    moto = _meta(session, amount=1_000_000, today="2026-06", target="2026-12")
    _buy(session, moto, 1_000_000, date(2026, 8, 10))

    with pytest.raises(ValidationError):
        metas.contribute(session, moto.id, year_month="2026-09", amount=500_000)


def test_a_dollar_meta_says_what_it_costs_the_month_in_pesos(session):
    """AC-26: only the peso cost is converted, and the breakdown is a peso column."""
    curso = _meta(session, "Curso", amount=200_000, today="2026-08", target="2027-01", currency="USD")
    assert curso.id is not None

    reported = _reported(session, "2026-08", "Curso")
    assert reported.asks == 33_334
    assert reported.asks_cop == 33_334 * int(SEEDED_TRM)


def test_a_month_the_meta_ran_through_still_names_it_after_it_is_closed(session):
    """AC-27's own figures. Closing in December cannot empty September."""
    moto = _meta(session, amount=1_000_000, today="2026-06", target="2026-12")
    before = _reported(session, "2026-09", "Moto")
    _buy(session, moto, 1_000_000, date(2026, 12, 10))
    metas.close_meta(session, moto.id, year_month="2026-12")

    after = _reported(session, "2026-09", "Moto")
    assert (after.holds, after.asks) == (before.holds, before.asks)
    assert [m.name for m in metas.list_metas(session, "2026-12")] == []


def test_a_dollar_meta_is_saved_in_pesos_like_everything_else_in_the_split(session):
    """The split is a peso reading of the month, the same one `available` gives."""
    curso = _meta(session, "Curso", amount=200_000, today="2026-08", target="2027-01", currency="USD")
    assert curso.id is not None

    split = month.month_split(load_month(session, "2026-08"))

    assert split.set_aside == 33_334 * int(SEEDED_TRM)


def test_the_answer_given_in_the_month_of_the_purchase_counts(session):
    """AC-8 puts the two offers on the completed meta, which is the purchase month's screen.

    Ignoring an edit made there would be the same failure the offers exist to
    prevent: the owner presses the button and no figure moves.
    """
    moto = _meta(session, amount=1_000_000, today="2026-06", target="2026-12")
    _buy(session, moto, 1_000_000, date(2026, 8, 10))

    metas.set_meta(session, moto.id, today="2026-08", amount=2_000_000)

    assert _reported(session, "2026-09", "Moto").asks > 0


def test_an_answer_given_later_does_not_reach_back_into_an_earlier_month(session):
    """AC-27: a past month answers as that month stood."""
    moto = _meta(session, amount=1_000_000, today="2026-06", target="2027-06")
    _buy(session, moto, 1_000_000, date(2026, 8, 10))

    metas.set_meta(session, moto.id, today="2026-12", amount=2_000_000)

    assert _reported(session, "2026-09", "Moto").asks == 0
    assert _reported(session, "2026-12", "Moto").asks > 0


def _salaried(session, monthly=5_000_000):
    from datetime import date as _date

    from quaestor.domain.models import IntervalUnit, TxType
    from quaestor.services import accounts, categories, recurring

    account = accounts.create_account(session, name="Banco", type=AccountType.debit, currency="COP", balance=30_000_000)
    salario = categories.create_category(session, name="Salario", is_income=True)
    recurring.create_recurring(
        session,
        name="Sueldo",
        payee="Empresa",
        type=TxType.income,
        mode="auto",
        amount=monthly,
        currency="COP",
        category_id=salario.id,
        account_id=account.id,
        interval_unit=IntervalUnit.month,
        interval_count=1,
        start_date=_date(2026, 1, 5),
    )


def test_cancelling_a_meta_gives_back_what_it_held_and_not_a_peso_more(session):
    """AC-15's arithmetic. Releasing more than was ever taken mints money (ADR-014).

    The month the owner cancels is the last one that names the meta: it charged
    the instalment, it charged the contribution, and it hands back what the meta
    held. Dropping the contribution from one side of that and leaving it in the
    other is a peso the app invents.
    """
    _salaried(session)
    moto = _meta(session, amount=8_000_000, today="2026-08", target="2026-12")
    metas.contribute(session, moto.id, year_month="2026-10", amount=2_000_000)
    before = month.month_available(load_month(session, "2026-10")).free

    metas.cancel_meta(session, moto.id, year_month="2026-10")

    after = month.month_available(load_month(session, "2026-10"))
    assert (before, after.contributed, after.released) == (1_400_000, 2_000_000, 6_800_000)
    assert after.free == 8_200_000


def test_the_report_totals_what_a_cancelled_meta_still_asked(session):
    """A table that lists a claim over a total that omits it does not add up (AC-36)."""
    _salaried(session)
    moto = _meta(session, amount=8_000_000, today="2026-08", target="2026-12")
    metas.cancel_meta(session, moto.id, year_month="2026-10")

    report = reports.monthly_report(session, "2026-10")

    assert [(line.meta_name, line.asks) for line in report.metas] == [("Moto", 1_600_000)]
    assert report.asked == 1_600_000


def test_a_meta_closed_after_being_lowered_leaves_the_screen_too(session):
    """AC-16 completes a meta without any purchase, and AC-29 takes it off the list.

    Reading the finish off the purchase alone left this one listed for ever,
    offered by the movement dialogs, and refused by the server when picked.
    """
    moto = _meta(session, amount=8_000_000, today="2026-08", target="2026-12")
    metas.set_meta(session, moto.id, today="2026-11", amount=3_000_000)
    metas.close_meta(session, moto.id, year_month="2026-11")

    assert [m.name for m in metas.list_metas(session, "2026-09")] == ["Moto"]
    for later in ("2026-11", "2026-12", "2027-03"):
        assert [m.name for m in metas.list_metas(session, later)] == []


def test_a_meta_is_not_listed_in_a_month_it_did_not_exist_in(session):
    """Reading April for a meta opened in June listed it at `lleva 0 · pide 0`."""
    _meta(session, today="2026-06", target="2026-12")

    assert [m.name for m in metas.list_metas(session, "2026-04")] == []
    assert [m.name for m in metas.list_metas(session, "2026-06")] == ["Moto"]


def test_a_meta_that_says_nothing_was_already_put_by_asks_for_the_whole_thing(session):
    """The fold opens at zero, and a centavo of slack there moves the first instalment."""
    _meta(session, amount=1_000_000, today="2026-06", target="2026-12")

    first = _reported(session, "2026-06", "Moto")
    assert (first.asks, first.holds) == (142_858, 142_858)


def test_a_meta_lowered_by_one_centavo_below_what_it_holds_has_finished(session):
    """The release that finishes a meta is any release, not a large one (AC-16)."""
    moto = _meta(session, amount=1_000_000, today="2026-06", target="2026-12")
    metas.set_meta(session, moto.id, today="2026-12", amount=857_142)

    december = _reported(session, "2026-12", "Moto")
    assert (december.released, december.complete) == (1, True)

    metas.close_meta(session, moto.id, year_month="2026-12")
    assert [m.name for m in metas.list_metas(session, "2026-11")] == ["Moto"]
    for after in ("2026-12", "2027-01"):
        assert [m.name for m in metas.list_metas(session, after)] == []
