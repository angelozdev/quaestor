from datetime import date
from decimal import Decimal

from quaestor.mcp import format
from quaestor.mcp.tools import temporal
from quaestor.mcp.tools.temporal import (
    ArchiveRecurringInput,
    ConfirmPaymentInput,
    CreateRecurringInput,
    ListRecurringInput,
    PlanPaymentInput,
    SkipPaymentInput,
    SkipRecurringInput,
    ToPayInput,
    UpdateRecurringInput,
)
from quaestor.services import accounts, fx


def _bank(session):
    return accounts.create_account(session, "Bancolombia", "debit", "COP", balance=10_000_000)


def test_create_recurring_tool(session):
    _bank(session)
    out = temporal.create_recurring(session, CreateRecurringInput(
        name="Rent", payee="Landlord", type="expense", mode="auto",
        amount=2_000_000, account="Bancolombia", interval_unit="month",
        interval_count=1, start_date=date(2026, 1, 1),
    ))
    assert "Rent" in out and "id=" in out


def test_create_recurring_unknown_account_returns_text(session):
    out = temporal.create_recurring(session, CreateRecurringInput(
        name="Rent", payee="Landlord", type="expense", mode="auto",
        amount=2_000_000, account="Nope", interval_unit="month",
        interval_count=1, start_date=date(2026, 1, 1),
    ))
    assert "not found" in out


def test_list_recurring_tool(session):
    _bank(session)
    temporal.create_recurring(session, CreateRecurringInput(
        name="Rent", payee="Landlord", type="expense", mode="auto",
        amount=2_000_000, account="Bancolombia", interval_unit="month",
        interval_count=1, start_date=date(2026, 1, 1),
    ))
    out = temporal.list_recurring(session, ListRecurringInput())
    assert "Rent" in out


def test_plan_confirm_to_pay_skip_flow(session):
    _bank(session)
    fx.set_trm(session, "4000")
    planned_out = temporal.plan_payment(session, PlanPaymentInput(
        payee="Friend", amount=80_000, account="Bancolombia", due_date=date(2026, 6, 20),
    ))
    assert "Friend" in planned_out and "id=" in planned_out

    to_pay_out = temporal.to_pay(session, ToPayInput(since=date(2026, 6, 1), until=date(2026, 6, 30)))
    assert "Friend" in to_pay_out and "## ⚠️ Overdue" in to_pay_out

    # extract the planned tx id from the queue
    from quaestor.services import transactions
    tx_id = transactions.list_transactions(session, status="planned")[0].id
    confirmed = temporal.confirm_payment(session, ConfirmPaymentInput(tx_id=tx_id, amount=85_000))
    assert "Confirmed" in confirmed


def test_to_pay_without_trm_returns_missing_rate_text(session):
    _bank(session)
    temporal.plan_payment(session, PlanPaymentInput(
        payee="Friend", amount=80_000, account="Bancolombia", due_date=date(2026, 6, 20),
    ))
    out = temporal.to_pay(session, ToPayInput(since=date(2026, 6, 1), until=date(2026, 6, 30)))
    assert "No TRM is set" in out
    assert "set_fx_rate" in out


def test_confirm_non_planned_returns_text(session):
    _bank(session)
    from quaestor.services import transactions
    tx = transactions.record_expense(session, 1, 1000, "COP", date(2026, 6, 1), "x")
    out = temporal.confirm_payment(session, ConfirmPaymentInput(tx_id=tx.id))
    assert "Can't do that" in out


def test_skip_payment_tool(session):
    _bank(session)
    temporal.plan_payment(session, PlanPaymentInput(
        payee="Friend", amount=80_000, account="Bancolombia", due_date=date(2026, 6, 20),
    ))
    from quaestor.services import transactions
    tx_id = transactions.list_transactions(session, status="planned")[0].id
    out = temporal.skip_payment(session, SkipPaymentInput(tx_id=tx_id))
    assert "Skipped" in out


def test_skip_recurring_tool(session):
    _bank(session)
    temporal.create_recurring(session, CreateRecurringInput(
        name="Water", payee="Utility", type="expense", mode="manual",
        amount=50_000, account="Bancolombia", interval_unit="month",
        interval_count=1, start_date=date(2026, 1, 5),
    ))
    from quaestor.services import recurring
    item_id = recurring.list_recurring(session)[0].id
    out = temporal.skip_recurring(session, SkipRecurringInput(
        recurring_id=item_id, due_date=date(2026, 1, 5),
    ))
    assert "Skipped" in out


