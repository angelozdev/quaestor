"""Step handlers — feature 015 fund-belongs-to-its-charge.

Feature 003 left 71 steps about a fund that hangs off a category and feature 014
added 14 more about what its figure is made of. This feature adds a second thing
a fund can hang off, so the vocabulary needs to keep the two apart without
inventing a word for either. It does it with a preposition:

``a fund on "Carro"``      the category fund — `fixed` and `average`, unchanged
``the fund for "Seguro"``  the charge fund — what marking a charge creates

Nothing here looks a fund up in ``world.funds``. A charge fund is found through
the charge that owns it, which is the invariant AC-8 is about: asking the
service for it is what makes an orphan impossible to assert into existence.
"""

from __future__ import annotations

from datetime import date
from datetime import date as Date

from quaestor.domain.models import Category, IntervalUnit, RecurringItem, RecurringMode, Transaction, TxType
from quaestor.domain.rules import year_month_of
from quaestor.services import categories, funds, recurring, transactions
from sqlmodel import select

from . import step
from .fx_read_time import _DEC, _default_account_id
from .sinking_funds import _MONTH, _call, _cents, _context, _month_of, _shift_months, _spending_category_id
from .world import World

_CURRENCY = r"(?P<currency>COP|USD)"

_CADENCE = r"every (?:(?P<count>\d+) )?(?P<unit>day|week|month|year)s?"


# ------------------------------------------------------------------ helpers


def _income_category_id(world: World, name: str) -> int:
    known = world.categories.get(name)
    if known is not None:
        return known
    cat = categories.create_category(world.session, name, is_income=True)
    world.categories[name] = cat.id
    return cat.id


def _charge_id(world: World, name: str) -> int:
    known = world.recurring_ids.get(name)
    if known is None:
        raise AssertionError(f"no repeating charge {name!r} in this scenario{_context(world)}")
    return known


def _fund_for(world: World, charge: str):
    fund = _call("fund_for_charge", world.session, _charge_id(world, charge))
    if fund is None:
        raise AssertionError(f"nothing is being saved for {charge!r}{_context(world)}")
    return fund


def _status_for(world: World, charge: str):
    return _call("fund_status", world.session, _fund_for(world, charge).id, _month_of(world.today))


def _the_only_charge(world: World, charge: str):
    """The one term the fund's figure is made of, since it fills for one charge."""
    status = _status_for(world, charge)
    terms = list(status.charges)
    if len(terms) != 1:
        named = [term.name for term in terms]
        raise AssertionError(f"the fund for {charge!r} is filling for {named}, not for one charge")
    return terms[0]


def _marks(world: World):
    return _call("charge_marks", world.session, _month_of(world.today))


def _mark_of(world: World, charge: str):
    found = next((mark for mark in _marks(world) if mark.name == charge), None)
    if found is None:
        named = sorted(mark.name for mark in _marks(world))
        raise AssertionError(f"the list of repeating charges says nothing about {charge!r}; it names {named}")
    return found


def _category_id(world: World, name: str) -> int:
    known = world.categories.get(name)
    if known is None:
        raise AssertionError(f"no category {name!r} in this scenario{_context(world)}")
    return known


def _movements(world: World) -> list[tuple]:
    """Every movement, as the facts a claim about «nothing moved» is about."""
    rows = world.session.exec(select(Transaction).order_by(Transaction.id)).all()
    return [
        (tx.id, tx.account_id, tx.amount, tx.currency, tx.date, tx.status, tx.category_id, tx.recurring_id, tx.meta_id)
        for tx in rows
    ]


def _told(world: World, expected: str) -> None:
    said = getattr(world, "last_rejection", None)
    if said is None:
        raise AssertionError("nothing was refused, so nothing was said about why")
    assert expected in said.lower(), f"the refusal does not say {expected!r}: {said!r}"


# -------------------------------------------------------------------- Given


@step(r'"(?P<charge>[^"]+)" is marked to be saved for')
def given_marked(world: World, charge: str) -> None:
    world.attempt(_call, "mark_charge", world.session, _charge_id(world, charge), _month_of(world.today))
    world.require_clean(f"marking {charge!r} to be saved for")


@step(r'the fund for "(?P<charge>[^"]+)" already holds (?P<amount>' + _DEC + r") (?:COP|USD)")
def given_fund_holds(world: World, charge: str, amount: str) -> None:
    """What the owner states the fund already has, in the charge's own money.

    Stated rather than computed, the same way a category fund's opening balance
    is (003, AC-19): nothing in the app writes it, and it is the only way a
    scenario can put a fund partway through its cycle without inventing a
    payment history for it.
    """
    world.attempt(_call, "set_fund", world.session, _fund_for(world, charge).id, balance=_cents(amount))
    world.require_clean(f"stating what the fund for {charge!r} holds")


