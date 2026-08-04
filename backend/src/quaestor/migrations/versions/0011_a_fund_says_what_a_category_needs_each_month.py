"""a fund says what a category needs each month (ADR-0043 / feature 003)

Additive. Creates the `fund` table and touches nothing else: goals, envelopes
and `transaction.goal_id` are still standing after this revision and are
removed by the destructive one that follows.

A fund stores its **funding rule**, never a balance. What it holds is folded
forward from the owner's own anchor over the spending the month aggregate
already carries, so nothing here has to be advanced by a job or a monthly
click — which is the whole reason the envelope surface stayed empty (zero
`budget` rows in the app's history).

The columns split into the rule and its parameters:

- `rule` + `start_month` + `accumulates` — every fund has these.
- `amount` — the `fixed` rule's monthly figure.
- `window_months` — the `average` rule's look-back.
- `target_amount` + `target_month` — the `target-by-date` rule.
- `anchor_month` + `anchor_amount` — the owner's statement of what the fund
  already held. `anchor_month` is nullable because a statement can be made
  without naming a month, in which case it stands for the month being looked
  at. It is a statement, not a snapshot: nothing in the app writes it and
  nothing reads it from an account (AC-19).

`from-recurring` needs no parameters — it reads the obligations already filed
under its category.

One fund per category, enforced by `uq_fund_category`: two funds on one
category would be two ways to lower the same headline, which is the shape of
the defect this feature exists to close (AC-25).

Amounts are BigInteger for the same reason revision 0002 widened the others: a
COP figure in cents passes the 32-bit ceiling at $21.474.836.

SQLite gets the same `create_table` as Postgres — nothing is rebuilt here, so
`batch_alter_table` is not needed; the enum type, however, is only created
explicitly on Postgres, as revision 0006 does.

`downgrade` is a real reversal: the table is new, so dropping it loses only
what this revision created.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-04

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UNIQUE_CATEGORY = "uq_fund_category"


def _rule_enum() -> sa.Enum:
    return sa.Enum("fixed", "average", "from_recurring", "target_by_date", name="fundrule")


def upgrade() -> None:
    rule = _rule_enum()
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        rule.create(bind, checkfirst=True)
    op.create_table(
        "fund",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("rule", rule, nullable=False),
        sa.Column("start_month", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("accumulates", sa.Boolean(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=True),
        sa.Column("window_months", sa.Integer(), nullable=True),
        sa.Column("target_amount", sa.BigInteger(), nullable=True),
        sa.Column("target_month", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("anchor_month", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("anchor_amount", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["category_id"], ["category.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("category_id", name=UNIQUE_CATEGORY),
    )


def downgrade() -> None:
    op.drop_table("fund")
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        _rule_enum().drop(bind, checkfirst=True)
