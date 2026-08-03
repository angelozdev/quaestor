from datetime import date

from quaestor.mcp.tools import recurring_restore
from quaestor.mcp.tools.temporal import (
    ArchiveRecurringInput,
    CreateRecurringInput,
)
from quaestor.services import accounts, recurring


def _seed(session):
    accounts.create_account(session, "Bancolombia", "debit", "COP", balance=10_000_000)
    from quaestor.mcp.tools.temporal import create_recurring

    create_recurring(
        session,
        CreateRecurringInput(
            name="Rent",
            payee="Landlord",
            type="expense",
            mode="auto",
            amount=2_000_000,
            account="Bancolombia",
            interval_unit="month",
            interval_count=1,
            start_date=date(2026, 1, 1),
        ),
    )
    return recurring.list_recurring(session)[0].id


def test_archive_recurring_renamed(session):
    """The `delete_recurring` name is gone; `archive_recurring` exists and works."""
    from quaestor.mcp.tools import temporal

    item_id = _seed(session)
    out = temporal.archive_recurring(session, ArchiveRecurringInput(recurring_id=item_id))
    assert "Deactivated" in out
    assert recurring.list_recurring(session, active=True) == []


def test_restore_recurring_roundtrip(session):
    item_id = _seed(session)
    from quaestor.mcp.tools.temporal import archive_recurring

    archive_recurring(session, ArchiveRecurringInput(recurring_id=item_id))
    out = recurring_restore.restore_recurring(session, recurring_restore.RestoreRecurringInput(recurring_id=item_id))
    # Controller decision: format.recurring_restored body uses lowercase "restored".
    assert "restored" in out
    assert len(recurring.list_recurring(session, active=True)) == 1
