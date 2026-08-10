"""Revision 0016 is additive, and reversible, and corrects revision 0013.

It creates `meta_amendment` — the values an edit made effective, and the month
it made them — and it narrows `uq_meta_name` to live metas only.

The narrowing is the half worth the file. Revision 0013 made the name unique
outright, which is stricter than AC-22 asks: a cancelled meta's name is free to
be used again, and the service already refused only against living ones. The
constraint was the stricter of the two and won, so until this revision the
criterion could not hold no matter what the service did. Both halves are pinned,
and so is the state before the correction.

The predicate is written twice, once per dialect. SQLite gets `archived = 0`,
which is what runs here; Postgres gets `NOT archived`, which is what runs in
production and which no test in this repository reaches.
"""

import pytest
import sqlalchemy as sa
from alembic import command as alembic_command
from tests.support.migrations import config_for, engine_at_revision, insert_meta

_INSERT_AMENDMENT = (
    "INSERT INTO meta_amendment (id, meta_id, year_month, amount, target_month, created_at) "
    "VALUES (:id, 1, :year_month, :amount, '2027-01', '2026-10-01 00:00:00')"
)


def test_the_upgrade_creates_the_table_that_remembers_an_edit():
    engine = engine_at_revision("0015")
    assert "meta_amendment" not in sa.inspect(engine).get_table_names()
    alembic_command.upgrade(config_for(engine), "0016")
    assert "meta_amendment" in sa.inspect(engine).get_table_names()


def test_a_meta_may_not_be_edited_twice_into_one_month():
    """One row per meta per month, so a month has a single answer.

    Two rows for October would make the fold's reading of October depend on
    which one it happened to pick up.
    """
    engine = engine_at_revision("0016")
    with engine.begin() as conn:
        insert_meta(conn, 1, "Televisor")
        conn.execute(sa.text(_INSERT_AMENDMENT), {"id": 1, "year_month": "2026-10", "amount": 600000000})
    with pytest.raises(sa.exc.IntegrityError), engine.begin() as conn:
        conn.execute(sa.text(_INSERT_AMENDMENT), {"id": 2, "year_month": "2026-10", "amount": 700000000})


def test_a_meta_may_be_edited_again_in_a_later_month():
    engine = engine_at_revision("0016")
    with engine.begin() as conn:
        insert_meta(conn, 1, "Televisor")
        conn.execute(sa.text(_INSERT_AMENDMENT), {"id": 1, "year_month": "2026-10", "amount": 600000000})
        conn.execute(sa.text(_INSERT_AMENDMENT), {"id": 2, "year_month": "2026-11", "amount": 700000000})
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT COUNT(*) FROM meta_amendment")).scalar_one() == 2


def test_a_live_name_is_still_refused_a_second_time():
    engine = engine_at_revision("0016")
    with engine.begin() as conn:
        insert_meta(conn, 1, "Televisor")
    with pytest.raises(sa.exc.IntegrityError), engine.begin() as conn:
        insert_meta(conn, 2, "Televisor")


def test_a_cancelled_metas_name_is_free_again():
    engine = engine_at_revision("0016")
    with engine.begin() as conn:
        insert_meta(conn, 1, "Televisor", archived=True)
        insert_meta(conn, 2, "Televisor")
    with engine.connect() as conn:
        living = conn.execute(sa.text("SELECT id FROM meta WHERE archived = 0")).scalars().all()
    assert living == [2]


def test_before_this_revision_the_cancelled_name_stayed_taken():
    """Evidence that the revision is what makes AC-22 possible.

    At 0015 the same pair of inserts is refused by the database itself, which
    is why narrowing the index — not a change in the service — is the fix.
    """
    engine = engine_at_revision("0015")
    with engine.begin() as conn:
        insert_meta(conn, 1, "Televisor", archived=True)
    with pytest.raises(sa.exc.IntegrityError), engine.begin() as conn:
        insert_meta(conn, 2, "Televisor")


def test_the_downgrade_takes_the_table_away_and_the_outright_refusal_back():
    engine = engine_at_revision("0016")
    cfg = config_for(engine)
    alembic_command.downgrade(cfg, "0015")
    assert "meta_amendment" not in sa.inspect(engine).get_table_names()
    with engine.begin() as conn:
        insert_meta(conn, 1, "Televisor", archived=True)
    with pytest.raises(sa.exc.IntegrityError), engine.begin() as conn:
        insert_meta(conn, 2, "Televisor")
