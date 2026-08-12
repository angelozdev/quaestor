"""Revision 0017 restates two stored prices, and only those two.

Hevy Pro and Smart Fit were written as the conversion of the day they were
created, because until ADR-0053 an obligation had to be stated in its account's
currency. The revision carries the merchant's prices in its body rather than
converting, and matches on name, amount and currency together so that a database
holding anything else is left alone.

The way back is the half worth the file. It restores the two prices and does not
touch the mode: production already holds both waiting for approval, so a
downgrade that wrote `auto` would switch automatic charging *on* — money moving
by itself as the result of a rollback.
"""

import sqlalchemy as sa
from alembic import command as alembic_command
from tests.support.migrations import config_for, engine_at_revision, insert_account, insert_category

_INSERT = (
    "INSERT INTO recurring_item "
    "(id, name, payee, type, mode, amount, currency, account_id, category_id, "
    "interval_unit, interval_count, start_date, active) "
    "VALUES (:id, :name, :name, 'expense', :mode, :amount, :currency, 1, 1, "
    "'month', 1, '2026-06-01', 1)"
)


def _seeded(rows):
    """A database at 0016 holding exactly `rows`, ready to be migrated."""
    engine = engine_at_revision("0016")
    with engine.begin() as conn:
        insert_account(conn, 1, "DolarApp")
        insert_category(conn, 1, "Suscripciones")
        for row in rows:
            conn.execute(sa.text(_INSERT), row)
    return engine


def _prices(engine):
    with engine.connect() as conn:
        return {
            name: (amount, currency, mode)
            for name, amount, currency, mode in conn.execute(
                sa.text("SELECT name, amount, currency, mode FROM recurring_item")
            )
        }


_HEVY = {"id": 1, "name": "Hevy Pro", "mode": "manual", "amount": 3022, "currency": "USD"}
_SMART = {"id": 2, "name": "Smart Fit", "mode": "manual", "amount": 3720, "currency": "USD"}


def test_the_two_obligations_come_out_priced_the_way_the_merchant_charges():
    engine = _seeded([_HEVY, _SMART])

    alembic_command.upgrade(config_for(engine), "0017")

    prices = _prices(engine)
    assert prices["Hevy Pro"] == (9990000, "COP", "manual")
    assert prices["Smart Fit"] == (12000000, "COP", "manual")


def test_an_obligation_that_paid_itself_comes_out_waiting_for_approval():
    """A peso price on a dollar account may not post itself (ADR-0053, AC-2)."""
    engine = _seeded([{**_HEVY, "mode": "auto"}])

    alembic_command.upgrade(config_for(engine), "0017")

    assert _prices(engine)["Hevy Pro"] == (9990000, "COP", "manual")


def test_a_row_the_revision_does_not_name_is_left_exactly_as_it_was():
    """`Smart Fit anual` is a real neighbouring row and must not be caught."""
    anual = {"id": 3, "name": "Smart Fit anual", "mode": "manual", "amount": 2651, "currency": "USD"}
    engine = _seeded([_SMART, anual])

    alembic_command.upgrade(config_for(engine), "0017")

    assert _prices(engine)["Smart Fit anual"] == (2651, "USD", "manual")


def test_a_row_whose_price_has_since_been_changed_by_hand_is_left_alone():
    """Matching on the amount too is what makes a stale carried figure safe."""
    engine = _seeded([{**_HEVY, "amount": 3500}])

    alembic_command.upgrade(config_for(engine), "0017")

    assert _prices(engine)["Hevy Pro"] == (3500, "USD", "manual")


def test_the_way_back_restores_the_two_prices():
    engine = _seeded([_HEVY, _SMART])
    cfg = config_for(engine)
    alembic_command.upgrade(cfg, "0017")

    alembic_command.downgrade(cfg, "0016")

    prices = _prices(engine)
    assert (prices["Hevy Pro"][0], prices["Hevy Pro"][1]) == (3022, "USD")
    assert (prices["Smart Fit"][0], prices["Smart Fit"][1]) == (3720, "USD")


def test_the_way_back_never_switches_automatic_charging_on():
    engine = _seeded([_HEVY, _SMART])
    cfg = config_for(engine)
    alembic_command.upgrade(cfg, "0017")

    alembic_command.downgrade(cfg, "0016")

    assert [row[2] for row in _prices(engine).values()] == ["manual", "manual"]
