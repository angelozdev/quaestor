"""recurring engine enum values (ADR-0035, ADR-0038)

Adds two enum values: ``occurrencestatus.offered`` — a due date waiting for
the user's answer, which consumes the date without being a charge — and
``source.recurring`` — the engine as the author of a movement.

Postgres stores these as native enum types, so each value needs
``ALTER TYPE .. ADD VALUE``, which cannot run inside Alembic's transaction;
both go in an ``autocommit_block``. SQLite stores them as plain VARCHAR with
no CHECK constraint (``create_constraint`` defaults to False), so it needs
nothing — which is exactly why a migration that gets the Postgres side wrong
still passes the whole test suite.

``downgrade`` is deliberately a no-op: Postgres cannot drop an enum value, and
recreating the type would mean rewriting every dependent column and destroying
any row already using the value.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-02

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_NEW_VALUES = (
    ("occurrencestatus", "offered"),
    ("source", "recurring"),
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    with op.get_context().autocommit_block():
        for type_name, value in _NEW_VALUES:
            op.execute(f"ALTER TYPE {type_name} ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    """No-op — Postgres cannot remove a value from an enum type."""
