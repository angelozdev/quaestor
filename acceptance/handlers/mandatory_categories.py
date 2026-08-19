"""Step handlers — feature 008 mandatory-categories.

Bound to the services layer (``quaestor.services.transactions/categories/
planned/recurring``); the AC-14 assistant steps go through the MCP tools
layer, and AC-17/18/19 go under the services layer on purpose — raw SQL
against the scenario's engine, and Alembic against a database built at the
pre-feature head.

The feature is not implemented, so most bindings name the *intended*
post-feature surface and fail red either on TypeError/AttributeError or on a
refusal that never comes. Every intended call is collected here so
Checkpoint-5 implementation only has to satisfy this list:

- ``transactions.record_expense/record_income(..., category_id=None)``
  refuses — an expense or income with no category is never stored (AC-1/2).
- ``categories.list_categories(session, is_income=<bool>)`` — the
  direction-filtered offering behind "the categories offered" (AC-4/10/12).
- ``transactions.record_expense/record_income(..., category_id=<a category
  of the other direction>)`` refuses (AC-15).
- ``transactions.record_expense/record_income(..., new_category="<name>")``
  — inline creation from the movement form: creates the category with the
  direction of the movement and records the movement in one action
  (AC-5/12), refusing a name an active category already holds and offering
  to restore an archived one instead (AC-13).
- ``transactions.transfer(..., category_id=...)`` refuses — a transfer
  carries no category (AC-3).
- ``planned.plan_payment(..., category_id=None)`` and
  ``recurring.create_recurring(..., category_id=None)`` refuse (AC-6/7).
- ``transactions.update_transaction(tx_id, category_id=None)`` refuses on a
  movement that already carries one (AC-11).
- The stored data itself refuses an uncategorised expense or income and a
  categorised transfer (AC-17), and the migration that installs that rule
  refuses to run while any movement is still uncategorised (AC-18).

The AC-14 steps call the tool body beneath the MCP ``_as_text`` wrapper:
that wrapper turns a domain refusal into agent text, which would hide the
refusal from the scenario's error stream. It is the same code path, minus
the presentation layer.

Scratchpad keys this module puts on the :class:`World`:
``offered_categories`` (the direction-filtered offering), ``last_income_id``,
``attempted_category`` (name + id last submitted), ``pre_upgrade_expected``
and ``pre_upgrade_transfers`` (the AC-18/19 fixtures).
"""

from __future__ import annotations

from pathlib import Path

from quaestor.domain.errors import QuaestorError
from quaestor.domain.models import TxType
from quaestor.domain.money import major_to_cents
from quaestor.services import accounts, categories, recurring, transactions
from sqlalchemy import text as sa_text
from sqlalchemy.exc import DatabaseError

from . import step
from .fx_read_time import _DEC
from .planned_payments import _DUE, _payment, _plan
from .recurring_engine import _WHEN, _declare, _item, _linked_tx, _when
from .transactions_crud import _last_expense
from .world import MISSING_ID, NO_CATEGORY, World

# The Alembic head before this feature. The migration that installs the
# mandatory-category rule is the revision after it (AC-18/19).
_PRE_FEATURE_REVISION = "0009"

_NO_CATEGORY_DECLARATION = (
    r" every (?P<count>\d+) (?P<unit>day|week|month|year)"
    r" starting (?P<start>" + _WHEN + r")"
    r" with no category, (?P<mode>paying itself|waiting for approval)"
)

_INSERT_MOVEMENT = """
    INSERT INTO "transaction"
        (date, payee, notes, type, status, amount, currency, account_id,
         category_id, transfer_group_id, transfer_direction, source,
         created_at)
    VALUES
        (:date, :payee, NULL, :type, 'posted', :amount, 'COP', :account_id,
         :category_id, :group_id, :direction, 'manual', :created_at)
"""

_SEED_ACCOUNT = """
    INSERT INTO account (name, type, currency, balance, archived)
    VALUES ('Bancolombia', 'debit', 'COP', 0, 0)
"""