def test_register_temporal_tools_exposes_all_nine():
    import asyncio
    from mcp.server.fastmcp import FastMCP
    from quaestor.mcp.registry import TEMPORAL_TOOL_NAMES, register_temporal_tools

    mcp = FastMCP("test")
    register_temporal_tools(mcp)
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert names == set(TEMPORAL_TOOL_NAMES)
    assert len(TEMPORAL_TOOL_NAMES) == 9


def test_mcp_update_recurring(session):
    _bank(session)
    temporal.create_recurring(session, CreateRecurringInput(
        name="Rent", payee="Landlord", type="expense", mode="auto",
        amount=2_000_000, account="Bancolombia", interval_unit="month",
        interval_count=1, start_date=date(2026, 1, 1),
    ))
    from quaestor.services import recurring as _rec_svc
    item_id = _rec_svc.list_recurring(session)[0].id
    out = temporal.update_recurring(session, UpdateRecurringInput(
        recurring_id=item_id, amount=5_000_000
    ))
    assert "5" in out  # formatted amount appears
    assert _rec_svc.list_recurring(session)[0].amount == 5_000_000


def test_mcp_archive_recurring(session):
    _bank(session)
    temporal.create_recurring(session, CreateRecurringInput(
        name="Rent", payee="Landlord", type="expense", mode="auto",
        amount=2_000_000, account="Bancolombia", interval_unit="month",
        interval_count=1, start_date=date(2026, 1, 1),
    ))
    from quaestor.services import recurring as _rec_svc
    item_id = _rec_svc.list_recurring(session)[0].id
    temporal.archive_recurring(session, ArchiveRecurringInput(recurring_id=item_id))
    assert _rec_svc.list_recurring(session, active=True) == []


def test_to_pay_table_renders_two_sections(session):
    from datetime import date as Date
    from quaestor.domain.planned import OutstandingQueue
    from quaestor.domain.models import AccountType
    from quaestor.services import accounts, planned

    a = accounts.create_account(session, "Bank", AccountType.debit, "COP", balance=10_000_000)
    overdue = planned.plan_payment(
        session, "Tigo", 8_500_00, "COP", Date(2026, 6, 28), a.id,
    )
    upcoming = planned.plan_payment(
        session, "Rent", 5_000_00, "COP", Date(2026, 7, 15), a.id,
    )
    queue = OutstandingQueue(overdue=[overdue], upcoming=[upcoming])
    out = format.to_pay_table(queue, Decimal("4000"))
    assert "## ⚠️ Overdue" in out
    assert "## Upcoming" in out
    assert "Tigo" in out
    assert "Rent" in out
    assert out.index("## ⚠️ Overdue") < out.index("## Upcoming")


def test_to_pay_table_omits_empty_overdue_section(session):
    from datetime import date as Date
    from quaestor.domain.planned import OutstandingQueue
    from quaestor.domain.models import AccountType
    from quaestor.services import accounts, planned

    a = accounts.create_account(session, "Bank", AccountType.debit, "COP", balance=10_000_000)
    upcoming = planned.plan_payment(
        session, "Rent", 5_000_00, "COP", Date(2026, 7, 15), a.id,
    )
    queue = OutstandingQueue(overdue=[], upcoming=[upcoming])
    out = format.to_pay_table(queue, Decimal("4000"))
    assert "## ⚠️ Overdue" not in out
    assert "## Upcoming" in out


def test_to_pay_table_omits_empty_upcoming_section(session):
    from datetime import date as Date
    from quaestor.domain.planned import OutstandingQueue
    from quaestor.domain.models import AccountType
    from quaestor.services import accounts, planned

    a = accounts.create_account(session, "Bank", AccountType.debit, "COP", balance=10_000_000)
    overdue = planned.plan_payment(
        session, "Tigo", 8_500_00, "COP", Date(2026, 6, 28), a.id,
    )
    queue = OutstandingQueue(overdue=[overdue], upcoming=[])
    out = format.to_pay_table(queue, Decimal("4000"))
    assert "## ⚠️ Overdue" in out
    assert "## Upcoming" not in out


def test_to_pay_table_empty_queue():
    from quaestor.domain.planned import OutstandingQueue

    out = format.to_pay_table(OutstandingQueue(), Decimal("4000"))
    assert out == "Nothing outstanding."