@step(
    r'a repeating income "(?P<payee>[^"]+)" on "(?P<category>[^"]+)"'
    r" of (?P<amount>" + _DEC + r") " + _CURRENCY + r" " + _CADENCE + r", next due (?P<due>" + _MONTH + r")"
)
def given_repeating_income_charge(
    world: World,
    payee: str,
    category: str,
    amount: str,
    currency: str,
    unit: str,
    due: str,
    count: str | None = None,
) -> None:
    """Money coming in, shaped like the charge given so the only difference is direction.

    AC-10 refuses to save for an income, and a monthly one would be refused for
    its rhythm instead — so this one repeats yearly and leaves the direction as
    the only thing left to refuse it for.
    """
    first = Date.fromisoformat(f"{due}-05")
    item = world.attempt(
        recurring.create_recurring,
        world.session,
        name=payee,
        payee=payee,
        type=TxType.income,
        mode=RecurringMode.auto,
        amount=_cents(amount),
        currency=currency,
        category_id=_income_category_id(world, category),
        account_id=_default_account_id(world, currency),
        interval_unit=IntervalUnit(unit),
        interval_count=int(count or 1),
        start_date=first,
        declared_on=first,
    )
    world.require_clean(f"declaring the repeating income {payee!r}")
    world.recurring_ids[payee] = item.id


# --------------------------------------------------------------------- When


@step(r'the user (?:marks|tries to mark) "(?P<charge>[^"]+)" to save for it')
def when_mark(world: World, charge: str) -> None:
    world.movements_before = _movements(world)
    world.attempt(_call, "mark_charge", world.session, _charge_id(world, charge), _month_of(world.today))


@step(r'the user unmarks "(?P<charge>[^"]+)"')
def when_unmark(world: World, charge: str) -> None:
    world.movements_before = _movements(world)
    world.attempt(_call, "unmark_charge", world.session, _charge_id(world, charge))


# --------------------------------------------------------------------- Then


@step(r'there is a fund for "(?P<charge>[^"]+)"')
def then_there_is_a_fund(world: World, charge: str) -> None:
    _fund_for(world, charge)


@step(r'there is no fund for "(?P<charge>[^"]+)"')
def then_there_is_no_fund(world: World, charge: str) -> None:
    fund = _call("fund_for_charge", world.session, _charge_id(world, charge))
    assert fund is None, f"{charge!r} still carries a fund (id {fund.id}){_context(world)}"


@step(r'the fund for "(?P<charge>[^"]+)" asks (?P<amount>' + _DEC + r") " + _CURRENCY + r" this month")
def then_fund_asks(world: World, charge: str, amount: str, currency: str) -> None:
    status = _status_for(world, charge)
    assert status.currency == currency, (
        f"the fund for {charge!r} reports in {status.currency}, not in {currency} — "
        f"a charge is saved for in the money it is charged in"
    )
    assert status.asks == _cents(amount), f"the fund for {charge!r} asks {status.asks}, expected {_cents(amount)}"


@step(r'the fund for "(?P<charge>[^"]+)" says the charge costs (?P<amount>' + _DEC + r") " + _CURRENCY)
def then_charge_costs(world: World, charge: str, amount: str, currency: str) -> None:
    status = _status_for(world, charge)
    assert status.currency == currency, f"the fund for {charge!r} reports in {status.currency}, not in {currency}"
    costs = _the_only_charge(world, charge).costs
    assert costs == _cents(amount), f"the fund for {charge!r} says it costs {costs}, expected {_cents(amount)}"


@step(r'the fund for "(?P<charge>[^"]+)" says the charge lands in (?P<month>' + _MONTH + r")")
def then_charge_lands_in(world: World, charge: str, month: str) -> None:
    lands = _the_only_charge(world, charge).charge_month
    assert lands == month, f"the fund for {charge!r} is filling for {lands}, expected {month}"


@step(r'"(?P<charge>[^"]+)" (?P<verdict>can|cannot) be marked')
def then_can_be_marked(world: World, charge: str, verdict: str) -> None:
    mark = _mark_of(world, charge)
    wanted = verdict == "can"
    assert mark.can_be_marked is wanted, (
        f"the list says {charge!r} can_be_marked={mark.can_be_marked}, expected {wanted}"
        f"{' — it says: ' + repr(mark.why_not) if mark.why_not else ''}"
    )
    if not wanted:
        assert mark.why_not, f"the list refuses {charge!r} the mark and says nothing about why"


