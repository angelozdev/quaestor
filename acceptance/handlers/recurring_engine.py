"""Step handlers — feature 007 recurring-engine.

Bound to the services layer (``quaestor.services.recurring/transactions/
accounts``); the assistant steps go through the MCP tools layer
(``quaestor.mcp.tools.temporal``), which is the conversational surface the
specs describe.

Ten ACs are decided target behaviour, so their bindings are RED against
current code on purpose. Three of them name a service API that does not
exist yet and raise where they are called — ``pending_dates``,
``accept_pending_dates`` and ``decline_pending_dates`` for the per-date
acceptance of AC-12. The rest bind to shipped calls whose assertions simply
fail: per-item failure reporting (AC-24) reads a ``failures`` attribute that
``materialize_due`` does not carry, and the engine mark on a movement
(AC-25) reads a ``Source`` value that does not exist. Plan time owns the
final shape of all five; these bindings are the intent, not the design.

A ``Given`` obligation is created directly, which is the spec's "declared
before its start date" case. The ``When the user declares …`` steps go
through the same call today; what separates them is AC-12's offer, asserted
on its own.

Dates are relative to ``world.today`` except where the end-of-month clamp
needs a fixed calendar (AC-8), which uses absolute dates.
"""
from __future__ import annotations

import re as _re
from datetime import date as Date
from datetime import timedelta

from quaestor.domain.errors import NotFound, QuaestorError, ValidationError
from quaestor.domain.models import (
    IntervalUnit,
    OccurrenceStatus,
    RecurringItem,
    RecurringMode,
    RecurringOccurrence,
    Transaction,
    TxType,
)
from quaestor.domain.money import major_to_cents
from quaestor.mcp.tools import temporal
from quaestor.services import accounts, occurrences, recurring, transactions
from sqlmodel import select

from . import step
from .fx_read_time import _DEC
from .world import World

_REJECTED = (ValidationError, NotFound, QuaestorError, TypeError, ValueError)

_WHEN = r"today|in \d+ days|\d+ days ago|on \d{4}-\d{2}-\d{2}|\d{4}-\d{2}-\d{2}"

_DECLARATION = (
    r" every (?P<count>-?\d+) (?P<unit>day|week|month|year)"
    r" starting (?P<start>" + _WHEN + r")"
    r"(?: ending (?P<end>" + _WHEN + r"))?"
    r'(?: in category "(?P<category>[^"]+)")?'
    r", (?P<mode>paying itself|waiting for approval)"
)


def _when(world: World, phrase: str) -> Date:
    """Resolve a date phrase against the scenario's today."""
    if phrase == "today":
        return world.today
    iso = _re.fullmatch(r"(?:on )?(\d{4})-(\d{2})-(\d{2})", phrase)
    if iso is not None:
        return Date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
    ahead = _re.fullmatch(r"in (\d+) days", phrase)
    if ahead is not None:
        return world.today + timedelta(days=int(ahead.group(1)))
    behind = _re.fullmatch(r"(\d+) days ago", phrase)
    if behind is not None:
        return world.today - timedelta(days=int(behind.group(1)))
    raise AssertionError(f"unrecognised date phrase: {phrase!r}")


def _mode(phrase: str) -> RecurringMode:
    return RecurringMode.auto if phrase == "paying itself" else RecurringMode.manual


def _item(world: World, name: str) -> RecurringItem:
    item_id = world.recurring_ids.get(name)
    if item_id is None:
        raise AssertionError(f"no repeating obligation {name!r} in this scenario")
    item = world.session.get(RecurringItem, item_id)
    if item is None:
        raise AssertionError(f"the obligation {name!r} is gone from the records")
    world.session.refresh(item)
    return item


def _occurrences(world: World, name: str) -> list[RecurringOccurrence]:
    rows = list(
        world.session.exec(
            select(RecurringOccurrence)
            .where(RecurringOccurrence.recurring_id == _item(world, name).id)
            .order_by(RecurringOccurrence.due_date)
        ).all()
    )
    for row in rows:
        world.session.refresh(row)
    return rows


def _occurrence_on(world: World, name: str, due: Date) -> RecurringOccurrence:
    for occ in _occurrences(world, name):
        if occ.due_date == due:
            return occ
    raise AssertionError(
        f"{name!r} has no turn due on {due}; it has "
        f"{[str(o.due_date) for o in _occurrences(world, name)]}"
    )


