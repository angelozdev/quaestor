"""Step handlers — feature 006 planned-payments-to-pay.

Bound to the services layer (``quaestor.services.planned/recurring/
transactions/settings/reports``); the assistant steps go through the MCP
tools layer (``quaestor.mcp.tools.temporal``), which is the conversational
surface the specs describe.

Two intended bindings are RED against current code, on purpose (AC-8 and
AC-15 are decided target behaviour, not shipped behaviour):

- Restoring a skipped payment (AC-8) binds to ``planned.restore_payment``,
  which does not exist yet — the scenario errors until it does.
- The outstanding queue carrying only obligations (AC-15) needs no new
  binding: the assertions simply fail while planned incomes still reach
  the queue.

Due dates are relative to ``world.today`` so the overdue/upcoming boundary
is exercised against a moving today rather than a frozen calendar.
"""
from __future__ import annotations

import re as _re
from datetime import date as Date
from datetime import timedelta

from sqlmodel import select

from quaestor.domain.errors import QuaestorError, ValidationError
from quaestor.domain.models import (
    IntervalUnit,
    OccurrenceStatus,
    RecurringItem,
    RecurringMode,
    RecurringOccurrence,
    Source,
    Transaction,
    TransferDirection,
    TxStatus,
    TxType,
)
from quaestor.domain.money import cents_to_major, major_to_cents
from quaestor.services import (
    fx,
    occurrences,
    planned,
    recurring,
    reports,
    settings as settings_svc,
    transactions,
)

from . import step
from .fx_read_time import _DEC
from .world import World

_DUE = (
    r"due in (?P<in_days>\d+) days"
    r"|due today"
    r"|that fell due (?P<ago_days>\d+) days ago"
    r"|that fell due in a month before last"
)


def _due_date(world: World, phrase: str) -> Date:
    """Resolve a relative due-date phrase against the scenario's today."""
    match = _re.fullmatch(_DUE, phrase)
    if match is None:
        raise AssertionError(f"unrecognised due-date phrase: {phrase!r}")
    if match.group("in_days") is not None:
        return world.today + timedelta(days=int(match.group("in_days")))
    if match.group("ago_days") is not None:
        return world.today - timedelta(days=int(match.group("ago_days")))
    if phrase == "due today":
        return world.today
    return world.previous_month_day.replace(day=1) - timedelta(days=10)


def _account_id(world: World, name: str) -> int:
    return world.account_id_or_missing(name)


def _payment(world: World, payee: str) -> Transaction:
    """The most recent transaction for a payee, whatever its state."""
    rows = world.session.exec(
        select(Transaction).where(Transaction.payee == payee)
    ).all()
    if not rows:
        raise AssertionError(f"no payment to {payee!r} exists in this scenario")
    return max(rows, key=lambda t: t.id)


def _transfer(world: World, destination: str) -> Transaction:
    tx_id = world.transfer_ids.get(destination)
    if tx_id is None:
        raise AssertionError(
            f"no proposed contribution into {destination!r} in this scenario"
        )
    return world.session.get(Transaction, tx_id)


def _compute_queue(world: World, days: int):
    """The queue for [today, today + days], with no exchange-rate lookup."""
    return planned.to_pay(
        world.session,
        world.today,
        world.today + timedelta(days=days),
        today=world.today,
    )


def _viewed_queue(world: World):
    world.require_clean("viewing the outstanding list should have succeeded")
    if world.queue is None:
        raise AssertionError("the outstanding list was never viewed")
    return world.queue


def _payees(queue) -> list[str]:
    return [t.payee for t in queue.all_items()]


def _view(world: World, since: Date, until: Date) -> None:
    """The outstanding surface: the rate is fetched first and fails loud."""

    def action():
        trm = fx.get_trm(world.session)
        world.queue = planned.to_pay(world.session, since, until, today=world.today)
        world.queue_total = world.queue.total_cop_cents(trm)

    world.attempt(action)


