"""Revision 0020 moves rows, and the way back has to move them back (ADR-0057).

The upgrade is rehearsed against a restored copy of production before it runs
(CHARTER §7); the downgrade is the half nobody rehearses, because by the time it
is wanted the owner is already in trouble. So it is asserted here instead: what
it rebuilds, what it drops, and the one shape it refuses rather than guess at.
"""

import pytest
import sqlalchemy as sa
from alembic import command as alembic_command
from tests.support.migrations import config_for, engine_at_revision

_A_CATEGORY = (
    "INSERT INTO category (id, name, is_income, exclude_from_budget, exclude_from_totals, archived) "
    "VALUES (:id, :name, false, false, false, false)"
)
_AN_ACCOUNT = (
    "INSERT INTO account (id, name, type, currency, balance, archived) VALUES (1, 'Banco', 'debit', 'COP', 0, false)"
)
_A_CHARGE = (
    "INSERT INTO recurring_item (id, name, payee, type, mode, amount, currency, category_id, account_id, "
    "interval_unit, interval_count, start_date, active) "
    "VALUES (:id, :name, :name, 'expense', 'auto', :amount, 'COP', :category_id, 1, 'year', 1, '2027-07-05', true)"
)
_A_CHARGE_FUND = (
    "INSERT INTO fund (id, category_id, recurring_id, rule, start_month, accumulates) "
    "VALUES (:id, :category_id, :recurring_id, 'from_recurring', :start_month, true)"
)
_AN_AVERAGE_FUND = (
    "INSERT INTO fund (id, category_id, recurring_id, rule, start_month, accumulates, window_months) "
    "VALUES (:id, :category_id, NULL, 'average', '2026-08', true, 3)"
)


@pytest.fixture
def engine():
    """A book already migrated to 0020, with 🛡️ Carro carrying two charge funds."""
    made = engine_at_revision("0020")
    with made.begin() as conn:
        conn.execute(sa.text(_A_CATEGORY), {"id": 1, "name": "Carro"})
        conn.execute(sa.text(_A_CATEGORY), {"id": 2, "name": "Mercado"})
        conn.execute(sa.text(_AN_ACCOUNT))
        for charge_id, name, amount in ((1, "Seguro del Carro", 700_000_000), (2, "SOAT carro", 44_730_000)):
            conn.execute(sa.text(_A_CHARGE), {"id": charge_id, "name": name, "amount": amount, "category_id": 1})
    return made


def _funds(engine):
    with engine.connect() as conn:
        return (
            conn.execute(sa.text("SELECT id, category_id, recurring_id, rule, start_month FROM fund ORDER BY id"))
            .mappings()
            .all()
        )


def test_the_way_back_rejoins_the_charge_funds_into_the_one_they_came_from(engine):
    """Two funds on 🛡️ Carro become the single category fund 0020 split.

    The month they started in is the one thing that has to survive the round
    trip: a fund stores no balance (ADR-0043), so where it started is the whole
    of what it remembers.
    """
    with engine.begin() as conn:
        for fund_id, recurring_id in ((1, 1), (2, 2)):
            conn.execute(
                sa.text(_A_CHARGE_FUND),
                {"id": fund_id, "category_id": 1, "recurring_id": recurring_id, "start_month": "2026-08"},
            )

    alembic_command.downgrade(config_for(engine), "0019")

    remaining = _funds(engine)
    assert len(remaining) == 1
    assert remaining[0]["category_id"] == 1
    assert remaining[0]["recurring_id"] is None
    assert remaining[0]["start_month"] == "2026-08"


def test_a_fund_that_never_hung_off_a_charge_is_left_alone(engine):
    """The four `average` funds are not this revision's business, either way."""
    with engine.begin() as conn:
        conn.execute(sa.text(_AN_AVERAGE_FUND), {"id": 1, "category_id": 2})
        conn.execute(
            sa.text(_A_CHARGE_FUND),
            {"id": 2, "category_id": 1, "recurring_id": 1, "start_month": "2026-08"},
        )

    alembic_command.downgrade(config_for(engine), "0019")

    by_rule = {row["rule"]: row for row in _funds(engine)}
    assert by_rule["average"]["category_id"] == 2
    assert by_rule["average"]["start_month"] == "2026-08"


def test_charge_funds_the_owner_has_since_pulled_apart_are_refused_rather_than_guessed_at(engine):
    """Two start months mean there is no single fund they came from.

    Rejoining them would have to pick one and quietly throw the other away.
    The revision stops instead, which leaves the book exactly as it was.
    """
    with engine.begin() as conn:
        conn.execute(
            sa.text(_A_CHARGE_FUND),
            {"id": 1, "category_id": 1, "recurring_id": 1, "start_month": "2026-08"},
        )
        conn.execute(
            sa.text(_A_CHARGE_FUND),
            {"id": 2, "category_id": 1, "recurring_id": 2, "start_month": "2026-11"},
        )

    with pytest.raises(Exception, match="cannot be rejoined"):
        alembic_command.downgrade(config_for(engine), "0019")

    assert [row["id"] for row in _funds(engine)] == [1, 2]


def test_a_book_with_no_charge_fund_downgrades_to_nothing_at_all(engine):
    """The ordinary case for anyone who never marked a charge."""
    alembic_command.downgrade(config_for(engine), "0019")

    assert _funds(engine) == []