@step(r"the marking is rejected")
def then_marking_rejected(world: World) -> None:
    world.consume_rejection((Exception,), "marking the charge to be saved for")


@step(r"the user is told to mark it once it has been paid")
def then_told_mark_after_paying(world: World) -> None:
    _told(world, "once it has been paid")


@step(r"the user is told the charge has no turn left")
def then_told_no_turn_left(world: World) -> None:
    _told(world, "no turn left")


@step(r"the user is told the charge leaves no month to save in")
def then_told_no_month_to_save_in(world: World) -> None:
    _told(world, "before a whole month has passed")


@step(r'the user deletes "(?P<charge>[^"]+)"')
def when_delete_charge(world: World, charge: str) -> None:
    """Deleting a repeating charge *is* switching it off (ADR-0005).

    The app has no hard delete for a master record — `deactivate_recurring` is
    the delete, and the turns it already charged stay. So the two doors AC-8
    lists separately, «apagás el cobro» and «borrás el cobro definitivamente»,
    reach the same call, and the fund has to go through both.
    """
    world.attempt(recurring.deactivate_recurring, world.session, _charge_id(world, charge))


@step(r'the user changes "(?P<charge>[^"]+)" to charge every month')
def when_change_to_monthly(world: World, charge: str) -> None:
    world.attempt(
        recurring.update_recurring,
        world.session,
        _charge_id(world, charge),
        interval_unit=IntervalUnit.month,
        interval_count=1,
        today=world.today,
    )


@step(r"the archiving is rejected")
def then_archiving_rejected(world: World) -> None:
    world.consume_rejection((Exception,), "archiving the category")


@step(r'the category "(?P<name>[^"]+)" is archived')
def then_category_is_archived(world: World, name: str) -> None:
    world.require_clean(f"archiving {name!r}")
    cat = world.session.get(Category, _category_id(world, name))
    assert cat is not None and cat.archived, f"{name!r} is not archived"


@step(r'the user is told to unmark "(?P<charge>[^"]+)" first')
def then_told_to_unmark_first(world: World, charge: str) -> None:
    _told(world, f"unmark {charge.lower()!r}")


@step(r'the funds name only "(?P<charge>[^"]+)"')
def then_funds_name_only(world: World, charge: str) -> None:
    """The invariant of AC-8, asserted over the whole list rather than one row.

    «Una caja existe si y solo si su cobro está marcado y vivo» is a claim about
    what is *not* there, so checking the survivor alone would pass while an
    orphan sat beside it.
    """
    named = sorted(line.name for line in _call("list_funds", world.session))
    assert named == [charge], f"the funds name {named}, expected only [{charge!r}]"


@step(r"no movement was created, deleted or changed")
def then_no_movement_moved(world: World) -> None:
    before = getattr(world, "movements_before", None)
    assert before is not None, "nothing recorded what the movements were before the action"
    assert _movements(world) == before, (
        "the movements are not what they were — a fund never held money, so removing one moves none"
    )


@step(
    r"the user records an expense of (?P<amount>" + _DEC + r") " + _CURRENCY + r' in category "(?P<category>[^"]+)"'
    r' settling "(?P<charge>[^"]+)"'
)
def when_record_expense_settling(world: World, amount: str, currency: str, category: str, charge: str) -> None:
    """A payment the owner typed in himself, naming the charge it closed.

    The link is what settles, never the amount (AC-5): the same 1.100.000 spent
    on a fire extinguisher names nothing and settles nothing.

    The turn is the soonest one still open, which is what the screen fills in
    for the owner when a charge has only one (ADR-0058).
    """
    world.last_linked_id = world.attempt(
        transactions.record_expense,
        world.session,
        account_id=_default_account_id(world, currency),
        amount=_cents(amount),
        currency=currency,
        date=world.today,
        payee="Pago",
        category_id=_spending_category_id(world, category),
        recurring_id=_charge_id(world, charge),
        settles_due=_soonest_open_turn(world, charge),
    )
    world.require_clean(f"recording the payment that settled {charge!r}")


def _soonest_open_turn(world: World, charge: str) -> date:
    """The next turn of this charge nobody has settled, as the screen offers it."""
    open_turns = funds.open_turns_of(world.session, _charge_id(world, charge))
    assert open_turns, f"{charge!r} has no turn left open to settle"
    return open_turns[0]