def _plan(
    world: World,
    amount: str,
    currency: str,
    payee: str,
    account: str,
    due: str,
    category: str | None = None,
    notes: str | None = None,
) -> None:
    world.attempt(
        planned.plan_payment,
        world.session,
        payee,
        major_to_cents(amount),
        currency,
        _due_date(world, due),
        _account_id(world, account),
        category_id=world.categories.get(category) if category else None,
        notes=notes,
    )


def _materialize_manual_recurring(
    world: World,
    amount: str,
    currency: str,
    payee: str,
    account: str,
    tx_type: TxType,
) -> None:
    item = recurring.create_recurring(
        world.session,
        name=payee,
        payee=payee,
        type=tx_type,
        mode=RecurringMode.manual,
        amount=major_to_cents(amount),
        currency=currency,
        category_id=None,
        account_id=_account_id(world, account),
        interval_unit=IntervalUnit.month,
        interval_count=1,
        start_date=world.today,
    )
    world.recurring_ids[payee] = item.id
    occurrences.materialize_due(world.session, world.today)


def _occurrence(world: World, payee: str) -> RecurringOccurrence:
    item_id = world.recurring_ids.get(payee)
    if item_id is None:
        raise AssertionError(f"no recurring obligation to {payee!r} in this scenario")
    occ = world.session.exec(
        select(RecurringOccurrence).where(RecurringOccurrence.recurring_id == item_id)
    ).first()
    if occ is None:
        raise AssertionError(f"the obligation to {payee!r} never came due")
    world.session.refresh(occ)
    return occ


# ------------------------------------------------------------------- Given


@step(
    r"a planned payment of (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3})"
    r' to "(?P<payee>[^"]+)" from "(?P<account>[^"]+)" (?P<due>' + _DUE + r")"
)
def given_planned_payment_from_account(
    world: World, amount: str, currency: str, payee: str, account: str, due: str, **_
) -> None:
    _plan(world, amount, currency, payee, account, due)
    world.require_clean(f"planning the payment to {payee!r}")


@step(
    r"a planned income of (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3})"
    r' into "(?P<account>[^"]+)" (?P<due>' + _DUE + r")"
)
def given_planned_income(
    world: World, amount: str, currency: str, account: str, due: str, **_
) -> None:
    tx = Transaction(
        date=_due_date(world, due),
        payee="Ingreso esperado",
        type=TxType.income,
        status=TxStatus.planned,
        amount=major_to_cents(amount),
        currency=currency,
        account_id=_account_id(world, account),
        source=Source.manual,
    )
    world.session.add(tx)
    world.session.commit()


@step(
    r"a monthly obligation of (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3})"
    r' to "(?P<payee>[^"]+)" from "(?P<account>[^"]+)"'
    r" that the user approves by hand, already due"
)
def given_monthly_obligation(
    world: World, amount: str, currency: str, payee: str, account: str
) -> None:
    _materialize_manual_recurring(
        world, amount, currency, payee, account, TxType.expense
    )


@step(
    r"a monthly income of (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3})"
    r' from "(?P<payer>[^"]+)" into "(?P<account>[^"]+)"'
    r" that the user approves by hand, already due"
)
def given_monthly_income(
    world: World, amount: str, currency: str, payer: str, account: str
) -> None:
    _materialize_manual_recurring(
        world, amount, currency, payer, account, TxType.income
    )


@step(r'"(?P<account>[^"]+)" is the account transfers come from')
def given_default_source_account(world: World, account: str) -> None:
    settings_svc.update_settings(
        world.session, default_source_account_id=_account_id(world, account)
    )


@step(
    r"a proposed savings contribution of (?P<amount>" + _DEC + r")"
    r' (?P<currency>[A-Z]{3}) into "(?P<account>[^"]+)"'
)
def given_proposed_contribution(
    world: World, amount: str, currency: str, account: str
) -> None:
    tx = Transaction(
        date=world.today,
        payee=f"Aporte a {account}",
        type=TxType.transfer,
        status=TxStatus.planned,
        amount=major_to_cents(amount),
        currency=currency,
        account_id=_account_id(world, account),
        source=Source.manual,
    )
    world.session.add(tx)
    world.session.commit()
    world.session.refresh(tx)
    world.transfer_ids[account] = tx.id


