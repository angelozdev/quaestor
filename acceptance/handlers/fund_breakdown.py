"""Step handlers — feature 014 fund-explains-what-it-asks.

Feature 003 left 71 steps about funds in ``sinking_funds``, and this feature
adds one noun to that vocabulary: the **line**, one per charge the fund is
filling for. Everything a scenario says about a fund's figure still binds
there; what binds here is what the figure opens into, and what the warning is
now about.

The API bound is the same ``quaestor.services.funds``, reached through
``sinking_funds``' own ``_call`` so a missing capability still reds as the name
it wanted rather than as an import error.

Two steps measure rather than read, and both are deliberate:

``the month was read once``      counts statements while the month is read with
                                 every fund and again with one, and compares —
                                 a claim about cost that cannot be faked by a
                                 number a service reports about itself.
``the records hold no breakdown`` reads the schema, so a table added later to
                                 store what this feature derives fails it.
"""

from __future__ import annotations

from quaestor.domain.errors import MissingRate, QuaestorError
from quaestor.domain.models import RecurringItem
from quaestor.domain.rules import month_bounds
from sqlalchemy import event
from sqlalchemy import inspect as inspect_schema

from . import step
from .fx_read_time import _DEC, _set_trm
from .planned_payments import skip_the_obligations_turn
from .sinking_funds import (
    _MONTH,
    _assistant,
    _call,
    _cents,
    _context,
    _month_of,
    _shift_months,
    _status,
    given_fund_from_obligations,
    given_recurring_charge,
    warning_shown,
)
from .world import World

_REFUSED = (MissingRate, QuaestorError)

_A_BREAKDOWN = ("charge", "line", "breakdown", "term", "split")

_FUNDS_IN_THE_MEASURE = 5


# ------------------------------------------------------------------ helpers


def _lines(world: World, fund: str):
    """What the fund says its figure is made of."""
    status = _status(world, fund)
    charges = getattr(status, "charges", None)
    if charges is None:
        raise AssertionError(f"the fund on {fund!r} reports no lines behind its figure{_context(world)}")
    return charges


def _line(world: World, fund: str, charge: str):
    lines = _lines(world, fund)
    found = next((line for line in lines if line.name == charge), None)
    if found is None:
        named = sorted(line.name for line in lines)
        raise AssertionError(f"the fund on {fund!r} says nothing about {charge!r}; it names {named}{_context(world)}")
    return found


def _warning(world: World) -> str:
    said = warning_shown(world)
    if not said:
        raise AssertionError("the preview carries no warning")
    return said


def _statements_reading(world: World, year_month: str) -> int:
    """How many statements the month costs, read cold."""
    counted = 0

    def count(*_args) -> None:
        nonlocal counted
        counted += 1

    world.session.expire_all()
    event.listen(world.engine, "before_cursor_execute", count)
    try:
        _call("available", world.session, year_month)
    finally:
        event.remove(world.engine, "before_cursor_execute", count)
    return counted


# -------------------------------------------------------------------- Given


@step(r'the payment to "(?P<payee>[^"]+)" was skipped this month')
def given_skipped_this_month(world: World, payee: str) -> None:
    skip_the_obligations_turn(world, payee, world.today)
    world.require_clean(f"skipping this month's payment to {payee!r}")


@step(r"five categories each holding a repeating charge and a fund funded from its obligations")
def given_five_funded_categories(world: World) -> None:
    """Enough funds that reading the month once and reading it five times differ."""
    start = _month_of(world.today)
    charges_in = _month_of(_shift_months(world.today, -12))
    for index in range(1, _FUNDS_IN_THE_MEASURE + 1):
        category = f"Categoría {index}"
        given_recurring_charge(world, f"Cobro {index}", category, "1200000.00", "COP", "year", charges_in)
        given_fund_from_obligations(world, category, start, None, None)


# --------------------------------------------------------------------- When


@step(r"the TRM is set to (?P<value>" + _DEC + r")")
def when_trm_is_set(world: World, value: str) -> None:
    world.attempt(_set_trm, world.session, value)


@step(r'the assistant is asked about the fund on "(?P<name>[^"]+)"')
def when_assistant_asked_about_one_fund(world: World, name: str) -> None:
    """The card that states figures, unlike the list, which states none.

    003 bound *the funds* to the list, whose columns are the category, the rule
    and the month it started — a figure was never among them. AC-18 is about
    the answer that carries one, and that is this one.
    """
    world.assistant_answer = world.attempt(
        _assistant, world, "fund_status", "FundStatusInput", category=name, month=_month_of(world.today)
    )


@step(r'the assistant is asked to preview a fund on "(?P<name>[^"]+)" funded from its obligations')
def when_assistant_previews(world: World, name: str) -> None:
    world.assistant_answer = world.attempt(
        _assistant,
        world,
        "preview_fund",
        "PreviewFundInput",
        category=name,
        rule="from-recurring",
        start_month=_month_of(world.today),
    )


# --------------------------------------------------------------------- Then


@step(r'the fund on "(?P<fund>[^"]+)" says "(?P<charge>[^"]+)" asks (?P<amount>' + _DEC + r") COP")
def then_line_asks(world: World, fund: str, charge: str, amount: str) -> None:
    asks = _line(world, fund, charge).asks
    assert asks == _cents(amount), f"the fund on {fund!r} says {charge!r} asks {asks}, expected {_cents(amount)}"


@step(r'the fund on "(?P<fund>[^"]+)" says "(?P<charge>[^"]+)" costs (?P<amount>' + _DEC + r") COP")
def then_line_costs(world: World, fund: str, charge: str, amount: str) -> None:
    costs = _line(world, fund, charge).costs
    assert costs == _cents(amount), f"the fund on {fund!r} says {charge!r} costs {costs}, expected {_cents(amount)}"


