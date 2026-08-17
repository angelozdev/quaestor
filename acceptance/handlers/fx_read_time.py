"""Step handlers — feature 005 fx-read-time-conversion (ADR-0031).

Bound to the Quaestor **services layer as it should look after the
feature**. The feature is not implemented yet, so several bindings target
the *intended* post-feature API (see the "intended API" section below);
those steps fail red on AttributeError/TypeError, documenting the desired
shape. That is the correct ATDD state.

Intended post-feature surface (from ADR-0031 + acs.md), all in one place so
Checkpoint-5 implementation only adjusts these thin wrappers:

- ``fx.set_trm(session, value)``        — overwrite the single scalar TRM
                                          (ValidationError when value <= 0)
- ``fx.get_trm(session)``               — current TRM (Decimal);
                                          MissingRate when never set
- ``fx.to_cop_cents(session, amount_cents, currency)``
                                        — the single read-time conversion
                                          helper; COP is identity; USD is
                                          amount x TRM, half-up to the cent
- ``transactions.transfer_cross_currency(session, from_id, to_id,
      amount_sent, amount_received, date)``
                                        — two physical amounts, each leg in
                                          its account's currency, no rate
                                          stored
- ``money.implied_rate(sent_cents, received_cents)``
                                        — received / sent, information only
- REST ``GET /api/transactions/{id}``   — read-time field ``cop_equivalent``
                                          (COP cents)
- MCP ``get_transaction``               — card shows the read-time COP
                                          equivalent as ``(X COP)``
"""

from __future__ import annotations

import os
import re as _re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from unittest import mock

from quaestor.domain import money as money_mod
from quaestor.domain.errors import MissingRate, QuaestorError
from quaestor.domain.models import Settings, TxType
from quaestor.domain.money import major_to_cents
from quaestor.jobs import daily as daily_job
from quaestor.services import accounts, categories, fx, reports, transactions
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text as sa_text
from sqlmodel import select

from . import step
from .world import World

# Last Alembic revision of the frozen-conversion design (pre-feature head).
# The feature's migration will be a later revision that drops
# transaction.to_base / transaction.fx_rate and the dated fx_rate table.
_PRE_FEATURE_REVISION = "0004"

_DEC = r"-?\d+(?:\.\d+)?"


def _month_str(d) -> str:
    return f"{d.year:04d}-{d.month:02d}"


# ------------------------------------------------------ intended API (thin)


def _set_trm(session, value) -> None:
    """Manual TRM overwrite — intended ``fx.set_trm``."""
    fx.set_trm(session, Decimal(str(value)))


def _get_trm(session) -> Decimal:
    """Current TRM — intended ``fx.get_trm``."""
    return fx.get_trm(session)


def _cop_equivalent_cents(session, amount_cents: int, currency: str) -> int:
    """Read-time conversion: ``money.to_cop_cents`` at the current TRM."""
    return money_mod.to_cop_cents(amount_cents, currency, fx.get_trm(session))


def _transfer_cross_currency(session, from_id, to_id, sent_cents, received_cents, date):
    """Cross-currency transfer with two physical amounts (ADR-0031)."""
    return transactions.transfer(
        session,
        from_id,
        to_id,
        sent_cents,
        None,
        date,
        amount_received=received_cents,
    )


def _implied_rate(sent_cents: int, received_cents: int) -> Decimal:
    """Implied transfer rate helper — intended ``domain.money.implied_rate``."""
    return money_mod.implied_rate(sent_cents, received_cents)


# ------------------------------------------------------------------- Given


@step(r"no TRM has been set")
def given_no_trm(world: World) -> None:
    """Take the app back to before any rate existed.

    The World seeds one, because a running app always carries one. A scenario
    whose subject *is* the missing rate therefore has to remove it rather than
    assume it was never there.
    """
    for settings in world.session.exec(select(Settings)).all():
        settings.usd_cop = None
        world.session.add(settings)
    world.session.commit()


@step(r"the TRM is (?P<value>" + _DEC + r")")
def given_trm(world: World, value: str) -> None:
    _set_trm(world.session, value)