_SEED_CATEGORIES = """
    INSERT INTO category
        (name, group_id, is_income, exclude_from_budget,
         exclude_from_totals, archived)
    VALUES ('Comida', NULL, 0, 0, 0, 0), ('Salario', NULL, 1, 0, 0, 0)
"""

_SELECT_MOVEMENTS = """
    SELECT payee, category_id FROM "transaction"
    WHERE type IN ('expense', 'income') ORDER BY id
"""

_SELECT_UNCATEGORISED = """
    SELECT payee, type FROM "transaction"
    WHERE type IN ('expense', 'income') AND category_id IS NULL ORDER BY id
"""

_SELECT_TRANSFERS = """
    SELECT payee, category_id FROM "transaction"
    WHERE type = 'transfer' ORDER BY id
"""

_COUNT_MOVEMENTS = 'SELECT COUNT(*) FROM "transaction"'

_PRE_UPGRADE_EXPENSE_CATEGORY = 1
_PRE_UPGRADE_INCOME_CATEGORY = 2
_PRE_UPGRADE_DATE = "2026-05-10"
_PRE_UPGRADE_CLEAN = (
    ("Exito", "expense", _PRE_UPGRADE_EXPENSE_CATEGORY),
    ("Mercado", "expense", _PRE_UPGRADE_EXPENSE_CATEGORY),
    ("Empresa", "income", _PRE_UPGRADE_INCOME_CATEGORY),
)


# ------------------------------------------------------ intended API (thin)


def _offered_names(world: World, *, is_income: bool) -> list[str]:
    """The categories a movement form offers — intended direction filter."""
    offered = categories.list_categories(world.session, is_income=is_income)
    return sorted(cat.name for cat in offered)


def _record_creating_category(
    world: World,
    *,
    tx_type: TxType,
    account: str,
    amount: str,
    currency: str,
    payee: str,
    category: str,
    notes: str | None,
) -> None:
    """Inline creation from the movement form — intended ``new_category``."""
    record = transactions.record_expense if tx_type == TxType.expense else transactions.record_income

    def action():
        tx = record(
            world.session,
            world.accounts[account],
            major_to_cents(amount),
            currency,
            world.today,
            payee,
            notes=notes,
            new_category=category,
        )
        _remember_movement(world, tx_type, tx)
        world.categories[category] = tx.category_id

    world.attempt(action)


def _raw_tool(tool):
    """The tool body beneath the MCP error-to-text wrapper."""
    return getattr(tool, "__wrapped__", tool)


# ------------------------------------------------------------- scratchpad


def _submitted_category(world: World, name: str | None) -> int | None:
    """The id the form submits for a chosen category, remembering the choice."""
    if name is None:
        world.attempted_category = None
        return None
    category_id = world.categories.get(name, MISSING_ID)
    world.attempted_category = (name, category_id)
    return category_id


def _remember_movement(world: World, tx_type: TxType, tx) -> None:
    if tx_type == TxType.income:
        world.last_income_id = tx.id
        return
    world.last_expense_id = tx.id
    world.expense_ids.append(tx.id)


def _last_income(world: World):
    tx_id = getattr(world, "last_income_id", None)
    if tx_id is None:
        raise AssertionError("no income was recorded earlier in the scenario")
    return transactions.get_transaction(world.session, tx_id)


def _offered(world: World) -> list[str]:
    """The offering the scenario primed, or the expense one by default.

    A scenario that never says which movement it is recording means an
    expense — the direction this suite reads into an untyped category.
    """
    primed = getattr(world, "offered_categories", None)
    if primed is not None:
        return primed
    return _offered_names(world, is_income=False)


def _refusal(world: World, what: str) -> str:
    err = world.last_error
    if err is None:
        raise AssertionError(f"{what}: the action succeeded, so the user was told nothing")
    return str(err)


def _refusal_code(world: World, what: str) -> str | None:
    _refusal(world, what)
    return getattr(world.last_error, "code", None)


# ----------------------------------------------------------------- raw SQL


