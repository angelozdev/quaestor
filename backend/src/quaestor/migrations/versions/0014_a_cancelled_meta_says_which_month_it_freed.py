"""a cancelled meta says which month it freed (ADR-0046 / feature 009, AC-15)

Additive, and the second of three. Adds `meta.cancelled_month` and drops
nothing.

Cancelling a meta releases what it held back into the money available, and it
does so **in the month it was cancelled and in no other**. November must not
keep handing back what October already gave. The month is therefore the one
thing about a cancellation that cannot be derived — everything else a meta
reports is folded forward from its start month, but "when did this stop" is a
fact only the act itself knows.

Found in Phase 2 rather than at the plan: `archived` alone says a meta is gone
and says nothing about when, and AC-15's two scenarios differ only in that.

`downgrade` is a real reversal — the column is new.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-08

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("meta", sa.Column("cancelled_month", sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    op.drop_column("meta", "cancelled_month")