@step(
    r'an account "(?P<name>[^"]+)" in (?P<currency>[A-Z]{3})'
    r" with balance (?P<amount>" + _DEC + r") (?P<currency2>[A-Z]{3})"
)
def given_account_with_balance(world: World, name: str, currency: str, amount: str, currency2: str) -> None:
    acc = accounts.create_account(world.session, name, "debit", currency, balance=major_to_cents(amount))
    world.accounts[name] = acc.id


@step(r'an account "(?P<name>[^"]+)" in (?P<currency>[A-Z]{3})')
def given_account(world: World, name: str, currency: str) -> None:
    acc = accounts.create_account(world.session, name, "debit", currency, balance=0)
    world.accounts[name] = acc.id


def _default_account_id(world: World, currency: str) -> int:
    if currency not in world.default_accounts:
        acc = accounts.create_account(world.session, f"{currency} Wallet", "debit", currency, balance=0)
        world.default_accounts[currency] = acc.id
    return world.default_accounts[currency]


def _record_default_expense(world: World, amount: str, currency: str, on_date, category_id: int | None = None) -> None:
    tx = transactions.record_expense(
        world.session,
        _default_account_id(world, currency),
        major_to_cents(amount),
        currency,
        on_date,
        "Acceptance payee",
        category_id=category_id if category_id is not None else world.background_category(TxType.expense),
    )
    world.last_expense_id = tx.id


@step(
    r"a recorded expense of (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3})"
    r"(?: in the current month)?"
)
def given_recorded_expense(world: World, amount: str, currency: str) -> None:
    _record_default_expense(world, amount, currency, world.today)


@step(
    r"a recorded expense of (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3})"
    r" dated in a previous month"
)
def given_recorded_expense_previous_month(world: World, amount: str, currency: str) -> None:
    _record_default_expense(world, amount, currency, world.previous_month_day)


@step(
    r'a category "(?P<name>[^"]+)" with a recorded expense of '
    r"(?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3}) in the current month"
)
def given_category_with_expense(world: World, name: str, amount: str, currency: str) -> None:
    cat = categories.create_category(world.session, name)
    world.categories[name] = cat.id
    _record_default_expense(world, amount, currency, world.today, category_id=cat.id)


@step(r"transactions recorded before the upgrade, including foreign-currency ones")
def given_pre_upgrade_data(world: World) -> None:
    """Build a DB at the pre-feature schema and seed old-shape rows via SQL.

    Raw SQL (not the models) because after the feature the models no longer
    have ``to_base``/``fx_rate`` — but the historical schema at revision
    0004 is frozen forever, so these statements stay valid.
    """
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

    with engine.begin() as conn:
        conn.execute(
            sa_text(
                "INSERT INTO account (name, type, currency, balance, archived) "
                "VALUES ('Wise', 'debit', 'USD', 0, 0), "
                "('Bancolombia', 'debit', 'COP', 0, 0)"
            )
        )
        conn.execute(
            sa_text(
                "INSERT INTO category (name, is_income, exclude_from_budget, "
                "exclude_from_totals, archived) VALUES ('Antes del alta', 0, 0, 0, 0)"
            )
        )
        conn.execute(
            sa_text(
                'INSERT INTO "transaction" '
                "(date, payee, notes, type, status, amount, currency, fx_rate, "
                " to_base, account_id, category_id, source, created_at) VALUES "
                "('2026-05-10', 'Spotify', NULL, 'expense', 'posted', 1200, 'USD', "
                " 4000.0, 4800000, 1, 1, 'manual', '2026-05-10 12:00:00'), "
                "('2026-05-11', 'Mercado', NULL, 'expense', 'posted', 5000000, 'COP', "
                " 1.0, 5000000, 2, 1, 'manual', '2026-05-11 12:00:00')"
            )
        )
        conn.execute(sa_text("INSERT INTO fx_rate (date, usd_cop) VALUES ('2026-05-10', 4000.0)"))

    world.replace_engine(engine)
    world.alembic_cfg = cfg
    world.migration_expected = [
        ("Spotify", 1200, "USD"),
        ("Mercado", 5_000_000, "COP"),
    ]


# -------------------------------------------------------------------- When


