"""a meta edit starts in the month it was made (ADR-0046 / feature 009, AC-11)

Additive. Creates `meta_amendment` and drops nothing.

Raising a meta's amount in October must leave August and September saying what
they said. Everything else a meta reports is folded forward from its start
month and needs nothing stored, but an edit cannot be recovered from a single
current value: with only `Meta.amount` the fold re-derives every past month
against the new figure, and a September read in January stops matching the
September the owner saw. That is exactly what AC-27 forbids.

A row holds the values effective **from** its month. The meta's own `amount`
and `target_month` stay the values effective from its start month and are never
rewritten — they are the first term of the same series, not a mutable current
state.

This is the third time in this feature that an act had to record its own month:
`meta_contribution` for money set aside by hand, `meta.cancelled_month` for a
cancellation, and now this. The pattern is the boundary of what a fold can do.

`downgrade` is a real reversal — the table is new.

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-08

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0016"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UNIQUE_MONTH = "uq_meta_amendment_month"


def upgrade() -> None:
    op.create_table(
        "meta_amendment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("meta_id", sa.Integer(), nullable=False),
        sa.Column("year_month", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("target_month", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["meta_id"], ["meta.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("meta_id", "year_month", name=UNIQUE_MONTH),
    )


def downgrade() -> None:
    op.drop_table("meta_amendment")
