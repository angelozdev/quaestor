from datetime import date
from decimal import Decimal

import pytest
from quaestor.db import init_db, make_engine
from quaestor.domain.models import (
    Account,
    AccountType,
    Budget,
    Category,
    Transaction,
    TxStatus,
    TxType,
)
from quaestor.services.month_aggregate import load_month_aggregate
from sqlmodel import Session

from tests.support.query_counter import count_queries


@pytest.fixture
def session():
    engine = make_engine(memory=True)
    init_db(engine)
    with Session(engine) as s:
        yield s


TRM = Decimal("4000")


def _expense(acc_id, cat_id, d, amount):
    return Transaction(
        date=d, type=TxType.expense, status=TxStatus.posted, amount=amount,
        currency="COP", account_id=acc_id, category_id=cat_id, payee="seed",
    )


def _setup(session):
    acc = Account(name="Bank", type=AccountType.debit, currency="COP")
    cat = Category(name="Food")
    session.add(acc); session.add(cat); session.commit()
    session.refresh(acc); session.refresh(cat)
    return acc, cat


def test_rollover_folds_forward_without_recursion_queries(session):
    acc, cat = _setup(session)
    # May: assign 100k, spend 60k -> available 40k
    session.add(Budget(category_id=cat.id, year_month="2026-05", amount_assigned=100_000))
    session.add(_expense(acc.id, cat.id, date(2026, 5, 10), 60_000))
    # Jun: assign 100k, spend 30k, rollover_in 40k -> available 110k
    session.add(Budget(category_id=cat.id, year_month="2026-06", amount_assigned=100_000))
    session.add(_expense(acc.id, cat.id, date(2026, 6, 10), 30_000))
    session.commit()

    agg = load_month_aggregate(session, "2026-06", TRM)
    assert agg.assigned(cat.id, "2026-06") == 100_000
    assert agg.spent_for_budget(cat.id, "2026-06") == 30_000
    assert agg.available(cat.id, "2026-05") == 40_000
    assert agg.available(cat.id, "2026-06") == 110_000


def test_gap_month_resets_rollover(session):
    """A month with no assignment and no spending yields 0 and does NOT pass
    rollover forward — identical to the current recursion's base case."""
    acc, cat = _setup(session)
    session.add(Budget(category_id=cat.id, year_month="2026-04", amount_assigned=100_000))
    session.add(_expense(acc.id, cat.id, date(2026, 4, 10), 60_000))
    # 2026-05: gap (no budget, no spending)
    session.add(Budget(category_id=cat.id, year_month="2026-06", amount_assigned=50_000))
    session.add(_expense(acc.id, cat.id, date(2026, 6, 10), 10_000))
    session.commit()

    agg = load_month_aggregate(session, "2026-06", TRM)
    assert agg.available(cat.id, "2026-04") == 40_000
    assert agg.available(cat.id, "2026-05") == 0
    assert agg.available(cat.id, "2026-06") == 40_000  # gap reset: 0 + 50k - 10k


def test_load_issues_bounded_query_count(session):
    acc, cat = _setup(session)
    for i in range(200):
        session.add(_expense(acc.id, cat.id, date(2026, 6, 1 + (i % 27)), 1_000))
    session.commit()
    with count_queries(session) as c:
        agg = load_month_aggregate(session, "2026-06", TRM)
        # Force full in-memory computation:
        agg.totals_for("2026-06")
        agg.available(cat.id, "2026-06")
    assert c.count <= 10, f"expected bounded loads, got {c.count}"


def test_excluded_category_has_zero_budget_spend(session):
    acc = Account(name="Bank", type=AccountType.debit, currency="COP")
    cat = Category(name="Transfers", exclude_from_budget=True)
    session.add(acc); session.add(cat); session.commit()
    session.refresh(acc); session.refresh(cat)
    session.add(_expense(acc.id, cat.id, date(2026, 6, 3), 500_000))
    session.commit()
    agg = load_month_aggregate(session, "2026-06", TRM)
    assert agg.spent_for_budget(cat.id, "2026-06") == 0