@step(
    r"the user records an expense of (?P<amount>"
    + _DEC
    + r") "
    + _CURRENCY
    + r" in (?P<paid_in>\d{4}-\d{2}) in category \"(?P<category>[^\"]+)\""
    r" settling the (?P<turn>\d{4}-\d{2}) turn of \"(?P<charge>[^\"]+)\""
)
def when_record_expense_settling_a_named_turn(
    world: World, amount: str, currency: str, paid_in: str, category: str, turn: str, charge: str
) -> None:
    """A bill paid after it fell due, with the owner saying which turn it was.

    The month of the payment and the month of the turn are different on purpose:
    that gap is the whole case. Told which turn it answers for, the fund moves
    on by one cycle rather than reading a late payment as an early one and
    skipping a year (AC-5, ADR-0058).
    """
    item = world.session.get(RecurringItem, _charge_id(world, charge))
    due = next(d for d in funds.open_turns_of(world.session, item.id) if year_month_of(d) == turn)
    world.last_linked_id = world.attempt(
        transactions.record_expense,
        world.session,
        account_id=_default_account_id(world, currency),
        amount=_cents(amount),
        currency=currency,
        date=date(int(paid_in[:4]), int(paid_in[5:]), 10),
        payee="Pago",
        category_id=_spending_category_id(world, category),
        recurring_id=item.id,
        settles_due=due,
    )
    world.require_clean(f"recording the late payment that settled the {turn} turn of {charge!r}")


@step(r"the user deletes that payment")
def when_delete_that_payment(world: World) -> None:
    """Undoing the answer, which is not the same as calling off the charge."""
    world.attempt(transactions.delete_transaction, world.session, world.last_linked_id.id)
    world.require_clean("deleting the payment that settled a turn")


@step(
    r'in (?P<year_month>\d{4}-\d{2}) the fund for "(?P<charge>[^"]+)" says the charge lands in (?P<lands>\d{4}-\d{2})'
)
def then_fund_lands_in_month(world: World, year_month: str, charge: str, lands: str) -> None:
    """What the fund is filling for, read in a month the payment did not happen in.

    The month is named because that is the defect this exists for: settlement
    used to be counted inside the month being read, so a charge paid in August
    was forgotten in September and asked for all over again.
    """
    status = _call("fund_status", world.session, _fund_for(world, charge).id, year_month)
    assert status.charges, f"the fund for {charge!r} is filling for nothing in {year_month}"
    assert status.charges[0].charge_month == lands, (
        f"in {year_month} the fund for {charge!r} is filling for {status.charges[0].charge_month}, not {lands}"
    )


@step(r'"(?P<charge>[^"]+)" was charged (?P<back>\d+) months? ago')
def given_charge_was_paid_months_ago(world: World, charge: str, back: str) -> None:
    """A turn the engine already charged, carrying the charge's own name.

    Every payment the engine makes has said which charge it was since feature
    013; this is that, planted in a past month so the average has something to
    stop counting (AC-9).
    """
    item = world.session.get(RecurringItem, _charge_id(world, charge))
    world.attempt(
        transactions.record_expense,
        world.session,
        account_id=_default_account_id(world, item.currency),
        amount=item.amount,
        currency=item.currency,
        date=_shift_months(world.today, int(back)),
        payee=charge,
        category_id=item.category_id,
        source="agent",
        recurring_id=item.id,
    )
    world.require_clean(f"charging {charge!r} {back} months ago")


@step(r"the funds ask (?P<amount>" + _DEC + r") COP altogether this month")
def then_funds_ask_altogether(world: World, amount: str) -> None:
    """Every fund's figure added up, each converted once at the month's rate.

    Read across the whole list rather than off one row, because the claim AC-6
    and AC-9 both make is about the total: the migration may move a figure from
    one row to two, and a marked charge may move one from an average to a fund
    of its own, but neither may change what the month asks.
    """
    year_month = _month_of(world.today)
    asking = sum(
        _call("fund_status", world.session, line.fund_id, year_month).asks_cop
        for line in _call("list_funds", world.session)
    )
    assert asking == _cents(amount), f"the funds ask {asking} altogether, expected {_cents(amount)}"


@step(r'there is no fund on "(?P<category>[^"]+)"')
def then_no_category_fund(world: World, category: str) -> None:
    fund = _call("fund_on_category", world.session, _category_id(world, category))
    assert fund is None, f"{category!r} still carries a fund of its own (id {fund.id})"


@step(r'there is still a fund on "(?P<category>[^"]+)"')
def then_still_a_category_fund(world: World, category: str) -> None:
    fund = _call("fund_on_category", world.session, _category_id(world, category))
    assert fund is not None, f"{category!r} lost the fund that covers the whole category{_context(world)}"
