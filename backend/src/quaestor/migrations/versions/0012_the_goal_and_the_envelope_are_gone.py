"""the goal and the envelope are gone (ADR-0043 / feature 003, AC-26/27)

Destructive, and the first revision of this project that is. Revision 0010
added constraints and its `downgrade` dropped them losing nothing; this one
removes three tables and one column. **The way back is the dump, not the
downgrade** — see `features/003-sinking-funds/runbook.md`.

Five things, in this order:

1. A pre-flight count of `posted` transfers still carrying a `goal_id`. A
   confirmed proposal is a real transfer that moved money between two of the
   owner's own accounts; deleting it would undo a fact, so the revision
   refuses, names how many, and touches nothing. Same shape as revision
   0010's guard over uncategorised rows, and the same reason: the change
   lands on data it understands or it does not land.
2. The unconfirmed proposals go — transfers carrying a `goal_id` whose status
   is `planned` or `skipped`. They were suggestions made by a month-end
   routine that no longer exists and they never moved a peso (AC-27).
3. `goal_contribution` is dropped: it points at both `goal` and
   `transaction`, so it goes before either.
4. `transaction.goal_id` is dropped. It happens **before** `goal` and not
   after, because on Postgres the column's foreign key is what makes `goal`
   undroppable; SQLite would tolerate the other order and the owner's
   database would not. SQLite cannot `ALTER TABLE DROP COLUMN` on a
   constrained table, so it goes through `batch_alter_table` (a table
   rebuild) exactly as revision 0010 did; Postgres gets a plain ALTER.
5. `goal` and `budget` are dropped, and on Postgres their enum types with
   them.

`budget` has never held a row in the app's history — the envelope ritual was
never run once — so nothing is migrated into a fund. A goal is not migrated
either: the owner decided during CP2 that the money exists but was never
recorded, and the moment they sit down to record it is the moment they create
the fund.

`downgrade` recreates the three tables **empty** and the column **null**. It
is written that way on purpose: the schema comes back, the goal and its
proposals do not. Say it out loud rather than let an operator discover it.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-04

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GOAL_FK = "transaction_goal_id_fkey"

CONTRIBUTION_INDEX = "ix_goal_contribution_goal_date"

_COUNT_CONFIRMED = sa.text("SELECT COUNT(*) FROM \"transaction\" WHERE goal_id IS NOT NULL AND status = 'posted'")

_DELETE_PROPOSALS = sa.text(
    "DELETE FROM \"transaction\" WHERE goal_id IS NOT NULL AND status IN ('planned', 'skipped')"
)


def _goal_status_enum() -> sa.Enum:
    return sa.Enum("active", "reached", "paused", name="goalstatus")


def _contribution_source_enum() -> sa.Enum:
    return sa.Enum("confirmed", "manual", name="contributionsource")


def _refuse_over_confirmed_contributions() -> None:
    """Stop before touching anything if a proposal was ever confirmed."""
    confirmed = op.get_bind().execute(_COUNT_CONFIRMED).scalar_one()
    if not confirmed:
        return
    movement = "transfer was" if confirmed == 1 else "transfers were"
    raise RuntimeError(
        f"[0012] refusing to remove goals: {confirmed} posted {movement} confirmed against one. "
        "A confirmed contribution moved real money between two accounts — release it from its "
        "goal by hand first, so the movement survives the goal it was filed under."
    )


def upgrade() -> None:
    _refuse_over_confirmed_contributions()
    bind = op.get_bind()
    op.execute(_DELETE_PROPOSALS)
    op.drop_index(CONTRIBUTION_INDEX, table_name="goal_contribution")
    op.drop_table("goal_contribution")
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("transaction") as batch_op:
            batch_op.drop_column("goal_id")
    else:
        op.drop_column("transaction", "goal_id")
    op.drop_table("goal")
    op.drop_table("budget")
    if bind.dialect.name != "sqlite":
        _goal_status_enum().drop(bind, checkfirst=True)
        _contribution_source_enum().drop(bind, checkfirst=True)


def downgrade() -> None:
    """Bring the schema back, empty. The goal and its proposals do not return."""
    bind = op.get_bind()
    goal_status = _goal_status_enum()
    contribution_source = _contribution_source_enum()
    if bind.dialect.name != "sqlite":
        goal_status.create(bind, checkfirst=True)
        contribution_source.create(bind, checkfirst=True)
    op.create_table(
        "budget",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("year_month", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("amount_assigned", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["category.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("category_id", "year_month", name="uq_budget_category_month"),
    )
    op.create_table(
        "goal",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("target_amount", sa.Integer(), nullable=True),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("monthly_amount", sa.Integer(), nullable=False),
        sa.Column("savings_account_id", sa.Integer(), nullable=False),
        sa.Column("status", goal_status, nullable=False),
        sa.ForeignKeyConstraint(["savings_account_id"], ["account.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("transaction") as batch_op:
            batch_op.add_column(sa.Column("goal_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(GOAL_FK, "goal", ["goal_id"], ["id"])
    else:
        op.add_column("transaction", sa.Column("goal_id", sa.Integer(), nullable=True))
        op.create_foreign_key(GOAL_FK, "transaction", "goal", ["goal_id"], ["id"])
    op.create_table(
        "goal_contribution",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("goal_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("source", contribution_source, nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["goal_id"], ["goal.id"]),
        sa.ForeignKeyConstraint(["transaction_id"], ["transaction.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(CONTRIBUTION_INDEX, "goal_contribution", ["goal_id", "date"], unique=False)
