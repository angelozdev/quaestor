"""Revision 0015 is destructive, and it refuses rather than guess.

It withdraws `target-by-date` from the fund: two columns and one enum value.
Saying "put aside an amount by a date" is a meta's job now, and a fund that
still held that rule would be a decision about what the owner was saving for
with nowhere left to say it. So the revision counts them first and stops.

That guard is the only thing between the owner and a silent loss, and until
this file it had never fired — it ran against an empty database every time,
where a count of zero proves nothing about a count of one.

`_rebuild_enum` is unreachable from here. It returns immediately on SQLite,
which is what `engine_at_revision` gives, so the four `ALTER TYPE` / `ALTER
COLUMN` statements Postgres needs are exercised by nothing in this file. What
is pinned is the refusal, the column drops, and the reversal.
"""

import pytest
import sqlalchemy as sa
from alembic import command as alembic_command
from tests.support.migrations import config_for, engine_at_revision, insert_category

WITHDRAWN = ("target_amount", "target_month")

_INSERT_FUND = (
    "INSERT INTO fund (id, category_id, rule, start_month, accumulates, amount, window_months, "
    "target_amount, target_month) "
    "VALUES (:id, :category_id, :rule, '2026-06', true, :amount, :window_months, "
    ":target_amount, :target_month)"
)

DATED = {
    "rule": "target_by_date",
    "amount": None,
    "window_months": None,
    "target_amount": 5000000,
    "target_month": "2026-12",
}
FIXED = {"rule": "fixed", "amount": 30000000, "window_months": None, "target_amount": None, "target_month": None}
AVERAGE = {"rule": "average", "amount": None, "window_months": 3, "target_amount": None, "target_month": None}
FROM_RECURRING = {
    "rule": "from_recurring",
    "amount": None,
    "window_months": None,
    "target_amount": None,
    "target_month": None,
}


def _columns(engine, table):
    return {column["name"] for column in sa.inspect(engine).get_columns(table)}


def _seed_funds(engine, *shapes):
    with engine.begin() as conn:
        for index, shape in enumerate(shapes, start=1):
            insert_category(conn, index, f"Categoria {index}")
            conn.execute(sa.text(_INSERT_FUND), {"id": index, "category_id": index, **shape})


def _funds(engine):
    with engine.connect() as conn:
        return conn.execute(sa.text("SELECT id, rule, amount, window_months FROM fund ORDER BY id")).fetchall()


def test_the_upgrade_withdraws_the_two_columns_the_dated_rule_needed():
    engine = engine_at_revision("0014")
    assert set(WITHDRAWN) <= _columns(engine, "fund")
    alembic_command.upgrade(config_for(engine), "0015")
    assert not set(WITHDRAWN) & _columns(engine, "fund")


def test_a_fund_on_any_other_rule_keeps_what_it_held():
    engine = engine_at_revision("0014")
    _seed_funds(engine, FIXED, AVERAGE, FROM_RECURRING)
    alembic_command.upgrade(config_for(engine), "0015")
    assert _funds(engine) == [
        (1, "fixed", 30000000, None),
        (2, "average", None, 3),
        (3, "from_recurring", None, None),
    ]


def test_the_upgrade_refuses_while_a_fund_still_saves_toward_a_date():
    engine = engine_at_revision("0014")
    _seed_funds(engine, DATED)
    with pytest.raises(RuntimeError, match="1 fund\\(s\\) still use it"):
        alembic_command.upgrade(config_for(engine), "0015")


def test_the_refusal_counts_every_dated_fund_it_found():
    engine = engine_at_revision("0014")
    _seed_funds(engine, DATED, FIXED, DATED)
    with pytest.raises(RuntimeError, match="2 fund\\(s\\) still use it"):
        alembic_command.upgrade(config_for(engine), "0015")


def test_the_refusal_leaves_the_columns_and_the_fund_alone():
    """A stopped migration must lose nothing, or it is not a guard.

    The count runs before the first `drop_column` precisely so the database is
    still whole when the exception leaves — the owner turns his dated funds
    into metas and runs it again.
    """
    engine = engine_at_revision("0014")
    _seed_funds(engine, DATED)
    with pytest.raises(RuntimeError, match="refusing to withdraw the dated rule"):
        alembic_command.upgrade(config_for(engine), "0015")
    assert set(WITHDRAWN) <= _columns(engine, "fund")
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT target_amount, target_month FROM fund WHERE id = 1")).one() == (
            5000000,
            "2026-12",
        )


def test_the_downgrade_puts_the_columns_back_empty():
    """The way back to data is the dump, not the downgrade.

    Nothing is converted on the way out because production held no dated fund,
    so there is nothing for the reversal to restore into the columns it
    recreates.
    """
    engine = engine_at_revision("0014")
    _seed_funds(engine, FIXED)
    cfg = config_for(engine)
    alembic_command.upgrade(cfg, "0015")
    alembic_command.downgrade(cfg, "0014")
    assert set(WITHDRAWN) <= _columns(engine, "fund")
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT target_amount, target_month FROM fund WHERE id = 1")).one() == (None, None)
