"""a meta is a named thing to save for (ADR-0046 / feature 009)

Additive. Creates `meta` and `meta_contribution`, adds `transaction.meta_id`
and `category.counts_as_saving`, and drops nothing. The app keeps running on
the code that exists before this revision, so nothing depends on the new schema
until the feature is built on it. The destructive half — the fund's dated rule
and its two columns — is revision 0014 and runs only after that code is merged.

A meta stores **no balance**, the same constraint revision 0011 put on the fund
and for the same reason: what it holds is folded forward from `start_month`, so
asking about September next year gives September's answer whenever it is asked,
and cancelling in December cannot rewrite what September reported.

`stated_opening` is the owner's own statement of what he had already put by
before the meta existed. It costs no month, unlike a contribution, and it is
read for the start month only.

`meta_contribution` is the shape `goal_contribution` had before revision 0012
removed it, and the difference is everything around it: no month-end routine
generates rows, there is no proposal to confirm and no source account. A row
exists because the owner pressed a button, and he can delete it.

`transaction.meta_id` is `transaction.goal_id` returning, and the same applies:
the old column hung off a transfer proposal a ritual generated into a forced
savings account; this one hangs off a posted expense the owner names once, on
the day he buys the thing. `ck_transaction_meta_only_on_expense` confines it to
expenses the way revision 0010's constraint confines `category_id` by
direction — money coming in and money moving between the owner's own accounts
are not purchases.

`uq_meta_name` mirrors the refusal categories already make: two live metas may
not carry one name.

Amounts are BigInteger for the reason revision 0002 widened the others: a COP
figure in cents passes the 32-bit ceiling at $21.474.836.

SQLite needs `batch_alter_table` to add a constraint, as revision 0010 does;
Postgres does not.

`downgrade` is a real reversal — every object here is new, so dropping them
loses only what this revision created.

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-08

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UNIQUE_NAME = "uq_meta_name"
META_ONLY_ON_EXPENSE = "ck_transaction_meta_only_on_expense"
META_ON_EXPENSE = "meta_id IS NULL OR type = 'expense'"
META_FK = "fk_transaction_meta_id"


def upgrade() -> None:
    op.create_table(
        "meta",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("currency", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("start_month", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("target_month", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("stated_opening", sa.BigInteger(), nullable=True),
        sa.Column("closed", sa.Boolean(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name=UNIQUE_NAME),
    )
    op.create_table(
        "meta_contribution",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("meta_id", sa.Integer(), nullable=False),
        sa.Column("year_month", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["meta_id"], ["meta.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column("category", sa.Column("counts_as_saving", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("transaction", sa.Column("meta_id", sa.Integer(), nullable=True))

    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("transaction") as batch_op:
            batch_op.create_foreign_key(META_FK, "meta", ["meta_id"], ["id"])
            batch_op.create_check_constraint(META_ONLY_ON_EXPENSE, META_ON_EXPENSE)
    else:
        op.create_foreign_key(META_FK, "transaction", "meta", ["meta_id"], ["id"])
        op.create_check_constraint(META_ONLY_ON_EXPENSE, "transaction", sa.text(META_ON_EXPENSE))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("transaction") as batch_op:
            batch_op.drop_constraint(META_ONLY_ON_EXPENSE, type_="check")
            batch_op.drop_constraint(META_FK, type_="foreignkey")
    else:
        op.drop_constraint(META_ONLY_ON_EXPENSE, "transaction", type_="check")
        op.drop_constraint(META_FK, "transaction", type_="foreignkey")

    op.drop_column("transaction", "meta_id")
    op.drop_column("category", "counts_as_saving")
    op.drop_table("meta_contribution")
    op.drop_table("meta")
