"""the fund no longer saves toward a date (product ADR-043 / ADR-0046)

**Destructive.** Drops `fund.target_amount`, `fund.target_month` and the
`target_by_date` value from the `fundrule` enum. Runs only after the code that
stops writing them is merged — the reverse order would leave the app reading
columns that are gone.

Nothing is converted, and that is a fact rather than a hope: the production
database was read read-only on 2026-08-08 and `SELECT rule, COUNT(*) FROM fund`
returned zero rows. The `confirm-no-dated-funds` step in the feature's runbook
takes that count again immediately before this runs, because a fact four days
old is not a fact.

Saving an amount by a date is said one way now, as a meta: a named thing with
an end, belonging to no category, linked to the purchase on the movement. The
rule's own shipped label was `Junto una cantidad para una fecha`, explained as
`Reparto lo que falta entre los meses que quedan` — a meta's definition word
for word, and only visible after committing to the noun *fondo*.

A dated **charge** is unaffected and keeps the rule that fits it: a fund reading
its category's obligations covers it and renews itself each cycle, which this
one never did.

Postgres cannot drop a value from an enum, so `fundrule` is rebuilt: a new type
without the value, the column cast across, the old type dropped. SQLite stores
the enum as text and needs only the column drops.

`downgrade` puts the columns and the value back, empty. It does **not** restore
what any row held, because no row held anything — the way back to data is the
dump, not the downgrade.

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-08

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WITHOUT = ("fixed", "average", "from_recurring")
WITH = ("fixed", "average", "from_recurring", "target_by_date")


def _refuse_over_dated_funds() -> None:
    bind = op.get_bind()
    left = bind.execute(sa.text("SELECT COUNT(*) FROM fund WHERE rule = 'target_by_date'")).scalar_one()
    if left:
        raise RuntimeError(
            f"[0015] refusing to withdraw the dated rule: {left} fund(s) still use it. "
            "Each one is a decision about what the owner was saving for — turn them into metas first."
        )


def _rebuild_enum(values: tuple[str, ...], previous: tuple[str, ...]) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    sa.Enum(*values, name="fundrule_new").create(bind)
    op.execute("ALTER TABLE fund ALTER COLUMN rule TYPE fundrule_new USING rule::text::fundrule_new")
    sa.Enum(*previous, name="fundrule").drop(bind)
    op.execute("ALTER TYPE fundrule_new RENAME TO fundrule")


def upgrade() -> None:
    _refuse_over_dated_funds()
    op.drop_column("fund", "target_amount")
    op.drop_column("fund", "target_month")
    _rebuild_enum(WITHOUT, WITH)


def downgrade() -> None:
    _rebuild_enum(WITH, WITHOUT)
    op.add_column("fund", sa.Column("target_month", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column("fund", sa.Column("target_amount", sa.BigInteger(), nullable=True))
