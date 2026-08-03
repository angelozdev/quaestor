"""repeating incomes pay themselves (ADR-0035 / feature 007, AC-6)

Turns every existing repeating income that was waiting for approval into one
that records itself. A repeating income in `manual` mode produces a `planned`
income transaction, and the outstanding queue shows only money going out
(feature 006) — so that money sat waiting in a room with no door: no screen
could ever confirm it, and another one appeared every period.

`create_recurring` refuses the combination from now on. This revision closes
the rows that predate that rule.

Only the item's mode changes. Transactions already materialized are left
exactly as they are: posting them would move balances by amounts the user
never confirmed, and cancelling them would erase a record the user may still
want. Whichever of those is right is a decision per row, not a migration.

`downgrade` is deliberately a no-op: putting an income back to `manual` would
recreate the very orphan this closes, and the service layer would refuse to
save it anyway.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-02

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    result = op.get_bind().execute(
        sa.text("UPDATE recurring_item SET mode = 'auto' WHERE type = 'income' AND mode = 'manual'")
    )
    print(f"[0009] repeating incomes switched to automatic: {result.rowcount}")


def downgrade() -> None:
    """No-op — restoring `manual` would recreate the unconfirmable income."""
