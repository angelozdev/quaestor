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
from pathlib import Path as _Path

from quaestor.domain.errors import NotFound, QuaestorError, ValidationError
from quaestor.domain.models import Category as _Category
from quaestor.domain.models import Meta as _Meta
from quaestor.domain.money import major_to_cents
from quaestor.mcp import tools as _mcp_tools
from quaestor.services import categories, planned, transactions
from quaestor.services import funds as funds_service
from quaestor.services import metas as service
from sqlmodel import select as _select

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


@step(
    rf"the user plans an expense of (?P<amount>{_DEC}) COP"
    rf' in category "(?P<category>[^"]+)" linked to the meta "(?P<name>[^"]+)"'
)
def when_plan_linked(world: World, amount: str, category: str, name: str) -> None:
    given_planned_linked(world, amount, category, name)


@step(
    rf"a planned expense of (?P<amount>{_DEC}) COP"
    rf' in category "(?P<category>[^"]+)" linked to the meta "(?P<name>[^"]+)" this month'
)
def given_planned_linked(world: World, amount: str, category: str, name: str) -> None:
    world.last_planned_id = planned.plan_payment(
        world.session,
        payee="Compra",
        amount=_cents(amount),
        currency="COP",
        due_date=world.today,
        account_id=_default_account_id(world, "COP"),
        category_id=_spending_category_id(world, category),
        meta_id=_meta_id(world, name),
    ).id


@step(r"the user confirms that payment")
def when_confirm_planned(world: World) -> None:
    planned.confirm_payment(world.session, world.last_planned_id)


@step(r"the user skips that payment")
def when_skip_planned(world: World) -> None:
    planned.skip_payment(world.session, world.last_planned_id)


# --------------------------------------------------------------- the acts


@step(rf'the user contributes (?P<amount>{_DEC}) COP to "(?P<name>[^"]+)"')
def when_contribute(world: World, amount: str, name: str) -> None:
    try:
        world.last_contributed_to = _meta_id(world, name)
        world.last_put_in = service.contribute(
            world.session, world.last_contributed_to, year_month=_today(world), amount=_cents(amount)
        )
    except _REJECTED as exc:
        world.session.rollback()
        world.contribution_refusal = str(exc)


@step(rf'a contribution of (?P<amount>{_DEC}) COP to "(?P<name>[^"]+)" made (?P<month>{_MONTH})')
def given_contribution(world: World, amount: str, name: str, month: str) -> None:
    world.last_contributed_to = _meta_id(world, name)
    service.contribute(world.session, world.last_contributed_to, year_month=month, amount=_cents(amount))


@step(r"the contribution is rejected")
def then_contribution_rejected(world: World) -> None:
    assert getattr(world, "contribution_refusal", None), "the contribution was accepted, expected a refusal"


@step(rf"the user is told (?P<amount>{_DEC}) COP was put in, which is what was missing")
def then_told_trimmed(world: World, amount: str) -> None:
    assert world.last_put_in == _cents(amount), f"put in {world.last_put_in}, expected {_cents(amount)}"


@step(r"the user removes that contribution")
def when_remove_contribution(world: World) -> None:
    rows = service.contributions_of(world.session, world.last_contributed_to)
    service.remove_contribution(world.session, rows[-1].id)


@step(rf'the meta "(?P<name>[^"]+)" lists a contribution of (?P<amount>{_DEC}) COP made (?P<month>{_MONTH})')
def then_lists_contribution(world: World, name: str, amount: str, month: str) -> None:
    rows = service.contributions_of(world.session, _meta_id(world, name))
    assert any(r.amount == _cents(amount) and r.year_month == month for r in rows), (
        f"the meta {name!r} lists {[(r.year_month, r.amount) for r in rows]}"
    )


@step(r'the user cancels the meta "(?P<name>[^"]+)"')
def when_cancel(world: World, name: str) -> None:
    try:
        service.cancel_meta(world.session, _meta_id(world, name), year_month=_today(world))
    except _REJECTED as exc:
        world.session.rollback()
        world.cancel_refusal = str(exc)


@step(rf'the meta "(?P<name>[^"]+)" was cancelled (?P<month>{_MONTH})')
def given_cancelled(world: World, name: str, month: str) -> None:
    service.cancel_meta(world.session, _meta_id(world, name), year_month=month)


@step(r"the cancellation is rejected")
def then_cancel_rejected(world: World) -> None:
    assert getattr(world, "cancel_refusal", None), "the cancellation was accepted, expected a refusal"


@step(r"the user is told a meta that was bought is closed, not cancelled")
def then_told_closed_not_cancelled(world: World) -> None:
    assert "closed rather than cancelled" in getattr(world, "cancel_refusal", "")


