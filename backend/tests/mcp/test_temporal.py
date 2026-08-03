from datetime import date, timedelta
from decimal import Decimal

from quaestor.domain.dates import display_date
from quaestor.domain.planned import OutstandingQueue
from quaestor.mcp import format
from quaestor.mcp.tools import temporal
from quaestor.mcp.tools.temporal import (
    ArchiveRecurringInput,
    ConfirmPaymentInput,
    CreateRecurringInput,
    ListRecurringInput,
    PlanPaymentInput,
    RestorePaymentInput,
    SkipPaymentInput,
    SkipRecurringInput,
    ToPayInput,
    UpdateRecurringInput,
)
from quaestor.services import accounts, fx, planned


def _bank(session):
    return accounts.create_account(session, "Bancolombia", "debit", "COP", balance=10_000_000)


def test_create_recurring_tool(session):
    _bank(session)
    out = temporal.create_recurring(
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
    assert "Rent" in out and "id=" in out


def test_create_recurring_unknown_account_returns_text(session):
    out = temporal.create_recurring(
        session,
        CreateRecurringInput(
            name="Rent",
            payee="Landlord",
            type="expense",
            mode="auto",
            amount=2_000_000,
            account="Nope",
            interval_unit="month",
            interval_count=1,
            start_date=date(2026, 1, 1),
        ),
    )
    assert "not found" in out


def test_list_recurring_tool(session):
    _bank(session)
    temporal.create_recurring(
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
    out = temporal.list_recurring(session, ListRecurringInput())
    assert "Rent" in out


def test_plan_confirm_to_pay_skip_flow(session):
    _bank(session)
    fx.set_trm(session, "4000")
    planned_out = temporal.plan_payment(
        session,
        PlanPaymentInput(
            payee="Friend",
            amount=80_000,
            account="Bancolombia",
            due_date=date(2026, 6, 20),
        ),
    )
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
    temporal.plan_payment(
        session,
        PlanPaymentInput(
            payee="Friend",
            amount=80_000,
            account="Bancolombia",
            due_date=date(2026, 6, 20),
        ),
    )
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
    temporal.plan_payment(
        session,
        PlanPaymentInput(
            payee="Friend",
            amount=80_000,
            account="Bancolombia",
            due_date=date(2026, 6, 20),
        ),
    )
    from quaestor.services import transactions

    tx_id = transactions.list_transactions(session, status="planned")[0].id
    out = temporal.skip_payment(session, SkipPaymentInput(tx_id=tx_id))
    assert "Skipped" in out


def test_skip_recurring_tool(session):
    _bank(session)
    temporal.create_recurring(
        session,
        CreateRecurringInput(
            name="Water",
            payee="Utility",
            type="expense",
            mode="manual",
            amount=50_000,
            account="Bancolombia",
            interval_unit="month",
            interval_count=1,
            start_date=date(2026, 1, 5),
        ),
    )
    from quaestor.services import recurring

    item_id = recurring.list_recurring(session)[0].id
    out = temporal.skip_recurring(
        session,
        SkipRecurringInput(
            recurring_id=item_id,
            due_date=date(2026, 1, 5),
        ),
    )
    assert "Skipped" in out


def test_restore_payment_tool(session):
    _bank(session)
    temporal.plan_payment(
        session,
        PlanPaymentInput(
            payee="Claro",
            amount=85_000,
            account="Bancolombia",
            due_date=date(2026, 6, 20),
        ),
    )
    from quaestor.services import transactions

    tx_id = transactions.list_transactions(session, status="planned")[0].id
    temporal.skip_payment(session, SkipPaymentInput(tx_id=tx_id))
    out = temporal.restore_payment(session, RestorePaymentInput(tx_id=tx_id))
    assert "Restored" in out
    assert transactions.get_transaction(session, tx_id).status.value == "planned"


def test_restore_payment_confirmation_names_payee_amount_and_due_date(session):
    """AC-8 promises the payment comes back with its payee, amount and
    due date intact — the chat confirmation is where the user reads that,
    so the whole line is asserted, not just the verb."""
    a = _bank(session)
    tx = planned.plan_payment(session, "Claro", 85_000_00, "COP", date(2026, 7, 15), a.id)
    planned.skip_payment(session, tx.id)
    restored = planned.restore_payment(session, tx.id)
    assert format.payment_restored(restored) == (
        f"✅ Restored **Claro** — 85000.00 COP due {display_date(date(2026, 7, 15))}. id={tx.id} (back in the queue)"
    )


def test_restore_payment_tool_rejects_non_skipped(session):
    _bank(session)
    temporal.plan_payment(
        session,
        PlanPaymentInput(
            payee="Claro",
            amount=85_000,
            account="Bancolombia",
            due_date=date(2026, 6, 20),
        ),
    )
    from quaestor.services import transactions

    tx_id = transactions.list_transactions(session, status="planned")[0].id
    out = temporal.restore_payment(session, RestorePaymentInput(tx_id=tx_id))
    assert "Can't do that" in out


def test_restore_payment_is_write_destructive_and_hidden_from_llm():
    from quaestor.mcp.registry import LLM_ALLOWED_TOOLS, ToolTier, tool_tier

    assert tool_tier("restore_payment") == ToolTier.WRITE_DESTRUCTIVE
    assert "restore_payment" not in LLM_ALLOWED_TOOLS


def test_register_temporal_tools_matches_the_registry_list():
    import asyncio

    from mcp.server.fastmcp import FastMCP
    from quaestor.mcp.registry import TEMPORAL_TOOL_NAMES, register_temporal_tools

    mcp = FastMCP("test")
    register_temporal_tools(mcp)
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert names == set(TEMPORAL_TOOL_NAMES)
    assert len(TEMPORAL_TOOL_NAMES) == 13


def test_mcp_update_recurring(session):
    _bank(session)
    temporal.create_recurring(
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
    from quaestor.services import recurring as _rec_svc

    item_id = _rec_svc.list_recurring(session)[0].id
    out = temporal.update_recurring(session, UpdateRecurringInput(recurring_id=item_id, amount=5_000_000))
    assert "5" in out  # formatted amount appears
    assert _rec_svc.list_recurring(session)[0].amount == 5_000_000


def test_mcp_archive_recurring(session):
    _bank(session)
    temporal.create_recurring(
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
    from quaestor.services import recurring as _rec_svc

    item_id = _rec_svc.list_recurring(session)[0].id
    temporal.archive_recurring(session, ArchiveRecurringInput(recurring_id=item_id))
    assert _rec_svc.list_recurring(session, active=True) == []


def test_to_pay_table_renders_two_sections(session):
    a = _bank(session)
    overdue = planned.plan_payment(
        session,
        "Tigo",
        8_500_00,
        "COP",
        date(2026, 6, 28),
        a.id,
    )
    upcoming = planned.plan_payment(
        session,
        "Rent",
        5_000_00,
        "COP",
        date(2026, 7, 15),
        a.id,
    )
    queue = OutstandingQueue(overdue=[overdue], upcoming=[upcoming])
    out = format.to_pay_table(queue, Decimal("4000"))
    assert "## ⚠️ Overdue" in out
    assert "## Upcoming" in out
    assert "Tigo" in out
    assert "Rent" in out
    assert out.index("## ⚠️ Overdue") < out.index("## Upcoming")


def test_to_pay_table_omits_empty_overdue_section(session):
    a = _bank(session)
    upcoming = planned.plan_payment(
        session,
        "Rent",
        5_000_00,
        "COP",
        date(2026, 7, 15),
        a.id,
    )
    queue = OutstandingQueue(overdue=[], upcoming=[upcoming])
    out = format.to_pay_table(queue, Decimal("4000"))
    assert "## ⚠️ Overdue" not in out
    assert "## Upcoming" in out


def test_to_pay_table_omits_empty_upcoming_section(session):
    a = _bank(session)
    overdue = planned.plan_payment(
        session,
        "Tigo",
        8_500_00,
        "COP",
        date(2026, 6, 28),
        a.id,
    )
    queue = OutstandingQueue(overdue=[overdue], upcoming=[])
    out = format.to_pay_table(queue, Decimal("4000"))
    assert "## ⚠️ Overdue" in out
    assert "## Upcoming" not in out


def test_to_pay_table_empty_queue():
    out = format.to_pay_table(OutstandingQueue(), Decimal("4000"))
    assert out == "Nothing outstanding."


def test_to_pay_table_closes_with_the_combined_total(session):
    a = _bank(session)
    overdue = planned.plan_payment(session, "Claro", 85_000_00, "COP", date(2026, 6, 28), a.id)
    upcoming = planned.plan_payment(session, "Netflix", 45_000_00, "COP", date(2026, 7, 15), a.id)
    queue = OutstandingQueue(overdue=[overdue], upcoming=[upcoming])
    out = format.to_pay_table(queue, Decimal("4000"))
    assert out.splitlines()[-1] == "**Total to pay (COP): 130000.00** · 2 item(s)"
    assert "**To pay (COP): 85000.00**" in out
    assert "**To pay (COP): 45000.00**" in out


def test_to_pay_table_single_section_has_no_combined_total(session):
    a = _bank(session)
    upcoming = planned.plan_payment(session, "Netflix", 45_000_00, "COP", date(2026, 7, 15), a.id)
    out = format.to_pay_table(OutstandingQueue(overdue=[], upcoming=[upcoming]), Decimal("4000"))
    assert "Total to pay" not in out
    assert out.splitlines()[-1] == "**To pay (COP): 45000.00** · 1 item(s)"


def test_to_pay_table_two_section_layout_is_exact(session):
    """The whole rendered block is the contract, blank-line separators
    included — the chat answer must not drift line by line."""
    a = _bank(session)
    overdue = planned.plan_payment(session, "Claro", 85_000_00, "COP", date(2026, 6, 28), a.id)
    upcoming = planned.plan_payment(session, "Netflix", 45_000_00, "COP", date(2026, 7, 15), a.id)
    queue = OutstandingQueue(overdue=[overdue], upcoming=[upcoming])
    assert format.to_pay_table(queue, Decimal("4000")).splitlines() == [
        "## ⚠️ Overdue",
        "",
        "| id | Due | Payee | Amount | Currency | COP |",
        "|---|---|---|---|---|---|",
        f"| {overdue.id} | {display_date(overdue.date)} | Claro | 85000.00 | COP | 85000.00 |",
        "",
        "**To pay (COP): 85000.00** · 1 item(s)",
        "",
        "## Upcoming",
        "",
        "| id | Due | Payee | Amount | Currency | COP |",
        "|---|---|---|---|---|---|",
        f"| {upcoming.id} | {display_date(upcoming.date)} | Netflix | 45000.00 | COP | 45000.00 |",
        "",
        "**To pay (COP): 45000.00** · 1 item(s)",
        "",
        "**Total to pay (COP): 130000.00** · 2 item(s)",
    ]


def test_to_pay_table_single_section_layout_is_exact(session):
    """A one-section answer opens straight on its heading — no leading
    blank line — and closes on its own subtotal, exactly as before the
    combined-total line existed."""
    a = _bank(session)
    upcoming = planned.plan_payment(session, "Netflix", 45_000_00, "COP", date(2026, 7, 15), a.id)
    queue = OutstandingQueue(overdue=[], upcoming=[upcoming])
    assert format.to_pay_table(queue, Decimal("4000")).splitlines() == [
        "## Upcoming",
        "",
        "| id | Due | Payee | Amount | Currency | COP |",
        "|---|---|---|---|---|---|",
        f"| {upcoming.id} | {display_date(upcoming.date)} | Netflix | 45000.00 | COP | 45000.00 |",
        "",
        "**To pay (COP): 45000.00** · 1 item(s)",
    ]


def _declared_late(session):
    """Weekly Netflix declared today with a start three weeks behind."""
    _bank(session)
    temporal.create_recurring(
        session,
        CreateRecurringInput(
            name="Netflix",
            payee="Netflix",
            type="expense",
            mode="auto",
            amount=25_900,
            account="Bancolombia",
            interval_unit="week",
            interval_count=1,
            start_date=date.today() - timedelta(days=21),
        ),
    )
    from quaestor.services import recurring

    return recurring.list_recurring(session)[0].id


def test_pending_recurring_dates_tool_lists_what_awaits_a_decision(session):
    item_id = _declared_late(session)
    out = temporal.pending_recurring_dates(session, temporal.PendingDatesInput(recurring_id=item_id))
    assert "Netflix" in out and "4 passed due date" in out


def test_accept_recurring_dates_tool_records_only_what_was_ticked(session):
    from quaestor.services import occurrences

    item_id = _declared_late(session)
    offered = occurrences.pending_dates(session, item_id)
    out = temporal.accept_recurring_dates(
        session,
        temporal.AnswerPendingDatesInput(recurring_id=item_id, due_dates=offered[:2]),
    )
    assert "Recorded 2" in out
    assert len(occurrences.pending_dates(session, item_id)) == 2


def test_decline_recurring_dates_tool_closes_them_for_good(session):
    from quaestor.services import occurrences

    item_id = _declared_late(session)
    offered = occurrences.pending_dates(session, item_id)
    out = temporal.decline_recurring_dates(
        session,
        temporal.AnswerPendingDatesInput(recurring_id=item_id, due_dates=offered),
    )
    assert "Declined 4" in out
    assert occurrences.pending_dates(session, item_id) == []


def test_answering_passed_dates_is_write_destructive_and_hidden_from_llm():
    from quaestor.mcp.registry import LLM_ALLOWED_TOOLS, ToolTier, tool_tier

    for name in ("accept_recurring_dates", "decline_recurring_dates"):
        assert tool_tier(name) == ToolTier.WRITE_DESTRUCTIVE
        assert name not in LLM_ALLOWED_TOOLS


def test_asking_which_dates_are_pending_is_read_only():
    from quaestor.mcp.registry import LLM_ALLOWED_TOOLS, ToolTier, tool_tier

    assert tool_tier("pending_recurring_dates") == ToolTier.READ
    assert "pending_recurring_dates" in LLM_ALLOWED_TOOLS
