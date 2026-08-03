"""The model and the migration must state the same rule.

ADR-0041 declares the category CHECK twice on purpose: in
`Transaction.__table_args__`, which is what a developer reads, and in revision
0010, which is what the database actually has. Nothing enforced that they agree
until this test — the acceptance suite exercises the migrated schema through
the models, but never compares the two definitions, so an edit to either one
alone passed every gate.
"""

from __future__ import annotations

import re

import sqlalchemy as sa
from quaestor.domain.models import Transaction
from tests.support.migrations import engine_at_revision

CONSTRAINT_NAME = "ck_transaction_category_by_type"


def _normalised(expression: str) -> str:
    """Compare the rule, not the whitespace or the engine's rendering."""
    return re.sub(r"[\s()]+", " ", expression).strip().lower()


def _declared_on_the_model() -> str:
    constraint = next(
        arg for arg in Transaction.__table_args__ if isinstance(arg, sa.CheckConstraint) and arg.name == CONSTRAINT_NAME
    )
    return _normalised(str(constraint.sqltext))


def _installed_by_the_migration() -> str:
    engine = engine_at_revision("head")
    inspector = sa.inspect(engine)
    constraint = next(c for c in inspector.get_check_constraints("transaction") if c["name"] == CONSTRAINT_NAME)
    return _normalised(constraint["sqltext"])


def test_the_model_declares_the_constraint_the_migration_installs():
    assert _declared_on_the_model() == _installed_by_the_migration()


def test_the_constraint_states_the_rule_ADR_0041_describes():
    rule = _declared_on_the_model()
    assert "type in 'expense', 'income' and category_id is not null" in rule
    assert "type = 'transfer' and category_id is null" in rule