@step(
    r"the user registers an expense of (?P<amount>" + _DEC + r") "
    r'(?P<currency>[A-Z]{3}) from "(?P<account>[^"]+)"'
    r'(?: in category "(?P<category>[^"]+)")?'
)
def when_register_expense(world: World, amount: str, currency: str, account: str, category: str | None) -> None:
    def action():
        tx = transactions.record_expense(
            world.session,
            world.accounts[account],
            major_to_cents(amount),
            currency,
            world.today,
            "Acceptance payee",
            category_id=world.categories[category] if category else world.background_category(TxType.expense),
        )
        world.last_expense_id = tx.id

    world.attempt(action)


def _view_last_expense(world: World) -> None:
    def action():
        if world.last_expense_id is None:
            raise AssertionError("no expense was recorded earlier in the scenario")
        tx = transactions.get_transaction(world.session, world.last_expense_id)
        world.viewed_cop_cents = _cop_equivalent_cents(world.session, tx.amount, tx.currency)

    world.attempt(action)


@step(r"the user views the expense")
def when_view_expense(world: World) -> None:
    _view_last_expense(world)


@step(r"the user sets the TRM to (?P<value>" + _DEC + r")")
def when_set_trm(world: World, value: str) -> None:
    world.attempt(_set_trm, world.session, value)


@step(r"the daily rate update sets the TRM to (?P<value>" + _DEC + r")")
def when_daily_rate_update(world: World, value: str) -> None:
    def action():
        with mock.patch.object(daily_job, "fetch_usd_cop", return_value=Decimal(value)):
            daily_job.run_daily(world.session, world.today, "https://fx.acceptance.invalid", None)

    world.attempt(action)


@dataclass(frozen=True)
class _SpendingLine:
    """What one category spent in the month, whatever set money aside for it."""

    category_name: str
    spent: int


def _view_report(world: World, month: str) -> None:
    """Open the month's report, and the per-category lines it carries with it.

    ``the spending for "X" shows N`` reads those lines. 003's AC-12 asks for
    them off the report and 005's AC-2 off the budget — two doors onto the
    same question, so both fill the same scratchpad. The budget door survives
    the envelope it was named after: the report's per-category sections answer
    it for every category, funded or not.
    """
    world.report = None
    world.report_month = month

    def action():
        world.report = reports.monthly_report(world.session, month, today=world.today)
        world.spending_lines = [_SpendingLine(section.category, section.total) for section in world.report.by_category]

    world.attempt(action)


@step(r"the user views the current month's report")
def when_view_current_report(world: World) -> None:
    _view_report(world, _month_str(world.today))


@step(r"the user views the current month's budget")
def when_view_budget(world: World) -> None:
    _view_report(world, _month_str(world.today))


@step(
    r"the user transfers sending (?P<sent>" + _DEC + r") (?P<sent_cur>[A-Z]{3}) "
    r'from "(?P<src>[^"]+)" and receiving (?P<received>' + _DEC + r") "
    r'(?P<recv_cur>[A-Z]{3}) into "(?P<dst>[^"]+)"'
)
def when_cross_currency_transfer(
    world: World,
    sent: str,
    sent_cur: str,
    src: str,
    received: str,
    recv_cur: str,
    dst: str,
) -> None:
    def action():
        world.transfer_legs = _transfer_cross_currency(
            world.session,
            world.accounts[src],
            world.accounts[dst],
            major_to_cents(sent),
            major_to_cents(received),
            world.today,
        )

    world.attempt(action)


@step(
    r"the user transfers (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3}) "
    r'from "(?P<src>[^"]+)" to "(?P<dst>[^"]+)"'
)
def when_same_currency_transfer(world: World, amount: str, currency: str, src: str, dst: str) -> None:
    def action():
        world.transfer_legs = transactions.transfer(
            world.session,
            world.account_id_or_missing(src),
            world.account_id_or_missing(dst),
            major_to_cents(amount),
            currency,
            world.today,
        )

    world.attempt(action)


@step(
    r"the user prepares a transfer sending (?P<sent>" + _DEC + r") "
    r'(?P<sent_cur>[A-Z]{3}) from "(?P<src>[^"]+)" and receiving '
    r"(?P<received>" + _DEC + r") (?P<recv_cur>[A-Z]{3}) "
    r'into "(?P<dst>[^"]+)"'
)
def when_prepare_transfer(
    world: World,
    sent: str,
    sent_cur: str,
    src: str,
    received: str,
    recv_cur: str,
    dst: str,
) -> None:
    world.implied_rate = None
    world.implied_rate_error = None
    try:
        world.implied_rate = _implied_rate(major_to_cents(sent), major_to_cents(received))
    except Exception as exc:
        world.implied_rate_error = exc


