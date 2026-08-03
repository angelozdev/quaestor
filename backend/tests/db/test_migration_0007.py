from alembic import command as alembic_command
from tests.support.migrations import (
    config_for,
    directions_by_id,
    engine_at_revision,
    insert_account,
    insert_transaction,
)

_CONFIRMED_AT = "2026-06-15 09:30:00"


def _seeded_engine_at_rev_0006():
    """g1 = one add_all pair; g2 = a planned row confirmed two weeks later."""
    engine = engine_at_revision("0005")
    with engine.begin() as conn:
        insert_account(conn, 1, "Cash")
        insert_account(conn, 2, "Bank")
        insert_transaction(conn, 10, "transfer", 1, "g1")
        insert_transaction(conn, 11, "transfer", 2, "g1")
        insert_transaction(conn, 20, "transfer", 2, "g2")
        insert_transaction(conn, 21, "transfer", 1, "g2", created_at=_CONFIRMED_AT)
        insert_transaction(conn, 30, "expense", 1, None)
    alembic_command.upgrade(config_for(engine), "0006")
    return engine


def test_0006_inverts_a_planned_confirm_pair():
    engine = _seeded_engine_at_rev_0006()
    rows = directions_by_id(engine)
    assert rows[20] == "out"
    assert rows[21] == "in_"


def test_0007_flips_the_leg_created_later_to_outgoing():
    engine = _seeded_engine_at_rev_0006()
    alembic_command.upgrade(config_for(engine), "0007")
    rows = directions_by_id(engine)
    assert rows[21] == "out"
    assert rows[20] == "in_"


def test_0007_leaves_same_instant_pairs_untouched():
    engine = _seeded_engine_at_rev_0006()
    alembic_command.upgrade(config_for(engine), "0007")
    rows = directions_by_id(engine)
    assert rows[10] == "out"
    assert rows[11] == "in_"


def test_0007_leaves_non_transfer_rows_without_direction():
    engine = _seeded_engine_at_rev_0006()
    alembic_command.upgrade(config_for(engine), "0007")
    assert directions_by_id(engine)[30] is None


def test_0007_downgrade_restores_the_0006_shape():
    engine = _seeded_engine_at_rev_0006()
    cfg = config_for(engine)
    alembic_command.upgrade(cfg, "0007")
    alembic_command.downgrade(cfg, "0006")
    rows = directions_by_id(engine)
    assert rows[20] == "out"
    assert rows[21] == "in_"