@step(r'the fund on "(?P<fund>[^"]+)" says "(?P<charge>[^"]+)" charges in (?P<month>' + _MONTH + r")")
def then_line_charges_in(world: World, fund: str, charge: str, month: str) -> None:
    lands = _line(world, fund, charge).charge_month
    assert lands == month, f"the fund on {fund!r} says {charge!r} charges in {lands}, expected {month}"


@step(r'the fund on "(?P<fund>[^"]+)" says "(?P<charge>[^"]+)" is due this month')
def then_line_is_due_now(world: World, fund: str, charge: str) -> None:
    lands = _line(world, fund, charge).charge_month
    now = _month_of(world.today)
    assert lands == now, f"the fund on {fund!r} is saving {charge!r} for {lands}, not reporting it due in {now}"


@step(r'the fund on "(?P<fund>[^"]+)" says "(?P<charge>[^"]+)" is being saved for')
def then_line_is_being_saved_for(world: World, fund: str, charge: str) -> None:
    lands = _line(world, fund, charge).charge_month
    now = _month_of(world.today)
    assert lands > now, f"the fund on {fund!r} says {charge!r} lands in {lands}, which is not later than {now}"


@step(r'the fund on "(?P<fund>[^"]+)" says nothing about "(?P<charge>[^"]+)"')
def then_says_nothing_about(world: World, fund: str, charge: str) -> None:
    named = [line.name for line in _lines(world, fund)]
    assert charge not in named, f"the fund on {fund!r} still names {charge!r} among {named}"


@step(r'the fund on "(?P<fund>[^"]+)" says nothing about "(?P<charge>[^"]+)" landing this month')
def then_says_nothing_landing_now(world: World, fund: str, charge: str) -> None:
    now = _month_of(world.today)
    landing = [line.name for line in _lines(world, fund) if line.charge_month == now]
    assert charge not in landing, f"the fund on {fund!r} still has {charge!r} landing in {now}"


@step(r'the lines on "(?P<fund>[^"]+)" add up to what it asks')
def then_lines_add_up(world: World, fund: str) -> None:
    status = _status(world, fund)
    lines = _lines(world, fund)
    assert lines, f"the fund on {fund!r} asks {status.asks} and names nothing behind it"
    total = sum(line.asks for line in lines)
    assert total == status.asks, f"the lines on {fund!r} add to {total} but it asks {status.asks}"


@step(r'the warning names "(?P<charge>[^"]+)"')
def then_warning_names(world: World, charge: str) -> None:
    said = _warning(world)
    assert charge in said, f"the warning does not name {charge!r}: {said!r}"


@step(r"the warning states (?P<amount>" + _DEC + r") COP")
def then_warning_states(world: World, amount: str) -> None:
    said = _warning(world)
    assert f"{amount} COP" in said, f"the warning does not state {amount} COP: {said!r}"


@step(r"the reading is refused for want of a rate")
def then_refused_for_want_of_a_rate(world: World) -> None:
    refusal = world.consume_rejection(_REFUSED, "reading the funds")
    said = str(refusal).lower()
    assert "rate" in said or "trm" in said, f"the reading was refused, but not for want of a rate: {refusal!r}"


@step(r"the records hold no stored breakdown")
def then_records_hold_no_breakdown(world: World) -> None:
    world.require_clean("reading the funds")
    schema = inspect_schema(world.engine)
    tables = schema.get_table_names()
    stored = [
        f"{table}.{column['name']}"
        for table in tables
        if "fund" in table
        for column in schema.get_columns(table)
        if any(word in column["name"].lower() for word in _A_BREAKDOWN)
    ]
    stored += [table for table in tables if "fund" in table and table != "fund"]
    assert not stored, f"the records store what the fund should derive: {stored}"


@step(r"the month was read once, not once for each fund")
def then_month_read_once(world: World) -> None:
    world.require_clean("reading the funds")
    year_month = _month_of(world.today)
    listed = _call("list_funds", world.session)
    assert len(listed) > 1, "the scenario made one fund, so there is nothing about reading each of them to measure"
    for_many = _statements_reading(world, year_month)
    for line in listed[1:]:
        _call("delete_fund", world.session, line.fund_id)
    for_one = _statements_reading(world, year_month)
    assert for_many == for_one, (
        f"reading {len(listed)} funds cost {for_many} statements and reading one cost {for_one}: "
        f"the month is being read once for each fund"
    )


@step(r"the assistant's answer names no charge behind it")
def then_assistant_names_no_charge(world: World) -> None:
    answer = world.assistant_answer
    if answer is None:
        raise AssertionError("the assistant answered nothing")
    named = [payee for payee in world.recurring_ids if payee in str(answer)]
    assert not named, f"the assistant's answer names {named}, and AC-18 leaves that surface exactly as it is"


@step(r"the assistant's answer carries no warning")
def then_assistant_carries_no_warning(world: World) -> None:
    answer = world.assistant_answer
    if answer is None:
        raise AssertionError("the assistant answered nothing")
    assert "⚠️" not in str(answer), f"the assistant still warns about a charge that lands every month: {answer!r}"


@step(r'"(?P<payee>[^"]+)" stops repeating after (?P<month>' + _MONTH + r")")
def given_stops_repeating(world: World, payee: str, month: str) -> None:
    """The obligation's last turn is the one in `month` — nothing follows it.

    Reachable from the app: the recurring form takes an optional end date. It is
    the state in which a charge that arrives every month has no turn after it,
    which is what AC-13 must survive.
    """
    item = world.session.get(RecurringItem, world.recurring_ids[payee])
    if item is None:
        raise AssertionError(f"no repeating charge {payee!r} in this scenario")
    _, item.end_date = month_bounds(month)
    world.session.add(item)
    world.session.commit()
