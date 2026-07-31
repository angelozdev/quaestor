"""read-time fx conversion (ADR-0031)

Moves the app from frozen per-transaction conversions to a single scalar
TRM converted at read time:

1. Add ``settings.usd_cop`` (nullable Numeric(18, 6)).
2. Pre-load it from the most recent ``fx_rate`` row, so an upgraded
   database exits the migration with the TRM populated (no surprise
   MissingRate on the first read).
3. Drop the frozen snapshot columns ``transaction.fx_rate`` and
   ``transaction.to_base`` (batch mode for SQLite).
4. Drop the dated ``fx_rate`` table.

Original amounts and currencies are untouched (AC-12).

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("settings", sa.Column("usd_cop", sa.Numeric(18, 6), nullable=True))
    _preload_trm_from_latest_dated_rate()
    with op.batch_alter_table("transaction") as batch_op:
        batch_op.drop_column("fx_rate")
        batch_op.drop_column("to_base")
    op.drop_table("fx_rate")


def _preload_trm_from_latest_dated_rate() -> None:
    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT usd_cop FROM fx_rate ORDER BY date DESC LIMIT 1")
    ).fetchone()
    if row is not None:
        conn.execute(sa.text("UPDATE settings SET usd_cop = :rate"), {"rate": row[0]})


def downgrade() -> None:
    raise RuntimeError(
        "irreversible migration: the frozen per-transaction conversions "
        "(transaction.fx_rate/to_base) and the dated fx_rate history were "
        "dropped and cannot be reconstructed — restore from the pre-upgrade "
        "backup instead"
    )