@step(r"the savings contribution that follows a confirmation cannot be recorded")
def given_failing_post_confirm_step(world: World) -> None:
    def boom(tx, session):
        raise ValidationError("the savings contribution could not be recorded")

    planned.POST_CONFIRM_HOOKS.append(boom)
    world.cleanups.append(lambda: planned.POST_CONFIRM_HOOKS.remove(boom))


# -------------------------------------------------------------------- When


@step(
    r"the user (?P<mode>plans|tries to plan) a payment of (?P<amount>" + _DEC + r")"
    r' (?P<currency>[A-Z]{3}) to "(?P<payee>[^"]+)" from "(?P<account>[^"]+)"'
    r" (?P<due>" + _DUE + r")"
    r'(?: in category "(?P<category>[^"]+)")?'
    r'(?: with notes "(?P<notes>[^"]+)")?'
)
def when_user_plans_payment(
    world: World,
    mode: str,
    amount: str,
    currency: str,
    payee: str,
    account: str,
    due: str,
    category: str | None = None,
    notes: str | None = None,
    **_,
) -> None:
    _plan(world, amount, currency, payee, account, due, category, notes)


@step(
    r"the assistant plans a payment of (?P<amount>" + _DEC + r")"
    r' (?P<currency>[A-Z]{3}) to "(?P<payee>[^"]+)" from "(?P<account>[^"]+)"'
    r" (?P<due>" + _DUE + r")"
)
def when_assistant_plans_payment(
    world: World, amount: str, currency: str, payee: str, account: str, due: str, **_
) -> None:
    def action():
        from quaestor.mcp.tools import temporal

        return temporal.plan_payment(
            world.session,
            temporal.PlanPaymentInput(
                payee=payee,
                amount=major_to_cents(amount),
                currency=currency,
                due_date=_due_date(world, due),
                account=account,
            ),
        )

    world.attempt(action)


@step(r"the user views what is outstanding for the next (?P<days>\d+) days")
def when_view_outstanding_next_days(world: World, days: str) -> None:
    _view(world, world.today, world.today + timedelta(days=int(days)))


@step(
    r"the user views what is outstanding for the (?P<span>\d+) days"
    r" starting (?P<offset>\d+) days (?P<direction>from now|ago)"
)
def when_view_outstanding_window(
    world: World, span: str, offset: str, direction: str
) -> None:
    delta = timedelta(days=int(offset))
    since = world.today + delta if direction == "from now" else world.today - delta
    _view(world, since, since + timedelta(days=int(span)))


@step(
    r"the user tries to view what is outstanding for a period"
    r" that ends before it starts"
)
def when_view_inverted_window(world: World) -> None:
    _view(world, world.today + timedelta(days=5), world.today - timedelta(days=5))


@step(r"the user views the report for last month")
def when_view_last_month_report(world: World) -> None:
    month = world.previous_month_day.strftime("%Y-%m")

    def action():
        world.report = reports.monthly_report(world.session, month, today=world.today)
        world.report_month = month

    world.attempt(action)


@step(
    r"the user (?P<mode>confirms|tries to confirm) the payment"
    r' to "(?P<payee>[^"]+)"(?P<again> again)?'
    r"(?: for (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3}))?"
    r"(?: dated (?P<back>\d+) days ago)?"
)
def when_confirm_payment(
    world: World,
    mode: str,
    payee: str,
    again: str | None = None,
    amount: str | None = None,
    currency: str | None = None,
    back: str | None = None,
) -> None:
    tx = _payment(world, payee)
    world.attempt(
        planned.confirm_payment,
        world.session,
        tx.id,
        amount=major_to_cents(amount) if amount is not None else None,
        date=(
            world.today - timedelta(days=int(back)) if back is not None else None
        ),
    )


@step(r'the assistant confirms the payment to "(?P<payee>[^"]+)"')
def when_assistant_confirms_payment(world: World, payee: str) -> None:
    tx = _payment(world, payee)

    def action():
        from quaestor.mcp.tools import temporal

        return temporal.confirm_payment(
            world.session, temporal.ConfirmPaymentInput(tx_id=tx.id)
        )

    world.attempt(action)


