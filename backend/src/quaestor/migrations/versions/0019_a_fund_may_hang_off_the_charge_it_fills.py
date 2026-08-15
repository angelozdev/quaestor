"""a fund may hang off the charge it fills (ADR-0057 / feature 015, AC-1)

Schema only. Adds `fund.recurring_id`, turns `uq_fund_category` into a partial
unique index, and adds `uq_fund_recurring`. No data moves here — converting the
one existing category fund into one fund per charge is its own revision, run
with the owner present (CHARTER §7).

Null is the truth for every existing row: all five funds in production hang off
a category, and the four that use the `average` rule always will.

The partial index is the whole point, and it is why the old constraint is
recreated rather than dropped. ADR-0043 argued that two funds on one category
would be two ways to lower the same headline, and that argument still holds for
`fixed` and `average` — so those stay one per category. It does not hold for two
funds tied to *different charges*: each covers different money, and since
feature 013 the movement says which. `WHERE recurring_id IS NULL` is that
boundary written into the schema.

SQLite reaches the same constraint by a different road: it has no named unique
constraint to drop, so the batch operation rebuilds the table. Both dialects
support partial indexes, which is what makes one definition serve production
Postgres and the in-memory SQLite the tests run on.

`downgrade` cannot restore the whole-table uniqueness while two funds share a
category, so it deletes the funds that hang off a charge first. That is the
honest inverse: their rule has nowhere to live in the old shape, and a fund
stores no balance, so nothing but the rule is lost (ADR-0043).

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | Sequence[str] | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ONLY_CATEGORY_FUNDS = sa.text("recurring_id IS NULL")


def upgrade() -> None:
    with op.batch_alter_table("fund") as batch_op:
        batch_op.add_column(sa.Column("recurring_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_fund_recurring", "recurring_item", ["recurring_id"], ["id"])
        batch_op.drop_constraint("uq_fund_category", type_="unique")
        batch_op.create_unique_constraint("uq_fund_recurring", ["recurring_id"])
    op.create_index(
        "uq_fund_category",
        "fund",
        ["category_id"],
        unique=True,
        sqlite_where=_ONLY_CATEGORY_FUNDS,
        postgresql_where=_ONLY_CATEGORY_FUNDS,
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM fund WHERE recurring_id IS NOT NULL"))
    op.drop_index("uq_fund_category", table_name="fund")
    with op.batch_alter_table("fund") as batch_op:
        batch_op.drop_constraint("uq_fund_recurring", type_="unique")
        batch_op.drop_constraint("fk_fund_recurring", type_="foreignkey")
        batch_op.drop_column("recurring_id")
        batch_op.create_unique_constraint("uq_fund_category", ["category_id"])
