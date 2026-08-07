"""Step handlers — feature 003 sinking-funds.

Written at Checkpoint 3 against an API that did not exist yet — the bindings
recorded the intent and Checkpoint 4 owned the design. The feature has since
shipped, so every binding now reaches real code; the helpers that name a
missing capability survive as the message a future removal would produce.

The API bound throughout is ``quaestor.services.funds``:

``create_fund``      a fund on one expense category, one rule, one start month
``preview_fund``     what a fund would ask, before it exists (AC-24's warning)
``list_funds``       every fund, for the screen and the assistant
``set_fund``         change a fund's rule or amount
``delete_fund``      remove a fund
``fund_status``      what a fund asks, holds and reports for one month
``available``        the money available for a month, with its breakdown
``rates``            the earning rate, the cost rate and the margin

Each helper below fails with a message naming the capability it wanted, so
the red output reads as a to-do list rather than one repeated import error.

Assistant steps go through ``quaestor.mcp.tools.funds`` — the conversational
surface, per AC-28's parity requirement. They follow the house shape the
tools ship with, ``(session, inp: Model)`` with names resolved to ids and
``_as_text`` around the answer (decision D9, settled at Checkpoint 4).

Dates are absolute here, unlike the other suites. Every fund rule is month
arithmetic, and "2 months ago" cannot pin $74.550 the way a fixed calendar
can. ``today is YYYY-MM-DD`` sets the scenario clock.

Feature 010's ``@backend`` scenarios bind here too: their subject is the same
record, so the vocabulary belongs in the same module. They add three figures a
fund reports — what the category spent, what it carries, what next month has —
and their own plain-language names for the four rules.

Scratchpad keys this module puts on the :class:`World`: ``funds`` (name ->
id), ``funds_view``, ``available_view``, ``rates_view``, ``fund_preview``,
``pending_fund``, ``goals_probe`` and ``history_start``.
"""

from __future__ import annotations

import re as _re
from datetime import date as Date
from datetime import timedelta

from quaestor.domain.errors import NotFound, QuaestorError, ValidationError
from quaestor.domain.models import IntervalUnit, RecurringMode, TxType
from quaestor.domain.money import major_to_cents
from quaestor.services import categories, recurring, transactions
from sqlalchemy import text as sa_text

from . import step
from .fx_read_time import _DEC, _default_account_id
from .planned_payments import skip_the_obligations_turn
from .world import World

_REJECTED = (ValidationError, NotFound, QuaestorError, TypeError, ValueError, AttributeError)

_MONTH = r"\d{4}-\d{2}"

_PRE_FEATURE_REVISION = "0010"

_SEED_GOAL_ACCOUNT = """
    INSERT INTO account (name, type, currency, balance, archived)
    VALUES ('Ahorros', 'savings', 'COP', 0, 0)
"""

_SEED_GOAL_CATEGORIES = """
    INSERT INTO category
        (name, group_id, is_income, exclude_from_budget,
         exclude_from_totals, archived)
    VALUES ('Comida', NULL, 0, 0, 0, 0), ('Salario', NULL, 1, 0, 0, 0)
"""

_SEED_GOAL = """
    INSERT INTO goal
        (name, target_amount, deadline, monthly_amount, savings_account_id, status)
    VALUES ('Korea', 1000000000, '2026-08-31', 300000000, 1, 'active')
"""

_INSERT_PROPOSAL = """
    INSERT INTO "transaction"
        (date, payee, notes, type, status, amount, currency, account_id,
         category_id, goal_id, transfer_group_id, transfer_direction, source,
         created_at)
    VALUES
        (:date, :payee, NULL, 'transfer', :status, 300000000, 'COP', 1,
         NULL, 1, :group_id, 'out', 'manual', :created_at)
"""

_INSERT_MOVEMENT = """
    INSERT INTO "transaction"
        (date, payee, notes, type, status, amount, currency, account_id,
         category_id, transfer_group_id, transfer_direction, source,
         created_at)
    VALUES
        (:date, :payee, NULL, :type, 'posted', :amount, 'COP', 1,
         :category_id, :group_id, :direction, 'manual', :created_at)
"""

_SELECT_GOALS = "SELECT name FROM goal"


# ------------------------------------------------------------------ helpers


def _service():
    """The funds service, or a red naming its absence."""
    try:
        from quaestor.services import funds
    except ImportError as exc:
        raise AssertionError(
            "there is no funds service yet — a fund is the noun this whole feature adds (quaestor.services.funds)"
        ) from exc
    return funds


def _call(capability: str, *args, **kwargs):
    """Invoke one capability of the funds service, or a red naming it."""
    service = _service()
    fn = getattr(service, capability, None)
    if fn is None:
        raise AssertionError(f"the funds service has no {capability!r} yet — Checkpoint 4 owns its shape")
    return fn(*args, **kwargs)