@step(r'the user closes the meta "(?P<name>[^"]+)"')
def when_close(world: World, name: str) -> None:
    service.close_meta(world.session, _meta_id(world, name))


@step(r'the user restores the meta "(?P<name>[^"]+)"')
def when_restore(world: World, name: str) -> None:
    try:
        service.restore_meta(world.session, _meta_id(world, name))
    except _REJECTED as exc:
        world.session.rollback()
        world.restore_refusal = str(exc)


@step(rf"the user restores the meta cancelled in (?P<month>{_MONTH})")
def when_restore_cancelled_in(world: World, month: str) -> None:
    row = world.session.exec(_select(_Meta).where(_Meta.cancelled_month == month)).first()
    try:
        service.restore_meta(world.session, row.id)
    except _REJECTED as exc:
        world.session.rollback()
        world.restore_refusal = str(exc)


@step(r"the restore is rejected")
def then_restore_rejected(world: World) -> None:
    assert getattr(world, "restore_refusal", None), "the restore was accepted, expected a refusal"


@step(r"the user is told another meta already holds that name")
def then_told_name_taken(world: World) -> None:
    assert "already holds the name" in getattr(world, "restore_refusal", "")


@step(r'the meta "(?P<name>[^"]+)" is not listed')
def then_not_listed(world: World, name: str) -> None:
    agg = funds_service._month_view(world.session, _today(world))
    assert name not in [f.name for f in service.statuses(agg)], f"the meta {name!r} is still listed"


@step(r'the meta "(?P<name>[^"]+)" can be restored')
def then_can_be_restored(world: World, name: str) -> None:
    service.restore_meta(world.session, _meta_id(world, name))
    agg = funds_service._month_view(world.session, _today(world))
    assert name in [f.name for f in service.statuses(agg)], f"the meta {name!r} did not come back"


# --------------------------------------------------------------- the split


def _split(world: World):
    return funds_service.split(world.session, _today(world))


@step(r'an expense category "(?P<name>[^"]+)" where spending is saving')
def given_saving_category(world: World, name: str) -> None:
    cat = categories.create_category(world.session, name=name, counts_as_saving=True)
    world.categories[name] = cat.id


@step(rf"the month reports (?P<amount>{_DEC}) COP as (?P<term>consumo|ahorro|libre)")
def then_split_term(world: World, amount: str, term: str) -> None:
    found = getattr(_split(world), term)
    assert found == _cents(amount), f"the month reports {found} as {term}, expected {_cents(amount)}"


@step(r"the month reports (?P<share>-?\d+) percent of the income as ahorro")
def then_share(world: World, share: str) -> None:
    found = _split(world).ahorro_share
    assert found == int(share), f"the month reports {found} percent as ahorro, expected {share}"


@step(r"consumo, ahorro and libre add up to the income this month")
def then_split_adds_up(world: World) -> None:
    s = _split(world)
    total = s.consumo + s.ahorro + s.libre
    assert total == s.income, f"consumo + ahorro + libre is {total}, and the income is {s.income}"


@step(rf"the user views the month's report for (?P<month>{_MONTH})")
def when_view_split_for(world: World, month: str) -> None:
    world.split_view = funds_service.split(world.session, month)


@step(rf"that month reports (?P<amount>{_DEC}) COP as (?P<term>consumo|ahorro|libre)")
def then_that_month_term(world: World, amount: str, term: str) -> None:
    found = getattr(world.split_view, term)
    assert found == _cents(amount), f"that month reports {found} as {term}, expected {_cents(amount)}"


@step(r'spending in "(?P<name>[^"]+)" is not saving')
def then_not_saving(world: World, name: str) -> None:
    cat = world.session.get(_Category, world.categories[name])
    assert not cat.counts_as_saving, f"spending in {name!r} is marked as saving, and it should not be"


# ----------------------------------------------------------- the assistant

_META_VERBS = ("create_meta", "set_meta", "contribute_to_meta", "cancel_meta", "delete_meta")


def _assistant_meta_tools() -> list[str]:
    """Every meta-managing tool the assistant exposes. Expected empty (AC-32)."""
    found = []
    for module in _mcp_tools.__all__ if hasattr(_mcp_tools, "__all__") else []:
        found.extend(name for name in dir(module) if name in _META_VERBS)
    for path in (_Path(_mcp_tools.__file__).parent).glob("*.py"):
        text = path.read_text(encoding="utf-8")
        found.extend(verb for verb in _META_VERBS if f"def {verb}" in text)
    return sorted(set(found))


@step(r"the assistant is asked to create a meta")
def when_assistant_create_meta(world: World) -> None:
    world.assistant_meta_tools = _assistant_meta_tools()


@step(r"the assistant is asked to contribute to a meta")
def when_assistant_contribute(world: World) -> None:
    world.assistant_meta_tools = _assistant_meta_tools()
