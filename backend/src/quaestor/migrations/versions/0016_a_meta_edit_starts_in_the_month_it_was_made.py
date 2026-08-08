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
NAME_INDEX = "uq_meta_name"


def _free_the_name_of_a_cancelled_meta() -> None:
    """Make the name unique among LIVE metas only (AC-22).

    Revision 0013 made it unique outright, which contradicts the criterion it
    was meant to enforce: a cancelled meta's name is free to reuse, and the
    service already refuses only against live ones. The constraint was the
    stricter of the two and won.
    """
    bind = op.get_bind()
    where = "archived = 0" if bind.dialect.name == "sqlite" else "NOT archived"
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("meta") as batch_op:
            batch_op.drop_constraint(NAME_INDEX, type_="unique")
    else:
        op.drop_constraint(NAME_INDEX, "meta", type_="unique")
    op.create_index(
        NAME_INDEX, "meta", ["name"], unique=True, postgresql_where=sa.text(where), sqlite_where=sa.text(where)
    )


def upgrade() -> None:
    _free_the_name_of_a_cancelled_meta()
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
    bind = op.get_bind()
    op.drop_index(NAME_INDEX, table_name="meta")
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("meta") as batch_op:
            batch_op.create_unique_constraint(NAME_INDEX, ["name"])
    else:
        op.create_unique_constraint(NAME_INDEX, "meta", ["name"])