def _charges(world: World, name: str) -> list[RecurringOccurrence]:
    live = (OccurrenceStatus.posted, OccurrenceStatus.planned)
    return [o for o in _occurrences(world, name) if o.status in live]


def _pending_dates(world: World, name: str) -> list[Date]:
    """Dates awaiting the user's answer (AC-12) — RED until the API exists."""
    offer = getattr(occurrences, "pending_dates", None)
    if offer is None:
        raise AssertionError(
            "no way to offer passed due dates for the user to accept or decline "
            "(AC-12 is target behaviour)"
        )
    return list(offer(world.session, _item(world, name).id))


def _declare(
    world: World,
    *,
    name: str,
    payee: str,
    tx_type: TxType,
    amount: str,
    currency: str,
    account: str,
    count: str,
    unit: str,
    start: str,
    end: str | None,
    category: str | None,
    mode: str,
    already_existed: bool = False,
) -> None:
    start_date = _when(world, start)
    world.attempt(
        recurring.create_recurring,
        world.session,
        name=name,
        payee=payee,
        type=tx_type,
        mode=_mode(mode),
        amount=major_to_cents(amount),
        currency=currency,
        category_id=world.categories.get(category) if category else None,
        account_id=world.account_id_or_missing(account),
        interval_unit=IntervalUnit(unit) if unit else None,
        interval_count=int(count),
        start_date=start_date,
        end_date=_when(world, end) if end else None,
        declared_on=start_date if already_existed else world.today,
    )
    if world.last_error is None:
        item = world.session.exec(
            select(RecurringItem).where(RecurringItem.name == name)
        ).first()
        if item is not None:
            world.recurring_ids[name] = item.id


def _run(world: World, until: Date) -> None:
    """One daily run. Per-item failure reporting is AC-24, target behaviour."""
    world.run_failures = []
    try:
        result = occurrences.materialize_due(world.session, until)
    except Exception as exc:
        world.run_failures = [str(exc)]
        world.reopen_session()
        return
    world.run_failures = [str(f) for f in getattr(result, "failures", [])]


def _linked_tx(world: World, name: str, due: Date) -> Transaction:
    occ = _occurrence_on(world, name, due)
    if occ.transaction_id is None:
        raise AssertionError(f"the turn of {name!r} due on {due} has no movement")
    tx = world.session.get(Transaction, occ.transaction_id)
    if tx is None:
        raise AssertionError(
            f"the turn of {name!r} due on {due} points at a movement that no "
            f"longer exists"
        )
    world.session.refresh(tx)
    return tx


@step(
    r"a repeating payment of (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3})"
    r' to "(?P<payee>[^"]+)" from "(?P<account>[^"]+)"' + _DECLARATION
)
def given_repeating_payment(
    world: World, payee: str, **kw
) -> None:
    _declare(
        world, name=payee, payee=payee, tx_type=TxType.expense,
        already_existed=True, **kw
    )
    world.require_clean(f"declaring the repeating payment to {payee!r}")


@step(
    r"a repeating income of (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3})"
    r' from "(?P<payee>[^"]+)" into "(?P<account>[^"]+)"' + _DECLARATION
)
def given_repeating_income(world: World, payee: str, **kw) -> None:
    _declare(
        world, name=payee, payee=payee, tx_type=TxType.income,
        already_existed=True, **kw
    )
    world.require_clean(f"declaring the repeating income from {payee!r}")


@step(
    r"the user (?:declares|tries to declare) a repeating payment of"
    r" (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3})"
    r' to "(?P<payee>[^"]+)" from "(?P<account>[^"]+)"' + _DECLARATION
)
def when_declare_payment(world: World, payee: str, **kw) -> None:
    _declare(world, name=payee, payee=payee, tx_type=TxType.expense, **kw)


@step(
    r"the user (?:declares|tries to declare) a repeating income of"
    r" (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3})"
    r' from "(?P<payee>[^"]+)" into "(?P<account>[^"]+)"' + _DECLARATION
)
def when_declare_income(world: World, payee: str, **kw) -> None:
    _declare(world, name=payee, payee=payee, tx_type=TxType.income, **kw)


@step(
    r"the user tries to declare a repeating transfer of"
    r" (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3})"
    r' from "(?P<account>[^"]+)"' + _DECLARATION
)
def when_declare_transfer(world: World, **kw) -> None:
    _declare(
        world, name="Traslado", payee="Traslado", tx_type=TxType.transfer, **kw
    )