@step(r"the user tries to confirm that recorded expense")
def when_confirm_recorded_expense(world: World) -> None:
    tx_id = world.last_expense_id
    if tx_id is None:
        raise AssertionError("no expense was recorded earlier in the scenario")
    world.attempt(planned.confirm_payment, world.session, tx_id)


@step(r'the user (?P<mode>skips|tries to skip) the payment to "(?P<payee>[^"]+)"')
def when_skip_payment(world: World, mode: str, payee: str) -> None:
    tx = _payment(world, payee)
    world.attempt(planned.skip_payment, world.session, tx.id)


@step(r'the user restores the skipped payment to "(?P<payee>[^"]+)"')
def when_restore_payment(world: World, payee: str) -> None:
    tx = _payment(world, payee)
    world.attempt(planned.restore_payment, world.session, tx.id)


@step(
    r"the user (?P<mode>confirms|tries to confirm) the transfer"
    r' into "(?P<account>[^"]+)"'
    r"(?: for (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3}))?"
)
def when_confirm_transfer(
    world: World,
    mode: str,
    account: str,
    amount: str | None = None,
    currency: str | None = None,
) -> None:
    tx = _transfer(world, account)
    world.attempt(
        planned.confirm_payment,
        world.session,
        tx.id,
        amount=major_to_cents(amount) if amount is not None else None,
    )


@step(r'the user deletes the transfer into "(?P<account>[^"]+)"')
def when_delete_transfer(world: World, account: str) -> None:
    tx_id = world.transfer_ids[account]
    world.attempt(transactions.delete_transaction, world.session, tx_id)


@step(r"the obligations that have come due are raised again")
def when_materialize_again(world: World) -> None:
    world.attempt(occurrences.materialize_due, world.session, world.today)


@step(
    r"the assistant is asked what is outstanding"
    r" for the next (?P<days>\d+) days"
)
def when_assistant_asked_outstanding(world: World, days: str) -> None:
    def action():
        from quaestor.mcp.tools import temporal

        world.assistant_answer = temporal.to_pay(
            world.session,
            temporal.ToPayInput(
                since=world.today, until=world.today + timedelta(days=int(days))
            ),
        )

    world.attempt(action)


# -------------------------------------------------------------------- Then


@step(
    r"the outstanding list(?: for the next (?P<days>\d+) days)?"
    r' shows "(?P<payee>[^"]+)" as (?P<bucket>overdue|upcoming)'
)
def then_list_shows_in_bucket(
    world: World, payee: str, bucket: str, days: str | None = None
) -> None:
    queue = _compute_queue(world, int(days)) if days else _viewed_queue(world)
    items = queue.overdue if bucket == "overdue" else queue.upcoming
    other = queue.upcoming if bucket == "overdue" else queue.overdue
    assert payee in [t.payee for t in items], (
        f"{payee!r} is not in the {bucket} group "
        f"(overdue={[t.payee for t in queue.overdue]}, "
        f"upcoming={[t.payee for t in queue.upcoming]})"
    )
    assert payee not in [t.payee for t in other], (
        f"{payee!r} appears in both groups; they must be mutually exclusive"
    )


@step(r'the outstanding list shows "(?P<payee>[^"]+)" exactly once')
def then_list_shows_once(world: World, payee: str) -> None:
    queue = _viewed_queue(world)
    count = _payees(queue).count(payee)
    assert count == 1, f"{payee!r} appears {count} time(s) in the outstanding list"


@step(r'the outstanding list shows "(?P<payee>[^"]+)"')
def then_list_shows(world: World, payee: str) -> None:
    queue = _viewed_queue(world)
    assert payee in _payees(queue), (
        f"{payee!r} is not in the outstanding list ({_payees(queue)})"
    )