def _insert_movement(
    conn,
    *,
    payee: str,
    tx_type: str,
    category_id: int | None,
    account_id: int,
    date: str,
    group_id: str | None = None,
    direction: str | None = None,
    amount: int = 100_000,
) -> None:
    conn.execute(
        sa_text(_INSERT_MOVEMENT),
        {
            "date": date,
            "payee": payee,
            "type": tx_type,
            "amount": amount,
            "account_id": account_id,
            "category_id": category_id,
            "group_id": group_id,
            "direction": direction,
            "created_at": f"{date} 12:00:00",
        },
    )


def _rows(world: World, sql: str) -> list[tuple]:
    """Read straight from the scenario's database, past the ORM."""
    world.session.commit()
    with world.engine.connect() as conn:
        return [tuple(row) for row in conn.execute(sa_text(sql)).fetchall()]


def _forcing_account_id(world: World) -> int:
    if world.accounts:
        return next(iter(world.accounts.values()))
    acc = accounts.create_account(world.session, "Bancolombia", "debit", "COP", balance=0)
    world.accounts[acc.name] = acc.id
    return acc.id


def _force_movement(
    world: World,
    *,
    payee: str,
    tx_type: str,
    category_id: int | None,
    group_id: str | None = None,
    direction: str | None = None,
) -> None:
    """Write the row with SQL, so only the stored data can refuse it (AC-17)."""
    account_id = _forcing_account_id(world)
    world.session.commit()

    def action():
        with world.engine.begin() as conn:
            _insert_movement(
                conn,
                payee=payee,
                tx_type=tx_type,
                category_id=category_id,
                account_id=account_id,
                date=world.today.isoformat(),
                group_id=group_id,
                direction=direction,
            )

    world.attempt(action)
    world.reopen_session()