@step(
    r"the assistant declares a repeating payment of"
    r" (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3})"
    r' to "(?P<payee>[^"]+)" from "(?P<account>[^"]+)"' + _DECLARATION
)
def when_assistant_declares_payment(
    world: World,
    amount: str,
    currency: str,
    payee: str,
    account: str,
    count: str,
    unit: str,
    start: str,
    end: str | None = None,
    category: str | None = None,
    mode: str = "paying itself",
) -> None:
    def action():
        temporal.create_recurring(
            world.session,
            temporal.CreateRecurringInput(
                name=payee,
                payee=payee,
                type="expense",
                mode="auto" if mode == "paying itself" else "manual",
                amount=major_to_cents(amount),
                account=account,
                currency=currency,
                category=category,
                interval_unit=unit,
                interval_count=int(count),
                start_date=_when(world, start),
                end_date=_when(world, end) if end else None,
            ),
        )
        item = world.session.exec(
            select(RecurringItem).where(RecurringItem.name == payee)
        ).first()
        if item is not None:
            world.recurring_ids[payee] = item.id

    world.attempt(action)


@step(r"the assistant is asked about the repeating obligations")
def when_assistant_asked_recurring(world: World) -> None:
    def action():
        world.assistant_answer = temporal.list_recurring(
            world.session, temporal.ListRecurringInput()
        )

    world.attempt(action)


@step(r"the daily run happens(?P<again> again)?")
def when_daily_run(world: World, again: str | None = None) -> None:
    _run(world, world.today)


@step(r"the daily run happens as if it were (?P<when>" + _WHEN + r")")
def when_daily_run_as_if(world: World, when: str) -> None:
    _run(world, _when(world, when))


@step(r"the user views the repeating obligations")
def when_view_recurring(world: World) -> None:
    world.recurring_view = recurring.list_recurring(
        world.session, active=True, today=world.today
    )


@step(r"the user views the switched-off obligations")
def when_view_switched_off(world: World) -> None:
    world.recurring_view = recurring.list_recurring(
        world.session, active=False, today=world.today
    )


@step(r'the user switches off "(?P<name>[^"]+)"')
def when_switch_off(world: World, name: str) -> None:
    world.attempt(recurring.deactivate_recurring, world.session, _item(world, name).id)


@step(r'the user switches "(?P<name>[^"]+)" back on')
def when_switch_back_on(world: World, name: str) -> None:
    world.attempt(
        recurring.restore_recurring,
        world.session,
        _item(world, name).id,
        today=world.today,
    )


@step(
    r'the user (?:changes|tries to change) the amount of "(?P<name>[^"]+)"'
    r" to (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3})"
)
def when_change_amount(world: World, name: str, amount: str, currency: str) -> None:
    world.attempt(
        recurring.update_recurring,
        world.session,
        _item(world, name).id,
        amount=major_to_cents(amount),
    )


@step(
    r'the user tries to change the currency of "(?P<name>[^"]+)"'
    r" to (?P<currency>[A-Z]{3})"
)
def when_change_currency(world: World, name: str, currency: str) -> None:
    world.attempt(
        recurring.update_recurring,
        world.session,
        _item(world, name).id,
        currency=currency,
    )


@step(r'the user tries to turn "(?P<name>[^"]+)" into an income')
def when_change_type(world: World, name: str) -> None:
    world.attempt(
        recurring.update_recurring,
        world.session,
        _item(world, name).id,
        type=TxType.income,
    )


@step(
    r'the user moves the start of "(?P<name>[^"]+)" back to'
    r" (?P<when>" + _WHEN + r")"
)
def when_move_start_back(world: World, name: str, when: str) -> None:
    world.attempt(
        recurring.update_recurring,
        world.session,
        _item(world, name).id,
        start_date=_when(world, when),
    )


@step(
    r'the user extends the end of "(?P<name>[^"]+)" to (?P<when>' + _WHEN + r")"
)
def when_extend_end(world: World, name: str, when: str) -> None:
    world.attempt(
        recurring.update_recurring,
        world.session,
        _item(world, name).id,
        end_date=_when(world, when),
    )


