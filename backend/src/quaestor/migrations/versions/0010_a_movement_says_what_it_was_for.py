"""a movement says what it was for (ADR-0041 / feature 008, AC-17/18)

Puts the mandatory-category rule in the schema, so the guarantee survives the
services layer being wrong or bypassed. The 131 uncategorised movements that
motivated the feature were produced by code working exactly as written.

Three things, in this order:

1. A pre-flight count. If any expense or income is still uncategorised — or any
   transfer carries a category — the revision refuses, naming how many and of
   which kind, and touches nothing. The change lands on clean data or does not
   land, and the failure is a sentence rather than an integrity error from a
   half-applied schema.
2. A CHECK on `transaction` that discriminates by movement type. A blanket
   NOT NULL would close the gap and break all 39 existing transfers in the same
   statement: a transfer between the owner's own accounts is neither spending
   nor income, and categorising one counts the same money twice.
3. NOT NULL on `recurring_item.category_id`. A recurring item is only ever an
   expense or an income (`create_recurring` refuses `transfer`), so it needs no
   discrimination — and since `occurrences._create_occurrence_tx` copies the
   category onto every charge, a source that cannot be empty cannot produce an
   uncategorised charge.

The constraint pins presence, not direction: that an income's category is an
income category stays a services-layer refusal (ADR-0042). Enforcing it here
would need a trigger or a denormalised copy of `category.is_income` on every
row, and no acceptance criterion asks for it.

SQLite cannot `ALTER TABLE ADD CONSTRAINT`, so it goes through
`batch_alter_table` (a table rebuild); Postgres gets a plain ALTER. Both paths
matter: the acceptance suite migrates an in-memory SQLite database to head, so
the same barrier protects the tests and the owner's data.

`downgrade` is a real reversal, unlike revision 0009's — dropping the
constraint loses nothing.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT_NAME = "ck_transaction_category_by_type"

CATEGORY_BY_TYPE = (
    "(type IN ('expense', 'income') AND category_id IS NOT NULL) OR (type = 'transfer' AND category_id IS NULL)"
)

_COUNT_OFFENDERS = sa.text(
    "SELECT COUNT(*) FILTER (WHERE type = 'expense' AND category_id IS NULL) AS \"expense\","
    " COUNT(*) FILTER (WHERE type = 'income' AND category_id IS NULL) AS \"income\","
    " COUNT(*) FILTER (WHERE type = 'transfer' AND category_id IS NOT NULL) AS \"transfer\""
    ' FROM "transaction"'
)


def _phrase(count: int, singular: str, plural: str) -> str:
    noun = singular if count == 1 else plural
    verb = "is" if count == 1 else "are"
    return f"{count} {noun} {verb}"


def _refusals(uncategorised_expenses: int, uncategorised_incomes: int, categorised_transfers: int) -> list[str]:
    found = []
    if uncategorised_expenses:
        found.append(f"{_phrase(uncategorised_expenses, 'expense', 'expenses')} still uncategorised")
    if uncategorised_incomes:
        found.append(f"{_phrase(uncategorised_incomes, 'income', 'incomes')} still uncategorised")
    if categorised_transfers:
        found.append(f"{_phrase(categorised_transfers, 'transfer', 'transfers')} carrying a category")
    return found


def _refuse_over_dirty_data() -> None:
    """Stop before touching the schema if any movement breaks the new rule."""
    expenses, incomes, transfers = op.get_bind().execute(_COUNT_OFFENDERS).one()
    found = _refusals(expenses, incomes, transfers)
    if not found:
        return
    raise RuntimeError(
        "[0010] refusing to make the category mandatory: "
        + ", and ".join(found)
        + ". Categorise them first — which category a movement belongs to is a "
        "decision per movement, not one a migration can make."
    )


def upgrade() -> None:
    _refuse_over_dirty_data()
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("transaction") as batch_op:
            batch_op.create_check_constraint(CONSTRAINT_NAME, CATEGORY_BY_TYPE)
        with op.batch_alter_table("recurring_item") as batch_op:
            batch_op.alter_column("category_id", existing_type=sa.Integer(), nullable=False)
    else:
        op.create_check_constraint(CONSTRAINT_NAME, "transaction", sa.text(CATEGORY_BY_TYPE))
        op.alter_column("recurring_item", "category_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("recurring_item") as batch_op:
            batch_op.alter_column("category_id", existing_type=sa.Integer(), nullable=True)
        with op.batch_alter_table("transaction") as batch_op:
            batch_op.drop_constraint(CONSTRAINT_NAME, type_="check")
    else:
        op.alter_column("recurring_item", "category_id", existing_type=sa.Integer(), nullable=True)
        op.drop_constraint(CONSTRAINT_NAME, "transaction", type_="check")
