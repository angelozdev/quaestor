from alembic import command as alembic_command
from tests.support.migrations import (
    config_for,
    engine_at_revision,
    insert_account,
    insert_recurring,
    recurring_modes_by_id,
)


def _seeded_engine_at_rev_0008():
    """One manual income (the orphan AC-6 closes), plus rows that must not move."""
    engine = engine_at_revision("0008")
    with engine.begin() as conn:
        insert_account(conn, 1, "Bancolombia")
        insert_recurring(conn, 10, "Salario", "income", "manual")
        insert_recurring(conn, 11, "Bono", "income", "auto")
        insert_recurring(conn, 12, "Arriendo", "expense", "manual")
        insert_recurring(conn, 13, "Netflix", "expense", "auto")
    return engine


def test_0009_turns_a_manual_income_automatic():
    engine = _seeded_engine_at_rev_0008()
    alembic_command.upgrade(config_for(engine), "0009")
    assert recurring_modes_by_id(engine)[10] == "auto"


def test_0009_leaves_an_expense_waiting_for_approval_alone():
    engine = _seeded_engine_at_rev_0008()
    alembic_command.upgrade(config_for(engine), "0009")
    modes = recurring_modes_by_id(engine)
    assert modes[12] == "manual"
    assert modes[13] == "auto"


def test_0009_is_a_no_op_for_an_income_that_already_pays_itself():
    engine = _seeded_engine_at_rev_0008()
    alembic_command.upgrade(config_for(engine), "0009")
    assert recurring_modes_by_id(engine)[11] == "auto"


def test_0009_downgrade_does_not_recreate_the_orphan():
    engine = _seeded_engine_at_rev_0008()
    cfg = config_for(engine)
    alembic_command.upgrade(cfg, "0009")
    alembic_command.downgrade(cfg, "0008")
    assert recurring_modes_by_id(engine)[10] == "auto"
