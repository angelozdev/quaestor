"""Revision 0011 is additive, and reversible.

The fund table arrives on its own: goals, envelopes and `transaction.goal_id`
are still standing after it, because the destructive revision that removes them
is a later one and runs behind a human gate (charter §7, ADR-0030).
"""

import sqlalchemy as sa
from alembic import command as alembic_command
from quaestor.domain.models import Fund
from tests.support.migrations import config_for, engine_at_revision

SURVIVORS = ("goal", "goal_contribution", "budget")


def _columns(engine, table):
    return {column["name"] for column in sa.inspect(engine).get_columns(table)}


def test_the_upgrade_creates_the_fund_table():
    engine = engine_at_revision("0010")
    assert "fund" not in sa.inspect(engine).get_table_names()
    alembic_command.upgrade(config_for(engine), "0011")
    assert "fund" in sa.inspect(engine).get_table_names()


def test_the_fund_table_carries_the_columns_the_model_declares():
    """Every column the model declares exists at 0011.

    Equality, not a subset, until feature 009 withdrew `target-by-date`: the
    schema still carries `target_amount` and `target_month` at this revision
    and loses them at 0015, so between the two the model is the smaller side.
    """
    engine = engine_at_revision("0011")
    assert set(Fund.model_fields) <= _columns(engine, "fund")


def test_a_category_cannot_carry_two_funds():
    engine = engine_at_revision("0011")
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO category (id, name, is_income, exclude_from_budget, "
                "exclude_from_totals, archived) VALUES (1, 'Seguro', false, false, false, false)"
            )
        )
        for fund_id in (1, 2):
            statement = sa.text(
                "INSERT INTO fund (id, category_id, rule, start_month, accumulates, amount) "
                "VALUES (:id, 1, 'fixed', '2026-11', true, 10000)"
            )
            if fund_id == 1:
                conn.execute(statement, {"id": fund_id})
                continue
            try:
                conn.execute(statement, {"id": fund_id})
            except sa.exc.IntegrityError:
                return
    raise AssertionError("the records accepted a second fund on one category")


def test_the_upgrade_leaves_goals_and_envelopes_standing():
    engine = engine_at_revision("0011")
    tables = sa.inspect(engine).get_table_names()
    for table in SURVIVORS:
        assert table in tables
    assert "goal_id" in _columns(engine, "transaction")


def test_the_downgrade_removes_only_what_the_revision_created():
    engine = engine_at_revision("0011")
    alembic_command.downgrade(config_for(engine), "0010")
    tables = sa.inspect(engine).get_table_names()
    assert "fund" not in tables
    for table in SURVIVORS:
        assert table in tables
