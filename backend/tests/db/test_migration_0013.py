"""Revision 0013 is additive, and reversible.

It is the first of the four revisions feature 009 brought: the meta, the money
set aside by hand, the link a purchase carries, and the flag that says a
category's spending is really saving. Nothing is dropped and nothing is
rewritten, so the app keeps running on the code that existed before it.

Two claims of the revision's own docstring are pinned here because neither is
visible in the table list: a meta stores **no balance**, and only an expense may
name one. Both are the shape of the feature, not decoration — a balance column
would let a past month be rewritten, and an income pointing at a meta would
count money coming in as a purchase.
"""

import pytest
import sqlalchemy as sa
from alembic import command as alembic_command
from tests.support.migrations import (
    config_for,
    engine_at_revision,
    insert_account,
    insert_category,
    insert_meta,
    insert_transaction,
)

NEW_TABLES = ("meta", "meta_contribution")

META_COLUMNS = {
    "id",
    "name",
    "amount",
    "currency",
    "start_month",
    "target_month",
    "stated_opening",
    "closed",
    "archived",
}

_INSERT_TRANSACTION = (
    'INSERT INTO "transaction" '
    "(id, date, payee, type, status, amount, currency, account_id, category_id, meta_id, "
    "source, created_at) "
    "VALUES (:id, '2026-06-15', 'Falabella', :type, 'posted', 5000000, 'COP', 1, :category_id, "
    ":meta_id, 'manual', '2026-06-01 00:00:00')"
)


def _columns(engine, table):
    return {column["name"] for column in sa.inspect(engine).get_columns(table)}


def _seed_a_meta_and_what_it_needs(engine):
    with engine.begin() as conn:
        insert_account(conn, 1, "Nu Debito")
        insert_category(conn, 1, "Tecnologia")
        insert_category(conn, 2, "Salario", is_income=True)
        insert_meta(conn, 1, "Televisor")


def test_the_upgrade_creates_the_meta_and_the_money_set_aside_by_hand():
    engine = engine_at_revision("0012")
    assert not set(NEW_TABLES) & set(sa.inspect(engine).get_table_names())
    alembic_command.upgrade(config_for(engine), "0013")
    tables = sa.inspect(engine).get_table_names()
    for table in NEW_TABLES:
        assert table in tables


def test_the_upgrade_adds_the_link_a_purchase_carries_and_the_flag_a_category_carries():
    engine = engine_at_revision("0013")
    assert "meta_id" in _columns(engine, "transaction")
    assert "counts_as_saving" in _columns(engine, "category")


def test_a_meta_stores_no_balance():
    """The table holds what was decided, never what it currently has.

    What a meta holds is folded forward from `start_month`, so a September read
    in January still answers as September stood. A stored balance would be the
    one thing able to contradict that, which is why the column set is pinned
    whole rather than by presence.
    """
    engine = engine_at_revision("0013")
    assert _columns(engine, "meta") == META_COLUMNS


def test_only_an_expense_may_name_a_meta():
    engine = engine_at_revision("0013")
    _seed_a_meta_and_what_it_needs(engine)
    with engine.begin() as conn:
        conn.execute(sa.text(_INSERT_TRANSACTION), {"id": 1, "type": "expense", "category_id": 1, "meta_id": 1})
    with engine.connect() as conn:
        assert conn.execute(sa.text('SELECT meta_id FROM "transaction" WHERE id = 1')).scalar_one() == 1


@pytest.mark.parametrize(
    ("tx_type", "category_id"),
    [("income", 2), ("transfer", None)],
)
def test_money_that_is_not_a_purchase_is_refused_a_meta(tx_type, category_id):
    engine = engine_at_revision("0013")
    _seed_a_meta_and_what_it_needs(engine)
    with pytest.raises(sa.exc.IntegrityError), engine.begin() as conn:
        conn.execute(sa.text(_INSERT_TRANSACTION), {"id": 2, "type": tx_type, "category_id": category_id, "meta_id": 1})


def test_two_metas_may_not_carry_one_name():
    engine = engine_at_revision("0013")
    with engine.begin() as conn:
        insert_meta(conn, 1, "Televisor")
    with pytest.raises(sa.exc.IntegrityError), engine.begin() as conn:
        insert_meta(conn, 2, "Televisor")


def test_the_upgrade_leaves_every_movement_it_found_alone():
    engine = engine_at_revision("0012")
    with engine.begin() as conn:
        insert_account(conn, 1, "Nu Debito")
        insert_category(conn, 1, "Comida")
        insert_transaction(conn, 1, "expense", 1, None, category_id=1)
        insert_transaction(conn, 2, "transfer", 1, "move-1")
    alembic_command.upgrade(config_for(engine), "0013")
    with engine.connect() as conn:
        rows = conn.execute(sa.text('SELECT id, type, meta_id FROM "transaction" ORDER BY id')).fetchall()
    assert rows == [(1, "expense", None), (2, "transfer", None)]


def test_the_downgrade_removes_only_what_the_revision_created():
    engine = engine_at_revision("0012")
    with engine.begin() as conn:
        insert_account(conn, 1, "Nu Debito")
        insert_category(conn, 1, "Comida")
        insert_transaction(conn, 1, "expense", 1, None, category_id=1)
    cfg = config_for(engine)
    alembic_command.upgrade(cfg, "0013")
    alembic_command.downgrade(cfg, "0012")
    tables = sa.inspect(engine).get_table_names()
    for table in NEW_TABLES:
        assert table not in tables
    assert "meta_id" not in _columns(engine, "transaction")
    assert "counts_as_saving" not in _columns(engine, "category")
    with engine.connect() as conn:
        assert conn.execute(sa.text('SELECT COUNT(*) FROM "transaction"')).scalar_one() == 1
