"""a restored meta leaves its old contributions given back (ADR-0055 / feature 009, AC-29)

Additive, nullable, no backfill. Adds `meta_contribution.returned_month`.

Cancelling a meta hands back everything the months put in, contributions
included, and `restore_meta` left the rows untouched. A contribution made in the
month the meta was restored was then read a second time — a $1.000.000 put in by
hand left a meta cancelled and restored the same August holding $2.000.000 when
August had only ever put in $1.000.000. One made in an earlier month was the
mirror image: listed at face value and read by no month at all.

The column is written by `restore_meta` and by nothing else. Cancelling does not
write it, so a cancellation nobody undoes leaves its month reading exactly what
it read before — which is what AC-27 requires and what stamping at cancellation
time would have broken.

Null is the truth for every existing row: no meta in the database has been
restored, so there is nothing to backfill.

`downgrade` drops the column, and with it the record of which contributions were
given back. A meta restored before the downgrade would go back to holding money
its months never put in.

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-13

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0018"
down_revision: str | Sequence[str] | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("meta_contribution") as batch_op:
        batch_op.add_column(sa.Column("returned_month", sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("meta_contribution") as batch_op:
        batch_op.drop_column("returned_month")
