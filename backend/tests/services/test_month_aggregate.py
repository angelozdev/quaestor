from datetime import date
from decimal import Decimal

import pytest
from quaestor.db import init_db, make_engine
from quaestor.domain.errors import ValidationError
from quaestor.domain.models import (
    Account,
    AccountType,
    Category,
    Fund,
    FundRule,
    IntervalUnit,
    RecurringItem,
    RecurringMode,
    Transaction,
    TxStatus,
    TxType,
)
from quaestor.services.month_aggregate import load_month_aggregate, require_year_month
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


def test_a_malformed_month_is_refused_and_names_the_field_it_came_from():
    """One guard for three services, so a bad month reads the same everywhere."""
    with pytest.raises(ValidationError, match="target_month"):
        require_year_month("2026-13", "target_month")
    with pytest.raises(ValidationError):
        require_year_month("June")
    assert require_year_month("2026-06") == "2026-06"


BOUNDED_LOADS = 13
"""The ceiling one month load is held under (ADR-0028), asserted with `<=`.

Eight before feature 003, ten after it, fourteen after 009 — which added the
metas, their contributions, their amendments and the movements linked to them —
and thirteen once the month's expense and income windows became one statement
split in memory, which is the slot 009 bought back.
The measured count equals the ceiling, so there is no headroom left and the
next query added to `load_month_aggregate` fails this test on purpose. Raising
the number is a decision about the read path, not a
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


def _planned(acc_id, cat_id, d, amount):
    return Transaction(
        date=d,
        type=TxType.expense,
        status=TxStatus.planned,
        amount=amount,
        currency="COP",
        account_id=acc_id,
        category_id=cat_id,
        payee="seed",
    )


def test_a_movement_on_the_first_or_last_day_belongs_to_that_month(session):
    """The window is inclusive at both ends, and both ends are ordinary days.

    Rent falls on the first and card statements on the last, so a month that
    reads them out is a month missing its two biggest rows. Every figure the
    app shows is folded from this window, and nothing pinned its edges.
    """
    acc, cat = _setup(session)
    spent = ((date(2026, 6, 1), 222_000_00), (date(2026, 6, 15), 333_000_00), (date(2026, 6, 30), 444_000_00))
    for day, amount in spent:
        session.add(_expense(acc.id, cat.id, day, amount))
    session.add(_expense(acc.id, cat.id, date(2026, 5, 1), 111_000_00))
    session.commit()

    agg = load_month_aggregate(session, "2026-06", TRM)

    assert sum(agg.to_cop_cents(t) for t in agg.month_expense()) == 999_000_00
    assert sum(agg.to_cop_cents(t) for t in agg.posted_in_month("2026-05", TxType.expense)) == 111_000_00


def test_a_bill_planned_for_the_first_or_last_day_is_one_the_month_owes(session):
    """Same two edges, on the money the month has promised rather than spent."""
    acc, cat = _setup(session)
    owed = ((date(2026, 6, 1), 999_000_00), (date(2026, 6, 20), 100_000_00), (date(2026, 6, 30), 777_000_00))
    for day, amount in owed:
        session.add(_planned(acc.id, cat.id, day, amount))
    session.commit()

    agg = load_month_aggregate(session, "2026-06", TRM)

    assert sum(agg.to_cop_cents(t) for t in agg.month_planned_expense) == 1_876_000_00


def test_a_purchase_on_the_last_day_still_counts_against_its_meta(session):
    """The meta's own window has the same far edge, and it was unpinned too."""
    from quaestor.domain.models import Meta

    acc, cat = _setup(session)
    meta = Meta(name="Portatil", amount=5_000_000_00, currency="COP", target_month="2027-08", start_month="2026-06")
    session.add(meta)
    session.commit()
    session.refresh(meta)
    for day, amount in ((date(2026, 6, 20), 100_000_00), (date(2026, 6, 30), 900_000_00)):
        row = _expense(acc.id, cat.id, day, amount)
        row.meta_id = meta.id
        session.add(row)
    session.commit()

    agg = load_month_aggregate(session, "2026-06", TRM)

    assert sum(agg.to_cop_cents(t) for t in agg.linked_to(meta.id)) == 1_000_000_00


def test_a_movement_with_no_category_has_no_group(session):
    """Asked of every row the report groups, and an uncategorized one is a row.

    Answering it must not depend on the category being there — the whole point
    of the question is that it may not be.
    """
    _setup(session)
    agg = load_month_aggregate(session, "2026-06", TRM)

    assert agg.group_name(None) is None


