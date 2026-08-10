"""Revision 0014 is additive, and reversible.

One nullable column, and the whole of AC-15 rests on it: cancelling a meta
releases what it held back into the money available, in the month it was
cancelled and in no other. Every other thing a meta reports is folded forward
from its start month; "when did this stop" is the one fact only the act knows.

Nullable is the load-bearing half. A meta that was never cancelled must name no
month — a NOT NULL column with a default would have every meta already standing
claim a cancellation that never happened, and hand its money back twice.
"""

import sqlalchemy as sa
from alembic import command as alembic_command
from quaestor.domain.models import Meta
from tests.support.migrations import config_for, engine_at_revision, insert_meta


def _columns(engine, table):
    return {column["name"] for column in sa.inspect(engine).get_columns(table)}


def test_the_upgrade_adds_the_month_a_cancellation_freed():
    engine = engine_at_revision("0013")
    assert "cancelled_month" not in _columns(engine, "meta")
    alembic_command.upgrade(config_for(engine), "0014")
    assert "cancelled_month" in _columns(engine, "meta")


def test_the_meta_table_carries_every_column_the_model_declares():
    """0014 is where the model and the schema finally agree.

    `Meta.cancelled_month` was found in Phase 2, after 0013 shipped, so between
    the two revisions the model is the larger side and this equality is the
    first point it holds.
    """
    engine = engine_at_revision("0014")
    assert set(Meta.model_fields) <= _columns(engine, "meta")


def test_a_meta_that_was_never_cancelled_names_no_month():
    engine = engine_at_revision("0013")
    with engine.begin() as conn:
        insert_meta(conn, 1, "Televisor")
    alembic_command.upgrade(config_for(engine), "0014")
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT cancelled_month FROM meta WHERE id = 1")).scalar_one() is None


def test_a_cancellation_can_say_which_month_it_freed():
    engine = engine_at_revision("0014")
    with engine.begin() as conn:
        insert_meta(conn, 1, "Televisor", archived=True)
        conn.execute(sa.text("UPDATE meta SET cancelled_month = '2026-10' WHERE id = 1"))
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT cancelled_month FROM meta WHERE id = 1")).scalar_one() == "2026-10"


def test_the_downgrade_removes_the_column_and_leaves_the_meta_standing():
    engine = engine_at_revision("0013")
    with engine.begin() as conn:
        insert_meta(conn, 1, "Televisor")
    cfg = config_for(engine)
    alembic_command.upgrade(cfg, "0014")
    alembic_command.downgrade(cfg, "0013")
    assert "cancelled_month" not in _columns(engine, "meta")
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT name FROM meta WHERE id = 1")).scalar_one() == "Televisor"
