"""a fund that filled charges becomes one per charge (ADR-0057 / feature 015, AC-6)

Data only. The schema arrived at 0019; this is the revision that moves rows, so
it runs with the owner present and behind a fresh backup (CHARTER §7, ADR-0030).

Measured against production on 2026-08-15, read-only: exactly **one** fund uses
the `from_recurring` rule — 🛡️ Auto Insurance — and it fills for two yearly
charges, Seguro del Carro at 7.000.000 and SOAT carro at 447.300. So the real
migration is 1 → 2, and Fondos goes from 5 rows to 6. The four `average` funds
are not touched: their rule still hangs off a category and always will.

**The sum cannot move, and it cannot move by construction rather than by care.**
Each new fund keeps the old one's `start_month` and `accumulates`, and asks the
same division it was already asking — *what is missing ÷ the months left before
its charge*. The old fund's figure was the sum of exactly those terms
(`_ask_from_obligations` computed them per charge and added them), so splitting
the owner into one per charge re-adds the same addends. 636.363,64 + 49.700,00 =
686.063,64, before and after.

Every live expense charge of the category is migrated, with no exception made
for one that leaves no month to save in. That looks like it contradicts the rule
that only a spreadable charge may be *marked*, and it does not: marking is the
path that creates a fund, and this is not marking. A monthly charge asks its
whole amount under either owner — the divisor floors at one month either way —
so skipping it would be the thing that moved the figure. What the owner gets is
a row he can unmark, which is more than he had.

A fund carrying `anchor_amount` is refused rather than split. `claim_holdings`
would be the obvious rule for dividing it, but choosing it silently would freeze
a distribution the read path recomputes every time (ADR-0043), and that is the
owner's decision to make, not this revision's. No fund in production carries
one, so the refusal has no case today — it is here so that a future one stops
instead of guessing.

`downgrade` puts the category fund back and drops the per-charge ones. It can
only do that where every charge fund of a category shares one `start_month`,
which is what this revision produces; a set the owner has since edited apart
cannot be rejoined and is refused.

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | Sequence[str] | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FILLS_CHARGES = "from_recurring"

_CATEGORY_FUNDS = sa.text(
    "SELECT id, category_id, start_month, accumulates, anchor_month, anchor_amount "
    "FROM fund WHERE rule = :rule AND recurring_id IS NULL ORDER BY id"
)

_LIVE_CHARGES_OF = sa.text(
    "SELECT id, name FROM recurring_item "
    "WHERE category_id = :category_id AND type = 'expense' AND active = true ORDER BY id"
)

_MAKE_CHARGE_FUND = sa.text(
    "INSERT INTO fund (category_id, recurring_id, rule, start_month, accumulates) "
    "VALUES (:category_id, :recurring_id, :rule, :start_month, :accumulates)"
)

_DROP_FUND = sa.text("DELETE FROM fund WHERE id = :id")


def split_category_funds_into_charge_funds(connection) -> list[str]:
    """Give every charge of a category-wide obligations fund a fund of its own.

    Returns the names of the charges that got one, so a caller can report what
    moved instead of trusting that something did.

    Raises:
        RuntimeError: a fund states a balance, which cannot be divided without
            the owner deciding how.
    """
    moved: list[str] = []
    for fund in connection.execute(_CATEGORY_FUNDS, {"rule": _FILLS_CHARGES}).mappings().all():
        if fund["anchor_amount"] is not None:
            raise RuntimeError(
                f"fund {fund['id']} states a balance of {fund['anchor_amount']}, and dividing it between "
                f"its charges is the owner's decision — see ADR-0057. Clear the balance or split it by hand first."
            )
        charges = connection.execute(_LIVE_CHARGES_OF, {"category_id": fund["category_id"]}).mappings().all()
        for charge in charges:
            connection.execute(
                _MAKE_CHARGE_FUND,
                {
                    "category_id": fund["category_id"],
                    "recurring_id": charge["id"],
                    "rule": _FILLS_CHARGES,
                    "start_month": fund["start_month"],
                    "accumulates": fund["accumulates"],
                },
            )
            moved.append(charge["name"])
        connection.execute(_DROP_FUND, {"id": fund["id"]})
    return moved


def rejoin_charge_funds_into_category_funds(connection) -> list[int]:
    """Put one fund back on each category whose charges carry one.

    Raises:
        RuntimeError: the charge funds of one category no longer agree on the
            month they started, so there is no single fund they came from.
    """
    rejoined: list[int] = []
    grouped: dict[int, list] = {}
    rows = (
        connection.execute(
            sa.text(
                "SELECT id, category_id, start_month, accumulates FROM fund "
                "WHERE rule = :rule AND recurring_id IS NOT NULL ORDER BY id"
            ),
            {"rule": _FILLS_CHARGES},
        )
        .mappings()
        .all()
    )
    for row in rows:
        grouped.setdefault(row["category_id"], []).append(row)
    for category_id, funds in grouped.items():
        months = {fund["start_month"] for fund in funds}
        if len(months) > 1:
            raise RuntimeError(
                f"the charge funds on category {category_id} start in {sorted(months)}, so they cannot be "
                f"rejoined into the one fund they came from"
            )
        connection.execute(
            sa.text(
                "INSERT INTO fund (category_id, recurring_id, rule, start_month, accumulates) "
                "VALUES (:category_id, NULL, :rule, :start_month, :accumulates)"
            ),
            {
                "category_id": category_id,
                "rule": _FILLS_CHARGES,
                "start_month": months.pop(),
                "accumulates": funds[0]["accumulates"],
            },
        )
        for fund in funds:
            connection.execute(_DROP_FUND, {"id": fund["id"]})
        rejoined.append(category_id)
    return rejoined


def upgrade() -> None:
    moved = split_category_funds_into_charge_funds(op.get_bind())
    print(f"[0020] charges that got a fund of their own: {moved or 'none'}")


def downgrade() -> None:
    rejoined = rejoin_charge_funds_into_category_funds(op.get_bind())
    print(f"[0020] categories given their fund back: {rejoined or 'none'}")
