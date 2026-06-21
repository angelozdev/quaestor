from datetime import date

from quaestor.mcp.tools import temporal
from quaestor.mcp.tools.temporal import (
    ConfirmPaymentInput,
    CreateRecurringInput,
    DeleteRecurringInput,
    ListRecurringInput,
    PlanPaymentInput,
    SkipPaymentInput,
    SkipRecurringInput,
    ToPayInput,
    UpdateRecurringInput,
)
from quaestor.services import accounts


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
    planned_out = temporal.plan_payment(session, PlanPaymentInput(
        payee="Friend", amount=80_000, account="Bancolombia", due_date=date(2026, 6, 20),
    ))
    assert "Friend" in planned_out and "id=" in planned_out

    to_pay_out = temporal.to_pay(session, ToPayInput(since=date(2026, 6, 1), until=date(2026, 6, 30)))
    assert "Friend" in to_pay_out and "To pay (COP)" in to_pay_out

    # extract the planned tx id from the queue
    from quaestor.services import transactions
    tx_id = transactions.list_transactions(session, status="planned")[0].id
    confirmed = temporal.confirm_payment(session, ConfirmPaymentInput(tx_id=tx_id, amount=85_000))
    assert "Confirmed" in confirmed


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
    item = temporal.create_recurring(session, CreateRecurringInput(
        name="Rent", payee="Landlord", type="expense", mode="auto",
        amount=2_000_000, account="Bancolombia", interval_unit="month",
        interval_count=1, start_date=date(2026, 1, 1),
    ))
    out = temporal.update_recurring(session, UpdateRecurringInput(
        recurring_id=int(item.split("id=")[1]), amount=5_000_000
    ))
    assert "5" in out  # formatted amount appears
    from quaestor.services import recurring
    assert recurring.list_recurring(session)[0].amount == 5_000_000


def test_mcp_delete_recurring(session):
    _bank(session)
    item = temporal.create_recurring(session, CreateRecurringInput(
        name="Rent", payee="Landlord", type="expense", mode="auto",
        amount=2_000_000, account="Bancolombia", interval_unit="month",
        interval_count=1, start_date=date(2026, 1, 1),
    ))
    item_id = int(item.split("id=")[1])
    temporal.delete_recurring(session, DeleteRecurringInput(recurring_id=item_id))
    from quaestor.services import recurring
    assert recurring.list_recurring(session, active=True) == []
