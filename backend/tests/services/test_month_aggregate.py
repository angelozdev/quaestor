from datetime import date
from decimal import Decimal

import pytest
from quaestor.db import init_db, make_engine
from quaestor.domain.models import (
    Account,
    AccountType,
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
        date=d,
        type=TxType.expense,
        status=TxStatus.posted,
        amount=amount,
        currency="COP",
        account_id=acc_id,
        category_id=cat_id,
        payee="seed",
    )


def _setup(session):
    acc = Account(name="Bank", type=AccountType.debit, currency="COP")
    cat = Category(name="Food")
    session.add(acc)
    session.add(cat)
    session.commit()
    session.refresh(acc)
    session.refresh(cat)
    return acc, cat


def test_spending_is_summed_per_category_and_month(session):
    acc, cat = _setup(session)
    session.add(_expense(acc.id, cat.id, date(2026, 5, 10), 60_000))
    session.add(_expense(acc.id, cat.id, date(2026, 6, 10), 30_000))
    session.add(_expense(acc.id, cat.id, date(2026, 6, 20), 5_000))
    session.commit()

    agg = load_month_aggregate(session, "2026-06", TRM)
    assert agg.spent_in(cat.id, "2026-05") == 60_000
    assert agg.spent_in(cat.id, "2026-06") == 35_000


def test_a_month_the_category_never_spent_in_is_zero(session):
    _, cat = _setup(session)
    agg = load_month_aggregate(session, "2026-06", TRM)
    assert agg.spent_in(cat.id, "2026-06") == 0


BOUNDED_LOADS = 10
"""The ceiling one month load is held under (ADR-0028), asserted with `<=`.

The ceiling was already ten before feature 003 and has not moved. What moved
is the measured count: eight before, ten now — three statements added and one
dropped with the `budget` table, the +2 the plan budgeted. So there is no
headroom left, and the next query added to `load_month_aggregate` fails this
test on purpose. Raising the number is a decision about the read path, not a
repair to the test.

The ten: the categories, the groups, the per-category-and-month spending
sums, the expense and income windows, the active recurring items, the month's
planned expenses, the funds, the first posted movement (AC-3 needs to know
which months the app has data for) and the skipped turns (AC-17).
"""


def test_load_issues_bounded_query_count(session):
    acc, cat = _setup(session)
    for i in range(200):
        session.add(_expense(acc.id, cat.id, date(2026, 6, 1 + (i % 27)), 1_000))
    session.commit()
    with count_queries(session) as c:
        agg = load_month_aggregate(session, "2026-06", TRM)
        # Force full in-memory computation:
        agg.totals_for("2026-06")
        agg.spent_in(cat.id, "2026-06")
    assert c.count <= BOUNDED_LOADS, f"expected bounded loads, got {c.count}"


def test_a_category_excluded_from_totals_does_not_reach_the_month(session):
    acc = Account(name="Bank", type=AccountType.debit, currency="COP")
    cat = Category(name="Transfers", exclude_from_totals=True)
    session.add(acc)
    session.add(cat)
    session.commit()
    session.refresh(acc)
    session.refresh(cat)
    session.add(_expense(acc.id, cat.id, date(2026, 6, 3), 500_000))
    session.commit()
    agg = load_month_aggregate(session, "2026-06", TRM)
    assert agg.month_expense() == []
