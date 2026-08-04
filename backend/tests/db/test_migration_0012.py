"""Revision 0012 removes goals and envelopes, and refuses to undo a fact.

The revision is destructive in both senses the runbook names: it drops three
tables and a column, and its `downgrade` brings the schema back empty. Both
directions are pinned here, and so is the one case where it must refuse —
a proposal that was confirmed moved real money.
"""

import pytest
import sqlalchemy as sa
from alembic import command as alembic_command
from tests.support.migrations import (
    config_for,
    engine_at_revision,
    insert_account,
    insert_category,
)

GONE = ("goal", "goal_contribution", "budget")

_INSERT_GOAL = (
    "INSERT INTO goal (id, name, target_amount, deadline, monthly_amount, savings_account_id, status) "
    "VALUES (1, 'Korea', 1000000000, '2026-08-31', 300000000, 1, 'active')"
)

_INSERT_PROPOSAL = (
    'INSERT INTO "transaction" '
    "(id, date, payee, type, status, amount, currency, account_id, category_id, goal_id, "
    "transfer_group_id, transfer_direction, source, created_at) "
    "VALUES (:id, '2026-06-30', :payee, 'transfer', :status, 300000000, 'COP', 1, NULL, 1, "
    ":grp, 'out', 'manual', '2026-06-01 00:00:00')"
)

_INSERT_MOVEMENT = (
    'INSERT INTO "transaction" '
    "(id, date, payee, type, status, amount, currency, account_id, category_id, "
    "transfer_group_id, transfer_direction, source, created_at) "
    "VALUES (:id, '2026-06-15', :payee, :type, 'posted', 5000000, 'COP', 1, :category_id, "
    ":grp, :direction, 'manual', '2026-06-01 00:00:00')"
)


def _columns(engine, table):
    return {column["name"] for column in sa.inspect(engine).get_columns(table)}


def _movements(engine):
    with engine.connect() as conn:
        return conn.execute(sa.text('SELECT payee, type, category_id FROM "transaction" ORDER BY id')).fetchall()


def _seed(engine, *, proposal_statuses=("skipped", "planned", "planned"), with_movements=False):
    with engine.begin() as conn:
        insert_account(conn, 1, "Ahorros")
        insert_category(conn, 1, "Comida")
        insert_category(conn, 2, "Salario", is_income=True)
        conn.execute(sa.text(_INSERT_GOAL))
        for index, status in enumerate(proposal_statuses, start=1):
            conn.execute(
                sa.text(_INSERT_PROPOSAL),
                {"id": index, "payee": f"Aporte Korea {index}", "status": status, "grp": f"korea-{index}"},
            )
        if not with_movements:
            return
        for index, (payee, tx_type, category_id, group, direction) in enumerate(
            (
                ("Exito", "expense", 1, None, None),
                ("Empresa", "income", 2, None, None),
                ("Traslado", "transfer", None, "move-1", "out"),
            ),
            start=10,
        ):
            conn.execute(
                sa.text(_INSERT_MOVEMENT),
                {
                    "id": index,
                    "payee": payee,
                    "type": tx_type,
                    "category_id": category_id,
                    "grp": group,
                    "direction": direction,
                },
            )


def test_the_upgrade_removes_the_goal_the_contribution_and_the_envelope():
    engine = engine_at_revision("0011")
    _seed(engine)
    alembic_command.upgrade(config_for(engine), "0012")
    tables = sa.inspect(engine).get_table_names()
    for table in GONE:
        assert table not in tables
    assert "goal_id" not in _columns(engine, "transaction")


def test_the_upgrade_deletes_the_proposals_that_were_never_confirmed():
    engine = engine_at_revision("0011")
    _seed(engine)
    alembic_command.upgrade(config_for(engine), "0012")
    assert _movements(engine) == []


def test_everything_else_keeps_the_category_it_had():
    engine = engine_at_revision("0011")
    _seed(engine, with_movements=True)
    alembic_command.upgrade(config_for(engine), "0012")
    assert _movements(engine) == [("Exito", "expense", 1), ("Empresa", "income", 2), ("Traslado", "transfer", None)]


def test_the_upgrade_refuses_when_a_proposal_was_confirmed():
    engine = engine_at_revision("0011")
    _seed(engine, proposal_statuses=("posted", "planned"))
    with pytest.raises(Exception, match="1 posted transfer was confirmed"):
        alembic_command.upgrade(config_for(engine), "0012")


def test_the_refusal_leaves_the_schema_and_the_proposals_alone():
    engine = engine_at_revision("0011")
    _seed(engine, proposal_statuses=("posted", "planned"))
    with pytest.raises(Exception, match="refusing to remove goals"):
        alembic_command.upgrade(config_for(engine), "0012")
    tables = sa.inspect(engine).get_table_names()
    for table in GONE:
        assert table in tables
    assert "goal_id" in _columns(engine, "transaction")
    assert len(_movements(engine)) == 2


def test_the_movement_rule_of_revision_0010_survives_the_table_rebuild():
    engine = engine_at_revision("0011")
    _seed(engine)
    alembic_command.upgrade(config_for(engine), "0012")
    with pytest.raises(sa.exc.IntegrityError), engine.begin() as conn:
        conn.execute(
            sa.text(
                'INSERT INTO "transaction" '
                "(id, date, payee, type, status, amount, currency, account_id, category_id, source, created_at) "
                "VALUES (99, '2026-06-15', 'Sin categoria', 'expense', 'posted', 1000, 'COP', 1, NULL, "
                "'manual', '2026-06-01 00:00:00')"
            )
        )


def test_the_downgrade_brings_the_schema_back_empty():
    engine = engine_at_revision("0011")
    _seed(engine)
    cfg = config_for(engine)
    alembic_command.upgrade(cfg, "0012")
    alembic_command.downgrade(cfg, "0011")
    tables = sa.inspect(engine).get_table_names()
    for table in GONE:
        assert table in tables
    assert "goal_id" in _columns(engine, "transaction")
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT COUNT(*) FROM goal")).scalar_one() == 0
        assert conn.execute(sa.text("SELECT COUNT(*) FROM goal_contribution")).scalar_one() == 0
        assert conn.execute(sa.text("SELECT COUNT(*) FROM budget")).scalar_one() == 0