@step(r'the outstanding list shows "(?P<upper>[^"]+)" above "(?P<lower>[^"]+)"')
def then_list_order(world: World, upper: str, lower: str) -> None:
    payees = _payees(_viewed_queue(world))
    assert upper in payees and lower in payees, (
        f"expected both {upper!r} and {lower!r} in the list, got {payees}"
    )
    assert payees.index(upper) < payees.index(lower), (
        f"expected {upper!r} above {lower!r}, got {payees}"
    )


@step(r"the outstanding list shows the proposed savings contribution")
def then_list_shows_contribution(world: World) -> None:
    queue = _viewed_queue(world)
    kinds = [t.type for t in queue.all_items()]
    assert TxType.transfer in kinds, (
        f"no proposed contribution in the outstanding list (kinds={kinds})"
    )


@step(
    r"the outstanding list(?: for the next (?P<days>\d+) days)?"
    r' does not show "(?P<payee>[^"]+)"'
)
def then_list_omits(world: World, payee: str, days: str | None = None) -> None:
    queue = _compute_queue(world, int(days)) if days else _viewed_queue(world)
    assert payee not in _payees(queue), (
        f"{payee!r} is still in the outstanding list ({_payees(queue)})"
    )


@step(r"the outstanding list(?: for the next (?P<days>\d+) days)? is empty")
def then_list_empty(world: World, days: str | None = None) -> None:
    queue = _compute_queue(world, int(days)) if days else _viewed_queue(world)
    assert queue.is_empty, (
        f"the outstanding list is not empty: {_payees(queue)}"
    )


@step(r"the outstanding list has no overdue group")
def then_no_overdue_group(world: World) -> None:
    queue = _viewed_queue(world)
    assert not queue.overdue, (
        f"an overdue group was rendered: {[t.payee for t in queue.overdue]}"
    )


@step(r"the outstanding list has exactly (?P<count>\d+) item")
def then_list_item_count(world: World, count: str) -> None:
    queue = _viewed_queue(world)
    payees = _payees(queue)
    assert len(payees) == int(count), (
        f"expected {count} item(s) outstanding, got {len(payees)}: {payees}"
    )


@step(
    r"the outstanding total(?: for the next (?P<days>\d+) days)?"
    r" is (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3})"
)
def then_outstanding_total(
    world: World, amount: str, currency: str, days: str | None = None
) -> None:
    if days:
        total = _compute_queue(world, int(days)).total_cop_cents(
            fx.get_trm(world.session)
        )
    else:
        world.require_clean("viewing the outstanding list should have succeeded")
        total = world.queue_total
    assert total is not None, "the outstanding list was never viewed"
    expected = major_to_cents(amount)
    assert total == expected, (
        f"expected a total of {amount} {currency}, got {cents_to_major(total)}"
    )


@step(r"the outstanding list is not shown")
def then_list_not_shown(world: World) -> None:
    from quaestor.domain.errors import MissingRate

    assert world.queue is None, (
        "the outstanding list was shown although no TRM is set (AC-20: reads "
        "must fail loud, never assume a rate)"
    )
    world.consume_rejection(
        (MissingRate,), "viewing the outstanding list without a TRM"
    )


@step(r'the payment to "(?P<payee>[^"]+)" is waiting to be resolved')
def then_payment_waiting(world: World, payee: str) -> None:
    world.require_clean(f"the payment to {payee!r} should still be waiting")
    tx = _payment(world, payee)
    assert tx.status == TxStatus.planned, (
        f"the payment to {payee!r} is {tx.status.value}, not waiting"
    )


@step(r'the payment to "(?P<payee>[^"]+)" is no longer waiting')
def then_payment_not_waiting(world: World, payee: str) -> None:
    world.require_clean(f"resolving the payment to {payee!r}")
    tx = _payment(world, payee)
    assert tx.status != TxStatus.planned, (
        f"the payment to {payee!r} is still waiting"
    )