def _charge_with_its_own_fund(session, acc_id, cat_id):
    item = RecurringItem(
        name="Comida a domicilio",
        type=TxType.expense,
        mode=RecurringMode.manual,
        amount=15_000_00,
        currency="COP",
        category_id=cat_id,
        account_id=acc_id,
        interval_unit=IntervalUnit.month,
        interval_count=6,
        start_date=date(2026, 1, 1),
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    session.add(Fund(category_id=cat_id, recurring_id=item.id, rule=FundRule.from_recurring, start_month="2026-01"))
    session.commit()
    return item


def test_a_charge_settled_under_its_own_fund_is_missing_from_spent_in(session):
    """Pins the exclusion `spent_in`'s own docstring names (ADR-0057), so the
    fold below is proven against a real gap rather than an assumed one."""
    acc, cat = _setup(session)
    item = _charge_with_its_own_fund(session, acc.id, cat.id)
    session.add(_expense(acc.id, cat.id, date(2026, 2, 5), 35_000_00))
    settlement = _expense(acc.id, cat.id, date(2026, 2, 10), 15_000_00)
    settlement.recurring_id = item.id
    session.add(settlement)
    session.commit()

    agg = load_month_aggregate(session, "2026-08", TRM)

    assert agg.spent_in(cat.id, "2026-02") == 35_000_00


def test_category_month_totals_folds_a_settled_charges_own_fund_back_in(session):
    acc, cat = _setup(session)
    item = _charge_with_its_own_fund(session, acc.id, cat.id)
    session.add(_expense(acc.id, cat.id, date(2026, 2, 5), 35_000_00))
    settlement = _expense(acc.id, cat.id, date(2026, 2, 10), 15_000_00)
    settlement.recurring_id = item.id
    session.add(settlement)
    session.commit()

    agg = load_month_aggregate(session, "2026-08", TRM)

    assert agg.category_month_totals(["2026-02"])[(cat.id, "2026-02")] == 50_000_00


def test_category_month_totals_only_returns_the_requested_months(session):
    acc, cat = _setup(session)
    session.add(_expense(acc.id, cat.id, date(2026, 5, 10), 60_000))
    session.add(_expense(acc.id, cat.id, date(2026, 6, 10), 30_000))
    session.commit()

    agg = load_month_aggregate(session, "2026-06", TRM)
    totals = agg.category_month_totals(["2026-06"])

    assert totals == {(cat.id, "2026-06"): 30_000}


def test_category_month_totals_folds_in_a_settled_charge_with_nothing_else_that_month(session):
    """A month whose only spend is a fund-per-charge settlement has no prior
    entry in `_spent_by_cat_month`, so the fold's `.get(key, 0)` default is
    what actually produces the figure rather than being masked by a plain
    expense already occupying the key."""
    acc, cat = _setup(session)
    item = _charge_with_its_own_fund(session, acc.id, cat.id)
    settlement = _expense(acc.id, cat.id, date(2026, 2, 10), 15_000_00)
    settlement.recurring_id = item.id
    session.add(settlement)
    session.commit()

    agg = load_month_aggregate(session, "2026-08", TRM)

    assert agg.category_month_totals(["2026-02"]) == {(cat.id, "2026-02"): 15_000_00}


def test_category_month_totals_excludes_a_settled_charge_outside_the_requested_months(session):
    """A settled charge's own category is not None, so the guard must still
    catch it on the month leg alone — an `or` mutated to `and` would let a
    charge outside the requested window leak in as long as it has a
    category."""
    acc, cat = _setup(session)
    item = _charge_with_its_own_fund(session, acc.id, cat.id)
    settlement = _expense(acc.id, cat.id, date(2026, 2, 10), 15_000_00)
    settlement.recurring_id = item.id
    session.add(settlement)
    session.commit()

    agg = load_month_aggregate(session, "2026-08", TRM)

    assert agg.category_month_totals(["2026-06"]) == {}


def test_a_settled_charge_with_no_fund_of_its_own_counts_normally(session):
    """No `Fund` row means `load_month_aggregate` never diverts it out of
    `_spent_by_cat_month` in the first place — the fold has nothing to add."""
    acc, cat = _setup(session)
    item = RecurringItem(
        name="Gimnasio",
        type=TxType.expense,
        mode=RecurringMode.manual,
        amount=15_000_00,
        currency="COP",
        category_id=cat.id,
        account_id=acc.id,
        interval_unit=IntervalUnit.month,
        interval_count=6,
        start_date=date(2026, 1, 1),
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    settlement = _expense(acc.id, cat.id, date(2026, 2, 10), 15_000_00)
    settlement.recurring_id = item.id
    session.add(settlement)
    session.commit()

    agg = load_month_aggregate(session, "2026-08", TRM)

    assert agg.category_month_totals(["2026-02"]).get((cat.id, "2026-02"), 0) == 15_000_00
