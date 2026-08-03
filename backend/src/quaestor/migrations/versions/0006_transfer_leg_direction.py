"""transfer leg direction (ADR-0032)

Adds the nullable ``transaction.transfer_direction`` enum column
(``out`` | ``in_`` — SQLAlchemy stores enum member names, matching the
``source`` column's ``import_`` convention) and backfills historical
transfer pairs. The backfill materializes an invariant that holds for
``transactions.transfer()`` and ``goals.contribute_to_goal()``: they persist
the source leg first, so within each ``transfer_group_id`` the lower ``id``
is the outgoing leg. Non-transfer rows keep NULL.

The invariant does NOT hold for ``planned._confirm_transfer()``; revision
0007 corrects the pairs this backfill inverted (ADR-0032, amended
2026-07-31).

SQLite applies the column via ``batch_alter_table``; Postgres creates the
enum type first and adds the column directly.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-31

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _direction_enum() -> sa.Enum:
    return sa.Enum("out", "in_", name="transferdirection")


def upgrade() -> None:
    direction = _direction_enum()
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("transaction") as batch_op:
            batch_op.add_column(
                sa.Column("transfer_direction", direction, nullable=True)
            )
    else:
        direction.create(bind, checkfirst=True)
        op.add_column(
            "transaction", sa.Column("transfer_direction", direction, nullable=True)
        )
    _backfill_directions()


def _backfill_directions() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE \"transaction\" SET transfer_direction = 'out' "
            "WHERE transfer_group_id IS NOT NULL AND id = ("
            'SELECT MIN(t2.id) FROM "transaction" AS t2 '
            'WHERE t2.transfer_group_id = "transaction".transfer_group_id)'
        )
    )
    conn.execute(
        sa.text(
            "UPDATE \"transaction\" SET transfer_direction = 'in_' "
            "WHERE transfer_group_id IS NOT NULL AND transfer_direction IS NULL"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("transaction") as batch_op:
            batch_op.drop_column("transfer_direction")
    else:
        op.drop_column("transaction", "transfer_direction")
        _direction_enum().drop(bind, checkfirst=True)
