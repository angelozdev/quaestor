"""Step handlers — feature 009 named-goals.

The API bound here is ``quaestor.services.metas``:

``create_meta``    a meta with a name, an amount and a target month
``set_meta``       change its name, amount or target month while it runs
``preview_meta``   what it would ask before it exists (AC-45)
``statuses``       what every live meta asks and holds for one month
``asks_total``     what they ask together, in COP, for the month's number

Dates are absolute, as in 003 and for the same reason: a meta is month
arithmetic and "2 months ago" cannot pin $1.600.000 the way a calendar can.
``today is YYYY-MM-DD`` sets the scenario clock and comes from 003's module.

``opened YYYY-MM`` gives a meta a history the fold produces. No step states a
balance for a month — the first draft of the spec did, with figures the fold
could not reach, and the audits found them.

Scratchpad attributes this module puts on the :class:`World`: ``metas``
(name -> id), ``metas_view``, ``meta_preview``, ``pending_meta`` and
``meta_refusal``.
"""

from __future__ import annotations

from datetime import date as Date

from quaestor.domain.errors import NotFound, QuaestorError, ValidationError
from quaestor.domain.money import major_to_cents
from quaestor.services import funds as funds_service
from quaestor.services import metas as service
from quaestor.services import transactions

from . import step
from .fx_read_time import _default_account_id
from .sinking_funds import _spending_category_id
from .world import World

_REJECTED = (ValidationError, NotFound, QuaestorError, TypeError, ValueError, AttributeError)

_DEC = r"-?\d+(?:\.\d+)?"
_MONTH = r"\d{4}-\d{2}"


def _cents(amount: str) -> int:
    return major_to_cents(amount)


