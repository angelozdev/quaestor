"""read path indexes

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-22 12:52:54.379066

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_transaction_type_status_date",
        "transaction",
        ["type", "status", "date"],
    )


def downgrade() -> None:
    op.drop_index("ix_transaction_type_status_date", table_name="transaction")
