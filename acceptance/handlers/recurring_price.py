"""Step handlers — feature 013 recurring-charge-keeps-its-price.

Bound to the services layer, where an obligation now holds the merchant's price
and its account decides what is debited (ADR-0053). The steps that already
describe declaring, editing, moving and charging an obligation live in
``recurring_engine``; this module adds only what the split between price and
account made sayable for the first time.

``the stored prices are migrated`` runs the real Alembic revision against the
scenario's database rather than reimplementing what it does — a migration
checked by a copy of itself would prove nothing.
"""

from __future__ import annotations

from importlib import import_module

from quaestor.domain.errors import NotFound, QuaestorError, ValidationError
from quaestor.domain.models import Account, RecurringItem, RecurringMode
from quaestor.domain.money import major_to_cents, to_cop_cents
from quaestor.services import fx, reports

from . import step
from .fx_read_time import _DEC
from .recurring_engine import _item
from .world import World

_REJECTED = (ValidationError, NotFound, QuaestorError, ValueError)
_REVISION = "quaestor.migrations.versions.0017_two_obligations_go_back_to_the_price_the_merchant_charges"


def _revision():
    """The migration module itself — its name starts with a digit, so it is imported by path."""
    return import_module(_REVISION)


def _account_of(world: World, item: RecurringItem) -> Account:
    account = world.session.get(Account, item.account_id)
    if account is None:
        raise AssertionError(f"{item.name!r} points at account {item.account_id}, which does not exist")
    return account


@step(r'"(?P<name>[^"]+)" is charged to "(?P<account>[^"]+)"')
def then_charged_to_account(world: World, name: str, account: str) -> None:
    actual = _account_of(world, _item(world, name)).name
    assert actual == account, f"{name!r} is charged to {actual!r}, not {account!r}"


@step(r'"(?P<name>[^"]+)" still pays itself')
def then_still_pays_itself(world: World, name: str) -> None:
    mode = _item(world, name).mode
    assert mode == RecurringMode.auto, f"{name!r} is {mode.value}, not paying itself"


@step(r'"(?P<name>[^"]+)" waits for approval')
def then_waits_for_approval(world: World, name: str) -> None:
    mode = _item(world, name).mode
    assert mode == RecurringMode.manual, f"{name!r} is {mode.value}, not waiting for approval"


@step(r'the user tries to make "(?P<name>[^"]+)" pay itself')
def when_make_pay_itself(world: World, name: str) -> None:
    from quaestor.services import recurring

    world.attempt(
        recurring.update_recurring,
        world.session,
        _item(world, name).id,
        mode=RecurringMode.auto,
    )


def _refusal(world: World) -> str:
    """What the app said when it turned the action down, read as many times as asked.

    Two steps ask about the same refusal, so the first consumes it and both
    read what it left behind.
    """
    if world.last_error is not None and world.last_error in world.errors:
        world.consume_rejection(_REJECTED, "the refusal")
    if world.last_rejection is None:
        raise AssertionError("the refusal: expected the action to be rejected, but it succeeded")
    return world.last_rejection


@step(r"the refusal offers to hold the price in (?P<currency>[A-Z]{3})")
def then_refusal_offers_currency(world: World, currency: str) -> None:
    said = _refusal(world)
    assert currency in said, f"the refusal never names {currency}: {said!r}"


@step(r"the refusal offers to wait for approval instead")
def then_refusal_offers_manual(world: World) -> None:
    said = _refusal(world)
    assert "wait for approval" in said, f"the refusal never offers to wait for approval: {said!r}"


@step(
    r"the month (?P<year_month>\d{4}-\d{2}) reports (?P<amount>" + _DEC + r")"
    r" (?P<currency>[A-Z]{3}) still unconfirmed"
)
def then_month_reports_unconfirmed(world: World, year_month: str, amount: str, currency: str) -> None:
    """What the month says is still owed, read the way the report reads it.

    Every waiting figure converts by the currency IT declares, which is the
    whole point once a charge can be stated in one its account does not hold.
    """
    report = reports.monthly_report(world.session, year_month)
    expected = to_cop_cents(major_to_cents(amount), currency, fx.get_trm(world.session))
    total = sum(_pending_cents(line) for line in report.pending)
    assert total == expected, f"the month reports {total} cents unconfirmed, not {expected}"


def _pending_cents(line: str) -> int:
    """The cents inside one alert line — `'Name: $1,234.56 COP pending'`."""
    figure = line.rsplit(": $", 1)[1].split(" ", 1)[0].replace(",", "")
    return major_to_cents(figure)


@step(r"the stored prices are migrated")
def when_prices_migrated(world: World) -> None:
    """Run the real revision, not a copy of what it is supposed to do."""
    _revision().restate_stored_prices(world.session)
    world.session.commit()


@step(r'"(?P<name>[^"]+)" has been switched off')
def given_switched_off(world: World, name: str) -> None:
    from quaestor.services import recurring

    recurring.deactivate_recurring(world.session, _item(world, name).id)