_DATA_REVISIONS = ("quaestor.migrations.versions.0020_a_fund_that_filled_charges_becomes_one_per_charge",)
"""Revisions that move rows rather than columns, in the order Alembic runs them.

A scenario that starts from an old *schema* prepares one and lets Alembic walk
to head. One that starts from today's schema and an old *shape of the data* has
nothing for Alembic to do — the columns are already there — so the data half is
run on its own. Both are the same sentence to the owner: the upgrade completes.
"""


@step(r"the upgrade completes")
def when_upgrade_completes(world: World) -> None:
    """Run the real revisions, never a reimplementation of what they do.

    A migration checked by a copy of itself proves nothing (013 set this rule).
    """
    from importlib import import_module

    if world.alembic_cfg is not None:
        from alembic import command as alembic_command

        alembic_command.upgrade(world.alembic_cfg, "head")
        world.reopen_session()
        return
    for name in _DATA_REVISIONS:
        import_module(name).split_category_funds_into_charge_funds(world.session.connection())
    world.session.commit()
    world.session.expire_all()


# --------------------------------------------------- When (AC-13, parity)


def _rest_client(world: World):
    """A REST TestClient wired to this scenario's engine (same pattern as
    backend/tests/api/conftest.py)."""
    os.environ["APP_TOKEN"] = "acceptance-token"
    os.environ["APP_PASSWORD"] = "acceptance-password"
    os.environ["SESSION_SECRET"] = "a" * 64
    os.environ["FRONTEND_ORIGIN"] = "http://localhost:3000"
    os.environ.pop("COOKIE_SECURE", None)

    from fastapi.testclient import TestClient
    from quaestor.api import create_app
    from quaestor.api.deps import get_session
    from sqlmodel import Session

    app = create_app()

    def override_get_session():
        with Session(world.engine) as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app), {"Authorization": "Bearer acceptance-token"}


@step(r"the user views the expense in the app")
def when_view_expense_in_app(world: World) -> None:
    def action():
        if world.last_expense_id is None:
            raise AssertionError("no expense was recorded earlier in the scenario")
        client, auth = _rest_client(world)
        resp = client.get(f"/api/transactions/{world.last_expense_id}", headers=auth)
        if resp.status_code != 200:
            raise AssertionError(f"GET /api/transactions/{world.last_expense_id} -> {resp.status_code}: {resp.text}")
        data = resp.json()
        if "cop_equivalent" not in data:
            raise AssertionError(
                "the app's transaction read exposes no read-time "
                "'cop_equivalent' field (ADR-0031: COP figures are computed "
                f"at read time); got fields: {sorted(data)}"
            )
        world.app_cop_cents = data["cop_equivalent"]

    world.attempt(action)


@step(r"the assistant interface lists the same expense")
def when_assistant_lists_expense(world: World) -> None:
    def action():
        from quaestor.mcp.tools.transactions import (
            GetTransactionInput,
        )
        from quaestor.mcp.tools.transactions import (
            get_transaction as mcp_get_transaction,
        )

        if world.last_expense_id is None:
            raise AssertionError("no expense was recorded earlier in the scenario")
        card = mcp_get_transaction(world.session, GetTransactionInput(tx_id=world.last_expense_id))
        m = _re.search(r"\((" + _DEC + r") COP\)", card)
        if m is None:
            raise AssertionError(f"MCP transaction card shows no '(X COP)' equivalent: {card!r}")
        world.mcp_cop_major = Decimal(m.group(1))

    world.attempt(action)


# -------------------------------------------------------------------- Then


@step(
    r"the expense is recorded with amount (?P<amount>" + _DEC + r") "
    r"(?P<currency>[A-Z]{3})"
)
def then_expense_recorded(world: World, amount: str, currency: str) -> None:
    world.require_clean("the expense should have been recorded")
    assert world.last_expense_id is not None, "no expense was recorded"
    tx = transactions.get_transaction(world.session, world.last_expense_id)
    expected = major_to_cents(amount)
    assert tx.amount == expected, f"expected amount {expected} cents, got {tx.amount}"
    assert tx.currency == currency, f"expected currency {currency}, got {tx.currency}"