@step(
    r'the payment to "(?P<payee>[^"]+)" counts as spent for'
    r" (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3})"
)
def then_payment_spent_for(
    world: World, payee: str, amount: str, currency: str
) -> None:
    world.require_clean(f"confirming the payment to {payee!r}")
    tx = _payment(world, payee)
    assert tx.status == TxStatus.posted, (
        f"the payment to {payee!r} is {tx.status.value}, not spent"
    )
    expected = major_to_cents(amount)
    assert tx.amount == expected and tx.currency == currency, (
        f"expected {amount} {currency}, got "
        f"{cents_to_major(tx.amount)} {tx.currency}"
    )


@step(r'the payment to "(?P<payee>[^"]+)" is recorded (?P<back>\d+) days ago')
def then_payment_dated(world: World, payee: str, back: str) -> None:
    world.require_clean(f"confirming the payment to {payee!r}")
    tx = _payment(world, payee)
    expected = world.today - timedelta(days=int(back))
    assert tx.date == expected, f"expected date {expected}, got {tx.date}"


@step(
    r'the payment to "(?P<payee>[^"]+)" is still for'
    r" (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3})"
)
def then_payment_unchanged(
    world: World, payee: str, amount: str, currency: str
) -> None:
    tx = _payment(world, payee)
    expected = major_to_cents(amount)
    assert tx.amount == expected and tx.currency == currency, (
        f"expected {amount} {currency}, got "
        f"{cents_to_major(tx.amount)} {tx.currency}"
    )


@step(
    r'viewing the planned payment to "(?P<payee>[^"]+)" shows'
    r' category "(?P<category>[^"]+)" and notes "(?P<notes>[^"]+)"'
)
def then_planned_details(
    world: World, payee: str, category: str, notes: str
) -> None:
    world.require_clean(f"planning the payment to {payee!r}")
    tx = _payment(world, payee)
    expected_category = world.categories[category]
    assert tx.category_id == expected_category, (
        f"expected category {category!r} (id {expected_category}), "
        f"got category_id={tx.category_id}"
    )
    assert tx.notes == notes, f"expected notes {notes!r}, got {tx.notes!r}"


@step(
    r'the restored payment to "(?P<payee>[^"]+)" is for'
    r" (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3})"
    r" due in (?P<days>\d+) days"
)
def then_restored_payment_intact(
    world: World, payee: str, amount: str, currency: str, days: str
) -> None:
    world.require_clean(f"restoring the payment to {payee!r}")
    tx = _payment(world, payee)
    expected_date = world.today + timedelta(days=int(days))
    assert tx.amount == major_to_cents(amount) and tx.currency == currency, (
        f"expected {amount} {currency}, got "
        f"{cents_to_major(tx.amount)} {tx.currency}"
    )
    assert tx.date == expected_date, f"expected date {expected_date}, got {tx.date}"


@step(r'nothing is recorded as spent for "(?P<payee>[^"]+)"')
def then_nothing_spent(world: World, payee: str) -> None:
    world.require_clean(f"skipping the payment to {payee!r}")
    posted = [
        t
        for t in world.session.exec(
            select(Transaction).where(Transaction.payee == payee)
        ).all()
        if t.status == TxStatus.posted
    ]
    assert not posted, f"{payee!r} was recorded as spent after being skipped"


@step(
    r"this month's turn of the obligation to \"(?P<payee>[^\"]+)\" is"
    r" (?P<state>settled|marked skipped|still waiting)"
)
def then_occurrence_state(world: World, payee: str, state: str) -> None:
    expected = {
        "settled": OccurrenceStatus.posted,
        "marked skipped": OccurrenceStatus.skipped,
        "still waiting": OccurrenceStatus.planned,
    }[state]
    occ = _occurrence(world, payee)
    assert occ.status == expected, (
        f"this month's turn of {payee!r} is {occ.status.value}, expected "
        f"{expected.value}"
    )


@step(r'the obligation to "(?P<payee>[^"]+)" is still active')
def then_obligation_active(world: World, payee: str) -> None:
    item = world.session.get(RecurringItem, world.recurring_ids[payee])
    assert item is not None and item.active, (
        f"the obligation to {payee!r} was deactivated"
    )


