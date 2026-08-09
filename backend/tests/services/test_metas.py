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

import pytest
from quaestor.domain.errors import ValidationError
from quaestor.domain.models import Account, AccountType, MetaAmendment
from quaestor.services import fx, metas, transactions
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


def _buy(session, meta, amount, on):
    return transactions.record_expense(
        session,
        _account(session).id,
        amount,
        "COP",
        on,
        "Compra",
        new_category="Compras",
        meta_id=meta.id,
    )


def _reported(session, year_month, name):
    found = next((m for m in metas.list_metas(session, year_month) if m.name == name), None)
    assert found is not None, f"the month {year_month} reports no meta named {name!r}"
    return found


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


def test_a_month_before_the_meta_existed_reports_it_asking_and_holding_nothing(session):
    """`_walk`'s first branch — the whole of it was unreached."""
    _meta(session, today="2026-08", target="2026-12")

    reported = _reported(session, "2026-07", "Moto")
    assert reported.asks == 0
    assert reported.holds == 0
    assert reported.progress == 0


def test_a_purchase_dated_before_its_meta_existed_costs_the_month_all_of_itself(session):
    """Nothing refuses the link, so the month must still add up over it.

    The meta opened that month with nothing and asked it for nothing, so
    there is nothing for the purchase to net against.
    """
    meta = _meta(session, today="2026-08", target="2026-12")
    _buy(session, meta, 500_000, date(2026, 7, 15))

    assert metas.uncovered_total(load_month(session, "2026-07")) == 500_000


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

    assert metas.contribute(session, meta.id, year_month="2026-06", amount=1) == 1


def test_a_contribution_is_trimmed_to_the_last_centavo_missing(session):
    meta = _meta(session, amount=1_000_000)
    metas.contribute(session, meta.id, year_month="2026-06", amount=857_141)

    assert metas.contribute(session, meta.id, year_month="2026-06", amount=1_000) == 1


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

    uncovered = metas.uncovered_total(load_month(session, "2026-06"))
    assert uncovered == (10_000 - 1_429) * 4_200


def test_what_a_meta_would_ask_assumes_it_starts_with_nothing(session):
    """An amount that does not divide evenly is understated by assuming otherwise."""
    assert metas.preview_meta(amount=1_000_001, target_month="2026-07", today="2026-06", income=0).asks == 500_001


def test_a_meta_is_announced_as_bigger_than_the_month_only_when_it_is(session):
    over = metas.preview_meta(amount=1_000_000, target_month="2026-07", today="2026-06", income=100_000)
    under = metas.preview_meta(amount=1_000_000, target_month="2026-07", today="2026-06", income=900_000)

    assert over.over_the_month is True
    assert under.over_the_month is False


def test_a_meta_that_asks_exactly_the_months_income_is_not_over_it(session):
    preview = metas.preview_meta(amount=1_000_000, target_month="2026-07", today="2026-06", income=500_000)

    assert preview.over_the_month is False


def test_before_any_income_is_recorded_no_meta_is_announced_as_bigger_than_the_month(session):
    """The false alarm the income guard exists to prevent."""
    preview = metas.preview_meta(amount=1_000_000, target_month="2026-07", today="2026-06", income=0)

    assert preview.over_the_month is False


def test_a_month_earning_one_centavo_still_announces_a_meta_bigger_than_it(session):
    preview = metas.preview_meta(amount=1_000_000, target_month="2026-07", today="2026-06", income=1)

    assert preview.over_the_month is True


def test_closing_a_bought_meta_leaves_the_purchase_costing_the_month_it_was_made_in(session):
    """AC-39's own sentence, asked of the month it names rather than the next one.

    Closing releases nothing, so the gap the purchase left keeps costing August
    after the meta is off the screen. Nothing else asks this: AC-39's scenario
    closes in January a purchase made in December, where the meta asks nothing
    and the expense is not that month's, so closing moves no figure there.
    """
    moto = _meta(session, amount=1_000_000, today="2026-06", target="2026-12")
    _buy(session, moto, 1_000_000, date(2026, 8, 10))
    before = metas.uncovered_total(load_month(session, "2026-08"))
    assert before > 0

    metas.close_meta(session, moto.id, year_month="2026-08")

    assert metas.uncovered_total(load_month(session, "2026-08")) == before
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
    for month in ("2026-09", "2026-12"):
        after = _reported(session, month, "Moto")
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

    assert put_in == 2_000_000 - walked.holds
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