@step(r'the user moves "(?P<name>[^"]+)" to the account "(?P<account>[^"]+)"')
def when_move_account(world: World, name: str, account: str) -> None:
    world.attempt(
        recurring.update_recurring,
        world.session,
        _item(world, name).id,
        account_id=world.account_id_or_missing(account),
    )


@step(
    r'the user (?:skips|tries to skip) the turn of "(?P<name>[^"]+)"'
    r" due (?P<when>" + _WHEN + r")"
)
def when_skip_turn(world: World, name: str, when: str) -> None:
    world.attempt(
        recurring.skip_recurring,
        world.session,
        _item(world, name).id,
        _when(world, when),
    )


@step(
    r'the user deletes the charge to "(?P<name>[^"]+)"'
    r" from (?P<when>" + _WHEN + r")"
)
def when_delete_charge(world: World, name: str, when: str) -> None:
    tx = _linked_tx(world, name, _when(world, when))
    world.attempt(transactions.delete_transaction, world.session, tx.id)


@step(r"the user accepts (?P<count>\d+) of the passed dates for \"(?P<name>[^\"]+)\"")
def when_accept_some_passed(world: World, count: str, name: str) -> None:
    accept = getattr(occurrences, "accept_pending_dates", None)
    if accept is None:
        raise AssertionError(
            "no way to accept some of the passed due dates (AC-12 is target "
            "behaviour)"
        )
    dates = _pending_dates(world, name)[: int(count)]
    world.attempt(accept, world.session, _item(world, name).id, dates)


@step(r'the user accepts every passed date for "(?P<name>[^"]+)"')
def when_accept_all_passed(world: World, name: str) -> None:
    accept = getattr(occurrences, "accept_pending_dates", None)
    if accept is None:
        raise AssertionError(
            "no way to accept the passed due dates (AC-12 is target behaviour)"
        )
    world.attempt(
        accept, world.session, _item(world, name).id, _pending_dates(world, name)
    )


@step(r'the user declines every passed date for "(?P<name>[^"]+)"')
def when_decline_all_passed(world: World, name: str) -> None:
    decline = getattr(occurrences, "decline_pending_dates", None)
    if decline is None:
        raise AssertionError(
            "no way to decline the passed due dates (AC-12 is target behaviour)"
        )
    world.attempt(
        decline, world.session, _item(world, name).id, _pending_dates(world, name)
    )


@step(r'the account "(?P<name>[^"]+)" is retired')
def when_retire_account(world: World, name: str) -> None:
    world.attempt(accounts.archive_account, world.session, world.accounts[name])
    world.require_clean(f"retiring the account {name!r}")


@step(r'the account "(?P<name>[^"]+)" is brought back')
def when_restore_account(world: World, name: str) -> None:
    world.attempt(accounts.unarchive_account, world.session, world.accounts[name])
    world.require_clean(f"bringing the account {name!r} back")


@step(
    r"the user registers an expense of (?P<amount>" + _DEC + r")"
    r' (?P<currency>[A-Z]{3}) from "(?P<account>[^"]+)" to "(?P<payee>[^"]+)"'
)
def when_register_expense_to_payee(
    world: World, amount: str, currency: str, account: str, payee: str
) -> None:
    def action():
        tx = transactions.record_expense(
            world.session,
            world.accounts[account],
            major_to_cents(amount),
            currency,
            world.today,
            payee,
        )
        world.last_expense_id = tx.id

    world.attempt(action)


@step(r'"(?P<name>[^"]+)" has been charged (?P<count>\d+) times?')
def then_charged_times(world: World, name: str, count: str) -> None:
    charges = _charges(world, name)
    assert len(charges) == int(count), (
        f"{name!r} has {len(charges)} charge(s), expected {count} "
        f"(turns: {[(str(o.due_date), o.status.value) for o in _occurrences(world, name)]})"
    )


@step(r'"(?P<name>[^"]+)" was charged (?P<when>' + _WHEN + r")")
def then_charged_on(world: World, name: str, when: str) -> None:
    due = _when(world, when)
    occ = _occurrence_on(world, name, due)
    assert occ.status in (OccurrenceStatus.posted, OccurrenceStatus.planned), (
        f"the turn of {name!r} due on {due} is {occ.status.value}, not a charge"
    )