def _build_pre_upgrade_database(world: World, uncategorised_type: str | None, count: int) -> None:
    """A database at the pre-feature head, seeded with old movements.

    Raw SQL rather than the models: the schema at revision
    ``_PRE_FEATURE_REVISION`` is frozen forever, while the models move with
    the feature.
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

    expected: list[tuple[str, int | None]] = []
    with engine.begin() as conn:
        conn.execute(sa_text(_SEED_ACCOUNT))
        conn.execute(sa_text(_SEED_CATEGORIES))
        for payee, tx_type, category_id in _PRE_UPGRADE_CLEAN:
            _insert_movement(
                conn,
                payee=payee,
                tx_type=tx_type,
                category_id=category_id,
                account_id=1,
                date=_PRE_UPGRADE_DATE,
            )
            expected.append((payee, category_id))
        for index in range(count):
            payee = f"Sin categoria {index + 1}"
            _insert_movement(
                conn,
                payee=payee,
                tx_type=uncategorised_type or "expense",
                category_id=None,
                account_id=1,
                date=_PRE_UPGRADE_DATE,
            )
            expected.append((payee, None))

    world.replace_engine(engine)
    world.alembic_cfg = cfg
    world.pre_upgrade_expected = expected
    world.pre_upgrade_transfers = 0


# ------------------------------------------------------------------- Given


@step(r'an (?P<direction>expense|income) category "(?P<name>[^"]+)"')
def given_typed_category(world: World, direction: str, name: str) -> None:
    cat = categories.create_category(world.session, name, is_income=direction == "income")
    world.categories[name] = cat.id


@step(
    r"a planned payment of (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3})"
    r' to "(?P<payee>[^"]+)" from "(?P<account>[^"]+)" (?P<due>' + _DUE + r")"
    r' in category "(?P<category>[^"]+)"'
)
def given_planned_payment_in_category(
    world: World,
    amount: str,
    currency: str,
    payee: str,
    account: str,
    due: str,
    category: str,
    **_,
) -> None:
    _plan(world, amount, currency, payee, account, due, category)
    world.require_clean(f"planning the payment to {payee!r}")


@step(
    r"(?P<clean>\d+) categorised movements"
    r"(?: and (?P<count>\d+) uncategorised (?P<kind>expenses?|incomes?))?"
    r" recorded before the upgrade"
)
def given_pre_upgrade_movements(world: World, clean: str, count: str | None = None, kind: str | None = None) -> None:
    if int(clean) != len(_PRE_UPGRADE_CLEAN):
        raise AssertionError(
            f"the pre-upgrade fixture holds {len(_PRE_UPGRADE_CLEAN)} categorised movements, "
            f"the scenario asks for {clean}"
        )
    uncategorised_type = None if kind is None else ("income" if kind.startswith("income") else "expense")
    _build_pre_upgrade_database(world, uncategorised_type, int(count) if count else 0)


@step(r"(?P<count>\d+) transfers recorded before the upgrade with no category")
def given_pre_upgrade_transfers(world: World, count: str) -> None:
    if world.alembic_cfg is None:
        raise AssertionError("scenario setup error: no pre-upgrade database was prepared")
    world.session.commit()
    with world.engine.begin() as conn:
        for index in range(int(count)):
            _insert_movement(
                conn,
                payee=f"Traslado {index + 1}",
                tx_type="transfer",
                category_id=None,
                account_id=1,
                date=_PRE_UPGRADE_DATE,
                group_id=f"pre-upgrade-{index + 1}",
                direction="out",
            )
    world.pre_upgrade_transfers = int(count)
    world.reopen_session()


# -------------------------------------------------------------------- When


@step(
    r"the user tries to register an expense of (?P<amount>" + _DEC + r")"
    r' (?P<currency>[A-Z]{3}) from "(?P<account>[^"]+)" paying "(?P<payee>[^"]+)"'
    r'(?: in category "(?P<category>[^"]+)"| with no category)'
)
def when_try_register_expense(
    world: World,
    amount: str,
    currency: str,
    account: str,
    payee: str,
    category: str | None = None,
) -> None:
    def action():
        tx = transactions.record_expense(
            world.session,
            world.accounts[account],
            major_to_cents(amount),
            currency,
            world.today,
            payee,
            category_id=_submitted_category(world, category),
        )
        _remember_movement(world, TxType.expense, tx)

    world.attempt(action)


@step(
    r"the user (?:registers|tries to register) an income of (?P<amount>" + _DEC + r")"
    r' (?P<currency>[A-Z]{3}) into "(?P<account>[^"]+)" from "(?P<payee>[^"]+)"'
    r'(?: in category "(?P<category>[^"]+)"| with no category)'
)
def when_register_income_with_category(
    world: World,
    amount: str,
    currency: str,
    account: str,
    payee: str,
    category: str | None = None,
) -> None:
    def action():
        tx = transactions.record_income(
            world.session,
            world.accounts[account],
            major_to_cents(amount),
            currency,
            world.today,
            payee,
            category_id=_submitted_category(world, category),
        )
        _remember_movement(world, TxType.income, tx)

    world.attempt(action)


@step(
    r"the user tries to transfer (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3})"
    r' from "(?P<src>[^"]+)" to "(?P<dst>[^"]+)" in category "(?P<category>[^"]+)"'
)
def when_try_transfer_with_category(
    world: World, amount: str, currency: str, src: str, dst: str, category: str
) -> None:
    def action():
        world.transfer_legs = transactions.transfer(
            world.session,
            world.account_id_or_missing(src),
            world.account_id_or_missing(dst),
            major_to_cents(amount),
            currency,
            world.today,
            category_id=_submitted_category(world, category),
        )

    world.attempt(action)


@step(r"the user starts recording an (?P<direction>expense|income)")
def when_start_recording(world: World, direction: str) -> None:
    world.offered_categories = None

    def action():
        world.offered_categories = _offered_names(world, is_income=direction == "income")

    world.attempt(action)


@step(
    r"the user (?:records|tries to record) an expense of (?P<amount>" + _DEC + r")"
    r' (?P<currency>[A-Z]{3}) from "(?P<account>[^"]+)" paying "(?P<payee>[^"]+)"'
    r'(?: with notes "(?P<notes>[^"]+)")?'
    r' creating the category "(?P<category>[^"]+)"'
)
def when_record_expense_creating_category(
    world: World,
    amount: str,
    currency: str,
    account: str,
    payee: str,
    category: str,
    notes: str | None = None,
) -> None:
    _record_creating_category(
        world,
        tx_type=TxType.expense,
        account=account,
        amount=amount,
        currency=currency,
        payee=payee,
        category=category,
        notes=notes,
    )


@step(
    r"the user (?:records|tries to record) an income of (?P<amount>" + _DEC + r")"
    r' (?P<currency>[A-Z]{3}) into "(?P<account>[^"]+)" from "(?P<payee>[^"]+)"'
    r'(?: with notes "(?P<notes>[^"]+)")?'
    r' creating the category "(?P<category>[^"]+)"'
)
def when_record_income_creating_category(
    world: World,
    amount: str,
    currency: str,
    account: str,
    payee: str,
    category: str,
    notes: str | None = None,
) -> None:
    _record_creating_category(
        world,
        tx_type=TxType.income,
        account=account,
        amount=amount,
        currency=currency,
        payee=payee,
        category=category,
        notes=notes,
    )


@step(
    r"the user tries to declare a repeating payment of (?P<amount>" + _DEC + r")"
    r' (?P<currency>[A-Z]{3}) to "(?P<payee>[^"]+)" from "(?P<account>[^"]+)"' + _NO_CATEGORY_DECLARATION
)
def when_declare_uncategorised_payment(world: World, payee: str, **kw) -> None:
    _declare(world, name=payee, payee=payee, tx_type=TxType.expense, end=None, category=NO_CATEGORY, **kw)


@step(
    r"the user tries to plan a payment of (?P<amount>" + _DEC + r")"
    r' (?P<currency>[A-Z]{3}) to "(?P<payee>[^"]+)" from "(?P<account>[^"]+)"'
    r" (?P<due>" + _DUE + r") with no category"
)
def when_try_plan_uncategorised(
    world: World, amount: str, currency: str, payee: str, account: str, due: str, **_
) -> None:
    _plan(world, amount, currency, payee, account, due, category=NO_CATEGORY)


@step(r'the user moves the repeating payment to "(?P<name>[^"]+)" to category "(?P<category>[^"]+)"')
def when_move_recurring_category(world: World, name: str, category: str) -> None:
    world.attempt(
        recurring.update_recurring,
        world.session,
        _item(world, name).id,
        category_id=_submitted_category(world, category),
    )


@step(
    r'the user moves the charge to "(?P<name>[^"]+)" from (?P<when>' + _WHEN + r")"
    r' to category "(?P<category>[^"]+)"'
)
def when_move_charge_category(world: World, name: str, when: str, category: str) -> None:
    tx = _linked_tx(world, name, _when(world, when))
    world.attempt(
        transactions.update_transaction,
        world.session,
        tx.id,
        category_id=_submitted_category(world, category),
    )


@step(r'the user moves the expense to category "(?P<category>[^"]+)"')
def when_move_expense_category(world: World, category: str) -> None:
    world.attempt(
        transactions.update_transaction,
        world.session,
        _last_expense(world).id,
        category_id=_submitted_category(world, category),
    )


@step(r"the user tries to clear the expense's category")
def when_try_clear_category(world: World) -> None:
    world.attempt(
        transactions.update_transaction,
        world.session,
        _last_expense(world).id,
        category_id=None,
    )


@step(r'the user archives the category "(?P<name>[^"]+)"')
def when_archive_category(world: World, name: str) -> None:
    world.attempt(categories.archive_category, world.session, world.categories[name])


@step(r'the user restores the category "(?P<name>[^"]+)"')
def when_restore_category(world: World, name: str) -> None:
    world.attempt(categories.unarchive_category, world.session, world.categories[name])


@step(
    r"the assistant tries to record an expense of (?P<amount>" + _DEC + r")"
    r' (?P<currency>[A-Z]{3}) from "(?P<account>[^"]+)" paying "(?P<payee>[^"]+)"'
    r" with no category"
)
def when_assistant_records_uncategorised_expense(
    world: World, amount: str, currency: str, account: str, payee: str
) -> None:
    def action():
        from quaestor.mcp.tools import core as mcp_core

        _raw_tool(mcp_core.record_expense)(
            world.session,
            mcp_core.RecordExpenseInput(
                payee=payee,
                amount=major_to_cents(amount),
                account=account,
                currency=currency,
                date=world.today,
            ),
        )

    world.attempt(action)


@step(
    r"the assistant tries to plan a payment of (?P<amount>" + _DEC + r")"
    r' (?P<currency>[A-Z]{3}) to "(?P<payee>[^"]+)" from "(?P<account>[^"]+)"'
    r" (?P<due>" + _DUE + r") with no category"
)
def when_assistant_plans_uncategorised(
    world: World, amount: str, currency: str, payee: str, account: str, due: str, **_
) -> None:
    from .planned_payments import _due_date

    def action():
        from quaestor.mcp.tools import temporal

        _raw_tool(temporal.plan_payment)(
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


@step(
    r"the assistant tries to declare a repeating payment of (?P<amount>" + _DEC + r")"
    r' (?P<currency>[A-Z]{3}) to "(?P<payee>[^"]+)" from "(?P<account>[^"]+)"' + _NO_CATEGORY_DECLARATION
)
def when_assistant_declares_uncategorised(
    world: World,
    amount: str,
    currency: str,
    payee: str,
    account: str,
    count: str,
    unit: str,
    start: str,
    mode: str,
) -> None:
    def action():
        from quaestor.mcp.tools import temporal

        _raw_tool(temporal.create_recurring)(
            world.session,
            temporal.CreateRecurringInput(
                name=payee,
                payee=payee,
                type="expense",
                mode="auto" if mode == "paying itself" else "manual",
                amount=major_to_cents(amount),
                account=account,
                currency=currency,
                interval_unit=unit,
                interval_count=int(count),
                start_date=_when(world, start),
            ),
        )

    world.attempt(action)


@step(r"money (?P<direction>going out|coming in) with no category is forced into the records, bypassing the app")
def when_force_uncategorised_movement(world: World, direction: str) -> None:
    tx_type = "income" if direction == "coming in" else "expense"
    _force_movement(world, payee="Forzado", tx_type=tx_type, category_id=None)


@step(
    r"a transfer (?:carrying category \"(?P<category>[^\"]+)\"|with no category)"
    r" is forced into the records, bypassing the app"
)
def when_force_transfer(world: World, category: str | None = None) -> None:
    _force_movement(
        world,
        payee="Traslado forzado",
        tx_type="transfer",
        category_id=world.categories.get(category) if category else None,
        group_id="forced-transfer",
        direction="out",
    )


@step(r"the upgrade is attempted")
def when_upgrade_attempted(world: World) -> None:
    from alembic import command as alembic_command

    if world.alembic_cfg is None:
        raise AssertionError("scenario setup error: no pre-upgrade database was prepared")
    world.attempt(alembic_command.upgrade, world.alembic_cfg, "head")
    world.reopen_session()


# -------------------------------------------------------------------- Then


@step(r'viewing the expense shows category "(?P<category>[^"]+)"')
def then_expense_category(world: World, category: str) -> None:
    world.require_clean("the expense should carry a category")
    tx = _last_expense(world)
    expected = world.categories.get(category)
    assert expected is not None, f"the scenario never created a category named {category!r}"
    assert tx.category_id == expected, (
        f"expected category {category!r} (id {expected}), got category_id={tx.category_id}"
    )


@step(r'viewing the income shows category "(?P<category>[^"]+)"')
def then_income_category(world: World, category: str) -> None:
    world.require_clean("the income should carry a category")
    tx = _last_income(world)
    expected = world.categories.get(category)
    assert expected is not None, f"the scenario never created a category named {category!r}"
    assert tx.category_id == expected, (
        f"expected category {category!r} (id {expected}), got category_id={tx.category_id}"
    )


@step(r'viewing the expense shows payee "(?P<payee>[^"]+)" and notes "(?P<notes>[^"]*)"')
def then_expense_payee_and_notes(world: World, payee: str, notes: str) -> None:
    world.require_clean("what was already typed should have survived")
    tx = _last_expense(world)
    assert tx.payee == payee, f"expected payee {payee!r}, got {tx.payee!r}"
    written = tx.notes or ""
    assert written == notes, f"expected notes {notes!r}, got {tx.notes!r}"


@step(r"both sides of the transfer show no category")
def then_transfer_sides_uncategorised(world: World) -> None:
    world.require_clean("the transfer should have succeeded")
    assert world.transfer_legs is not None, "no transfer was recorded"
    categorised = [leg.id for leg in world.transfer_legs if leg.category_id is not None]
    assert not categorised, f"transfer legs {categorised} carry a category; a transfer carries none"


@step(r'the categories offered are "(?P<first>[^"]+)"(?: and "(?P<second>[^"]+)")?')
def then_categories_offered_are(world: World, first: str, second: str | None = None) -> None:
    world.require_clean("the form should have been able to offer its categories")
    expected = sorted(name for name in (first, second) if name)
    offered = _offered(world)
    assert offered == expected, f"expected the categories {expected}, got {offered}"


@step(r'the categories offered(?: for an (?P<direction>expense|income))? do not include "(?P<name>[^"]+)"')
def then_categories_offered_omit(world: World, name: str, direction: str | None = None) -> None:
    if direction is None:
        world.require_clean("the form should have been able to offer its categories")
        offered = _offered(world)
    else:
        offered = _offered_names(world, is_income=direction == "income")
    assert name not in offered, f"{name!r} is still offered: {offered}"


@step(
    r"the charge (?:to|from) \"(?P<name>[^\"]+)\" from (?P<when>" + _WHEN + r")"
    r' shows category "(?P<category>[^"]+)"'
)
def then_charge_category(world: World, name: str, when: str, category: str) -> None:
    world.require_clean(f"the charge of {name!r} should carry a category")
    tx = _linked_tx(world, name, _when(world, when))
    expected = world.categories.get(category)
    assert expected is not None, f"the scenario never created a category named {category!r}"
    assert tx.category_id == expected, (
        f"the charge of {name!r} is in category_id={tx.category_id}, expected {category!r} (id {expected})"
    )


@step(r'the repeating payment to "(?P<name>[^"]+)" is in category "(?P<category>[^"]+)"')
def then_recurring_category(world: World, name: str, category: str) -> None:
    world.require_clean(f"re-classifying {name!r}")
    item = _item(world, name)
    expected = world.categories.get(category)
    assert expected is not None, f"the scenario never created a category named {category!r}"
    assert item.category_id == expected, (
        f"{name!r} is in category_id={item.category_id}, expected {category!r} (id {expected})"
    )


@step(r'viewing the planned payment to "(?P<payee>[^"]+)" shows category "(?P<category>[^"]+)"')
def then_planned_payment_category(world: World, payee: str, category: str) -> None:
    world.require_clean(f"the planned payment to {payee!r} should carry a category")
    tx = _payment(world, payee)
    expected = world.categories.get(category)
    assert expected is not None, f"the scenario never created a category named {category!r}"
    assert tx.category_id == expected, (
        f"the payment to {payee!r} is in category_id={tx.category_id}, expected {category!r} (id {expected})"
    )


@step(r"the edit is rejected")
def then_edit_rejected(world: World) -> None:
    world.consume_rejection((QuaestorError,), "the invalid edit")


@step(r"the user is told the category is missing")
def then_told_category_missing(world: World) -> None:
    message = _refusal(world, "recording without a category").lower()
    assert "category" in message and ("missing" in message or "required" in message), (
        f"the refusal does not say the category is missing: {message}"
    )


@step(r"the user is told the category does not match the direction of the money")
def then_told_wrong_direction(world: World) -> None:
    message = _refusal(world, "recording under a category of the wrong direction").lower()
    named = ("direction", "income", "expense", "spending")
    assert "category" in message and any(word in message for word in named), (
        f"the refusal does not say the category is of the wrong direction: {message}"
    )


@step(r"the user is told which category was at fault")
def then_told_which_category(world: World) -> None:
    message = _refusal(world, "recording under an unknown or archived category")
    attempted = getattr(world, "attempted_category", None)
    assert attempted is not None, "scenario setup error: no category was submitted"
    name, category_id = attempted
    assert name in message or str(category_id) in message, (
        f"the refusal does not say which category was at fault (expected {name!r} or id {category_id}): {message}"
    )


@step(r"the user is told that category already exists")
def then_told_category_exists(world: World) -> None:
    code = _refusal_code(world, "creating a category whose name is taken")
    assert code == "category_duplicate_active", (
        f"the refusal does not carry the duplicate-active category code: got {code!r} (error: {world.last_error!r})"
    )


@step(r'the user is offered to restore the archived category "(?P<name>[^"]+)"')
def then_offered_to_restore(world: World, name: str) -> None:
    code = _refusal_code(world, "creating a category that matches an archived one")
    assert code == "category_duplicate_archived", (
        f"the refusal does not carry the duplicate-archived category code: got {code!r} (error: {world.last_error!r})"
    )
    data = getattr(world.last_error, "data", {})
    assert data.get("name") == name, (
        f"the refusal does not name the archived category being offered for restore: "
        f"expected {name!r}, got {data.get('name')!r} (error: {world.last_error!r})"
    )


@step(r"the records refuse to hold it")
def then_records_refuse(world: World) -> None:
    world.consume_rejection((DatabaseError,), "forcing the movement into the records")


@step(r"the records hold it")
def then_records_hold(world: World) -> None:
    world.require_clean("an uncategorised transfer is a valid row")
    stored = _rows(world, _COUNT_MOVEMENTS)[0][0]
    assert stored == 1, f"expected the forced transfer to be stored, found {stored} movement(s)"


@step(r"the upgrade is refused")
def then_upgrade_refused(world: World) -> None:
    world.consume_rejection((Exception,), "the upgrade over uncategorised movements")


@step(r"the refusal says (?P<count>\d+) (?P<kind>expenses?|incomes?) (?:is|are) still uncategorised")
def then_refusal_counts(world: World, count: str, kind: str) -> None:
    message = _refusal(world, "the upgrade over uncategorised movements").lower()
    singular = kind.rstrip("s")
    assert count in message and singular in message, (
        f"the refusal does not say {count} {kind} are still uncategorised: {message}"
    )


@step(r"every transfer still shows no category")
def then_transfers_still_uncategorised(world: World) -> None:
    world.require_clean("the upgrade should have completed")
    rows = _rows(world, _SELECT_TRANSFERS)
    expected = getattr(world, "pre_upgrade_transfers", 0)
    assert len(rows) == expected, f"expected {expected} transfer(s) to survive the upgrade, got {len(rows)}"
    categorised = [payee for payee, category_id in rows if category_id is not None]
    assert not categorised, f"the upgrade gave a category to transfers {categorised}"


@step(r"every expense and income still shows the category it had")
def then_categories_preserved(world: World) -> None:
    world.require_clean("the upgrade should have completed")
    expected = getattr(world, "pre_upgrade_expected", None)
    assert expected is not None, "scenario setup error: no pre-upgrade movements were seeded"
    rows = _rows(world, _SELECT_MOVEMENTS)
    assert rows == expected, f"the upgrade changed what movements are filed under: expected {expected}, got {rows}"


@step(r"no expense or income is left uncategorised")
def then_nothing_uncategorised(world: World) -> None:
    world.require_clean("the upgrade should have completed")
    rows = _rows(world, _SELECT_UNCATEGORISED)
    assert not rows, f"movements survived the upgrade with no category: {rows}"
