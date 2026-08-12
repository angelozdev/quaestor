"""Two obligations go back to the price the merchant charges.

Hevy Pro costs 99.900 COP a year and Smart Fit 120.000 COP a month; both are
debited from DolarApp, which holds dollars. Until ADR-0053 an obligation had to
be stated in its account's currency, so both were written as the conversion of
the day they were created — 30,22 USD and 37,20 USD — and both have been drifting
since, because the rate moves and the price does not.

**The prices are carried, not computed.** Converting the stored 30,22 USD at
today's rate gives 94.951 COP against a real 99.900, and 37,20 USD gives 116.882
against a real 120.000: the rate that wrote them (~3.306) survives nowhere, and
ADR-0031 removed frozen per-transaction rates on purpose. A migration that
converted would write two fresh wrong numbers — the defect this is repairing.

Both are left waiting for approval. An obligation that posts itself copies its
own figure onto its account's balance, so a peso price charging a dollar account
would add pesos to a dollar balance; ADR-0053 forbids the pair, and the owner
chose confirming by hand over losing the price. Both already wait for approval in
production, so this half writes nothing there — it is here so the revision is
also correct on a database where they do not.

**The way back restores the two prices and nothing else.** It deliberately does
not touch the mode: the revision cannot know what the mode was before it ran, and
guessing wrong in that direction switches automatic charging *on* — a rollback
that starts moving money by itself is worse than the drift it is undoing.

Every row is matched on name, amount and currency together. A database that does
not hold exactly those rows — a test one, the sandbox, a fresh install — matches
nothing and is left untouched.

Revision ID: 0017
Revises: 0016
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | Sequence[str] | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_RESTATED = (
    {"name": "Hevy Pro", "was": (3022, "USD"), "now": (9990000, "COP")},
    {"name": "Smart Fit", "was": (3720, "USD"), "now": (12000000, "COP")},
)

_MODE = sa.Enum("auto", "manual", name="recurringmode")
_WAITING = sa.cast("manual", _MODE)
"""Cast, because `mode` is a native enum in Postgres and a bare string is refused there."""

_RECURRING = sa.table(
    "recurring_item",
    sa.column("name", sa.String),
    sa.column("amount", sa.Integer),
    sa.column("currency", sa.String),
    sa.column("mode", _MODE),
)


def _restate(connection, name: str, frm: tuple[int, str], to: tuple[int, str], **also) -> None:
    connection.execute(
        _RECURRING.update()
        .where(_RECURRING.c.name == name, _RECURRING.c.amount == frm[0], _RECURRING.c.currency == frm[1])
        .values(amount=to[0], currency=to[1], **also)
    )


def restate_stored_prices(session) -> None:
    """Apply the restatement through an open session — the acceptance path."""
    _restate_all(session.connection())


def _restate_all(connection) -> None:
    for row in _RESTATED:
        _restate(connection, row["name"], row["was"], row["now"], mode=_WAITING)


def upgrade() -> None:
    _restate_all(op.get_bind())


def downgrade() -> None:
    connection = op.get_bind()
    for row in _RESTATED:
        _restate(connection, row["name"], row["now"], row["was"])
