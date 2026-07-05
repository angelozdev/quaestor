"""widen transaction.to_base to BIGINT to fit SQLite data

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-05 16:30:00.000000

The SQLite source has transaction.to_base values that exceed PostgreSQL's
4-byte INTEGER range:
- transaction.to_base min: -2,908,443,655 (< -2,147,483,648)

`to_base` is the COP-centavos equivalent of `amount`, frozen at the
transaction's FX rate. For large negative transactions (e.g. expense in
a strong foreign currency), it can be as large in magnitude as `amount`.

Migration 0002 widened account.balance and transaction.amount. This
migration widens transaction.to_base.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.alter_column(
        "transaction",
        "to_base",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.alter_column(
        "transaction",
        "to_base",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
    )