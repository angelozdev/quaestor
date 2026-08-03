"""widen balance and amount columns to BIGINT to fit SQLite data

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-05 16:00:00.000000

The SQLite source has values that exceed PostgreSQL's 4-byte INTEGER range:
- account.balance max: 3,080,514,628 (> 2,147,483,647)
- transaction.amount min: -2,908,443,655 (< -2,147,483,648)

SQLite INTEGER is 8 bytes; PostgreSQL INTEGER is 4 bytes. Widen the affected
columns to BIGINT (8 bytes) to fit the data. Only the two columns with
actual overflowing values are changed; other amount columns (budget,
goal, recurring, goal_contribution) fit in INTEGER and are not modified.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # SQLite's INTEGER is already 8 bytes (equivalent to BIGINT), so no
    # widening is needed there. The ALTER COLUMN syntax is also Postgres-
    # specific. Skip on SQLite; only run on Postgres.
    if op.get_bind().dialect.name != "postgresql":
        return
    op.alter_column(
        "account",
        "balance",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )
    op.alter_column(
        "transaction",
        "amount",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.alter_column(
        "account",
        "balance",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
    )
    op.alter_column(
        "transaction",
        "amount",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
    )