@step(r"viewing the expense shows no exchange rate")
def then_viewing_expense_no_rate(world: World) -> None:
    world.require_clean("the expense should have been recorded")
    assert world.last_expense_id is not None, "no expense was recorded"
    tx = transactions.get_transaction(world.session, world.last_expense_id)
    rate = getattr(tx, "fx_rate", None)
    converted = getattr(tx, "to_base", None)
    assert rate is None, (
        f"transaction still carries a frozen rate (fx_rate={rate}); ADR-0031 drops per-transaction rates"
    )
    assert converted is None, (
        f"transaction still carries a frozen converted amount (to_base={converted}); ADR-0031 drops stored conversions"
    )


@step(
    r'"(?P<name>[^"]+)" has balance (?P<amount>' + _DEC + r") "
    r"(?P<currency>[A-Z]{3})"
)
def then_account_balance(world: World, name: str, amount: str, currency: str) -> None:
    acc = accounts.get_account(world.session, world.accounts[name])
    expected = major_to_cents(amount)
    assert acc.currency == currency, f"account {name!r} is in {acc.currency}, expected {currency}"
    # No require_clean(): this step also asserts unchanged balances after a
    # rejected action. But if the balance is wrong AND an action failed,
    # surface that failure as the likely cause.
    context = ""
    if world.errors:
        details = "; ".join(f"{type(e).__name__}: {e}" for e in world.errors)
        context = f" (a preceding action failed — {details})"
    assert acc.balance == expected, (
        f"account {name!r}: expected balance {expected} cents ({amount} {currency}), got {acc.balance}{context}"
    )


@step(r"its COP equivalent shows (?P<amount>" + _DEC + r") COP")
def then_cop_equivalent(world: World, amount: str) -> None:
    world.require_clean("viewing the expense should have succeeded")
    expected = major_to_cents(amount)
    assert world.viewed_cop_cents == expected, (
        f"expected COP equivalent {expected} cents ({amount} COP), got {world.viewed_cop_cents}"
    )


@step(r"the month's expense total shows (?P<amount>" + _DEC + r") COP")
def then_month_expense_total(world: World, amount: str) -> None:
    world.require_clean("viewing the report should have succeeded")
    assert world.report is not None, "no report was produced"
    expected = major_to_cents(amount)
    assert world.report.expense == expected, (
        f"month {world.report_month}: expected expense total {expected} cents "
        f"({amount} COP), got {world.report.expense}"
    )


def _assert_report_total(world: World, month: str, amount: str) -> None:
    """Combined read+assert: build the month's report now, check its total."""
    world.require_clean(f"reading the {month} report should be possible")
    report = reports.monthly_report(world.session, month, today=world.today)
    expected = major_to_cents(amount)
    assert report.expense == expected, (
        f"month {month}: expected expense total {expected} cents ({amount} COP), got {report.expense}"
    )


@step(
    r"that previous month's report shows an expense total of "
    r"(?P<amount>" + _DEC + r") COP"
)
def then_previous_month_report_total(world: World, amount: str) -> None:
    _assert_report_total(world, _month_str(world.previous_month_day), amount)


@step(
    r"the current month's report shows an expense total of "
    r"(?P<amount>" + _DEC + r") COP"
)
def then_current_month_report_total(world: World, amount: str) -> None:
    _assert_report_total(world, _month_str(world.today), amount)


@step(r"the expense's COP equivalent shows (?P<amount>" + _DEC + r") COP")
def then_expense_cop_equivalent_now(world: World, amount: str) -> None:
    """Combined read+assert: convert the recorded expense at read time now."""
    world.require_clean("the preceding TRM change should have succeeded")
    assert world.last_expense_id is not None, "no expense was recorded"
    tx = transactions.get_transaction(world.session, world.last_expense_id)
    got = _cop_equivalent_cents(world.session, tx.amount, tx.currency)
    expected = major_to_cents(amount)
    assert got == expected, f"expected COP equivalent {expected} cents ({amount} COP), got {got}"