@step(
    r'the transfer into "(?P<account>[^"]+)" is recorded as'
    r" one movement out and one movement in"
)
def then_transfer_pair(world: World, account: str) -> None:
    world.require_clean(f"confirming the transfer into {account!r}")
    legs = transactions.list_transactions(
        world.session, status="posted", type=TxType.transfer
    )
    assert len(legs) == 2, f"expected two linked movements, got {len(legs)}"
    groups = {leg.transfer_group_id for leg in legs}
    assert len(groups) == 1 and None not in groups, (
        f"the two movements are not linked as one transfer (groups={groups})"
    )
    directions = {leg.transfer_direction for leg in legs}
    assert directions == {TransferDirection.out, TransferDirection.in_}, (
        f"expected one outgoing and one incoming movement, got {directions}"
    )


@step(
    r'the proposed savings contribution into "(?P<account>[^"]+)"'
    r" is still waiting"
)
def then_contribution_still_waiting(world: World, account: str) -> None:
    tx = _transfer(world, account)
    world.session.refresh(tx)
    assert tx.status == TxStatus.planned, (
        f"the contribution into {account!r} is {tx.status.value}, not waiting"
    )


@step(r"the plan is rejected")
def then_plan_rejected(world: World) -> None:
    world.consume_rejection((QuaestorError,), "the invalid plan")


@step(r"the confirmation is rejected")
def then_confirmation_rejected(world: World) -> None:
    world.consume_rejection((QuaestorError,), "the invalid confirmation")


@step(r"the request is rejected as an impossible period")
def then_inverted_period_rejected(world: World) -> None:
    err = world.consume_rejection((ValidationError,), "the inverted period")
    assert "inverted" in str(err).lower(), (
        f"the answer does not say the period is impossible: {err}"
    )


@step(r"the user is told it is no longer pending")
def then_told_no_longer_pending(world: World) -> None:
    err = world.consume_rejection((QuaestorError,), "resolving a settled payment")
    message = str(err).lower()
    assert "planned" in message or "pending" in message or "not found" in message, (
        f"the answer does not say it is no longer pending: {err}"
    )


@step(r"the report for last month reports nothing pending")
def then_report_nothing_pending(world: World) -> None:
    world.require_clean("viewing the report for last month")
    assert world.report is not None, "the report was never viewed"
    assert world.report.pending == [], (
        f"the retrospective still carries pending items: {world.report.pending}"
    )


@step(
    r'the assistant\'s answer shows "(?P<payee>[^"]+)"'
    r" as (?P<bucket>overdue|upcoming)"
)
def then_assistant_answer_bucket(world: World, payee: str, bucket: str) -> None:
    answer = _assistant_answer(world)
    heading = "Overdue" if bucket == "overdue" else "Upcoming"
    section = _section_of(answer, heading)
    assert payee in section, (
        f"{payee!r} is not under the {heading} section of the assistant's "
        f"answer:\n{answer}"
    )


@step(
    r"the assistant's answer shows a total of (?P<amount>" + _DEC + r")"
    r" (?P<currency>[A-Z]{3})"
)
def then_assistant_answer_total(world: World, amount: str, currency: str) -> None:
    answer = _assistant_answer(world)
    expected = str(cents_to_major(major_to_cents(amount)))
    assert expected in answer, (
        f"the assistant's answer does not report a total of {expected}:\n{answer}"
    )


@step(r"the assistant's answer says nothing is outstanding")
def then_assistant_answer_empty(world: World) -> None:
    answer = _assistant_answer(world)
    assert "nothing outstanding" in answer.lower(), (
        f"the assistant's answer does not say the queue is empty:\n{answer}"
    )


def _assistant_answer(world: World) -> str:
    world.require_clean("asking the assistant what is outstanding")
    if world.assistant_answer is None:
        raise AssertionError("the assistant was never asked")
    return world.assistant_answer


def _section_of(answer: str, heading: str) -> str:
    """The lines under a markdown heading, up to the next heading."""
    lines = answer.splitlines()
    out: list[str] = []
    collecting = False
    for line in lines:
        if line.startswith("##"):
            collecting = heading in line
            continue
        if collecting:
            out.append(line)
    return "\n".join(out)
