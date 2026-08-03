"""Shared seeding helpers for Alembic revision tests."""

import sqlalchemy as sa
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from quaestor.db import _ALEMBIC_INI, make_engine

DEFAULT_CREATED_AT = "2026-06-01 00:00:00"


def config_for(engine):
    cfg = AlembicConfig(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", str(engine.url))
    cfg.attributes["engine"] = engine
    return cfg


def insert_account(conn, account_id, name):
    conn.execute(
        sa.text(
            "INSERT INTO account (id, name, type, currency, balance, archived) "
            "VALUES (:id, :name, 'debit', 'COP', 0, 0)"
        ),
        {"id": account_id, "name": name},
    )


def insert_category(conn, category_id, name="Seeded", is_income=False):
    conn.execute(
        sa.text(
            "INSERT INTO category (id, name, is_income, exclude_from_budget, "
            "exclude_from_totals, archived) "
            "VALUES (:id, :name, :is_income, false, false, false)"
        ),
        {"id": category_id, "name": name, "is_income": is_income},
    )


def insert_transaction(conn, tx_id, tx_type, account_id, group, created_at=DEFAULT_CREATED_AT, category_id=None):
    """Seed one movement.

    `category_id` follows the rule the schema enforces from revision 0010 on:
    an expense or income carries one, a transfer carries none. A seed that
    breaks it cannot be migrated to head, which is the guard working.
    """
    conn.execute(
        sa.text(
            'INSERT INTO "transaction" '
            "(id, date, payee, type, status, amount, currency, account_id, "
            "category_id, transfer_group_id, source, created_at) "
            "VALUES (:id, '2026-06-01', 'p', :type, 'posted', 1000, 'COP', "
            ":account_id, :category_id, :grp, 'manual', :created_at)"
        ),
        {
            "id": tx_id,
            "type": tx_type,
            "account_id": account_id,
            "category_id": None if tx_type == "transfer" else category_id,
            "grp": group,
            "created_at": created_at,
        },
    )


def engine_at_revision(revision):
    engine = make_engine(memory=True)
    alembic_command.upgrade(config_for(engine), revision)
    return engine


def directions_by_id(engine):
    with engine.connect() as conn:
        return dict(conn.execute(sa.text('SELECT id, transfer_direction FROM "transaction"')).fetchall())


def insert_recurring(conn, recurring_id, name, tx_type, mode, account_id=1):
    conn.execute(
        sa.text(
            "INSERT INTO recurring_item "
            "(id, name, payee, type, mode, amount, currency, account_id, "
            "interval_unit, interval_count, start_date, active) "
            "VALUES (:id, :name, :name, :type, :mode, 1000, 'COP', :account_id, "
            "'month', 1, '2026-06-01', 1)"
        ),
        {
            "id": recurring_id,
            "name": name,
            "type": tx_type,
            "mode": mode,
            "account_id": account_id,
        },
    )


def recurring_modes_by_id(engine):
    with engine.connect() as conn:
        return dict(conn.execute(sa.text("SELECT id, mode FROM recurring_item")).fetchall())
