from datetime import date

import pytest
from quaestor.db import init_db, make_engine
from quaestor.domain.models import (
    IntervalUnit,
    OccurrenceStatus,
    RecurringItem,
    RecurringMode,
    RecurringOccurrence,
    TxStatus,
    TxType,
)
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session


@pytest.fixture
def session():
    engine = make_engine(memory=True)
    init_db(engine)
    with Session(engine) as s:
        yield s


def test_skipped_status_exists():
    assert TxStatus.skipped.value == "skipped"


def test_create_recurring_item_and_occurrence(session):
    item = RecurringItem(
        name="Rent", payee="Landlord", type=TxType.expense, mode=RecurringMode.auto,
        amount=2_000_000, currency="COP", account_id=1,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 1, 1),
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    assert item.id is not None and item.active is True

    occ = RecurringOccurrence(
        recurring_id=item.id, due_date=date(2026, 1, 1), status=OccurrenceStatus.planned,
    )
    session.add(occ)
    session.commit()
    session.refresh(occ)
    assert occ.id is not None and occ.transaction_id is None


def test_unique_recurring_due_date(session):
    item = RecurringItem(
        name="Water", payee="Utility", type=TxType.expense, mode=RecurringMode.manual,
        amount=50_000, currency="COP", account_id=1,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=date(2026, 1, 1),
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    session.add(RecurringOccurrence(recurring_id=item.id, due_date=date(2026, 1, 5), status=OccurrenceStatus.planned))
    session.commit()
    session.add(RecurringOccurrence(recurring_id=item.id, due_date=date(2026, 1, 5), status=OccurrenceStatus.planned))
    with pytest.raises(IntegrityError):
        session.commit()
