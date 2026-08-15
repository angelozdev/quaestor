"""Revision 0019 opens one door and leaves the other shut (ADR-0057).

The interesting half is not the new column — it is that `uq_fund_category`
survives as a *partial* index. ADR-0043 argued a category may carry one fund
because two would be two ways to lower the same headline, and that argument
still holds for the rules that cover a whole category. It does not hold for two
funds tied to different charges, and `WHERE recurring_id IS NULL` is exactly
that distinction written into the schema.

So these tests come in a pair: the door that opens, and the door that stays
shut. A revision that dropped the constraint outright would pass the first and
fail the second.
"""

import pytest
import sqlalchemy as sa
from alembic import command as alembic_command
from tests.support.migrations import config_for, engine_at_revision

_A_CATEGORY = (
    "INSERT INTO category (id, name, is_income, exclude_from_budget, exclude_from_totals, archived) "
    "VALUES (1, 'Carro', false, false, false, false)"
)
_AN_ACCOUNT = (
    "INSERT INTO account (id, name, type, currency, balance, archived) VALUES (1, 'Banco', 'debit', 'COP', 0, false)"
)
_A_CHARGE = (
    "INSERT INTO recurring_item (id, name, payee, type, mode, amount, currency, category_id, account_id, "
    "interval_unit, interval_count, start_date, active) "
    "VALUES (:id, :name, :name, 'expense', 'auto', 100, 'COP', 1, 1, 'year', 1, '2027-07-05', true)"
)
_A_CHARGE_FUND = (
    "INSERT INTO fund (id, category_id, recurring_id, rule, start_month, accumulates) "
    "VALUES (:id, 1, :recurring_id, 'from-recurring', '2026-08', true)"
)
_A_CATEGORY_FUND = (
    "INSERT INTO fund (id, category_id, recurring_id, rule, start_month, accumulates, amount) "
    "VALUES (:id, 1, NULL, 'fixed', '2026-08', true, 10000)"
)


@pytest.fixture
def engine():
    made = engine_at_revision("0019")
    with made.begin() as conn:
        conn.execute(sa.text(_A_CATEGORY))
        conn.execute(sa.text(_AN_ACCOUNT))
        for recurring_id, name in ((1, "Seguro"), (2, "SOAT")):
            conn.execute(sa.text(_A_CHARGE), {"id": recurring_id, "name": name})
    return made


def test_the_fund_table_gains_the_charge_it_fills_for(engine):
    columns = {column["name"] for column in sa.inspect(engine).get_columns("fund")}
    assert "recurring_id" in columns


def test_two_charges_in_one_category_may_each_carry_a_fund(engine):
    """The door this revision opens: 🛡️ Auto Insurance holds Seguro and SOAT."""
    with engine.begin() as conn:
        for fund_id, recurring_id in ((1, 1), (2, 2)):
            conn.execute(sa.text(_A_CHARGE_FUND), {"id": fund_id, "recurring_id": recurring_id})
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT count(*) FROM fund")).scalar() == 2


def test_a_category_still_cannot_carry_two_funds_of_its_own(engine):
    """The door that stays shut: ADR-0043's argument, still enforced."""
    with engine.begin() as conn:
        conn.execute(sa.text(_A_CATEGORY_FUND), {"id": 1})
    with pytest.raises(sa.exc.IntegrityError), engine.begin() as conn:
        conn.execute(sa.text(_A_CATEGORY_FUND), {"id": 2})


def test_one_charge_cannot_carry_two_funds(engine):
    with engine.begin() as conn:
        conn.execute(sa.text(_A_CHARGE_FUND), {"id": 1, "recurring_id": 1})
    with pytest.raises(sa.exc.IntegrityError), engine.begin() as conn:
        conn.execute(sa.text(_A_CHARGE_FUND), {"id": 2, "recurring_id": 1})


def test_the_downgrade_drops_the_charge_funds_and_keeps_the_category_one(engine):
    """The honest inverse: a charge fund's rule has nowhere to live in the old shape.

    Nothing but the rule is lost — a fund stores no balance (ADR-0043) — and
    leaving them behind would break the whole-table uniqueness the old
    constraint asserts.
    """
    with engine.begin() as conn:
        conn.execute(sa.text(_A_CHARGE_FUND), {"id": 1, "recurring_id": 1})
        conn.execute(sa.text(_A_CHARGE_FUND), {"id": 2, "recurring_id": 2})
        conn.execute(sa.text(_A_CATEGORY_FUND), {"id": 3})

    alembic_command.downgrade(config_for(engine), "0018")

    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT id FROM fund")).scalars().all() == [3]
    assert "recurring_id" not in {column["name"] for column in sa.inspect(engine).get_columns("fund")}
