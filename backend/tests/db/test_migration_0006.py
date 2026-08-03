import sqlalchemy as sa
from alembic import command as alembic_command
from quaestor.domain.models import Transaction, TransferDirection
from sqlmodel import Session
from tests.support.migrations import (
    config_for,
    directions_by_id,
    engine_at_revision,
    insert_account,
    insert_transaction,
)


def _seeded_engine_at_rev_0005():
    engine = engine_at_revision("0005")
    with engine.begin() as conn:
        insert_account(conn, 1, "Cash")
        insert_account(conn, 2, "Bank")
        insert_transaction(conn, 10, "transfer", 1, "g1")
        insert_transaction(conn, 11, "transfer", 2, "g1")
        insert_transaction(conn, 21, "transfer", 2, "g2")
        insert_transaction(conn, 20, "transfer", 1, "g2")
        insert_transaction(conn, 30, "expense", 1, None)
    return engine


def test_backfill_marks_lower_id_as_out_and_the_other_as_in():
    engine = _seeded_engine_at_rev_0005()
    alembic_command.upgrade(config_for(engine), "0006")
    rows = directions_by_id(engine)
    assert rows[10] == "out"
    assert rows[11] == "in_"
    assert rows[20] == "out"
    assert rows[21] == "in_"


def test_backfill_leaves_non_transfer_rows_without_direction():
    engine = _seeded_engine_at_rev_0005()
    alembic_command.upgrade(config_for(engine), "0006")
    with engine.connect() as conn:
        row = conn.execute(sa.text('SELECT transfer_direction FROM "transaction" WHERE id = 30')).fetchone()
    assert row[0] is None


def test_backfilled_directions_read_back_through_the_model():
    engine = _seeded_engine_at_rev_0005()
    alembic_command.upgrade(config_for(engine), "head")
    with Session(engine) as session:
        assert session.get(Transaction, 10).transfer_direction == TransferDirection.out
        assert session.get(Transaction, 11).transfer_direction == TransferDirection.in_
        assert session.get(Transaction, 30).transfer_direction is None