def _attr(obj, name: str, what: str):
    value = getattr(obj, name, None)
    if value is None:
        raise AssertionError(f"{what} carries no {name!r} — nothing reports it yet")
    return value


def _month_of(day: Date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def _shift_months(day: Date, back: int) -> Date:
    total = day.year * 12 + (day.month - 1) - back
    year, month = divmod(total, 12)
    return Date(year, month + 1, min(day.day, 28))


def _cents(amount: str) -> int:
    return major_to_cents(amount)


def _context(world: World) -> str:
    """Any unconsumed failure, as a suffix naming the likely cause.

    Used instead of ``require_clean`` by the steps that read a fund's state
    *after* a refusal — AC-21 and AC-25 assert that the refused action left the
    fund exactly as it was, and there is no step between them to consume the
    rejection. Same shape as ``fx_read_time.then_account_balance``.
    """
    if not world.errors:
        return ""
    details = "; ".join(f"{type(e).__name__}: {e}" for e in world.errors)
    return f" (a preceding action failed — {details})"


def _fund_id(world: World, name: str) -> int:
    known = getattr(world, "funds", {})
    fund_id = known.get(name)
    if fund_id is None:
        raise AssertionError(f"no fund on {name!r} in this scenario{_context(world)}")
    return fund_id


def _status(world: World, name: str, year_month: str | None = None):
    return _call("fund_status", world.session, _fund_id(world, name), year_month or _month_of(world.today))


def _category_id(world: World, name: str) -> int:
    cat = world.categories.get(name)
    if cat is None:
        raise AssertionError(f"no category {name!r} in this scenario")
    return cat


def _spending_category_id(world: World, name: str) -> int:
    """The expense category a recorded expense is filed under, created if unnamed.

    AC-9 and AC-10 spend in "Transporte" to show what *no* fund covers, and
    never declare it — the category is background to what those scenarios pin,
    exactly like `World.background_category`, but it carries a name because the
    breakdown is read by name.
    """
    known = world.categories.get(name)
    if known is not None:
        return known
    cat = categories.create_category(world.session, name, is_income=False)
    world.categories[name] = cat.id
    return cat.id


def _make_fund(world: World, name: str, **spec) -> None:
    fund = world.attempt(_call, "create_fund", world.session, category_id=_category_id(world, name), **spec)
    if fund is not None:
        world.funds = getattr(world, "funds", {})
        world.funds[name] = fund.id
    world.pending_fund = (name, spec)


def _fixed_spec(amount: str, start: str, roll: str | None) -> dict:
    spec: dict = {"rule": "fixed", "amount": _cents(amount), "start_month": start}
    if roll:
        spec["accumulates"] = roll.strip(", ") == "accumulating"
    return spec


def _target_spec(target: str, by: str, start: str, opening: str | None, roll: str | None) -> dict:
    spec: dict = {
        "rule": "target-by-date",
        "target_amount": _cents(target),
        "target_month": by,
        "start_month": start,
    }
    if opening is not None:
        spec["opening_balance"] = _cents(opening)
    if roll:
        spec["accumulates"] = roll.strip(", ") == "accumulating"
    return spec


_FIXED = (
    r" that asks a fixed (?P<amount>" + _DEC + r") COP each month,"
    r" starting (?P<start>" + _MONTH + r")(?P<roll>, accumulating|, resetting)?"
)
_AVERAGE = r" averaging the last (?P<window>\d+) months, starting (?P<start>" + _MONTH + r")"
_OBLIGATIONS = r" funded from its obligations, starting (?P<start>" + _MONTH + r")"
_TARGET = (
    r" targeting (?P<target>" + _DEC + r") COP by (?P<by>" + _MONTH + r"),"
    r" starting (?P<start>" + _MONTH + r")"
    r"(?:, opening with (?P<opening>" + _DEC + r") COP)?"
    r"(?P<roll>, accumulating|, resetting)?"
)

_FIXED_RESETTING = (
    r" that asks a fixed (?P<amount>" + _DEC + r") COP each month without accumulating,"
    r" starting (?P<start>" + _MONTH + r")"
)
_CATEGORY_AVERAGE = (
    r" that asks what the category averaged over the last (?P<window>\d+) months?,"
    r" starting (?P<start>" + _MONTH + r")"
)
_RECURRING_CHARGES = r" that asks what its recurring charges need, starting (?P<start>" + _MONTH + r")"
_SAVES_BY = (
    r" that saves (?P<target>" + _DEC + r") COP by (?P<by>" + _MONTH + r"),"
    r" starting (?P<start>" + _MONTH + r")"
)
"""Feature 010's plain-language phrasings of the four rules.

The same four specs 003 already builds, said the way the screen says them:
010 is a vocabulary feature and its spec names each rule by the job it does
rather than by the arithmetic it runs. Registered as their own patterns
instead of widened into 003's, so the 348 scenarios resting on those keep
matching exactly what they matched before.
"""


# -------------------------------------------------------------------- Given


@step(r"today is (?P<day>\d{4}-\d{2}-\d{2})")
def given_today(world: World, day: str) -> None:
    world.today = Date.fromisoformat(day)
    world.previous_month_day = (world.today.replace(day=1) - timedelta(days=1)).replace(day=15)


@step(r"the app has recorded movements since (?P<count>\d+) months? ago")
def given_history_since(world: World, count: str) -> None:
    when = _shift_months(world.today, int(count))
    world.history_start = when
    transactions.record_expense(
        world.session,
        account_id=_default_account_id(world, "COP"),
        amount=100,
        currency="COP",
        date=when,
        payee="Historia",
        category_id=world.background_category(TxType.expense),
    )


@step(
    r"a recorded expense of (?P<amount>" + _DEC + r") COP"
    r' in category "(?P<category>[^"]+)" (?P<when>this month|\d+ months? ago)'
)
def given_recorded_expense_in_category(world: World, amount: str, category: str, when: str) -> None:
    back = 0 if when == "this month" else int(_re.match(r"(\d+)", when).group(1))
    transactions.record_expense(
        world.session,
        account_id=_default_account_id(world, "COP"),
        amount=_cents(amount),
        currency="COP",
        date=_shift_months(world.today, back),
        payee="Gasto",
        category_id=_spending_category_id(world, category),
    )


@step(r'a fund on "(?P<name>[^"]+)"' + _FIXED)
def given_fund_fixed(world: World, name: str, amount: str, start: str, roll: str | None) -> None:
    _make_fund(world, name, **_fixed_spec(amount, start, roll))
    world.require_clean(f"creating the fund on {name!r}")


@step(r'a fund on "(?P<name>[^"]+)"' + _AVERAGE)
@step(r'a fund on "(?P<name>[^"]+)"' + _CATEGORY_AVERAGE)
def given_fund_average(world: World, name: str, window: str, start: str) -> None:
    _make_fund(world, name, rule="average", window_months=int(window), start_month=start)
    world.require_clean(f"creating the fund on {name!r}")


@step(r'a fund on "(?P<name>[^"]+)"' + _OBLIGATIONS)
@step(r'a fund on "(?P<name>[^"]+)"' + _RECURRING_CHARGES)
def given_fund_from_obligations(world: World, name: str, start: str) -> None:
    _make_fund(world, name, rule="from-recurring", start_month=start)
    world.require_clean(f"creating the fund on {name!r}")


@step(r'a fund on "(?P<name>[^"]+)"' + _TARGET)
@step(r'a fund on "(?P<name>[^"]+)"' + _SAVES_BY)
def given_fund_target(world: World, name: str, target: str, by: str, start: str, opening=None, roll=None) -> None:
    _make_fund(world, name, **_target_spec(target, by, start, opening, roll))
    world.require_clean(f"creating the fund on {name!r}")


@step(r'a fund on "(?P<name>[^"]+)"' + _FIXED_RESETTING)
def given_fund_fixed_resetting(world: World, name: str, amount: str, start: str) -> None:
    _make_fund(world, name, **_fixed_spec(amount, start, ", resetting"))
    world.require_clean(f"creating the fund on {name!r}")


@step(
    r'a recurring charge "(?P<payee>[^"]+)" on "(?P<category>[^"]+)"'
    r" of (?P<amount>" + _DEC + r") COP every (?P<unit>day|week|month|year),"
    r" next due (?P<due>" + _MONTH + r")"
)
def given_recurring_charge(world: World, payee: str, category: str, amount: str, unit: str, due: str) -> None:
    """A charge that repeats and whose next turn falls in a named month.

    Declared as of that first turn, so nothing about it is waiting for the
    owner's answer: what the fund reads is a live obligation, and a turn
    offered for approval would be a different scenario.
    """
    first = Date.fromisoformat(f"{due}-05")
    world.attempt(
        recurring.create_recurring,
        world.session,
        name=payee,
        payee=payee,
        type=TxType.expense,
        mode=RecurringMode.auto,
        amount=_cents(amount),
        currency="COP",
        category_id=_spending_category_id(world, category),
        account_id=_default_account_id(world, "COP"),
        interval_unit=IntervalUnit(unit),
        interval_count=1,
        start_date=first,
        declared_on=first,
    )
    world.require_clean(f"declaring the recurring charge {payee!r}")


@step(r"an income of (?P<amount>" + _DEC + r") COP is due this month")
def given_income_due(world: World, amount: str) -> None:
    """Money the month is owed and has not received yet (ADR-0044).

    A repeating income landing inside the month, because *due* is what the
    month is promised rather than what already arrived — the same figure while
    nothing has posted, and a different one the moment something does.
    """
    world.attempt(
        recurring.create_recurring,
        world.session,
        name="Ingreso",
        payee="Ingreso",
        type=TxType.income,
        mode=RecurringMode.auto,
        amount=_cents(amount),
        currency="COP",
        category_id=world.background_category(TxType.income),
        account_id=_default_account_id(world, "COP"),
        interval_unit=IntervalUnit.month,
        interval_count=1,
        start_date=world.today,
        declared_on=world.today,
    )
    world.require_clean("declaring the income due this month")


@step(r'the fund on "(?P<name>[^"]+)" already holds (?P<amount>' + _DEC + r") COP")
def given_fund_holds(world: World, name: str, amount: str) -> None:
    world.attempt(_call, "set_fund", world.session, _fund_id(world, name), balance=_cents(amount))
    world.require_clean(f"setting what the fund on {name!r} already holds")


@step(r'the payment to "(?P<payee>[^"]+)" was skipped last month')
def given_skipped_last_month(world: World, payee: str) -> None:
    skip_the_obligations_turn(world, payee, _shift_months(world.today, 1))
    world.require_clean(f"skipping last month's payment to {payee!r}")


@step(r"goal proposals recorded before the upgrade, none of them confirmed")
def given_goal_proposals_before_upgrade(world: World) -> None:
    """A database at the pre-feature head holding the goal shape this feature deletes."""
    from pathlib import Path

    import quaestor
    from alembic import command as alembic_command
    from alembic.config import Config as AlembicConfig
    from quaestor.db import make_engine

    backend_root = Path(quaestor.__file__).resolve().parents[2]
    engine = make_engine(memory=True)
    cfg = AlembicConfig(str(backend_root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", str(engine.url))
    cfg.attributes["engine"] = engine
    alembic_command.upgrade(cfg, _PRE_FEATURE_REVISION)

    stamp = f"{world.today.isoformat()}T00:00:00"
    with engine.begin() as conn:
        conn.execute(sa_text(_SEED_GOAL_ACCOUNT))
        conn.execute(sa_text(_SEED_GOAL_CATEGORIES))
        conn.execute(sa_text(_SEED_GOAL))
        for index, status in enumerate(("skipped", "planned", "planned"), start=1):
            conn.execute(
                sa_text(_INSERT_PROPOSAL),
                {
                    "date": _shift_months(world.today, 2 - index).isoformat(),
                    "payee": f"Aporte Korea {index}",
                    "status": status,
                    "group_id": f"korea-{index}",
                    "created_at": stamp,
                },
            )

    world.replace_engine(engine)
    world.alembic_cfg = cfg
    world.pre_upgrade_expected = []
    world.pre_upgrade_transfers = 0


@step(r"ordinary movements recorded alongside them")
def given_ordinary_movements_before_upgrade(world: World) -> None:
    if world.alembic_cfg is None:
        raise AssertionError("scenario setup error: no pre-upgrade database was prepared")
    world.session.commit()
    stamp = f"{world.today.isoformat()}T00:00:00"
    expected: list[tuple[str, int | None]] = []
    with world.engine.begin() as conn:
        for payee, tx_type, category_id, amount in (
            ("Exito", "expense", 1, 5000000),
            ("Empresa", "income", 2, 500000000),
        ):
            conn.execute(
                sa_text(_INSERT_MOVEMENT),
                {
                    "date": world.today.isoformat(),
                    "payee": payee,
                    "type": tx_type,
                    "amount": amount,
                    "category_id": category_id,
                    "group_id": None,
                    "direction": None,
                    "created_at": stamp,
                },
            )
            expected.append((payee, category_id))
    world.pre_upgrade_expected = expected
    world.reopen_session()


@step(r"the user viewed the money available for (?P<month>" + _MONTH + r")")
def given_viewed_available(world: World, month: str) -> None:
    world.available_view = world.attempt(_call, "available", world.session, month)
    world.available_month = month


# --------------------------------------------------------------------- When


@step(r'the user (?P<mode>creates|tries to create) a fund on "(?P<name>[^"]+)"' + _FIXED)
def when_create_fund_fixed(world: World, mode: str, name: str, amount: str, start: str, roll) -> None:
    _make_fund(world, name, **_fixed_spec(amount, start, roll))


@step(r'the user (?P<mode>creates|tries to create) a fund on "(?P<name>[^"]+)"' + _AVERAGE)
def when_create_fund_average(world: World, mode: str, name: str, window: str, start: str) -> None:
    _make_fund(world, name, rule="average", window_months=int(window), start_month=start)


@step(r'the user (?P<mode>creates|tries to create) a fund on "(?P<name>[^"]+)"' + _OBLIGATIONS)
def when_create_fund_obligations(world: World, mode: str, name: str, start: str) -> None:
    _make_fund(world, name, rule="from-recurring", start_month=start)


@step(r'the user (?P<mode>creates|tries to create) a fund on "(?P<name>[^"]+)"' + _TARGET)
def when_create_fund_target(
    world: World, mode: str, name: str, target: str, by: str, start: str, opening, roll
) -> None:
    _make_fund(world, name, **_target_spec(target, by, start, opening, roll))


@step(r'the user starts creating a fund on "(?P<name>[^"]+)"' + _TARGET)
def when_start_creating_fund(world: World, name: str, target: str, by: str, start: str, opening, roll) -> None:
    spec = _target_spec(target, by, start, opening, roll)
    world.fund_preview = world.attempt(
        _call, "preview_fund", world.session, category_id=_category_id(world, name), **spec
    )
    world.pending_fund = (name, spec)


@step(r"the user goes ahead anyway")
def when_go_ahead(world: World) -> None:
    pending = getattr(world, "pending_fund", None)
    if pending is None:
        raise AssertionError("scenario setup error: no fund was being created")
    name, spec = pending
    _make_fund(world, name, **spec)


@step(r'the user sets the fund on "(?P<name>[^"]+)" to ask a fixed (?P<amount>' + _DEC + r") COP each month")
def when_set_fund_fixed(world: World, name: str, amount: str) -> None:
    world.attempt(_call, "set_fund", world.session, _fund_id(world, name), rule="fixed", amount=_cents(amount))


@step(r'the user sets the repeating income from "(?P<payee>[^"]+)" to (?P<amount>' + _DEC + r") COP")
def when_set_repeating_income(world: World, payee: str, amount: str) -> None:
    world.attempt(
        recurring.update_recurring,
        world.session,
        world.recurring_ids[payee],
        amount=_cents(amount),
    )


@step(r'the user deletes the fund on "(?P<name>[^"]+)"')
def when_delete_fund(world: World, name: str) -> None:
    world.attempt(_call, "delete_fund", world.session, _fund_id(world, name))
    world.funds.pop(name, None)


@step(r'the assistant deletes the fund on "(?P<name>[^"]+)"')
def when_assistant_deletes_fund(world: World, name: str) -> None:
    world.attempt(_assistant, world, "delete_fund", "FundInput", category=name)
    world.funds.pop(name, None)


@step(r'the assistant creates a fund on "(?P<name>[^"]+)"' + _FIXED)
def when_assistant_creates_fund(world: World, name: str, amount: str, start: str, roll) -> None:
    world.attempt(
        _assistant,
        world,
        "create_fund",
        "CreateFundInput",
        category=name,
        rule="fixed",
        amount=_cents(amount),
        start_month=start,
    )
    _remember_assistant_fund(world, name)


@step(r'the assistant tries to create a fund on "(?P<name>[^"]+)"' + _FIXED)
def when_assistant_tries_fund_fixed(world: World, name: str, amount: str, start: str, roll) -> None:
    world.attempt(
        _assistant,
        world,
        "create_fund",
        "CreateFundInput",
        raw=True,
        category=name,
        rule="fixed",
        amount=_cents(amount),
        start_month=start,
    )


@step(r'the assistant tries to create a fund on "(?P<name>[^"]+)"' + _AVERAGE)
def when_assistant_tries_fund_average(world: World, name: str, window: str, start: str) -> None:
    world.attempt(
        _assistant,
        world,
        "create_fund",
        "CreateFundInput",
        raw=True,
        category=name,
        rule="average",
        window_months=int(window),
        start_month=start,
    )


@step(r'the user tries to archive the category "(?P<name>[^"]+)"')
def when_try_archive_category(world: World, name: str) -> None:
    world.attempt(categories.archive_category, world.session, _category_id(world, name))


@step(r"the user views the funds")
def when_view_funds(world: World) -> None:
    world.funds_view = world.attempt(_call, "list_funds", world.session)


@step(r"the user views the money available this month")
def when_view_available(world: World) -> None:
    given_viewed_available(world, _month_of(world.today))


@step(r"the user views the money available for (?P<month>" + _MONTH + r")")
def when_view_available_for(world: World, month: str) -> None:
    given_viewed_available(world, month)


@step(r"the user looks for the goals")
def when_look_for_goals(world: World) -> None:
    try:
        from quaestor.services import goals

        world.goals_probe = goals
    except ImportError:
        world.goals_probe = None


@step(r"the assistant is asked to create a goal")
def when_assistant_asked_create_goal(world: World) -> None:
    world.goals_probe = _assistant_tool_names(world, "goal")


@step(r"the assistant is asked about the funds")
def when_assistant_asked_funds(world: World) -> None:
    world.assistant_answer = world.attempt(_assistant, world, "list_funds")


@step(r"the assistant is asked how much is available this month")
def when_assistant_asked_available(world: World) -> None:
    world.assistant_answer = world.attempt(
        _assistant, world, "money_available", "MonthInput", month=_month_of(world.today)
    )


def _assistant(world: World, tool: str, model: str | None = None, *, raw: bool = False, **fields):
    """Reach one fund tool the way the house builds them: ``(session, inp)``.

    Every tool takes one validated input model, speaks category names, and
    answers in text — a refusal included, because ``_as_text`` turns a domain
    error into words. ``raw`` steps past that translation for the scenarios
    that assert a refusal, since the world's rejection channel speaks
    exceptions; it is the same door `mandatory_categories` opens for the same
    reason.
    """
    module = _assistant_tools()
    fn = getattr(module, tool, None)
    if fn is None:
        raise AssertionError(f"the assistant has no {tool!r} tool yet — AC-28 asks for full parity with the app")
    call = getattr(fn, "__wrapped__", fn) if raw else fn
    if model is None:
        return call(world.session)
    shape = getattr(module, model, None)
    if shape is None:
        raise AssertionError(f"the assistant's {tool!r} has no {model!r} yet — the house shape is (session, inp)")
    return call(world.session, shape(**fields))


def _assistant_tools():
    """The assistant's fund tools, or a red naming their absence."""
    try:
        from quaestor.mcp.tools import funds as fund_tools
    except ImportError as exc:
        raise AssertionError("the assistant has no fund tools yet — AC-28 asks for full parity with the app") from exc
    return fund_tools


def _remember_assistant_fund(world: World, name: str) -> None:
    """The id the app sees for the fund the assistant just made — AC-28's parity."""
    if world.last_error is not None:
        return
    line = next((f for f in _call("list_funds", world.session) if f.name == name), None)
    if line is not None:
        world.funds = getattr(world, "funds", {})
        world.funds[name] = line.fund_id


def _assistant_tool_names(world: World, needle: str) -> list[str]:
    from quaestor.mcp import registry

    return [name for name in dir(registry) if needle in name.lower()]


# --------------------------------------------------------------------- Then


@step(r'the fund on "(?P<name>[^"]+)" asks (?P<amount>' + _DEC + r") COP this month")
def then_fund_asks(world: World, name: str, amount: str) -> None:
    asks = _attr(_status(world, name), "asks", f"the fund on {name!r}")
    assert asks == _cents(amount), f"the fund on {name!r} asks {asks}, expected {_cents(amount)}{_context(world)}"


@step(r'the fund on "(?P<name>[^"]+)" holds (?P<amount>' + _DEC + r") COP")
def then_fund_holds(world: World, name: str, amount: str) -> None:
    holds = _attr(_status(world, name), "holds", f"the fund on {name!r}")
    assert holds == _cents(amount), f"the fund on {name!r} holds {holds}, expected {_cents(amount)}{_context(world)}"


@step(r'the fund on "(?P<name>[^"]+)" spent (?P<amount>' + _DEC + r") COP this month")
def then_fund_spent(world: World, name: str, amount: str) -> None:
    world.require_clean(f"reading what the fund on {name!r} spent")
    spent = _attr(_status(world, name), "spent", f"the fund on {name!r}")
    assert spent == _cents(amount), f"the fund on {name!r} spent {spent}, expected {_cents(amount)}"


@step(r'the fund on "(?P<name>[^"]+)" carries (?P<amount>' + _DEC + r") COP into next month")
def then_fund_carries(world: World, name: str, amount: str) -> None:
    world.require_clean(f"reading what the fund on {name!r} carries")
    carries = _attr(_status(world, name), "carries", f"the fund on {name!r}")
    assert carries == _cents(amount), f"the fund on {name!r} carries {carries}, expected {_cents(amount)}"


@step(r'the fund on "(?P<name>[^"]+)" will have (?P<amount>' + _DEC + r") COP to spend next month")
def then_fund_next_month_has(world: World, name: str, amount: str) -> None:
    world.require_clean(f"reading what next month has on the fund on {name!r}")
    ahead = _attr(_status(world, name), "next_month_has", f"the fund on {name!r}")
    assert ahead == _cents(amount), f"the fund on {name!r} will have {ahead} next month, expected {_cents(amount)}"


@step(r'the fund on "(?P<name>[^"]+)" is (?P<state>on track|behind)')
def then_fund_track(world: World, name: str, state: str) -> None:
    world.require_clean(f"reading whether the fund on {name!r} is on track")
    on_track = _attr(_status(world, name), "on_track", f"the fund on {name!r}")
    assert on_track is (state == "on track"), f"the fund on {name!r} reports on_track={on_track}, expected {state!r}"


@step(r'the fund on "(?P<name>[^"]+)" says it averaged over (?P<count>\d+) months')
def then_fund_averaged_over(world: World, name: str, count: str) -> None:
    world.require_clean(f"reading how the fund on {name!r} averaged")
    over = _attr(_status(world, name), "averaged_over", f"the fund on {name!r}")
    assert over == int(count), f"the fund on {name!r} averaged over {over} months, expected {count}"


@step(r'the fund on "(?P<name>[^"]+)" says it spreads over (?P<count>\d+) months')
def then_fund_spreads_over(world: World, name: str, count: str) -> None:
    world.require_clean(f"reading how the fund on {name!r} spreads")
    over = _attr(_status(world, name), "spreads_over", f"the fund on {name!r}")
    assert over == int(count), f"the fund on {name!r} spreads over {over} months, expected {count}"


@step(r'the fund on "(?P<name>[^"]+)" says it is whole by (?P<month>' + _MONTH + r")")
def then_fund_whole_by(world: World, name: str, month: str) -> None:
    world.require_clean(f"reading when the fund on {name!r} is whole")
    whole = _attr(_status(world, name), "whole_by", f"the fund on {name!r}")
    assert str(whole) == month, f"the fund on {name!r} is whole by {whole}, expected {month}"


@step(r'the fund on "(?P<name>[^"]+)" accumulates')
def then_fund_accumulates(world: World, name: str) -> None:
    world.require_clean(f"reading whether the fund on {name!r} accumulates")
    accumulates = _attr(_status(world, name), "accumulates", f"the fund on {name!r}")
    assert accumulates is True, f"the fund on {name!r} does not accumulate"


@step(r'the fund on "(?P<name>[^"]+)" was not asked whether it accumulates')
def then_fund_not_asked(world: World, name: str) -> None:
    world.require_clean(f"reading whether the fund on {name!r} was asked")
    implied = _attr(_status(world, name), "accumulation_is_implied", f"the fund on {name!r}")
    assert implied is True, f"the fund on {name!r} offers a choice its rule does not have"


@step(r'the fund on "(?P<name>[^"]+)" names no account')
def then_fund_names_no_account(world: World, name: str) -> None:
    world.require_clean(f"reading whether the fund on {name!r} names an account")
    status = _status(world, name)
    account = getattr(status, "account_id", None)
    assert account is None, f"the fund on {name!r} still names an account ({account})"


@step(r"the fund is rejected")
def then_fund_rejected(world: World) -> None:
    world.consume_rejection(_REJECTED, "creating the fund")


@step(r"the user is told a fund only covers money going out")
def then_told_expense_only(world: World) -> None:
    _told(world, ("income", "going out", "salida"), "a fund only covers money going out")


@step(r'the user is told "(?P<name>[^"]+)" already has a fund')
def then_told_already_has_fund(world: World, name: str) -> None:
    _told(world, (name,), f"{name!r} already has a fund")


@step(r"the user is told a fund saving toward a date must accumulate")
def then_told_must_accumulate(world: World) -> None:
    _told(world, ("accumulate", "acumul"), "a fund saving toward a date must accumulate")


@step(r"the user is told the category holds a fund of (?P<amount>" + _DEC + r") COP")
def then_told_category_holds_fund(world: World, amount: str) -> None:
    _told(world, ("fund", "fondo"), f"the category holds a fund of {amount}")


@step(r"the user is told to name a fixed amount instead")
def then_told_use_fixed(world: World) -> None:
    _told(world, ("fixed", "fijo"), "to name a fixed amount instead")


def _told(world: World, needles: tuple[str, ...], what: str) -> None:
    """The refusal a rejection step already consumed said the right thing."""
    said = world.last_error
    if said is None:
        raise AssertionError(f"nothing refused anything, so nobody was told {what}")
    lowered = str(said).lower()
    assert any(n.lower() in lowered for n in needles), f"the refusal did not say {what}: {said!r}"


@step(r"the user is warned it would ask (?P<amount>" + _DEC + r") COP this month")
def then_warned_would_ask(world: World, amount: str) -> None:
    preview = getattr(world, "fund_preview", None)
    if preview is None:
        raise AssertionError("nothing previewed what the fund would ask before creating it")
    warning = _attr(preview, "warning", "the preview")
    would_ask = _attr(preview, "would_ask", "the preview")
    assert would_ask == _cents(amount), f"the preview says it would ask {would_ask}, expected {_cents(amount)}"
    assert warning, "the preview carries no warning"


@step(r"the user was not warned")
def then_not_warned(world: World) -> None:
    preview = getattr(world, "fund_preview", None)
    warning = getattr(preview, "warning", None) if preview is not None else None
    assert warning is None, f"the fund warned when it should not have: {warning!r}"


@step(r"no fund is listed")
def then_no_fund_listed(world: World) -> None:
    """Nothing is listed — reading the list here when no step viewed it.

    AC-24 asserts the warning came *before* the fund existed, and never opens
    the list to say so; the read belongs to the assertion, like the combined
    read+assert steps in ``fx_read_time``.
    """
    world.require_clean("listing the funds")
    listed = getattr(world, "funds_view", None)
    if listed is None:
        listed = _call("list_funds", world.session)
    assert not listed, f"expected no fund, got {[getattr(f, 'name', f) for f in listed]}"


@step(r"the money available this month is (?P<amount>" + _DEC + r") COP")
def then_available_this_month(world: World, amount: str) -> None:
    view = _call("available", world.session, _month_of(world.today))
    free = _attr(view, "free", "the money available")
    assert free == _cents(amount), f"the money available is {free}, expected {_cents(amount)}{_context(world)}"


@step(r"the money available that month is (?P<amount>" + _DEC + r") COP")
def then_available_that_month(world: World, amount: str) -> None:
    world.require_clean("reading the money available")
    view = getattr(world, "available_view", None)
    if view is None:
        raise AssertionError("no month's money available was viewed")
    free = _attr(view, "free", "the money available")
    assert free == _cents(amount), f"the money available is {free}, expected {_cents(amount)}"


def _breakdown(world: World):
    view = getattr(world, "available_view", None)
    if view is None:
        raise AssertionError("nothing opened the money available into its breakdown")
    return view


@step(r"the breakdown shows income of (?P<amount>" + _DEC + r") COP")
def then_breakdown_income(world: World, amount: str) -> None:
    income = _attr(_breakdown(world), "income", "the breakdown")
    assert income == _cents(amount), f"the breakdown shows income {income}, expected {_cents(amount)}"


@step(r'the breakdown names "(?P<name>[^"]+)" at (?P<amount>' + _DEC + r") COP")
def then_breakdown_names_fund(world: World, name: str, amount: str) -> None:
    lines = _attr(_breakdown(world), "funds", "the breakdown")
    named = {getattr(line, "name", None): getattr(line, "asks", None) for line in lines}
    assert name in named, f"the breakdown does not name {name!r}; it names {sorted(k for k in named if k)}"
    assert named[name] == _cents(amount), f"the breakdown puts {name!r} at {named[name]}, expected {_cents(amount)}"


@step(r"the breakdown shows uncovered spending of (?P<amount>" + _DEC + r") COP")
def then_breakdown_uncovered(world: World, amount: str) -> None:
    uncovered = _attr(_breakdown(world), "uncovered", "the breakdown")
    assert uncovered == _cents(amount), f"the breakdown shows uncovered {uncovered}, expected {_cents(amount)}"


@step(r"the breakdown adds up to the money available")
def then_breakdown_adds_up(world: World) -> None:
    view = _breakdown(world)
    income = _attr(view, "income", "the breakdown")
    lines = _attr(view, "funds", "the breakdown")
    uncovered = _attr(view, "uncovered", "the breakdown")
    free = _attr(view, "free", "the breakdown")
    total = income - sum(getattr(line, "asks", 0) for line in lines) - uncovered
    assert total == free, f"the breakdown adds to {total} but the money available is {free}"


def _rates(world: World):
    return _call("rates", world.session, _month_of(world.today))


@step(r"the earning rate is (?P<amount>" + _DEC + r") COP a month")
def then_earning_rate(world: World, amount: str) -> None:
    world.require_clean("reading the earning rate")
    earning = _attr(_rates(world), "earning", "the rates")
    assert earning == _cents(amount), f"the earning rate is {earning}, expected {_cents(amount)}"


@step(r"the cost rate is (?P<amount>" + _DEC + r") COP a month")
def then_cost_rate(world: World, amount: str) -> None:
    world.require_clean("reading the cost rate")
    cost = _attr(_rates(world), "cost", "the rates")
    assert cost == _cents(amount), f"the cost rate is {cost}, expected {_cents(amount)}"


@step(r"the margin is (?P<amount>" + _DEC + r") COP a month")
def then_margin(world: World, amount: str) -> None:
    world.require_clean("reading the margin")
    margin = _attr(_rates(world), "margin", "the rates")
    assert margin == _cents(amount), f"the margin is {margin}, expected {_cents(amount)}"


@step(r"the goals are not offered")
def then_goals_not_offered(world: World) -> None:
    probe = getattr(world, "goals_probe", "unset")
    assert probe is None, "the goals are still a concept the app offers"


@step(r"the assistant has no way to do it")
def then_assistant_cannot(world: World) -> None:
    probe = getattr(world, "goals_probe", None)
    assert not probe, f"the assistant still offers {probe}"


@step(r"the assistant's answer states (?P<amount>" + _DEC + r") COP")
def then_assistant_states_amount(world: World, amount: str) -> None:
    """The figure, in the words the scenario uses — which is how the house renders money."""
    answer = world.assistant_answer
    if answer is None:
        raise AssertionError("the assistant answered nothing")
    expected = f"{amount} COP"
    assert expected in str(answer), f"the assistant's answer does not state {expected}: {answer!r}"


@step(r"the records hold no goal")
def then_records_hold_no_goal(world: World) -> None:
    world.require_clean("the upgrade should have completed")
    with world.engine.begin() as conn:
        try:
            rows = list(conn.execute(sa_text(_SELECT_GOALS)))
        except Exception:
            return
    assert not rows, f"the records still hold goals {[r[0] for r in rows]}"