@step(
    r'"(?P<name>[^"]+)" was charged (?P<amount>' + _DEC + r")"
    r" (?P<currency>[A-Z]{3}) (?P<when>" + _WHEN + r")"
)
def then_charged_amount_on(
    world: World, name: str, amount: str, currency: str, when: str
) -> None:
    due = _when(world, when)
    tx = _linked_tx(world, name, due)
    expected = major_to_cents(amount)
    assert tx.amount == expected and tx.currency == currency, (
        f"the charge to {name!r} on {due} is {tx.amount} {tx.currency}, "
        f"expected {expected} {currency}"
    )
    assert tx.date == due, f"the charge to {name!r} is dated {tx.date}, not {due}"


@step(
    r'the turn of "(?P<name>[^"]+)" due (?P<when>' + _WHEN + r")"
    r" is (?P<state>recorded as paid|waiting for approval|skipped)"
)
def then_turn_state(world: World, name: str, when: str, state: str) -> None:
    expected = {
        "recorded as paid": OccurrenceStatus.posted,
        "waiting for approval": OccurrenceStatus.planned,
        "skipped": OccurrenceStatus.skipped,
    }[state]
    occ = _occurrence_on(world, name, _when(world, when))
    assert occ.status == expected, (
        f"the turn of {name!r} due {when} is {occ.status.value}, expected "
        f"{expected.value}"
    )


@step(r'nothing about "(?P<name>[^"]+)" is waiting for the user\'s answer')
def then_nothing_waiting(world: World, name: str) -> None:
    waiting = [
        o for o in _occurrences(world, name) if o.status == OccurrenceStatus.planned
    ]
    assert not waiting, (
        f"{name!r} left {len(waiting)} turn(s) waiting for approval: "
        f"{[str(o.due_date) for o in waiting]}"
    )
    offer = getattr(occurrences, "pending_dates", None)
    if offer is not None:
        pending = list(offer(world.session, _item(world, name).id))
        assert not pending, (
            f"{name!r} left {len(pending)} date(s) awaiting the user's decision"
        )


@step(r'the user is offered (?P<count>\d+) passed dates for "(?P<name>[^"]+)"')
def then_offered_passed_dates(world: World, count: str, name: str) -> None:
    dates = _pending_dates(world, name)
    assert len(dates) == int(count), (
        f"{name!r} offers {len(dates)} passed date(s), expected {count}: "
        f"{[str(d) for d in dates]}"
    )


@step(r'"(?P<name>[^"]+)" is switched off')
def then_switched_off(world: World, name: str) -> None:
    item = _item(world, name)
    assert not recurring.is_live(item, world.today), f"{name!r} is still live"


@step(r'"(?P<name>[^"]+)" is live')
def then_live(world: World, name: str) -> None:
    item = _item(world, name)
    assert recurring.is_live(item, world.today), f"{name!r} is switched off"


@step(
    r'"(?P<name>[^"]+)" is described as (?P<amount>' + _DEC + r")"
    r" (?P<currency>[A-Z]{3}) every (?P<count>\d+) (?P<unit>day|week|month|year)"
    r'(?: in category "(?P<category>[^"]+)")?'
)
def then_described_as(
    world: World,
    name: str,
    amount: str,
    currency: str,
    count: str,
    unit: str,
    category: str | None = None,
) -> None:
    item = _item(world, name)
    assert item.amount == major_to_cents(amount), (
        f"{name!r} is {item.amount}, expected {major_to_cents(amount)}"
    )
    assert item.currency == currency, f"{name!r} is in {item.currency}, not {currency}"
    assert item.interval_count == int(count) and item.interval_unit.value == unit, (
        f"{name!r} repeats every {item.interval_count} {item.interval_unit.value}, "
        f"expected every {count} {unit}"
    )
    if category is not None:
        assert item.category_id == world.categories.get(category), (
            f"{name!r} is not in category {category!r}"
        )


@step(r'the list shows "(?P<name>[^"]+)"')
def then_list_shows_obligation(world: World, name: str) -> None:
    names = [i.name for i in world.recurring_view or []]
    assert name in names, f"{name!r} is not in the list ({names})"


@step(r'the list does not show "(?P<name>[^"]+)"')
def then_list_omits_obligation(world: World, name: str) -> None:
    names = [i.name for i in world.recurring_view or []]
    assert name not in names, f"{name!r} is still in the list ({names})"