@step(r'the spending for "(?P<name>[^"]+)" shows (?P<amount>' + _DEC + r") COP")
def then_budget_spending(world: World, name: str, amount: str) -> None:
    world.require_clean("viewing the month's spending should have succeeded")
    assert world.spending_lines is not None, "no month view was produced"
    line = next((row for row in world.spending_lines if row.category_name == name), None)
    assert line is not None, (
        f"no spending line for category {name!r}; got {[row.category_name for row in world.spending_lines]}"
    )
    expected = major_to_cents(amount)
    assert line.spent == expected, (
        f"category {name!r}: expected spending {expected} cents ({amount} COP), got {line.spent}"
    )


@step(r"the current TRM is (?P<value>" + _DEC + r")")
def then_current_trm(world: World, value: str) -> None:
    current = _get_trm(world.session)
    assert current == Decimal(value), f"expected current TRM {value}, got {current}"


@step(r"viewing the transfer shows no exchange rate")
def then_viewing_transfer_no_rate(world: World) -> None:
    world.require_clean("the transfer should have succeeded")
    assert world.transfer_legs is not None, "no transfer was recorded"
    for leg in world.transfer_legs:
        rate = getattr(leg, "fx_rate", None)
        assert rate is None, (
            f"transfer leg {leg.id} carries a rate (fx_rate={rate}); "
            "ADR-0031: the effective rate is implicit in the two amounts"
        )


@step(r"the transfer form shows an implied rate of (?P<value>" + _DEC + r")")
def then_implied_rate(world: World, value: str) -> None:
    # The live dialog display is frontend behavior (AC-8) and cannot be
    # exercised host-side; this binds the shared computation the form uses.
    if world.implied_rate_error is not None:
        raise AssertionError(
            "no implied-rate computation exists "
            f"({type(world.implied_rate_error).__name__}: "
            f"{world.implied_rate_error}); AC-8 expects the transfer form to "
            "show received / sent as reference information"
        )
    assert world.implied_rate == Decimal(value), f"expected implied rate {value}, got {world.implied_rate}"


@step(r"the report is not shown")
def then_report_not_shown(world: World) -> None:
    assert world.report is None, (
        "the report was shown although no TRM is set (AC-9: reads must fail loud, never assume rate 1)"
    )
    world.consume_rejection((MissingRate,), "viewing the report without a TRM")


@step(r"the user is told to set the TRM")
def then_told_to_set_trm(world: World) -> None:
    err = world.last_error
    assert err is not None, "no error message was produced"
    assert "trm" in str(err).lower(), f"the error does not tell the user to set the TRM: {err}"


@step(r"the change is rejected")
def then_change_rejected(world: World) -> None:
    world.consume_rejection((QuaestorError,), "setting an invalid TRM")


@step(r"the transfer is rejected")
def then_transfer_rejected(world: World) -> None:
    world.consume_rejection((QuaestorError,), "the invalid transfer")


@step(r"every transaction still shows its original amount and currency")
def then_migration_preserves_amounts(world: World) -> None:
    with world.engine.connect() as conn:
        rows = conn.execute(sa_text('SELECT payee, amount, currency FROM "transaction" ORDER BY id')).fetchall()
    actual = [(r[0], r[1], r[2]) for r in rows]
    assert actual == world.migration_expected, (
        f"original amounts/currencies changed: expected {world.migration_expected}, got {actual}"
    )


@step(r"viewing any transaction shows no exchange rate")
def then_viewing_any_transaction_no_rate(world: World) -> None:
    columns = {col["name"] for col in sa_inspect(world.engine).get_columns("transaction")}
    leftovers = columns & {"fx_rate", "to_base"}
    assert not leftovers, (
        f"transaction views would still expose a stored rate/converted amount "
        f"— columns {sorted(leftovers)} survive the upgrade; ADR-0031 drops "
        "them so no view can show a frozen exchange rate"
    )


@step(r"both show a COP equivalent of (?P<amount>" + _DEC + r") COP")
def then_both_surfaces_agree(world: World, amount: str) -> None:
    world.require_clean("both surface reads should have succeeded")
    expected_cents = major_to_cents(amount)
    expected_major = Decimal(amount)
    assert world.app_cop_cents == expected_cents, (
        f"app (REST): expected {expected_cents} COP cents ({amount} COP), got {world.app_cop_cents}"
    )
    assert world.mcp_cop_major == expected_major, f"assistant (MCP): expected {amount} COP, got {world.mcp_cop_major}"