def _month_of(day: Date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def _today(world: World) -> str:
    return _month_of(world.today)


def _ids(world: World) -> dict[str, int]:
    world.metas = getattr(world, "metas", {})
    return world.metas


def _meta_id(world: World, name: str) -> int:
    ids = _ids(world)
    if name not in ids:
        raise AssertionError(f"no meta named {name!r} in this scenario")
    return ids[name]


def _status(world: World, name: str, year_month: str | None = None):
    month = year_month or _today(world)
    agg = funds_service._month_view(world.session, month)
    for found in service.statuses(agg):
        if found.name == name:
            return found
    raise AssertionError(f"the month {month} reports no meta named {name!r}")


def _open(world: World, *, name: str, amount: str, currency: str, target: str, opened: str, held: str | None) -> None:
    meta = service.create_meta(
        world.session,
        name=name,
        amount=_cents(amount),
        currency=currency,
        target_month=target,
        today=opened,
        stated_opening=_cents(held) if held is not None else None,
    )
    _ids(world)[name] = meta.id


# ------------------------------------------------------------------ given


@step(rf'a meta "(?P<name>[^"]+)" of (?P<amount>{_DEC}) (?P<currency>COP|USD) by (?P<target>{_MONTH})')
def given_meta(world: World, name: str, amount: str, currency: str, target: str) -> None:
    _open(world, name=name, amount=amount, currency=currency, target=target, opened=_today(world), held=None)


@step(
    rf'a meta "(?P<name>[^"]+)" of (?P<amount>{_DEC}) (?P<currency>COP|USD) by (?P<target>{_MONTH}), '
    rf"opened (?P<opened>{_MONTH})"
)
def given_meta_opened(world: World, name: str, amount: str, currency: str, target: str, opened: str) -> None:
    _open(world, name=name, amount=amount, currency=currency, target=target, opened=opened, held=None)


@step(
    rf'a meta "(?P<name>[^"]+)" of (?P<amount>{_DEC}) (?P<currency>COP|USD) by (?P<target>{_MONTH}), '
    rf"opened (?P<opened>{_MONTH}) stating it already held (?P<held>{_DEC}) (?:COP|USD)"
)
def given_meta_opened_holding(
    world: World, name: str, amount: str, currency: str, target: str, opened: str, held: str
) -> None:
    _open(world, name=name, amount=amount, currency=currency, target=target, opened=opened, held=held)


# ------------------------------------------------------------------- when


@step(rf'the user creates a meta "(?P<name>[^"]+)" of (?P<amount>{_DEC}) (?P<currency>COP|USD) by (?P<target>{_MONTH})')
def when_create(world: World, name: str, amount: str, currency: str, target: str) -> None:
    try:
        _open(world, name=name, amount=amount, currency=currency, target=target, opened=_today(world), held=None)
    except _REJECTED as exc:
        world.meta_refusal = str(exc)


@step(
    rf'the user creates a meta "(?P<name>[^"]+)" of (?P<amount>{_DEC}) (?P<currency>COP|USD) by (?P<target>{_MONTH}) '
    rf"stating it already held (?P<held>{_DEC}) (?:COP|USD)"
)
def when_create_holding(world: World, name: str, amount: str, currency: str, target: str, held: str) -> None:
    try:
        _open(world, name=name, amount=amount, currency=currency, target=target, opened=_today(world), held=held)
    except _REJECTED as exc:
        world.meta_refusal = str(exc)


@step(rf'the user creates a meta "(?P<name>[^"]+)" of (?P<amount>{_DEC}) (?:COP|USD) with no month')
def when_create_without_month(world: World, name: str, amount: str) -> None:
    try:
        service.create_meta(world.session, name=name, amount=_cents(amount), target_month="", today=_today(world))
    except _REJECTED as exc:
        world.meta_refusal = str(exc)


@step(rf'the user sets the meta "(?P<name>[^"]+)" to want (?P<amount>{_DEC}) (?:COP|USD)')
def when_set_amount(world: World, name: str, amount: str) -> None:
    try:
        service.set_meta(world.session, _meta_id(world, name), today=_today(world), amount=_cents(amount))
    except _REJECTED as exc:
        world.session.rollback()
        world.meta_refusal = str(exc)


@step(rf'the user sets the meta "(?P<name>[^"]+)" to be wanted by (?P<target>{_MONTH})')
def when_set_target(world: World, name: str, target: str) -> None:
    try:
        service.set_meta(world.session, _meta_id(world, name), today=_today(world), target_month=target)
    except _REJECTED as exc:
        world.session.rollback()
        world.meta_refusal = str(exc)


@step(r'the user renames the meta "(?P<name>[^"]+)" to "(?P<to>[^"]+)"')
def when_rename(world: World, name: str, to: str) -> None:
    meta_id = _meta_id(world, name)
    service.set_meta(world.session, meta_id, today=_today(world), name=to)
    _ids(world)[to] = meta_id


@step(rf"the user views the metas for (?P<month>{_MONTH})")
def when_view_metas(world: World, month: str) -> None:
    agg = funds_service._month_view(world.session, month)
    world.metas_view = {found.name: found for found in service.statuses(agg)}


@step(rf"the user asks what a meta of (?P<amount>{_DEC}) (?:COP|USD) by (?P<target>{_MONTH}) would ask")
def when_preview(world: World, amount: str, target: str) -> None:
    month = _today(world)
    income = funds_service.available(world.session, month).income
    world.meta_preview = service.preview_meta(amount=_cents(amount), target_month=target, today=month, income=income)
    world.pending_meta = (_cents(amount), target)


@step(
    rf"the user was warned a meta of (?P<amount>{_DEC}) (?:COP|USD) by (?P<target>{_MONTH}) "
    rf"would ask (?P<asks>{_DEC}) (?:COP|USD) a month"
)
def given_warned(world: World, amount: str, target: str, asks: str) -> None:
    when_preview(world, amount, target)
    preview = world.meta_preview
    assert preview.asks == _cents(asks), f"the warning said {preview.asks}, expected {_cents(asks)}"


@step(r'the user creates the meta anyway, naming it "(?P<name>[^"]+)"')
def when_create_anyway(world: World, name: str) -> None:
    """Deliberately not 003's `the user goes ahead anyway`.

    That phrase is bound to going ahead with a *fund* the app warned about, and
    the registry refuses two handlers for one text. Creating a meta over its
    warning is a different act on a different noun; sharing the words would
    make which one ran depend on registration order.
    """
    amount, target = world.pending_meta
    meta = service.create_meta(world.session, name=name, amount=amount, target_month=target, today=_today(world))
    _ids(world)[name] = meta.id


# ------------------------------------------------------------------- then


@step(r'the meta "(?P<name>[^"]+)" is running')
def then_running(world: World, name: str) -> None:
    found = _status(world, name)
    assert not found.complete, f"the meta {name!r} is complete, expected running"


@step(r'the meta "(?P<name>[^"]+)" is complete')
def then_complete(world: World, name: str) -> None:
    found = _status(world, name)
    assert found.complete, f"the meta {name!r} is still running, expected complete"


@step(rf'the meta "(?P<name>[^"]+)" wants (?P<amount>{_DEC}) (?:COP|USD) by (?P<target>{_MONTH})')
def then_wants(world: World, name: str, amount: str, target: str) -> None:
    found = _status(world, name)
    assert found.amount == _cents(amount), f"the meta {name!r} wants {found.amount}, expected {_cents(amount)}"
    assert found.target_month == target, f"the meta {name!r} is for {found.target_month}, expected {target}"


@step(rf'the meta "(?P<name>[^"]+)" asks (?P<amount>{_DEC}) (?:COP|USD) this month')
def then_asks(world: World, name: str, amount: str) -> None:
    found = _status(world, name)
    assert found.asks == _cents(amount), f"the meta {name!r} asks {found.asks}, expected {_cents(amount)}"


@step(rf'the meta "(?P<name>[^"]+)" holds (?P<amount>{_DEC}) (?:COP|USD) this month')
def then_holds(world: World, name: str, amount: str) -> None:
    found = _status(world, name)
    assert found.holds == _cents(amount), f"the meta {name!r} holds {found.holds}, expected {_cents(amount)}"


@step(rf'the meta "(?P<name>[^"]+)" held (?P<amount>{_DEC}) (?:COP|USD) that month')
def then_held_that_month(world: World, name: str, amount: str) -> None:
    view = getattr(world, "metas_view", None)
    assert view is not None, "nothing opened the metas for a month"
    found = view[name]
    assert found.holds == _cents(amount), f"the meta {name!r} held {found.holds}, expected {_cents(amount)}"


@step(r'the meta "(?P<name>[^"]+)" names no category')
def then_no_category(world: World, name: str) -> None:
    found = _status(world, name)
    assert not hasattr(found, "category_id"), "a meta reports a category, and it should belong to none"


@step(r"the meta is rejected")
def then_meta_rejected(world: World) -> None:
    assert getattr(world, "meta_refusal", None), "the meta was accepted, expected a refusal"


@step(r"the user is told a meta needs the month it is wanted by")
def then_told_needs_month(world: World) -> None:
    assert "target_month" in getattr(world, "meta_refusal", "")


@step(r"the user is told there is no way to save into the past")
def then_told_no_past(world: World) -> None:
    assert "past" in getattr(world, "meta_refusal", "")


@step(r"the user is told a meta needs an amount above zero")
def then_told_amount(world: World) -> None:
    assert "above zero" in getattr(world, "meta_refusal", "")


@step(r"the user is told that name is already held by another meta")
def then_told_name_held(world: World) -> None:
    assert "already holds the name" in getattr(world, "meta_refusal", "")


@step(rf"the breakdown shows the metas asking (?P<amount>{_DEC}) COP")
def then_breakdown_metas(world: World, amount: str) -> None:
    view = getattr(world, "available_view", None)
    assert view is not None, "nothing opened the money available into its breakdown"
    asking = sum(found.asks for found in view.metas)
    assert asking == _cents(amount), f"the metas ask {asking}, expected {_cents(amount)}"


@step(rf"the breakdown shows (?P<amount>{_DEC}) COP contributed by hand")
def then_breakdown_contributed(world: World, amount: str) -> None:
    view = world.available_view
    assert view.contributed == _cents(amount), f"contributed {view.contributed}, expected {_cents(amount)}"


@step(rf"the breakdown shows (?P<amount>{_DEC}) COP released by a cancelled meta")
def then_breakdown_released(world: World, amount: str) -> None:
    view = world.available_view
    assert view.released == _cents(amount), f"released {view.released}, expected {_cents(amount)}"


@step(rf"the answer is (?P<amount>{_DEC}) COP a month")
def then_preview_asks(world: World, amount: str) -> None:
    preview = world.meta_preview
    assert preview.asks == _cents(amount), f"the preview asks {preview.asks}, expected {_cents(amount)}"


@step(rf"the user is warned it would ask (?P<amount>{_DEC}) COP a month")
def then_warned_amount(world: World, amount: str) -> None:
    preview = world.meta_preview
    assert preview.asks == _cents(amount), f"the warning said {preview.asks}, expected {_cents(amount)}"


@step(r"the user is warned that is more than the month has")
def then_warned_over(world: World) -> None:
    preview = world.meta_preview
    assert preview.over_the_month, "the meta was not announced as more than the month has"


# --------------------------------------------------- the link on the movement


def _record_linked(world: World, amount: str, category: str, name: str, when: Date, kind: str = "expense"):
    write = transactions.record_expense if kind == "expense" else transactions.record_income
    return write(
        world.session,
        account_id=_default_account_id(world, "COP"),
        amount=_cents(amount),
        currency="COP",
        date=when,
        payee="Compra",
        category_id=_spending_category_id(world, category),
        meta_id=_meta_id(world, name),
    )


@step(
    rf"the user records an expense of (?P<amount>{_DEC}) COP"
    rf' in category "(?P<category>[^"]+)" linked to the meta "(?P<name>[^"]+)"'
)
def when_record_linked(world: World, amount: str, category: str, name: str) -> None:
    try:
        world.last_linked_id = _record_linked(world, amount, category, name, world.today).id
    except _REJECTED as exc:
        world.session.rollback()
        world.movement_refusal = str(exc)


@step(
    rf"the user records an income of (?P<amount>{_DEC}) COP"
    rf' in category "(?P<category>[^"]+)" linked to the meta "(?P<name>[^"]+)"'
)
def when_record_income_linked(world: World, amount: str, category: str, name: str) -> None:
    try:
        _record_linked(world, amount, category, name, world.today, kind="income")
    except _REJECTED as exc:
        world.session.rollback()
        world.movement_refusal = str(exc)


@step(
    rf"a recorded expense of (?P<amount>{_DEC}) COP"
    rf' in category "(?P<category>[^"]+)" linked to the meta "(?P<name>[^"]+)" this month'
)
def given_linked_this_month(world: World, amount: str, category: str, name: str) -> None:
    world.last_linked_id = _record_linked(world, amount, category, name, world.today).id


@step(
    rf"a recorded expense of (?P<amount>{_DEC}) COP"
    rf' in category "(?P<category>[^"]+)" linked to the meta "(?P<name>[^"]+)"'
    r" on (?P<day>\d{4}-\d{2}-\d{2})"
)
def given_linked_on(world: World, amount: str, category: str, name: str, day: str) -> None:
    world.last_linked_id = _record_linked(world, amount, category, name, Date.fromisoformat(day)).id


@step(r"the movement is rejected")
def then_movement_rejected(world: World) -> None:
    assert getattr(world, "movement_refusal", None), "the movement was accepted, expected a refusal"


@step(r"the user is told only money going out can be pointed at a meta")
def then_told_only_expense(world: World) -> None:
    assert "money going out" in getattr(world, "movement_refusal", "")


@step(r'the meta "(?P<name>[^"]+)" is waiting on its purchase')
def then_waiting(world: World, name: str) -> None:
    found = _status(world, name)
    assert found.waiting, f"the meta {name!r} is not waiting, expected it to be"


@step(r"no meta is waiting on its purchase")
def then_none_waiting(world: World) -> None:
    agg = funds_service._month_view(world.session, _today(world))
    waiting = [found.name for found in service.statuses(agg) if found.waiting]
    assert not waiting, f"these metas are waiting: {waiting}"