@step(
    r'the list shows "(?P<name>[^"]+)" at (?P<amount>' + _DEC + r")"
    r" (?P<currency>[A-Z]{3}) every (?P<count>\d+) (?P<unit>day|week|month|year)"
)
def then_list_shows_detail(
    world: World, name: str, amount: str, currency: str, count: str, unit: str
) -> None:
    listed = {i.name: i for i in world.recurring_view or []}
    assert name in listed, f"{name!r} is not in the list ({list(listed)})"
    item = listed[name]
    assert item.amount == major_to_cents(amount) and item.currency == currency, (
        f"{name!r} is listed at {item.amount} {item.currency}"
    )
    assert item.interval_count == int(count) and item.interval_unit.value == unit, (
        f"{name!r} is listed as every {item.interval_count} "
        f"{item.interval_unit.value}"
    )


@step(r'the daily run reports "(?P<name>[^"]+)" as needing attention')
def then_run_reports_failure(world: World, name: str) -> None:
    reported = world.run_failures
    assert any(name in message for message in reported), (
        f"the run did not report {name!r} as needing attention (reported: "
        f"{reported})"
    )


@step(r'the daily run does not report "(?P<name>[^"]+)" as needing attention')
def then_run_omits_failure(world: World, name: str) -> None:
    reported = world.run_failures
    assert not any(name in message for message in reported), (
        f"the run reported {name!r} as needing attention: {reported}"
    )


@step(
    r'the movements list shows the charge to "(?P<name>[^"]+)"'
    r" as (?P<origin>made by the engine|entered by hand)"
)
def then_movement_origin(world: World, name: str, origin: str) -> None:
    if origin == "entered by hand":
        tx = world.session.get(Transaction, world.last_expense_id)
        assert tx is not None, "no movement was registered earlier in the scenario"
        assert tx.source.value == "manual", (
            f"the movement to {name!r} is marked {tx.source.value}, not hand-entered"
        )
        return
    tx = _linked_tx(world, name, world.today)
    assert tx.source.value != "manual", (
        f"the charge to {name!r} is recorded as hand-entered "
        f"({tx.source.value}); nothing on the movements list says the engine "
        f"made it"
    )


@step(r'that movement names "(?P<name>[^"]+)" as the obligation behind it')
def then_movement_names_obligation(world: World, name: str) -> None:
    tx = _linked_tx(world, name, world.today)
    assert tx.recurring_id is not None, (
        f"the charge to {name!r} does not point back at any obligation"
    )
    item = world.session.get(RecurringItem, tx.recurring_id)
    assert item is not None and item.name == name, (
        f"the charge to {name!r} points at a different obligation"
    )


@step(r'the assistant\'s answer names "(?P<name>[^"]+)"')
def then_assistant_names(world: World, name: str) -> None:
    world.require_clean("asking the assistant about the repeating obligations")
    answer = world.assistant_answer or ""
    assert name in answer, f"the assistant's answer does not name {name!r}: {answer!r}"


@step(
    r"the assistant's answer shows (?P<amount>" + _DEC + r")"
    r' (?P<currency>[A-Z]{3}) for "(?P<name>[^"]+)"'
)
def then_assistant_shows_amount(
    world: World, amount: str, currency: str, name: str
) -> None:
    world.require_clean("asking the assistant about the repeating obligations")
    answer = world.assistant_answer or ""
    digits = amount.split(".", maxsplit=1)[0]
    grouped = f"{int(digits):,}".replace(",", ".")
    assert digits in answer or grouped in answer, (
        f"the assistant's answer does not state {amount} for {name!r}: {answer!r}"
    )


@step(r"the declaration is rejected")
def then_declaration_rejected(world: World) -> None:
    world.consume_rejection(_REJECTED, "declaring the repeating obligation")


@step(r'the change to "(?P<name>[^"]+)" is rejected')
def then_change_rejected(world: World, name: str) -> None:
    world.consume_rejection(_REJECTED, f"changing {name!r}")


@step(r"the skip is rejected")
def then_skip_rejected(world: World) -> None:
    world.consume_rejection(_REJECTED, "skipping the turn")


@step(r"the user is told that date was already charged")
def then_told_already_charged(world: World) -> None:
    err = world.last_error
    assert err is not None, (
        "the skip succeeded; the user was never told the date was already charged"
    )
    message = str(err).lower()
    assert "charged" in message or "posted" in message or "paid" in message, (
        f"the refusal does not say the date was already charged: {err}"
    )
