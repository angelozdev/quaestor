"""Tool registration and the growth pattern.

`register_core_tools(mcp)` registers the P2 core tools. P3/P4/P5 add their own
`register_<feature>_tools(mcp)` and `server.py` calls each — growing the surface
means one extra line of wiring, never a change to transport or auth.

Each tool opens ONE Session per call, bound to ``db.engine`` resolved
dynamically (so tests can swap the engine), and delegates to a `core` impl that
already translates domain errors to text.
"""
from sqlmodel import Session

from .. import db
from .tools import core, planning, temporal
from .tools.core import (
    GetFxRateInput,
    ListTransactionsInput,
    RecordExpenseInput,
    RecordIncomeInput,
    SetFxRateInput,
    TransferInput,
)
from .tools.planning import AssignBudgetInput
from .tools.temporal import (
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

TEMPORAL_TOOL_NAMES = (
    "create_recurring",
    "list_recurring",
    "plan_payment",
    "confirm_payment",
    "skip_payment",
    "skip_recurring",
    "to_pay",
    "update_recurring",
    "delete_recurring",
)

PLANNING_TOOL_NAMES = ("assign_budget",)

CORE_TOOL_NAMES = (
    "record_expense",
    "record_income",
    "transfer",
    "set_fx_rate",
    "list_transactions",
    "get_fx_rate",
    "list_accounts",
    "list_categories",
    "list_tags",
)


def register_core_tools(mcp) -> None:
    """Register the 9 P2 core tools on the given FastMCP instance."""

    @mcp.tool(name="record_expense", description="Record an expense in an account.")
    def record_expense(expense: RecordExpenseInput) -> str:
        with Session(db.engine) as session:
            return core.record_expense(session, expense)

    @mcp.tool(name="record_income", description="Record income in an account.")
    def record_income(income: RecordIncomeInput) -> str:
        with Session(db.engine) as session:
            return core.record_income(session, income)

    @mcp.tool(name="transfer", description="Transfer money between two accounts.")
    def transfer(transfer: TransferInput) -> str:
        with Session(db.engine) as session:
            return core.transfer(session, transfer)

    @mcp.tool(name="set_fx_rate", description="Set the USD→COP exchange rate for a date.")
    def set_fx_rate(rate: SetFxRateInput) -> str:
        with Session(db.engine) as session:
            return core.set_fx_rate(session, rate)

    @mcp.tool(
        name="list_transactions",
        description="List transactions with optional filters (dates, account, category, tag, type, status).",
    )
    def list_transactions(filters: ListTransactionsInput) -> str:
        with Session(db.engine) as session:
            return core.list_transactions(session, filters)

    @mcp.tool(name="get_fx_rate", description="Get the current USD→COP exchange rate for a date.")
    def get_fx_rate(query: GetFxRateInput) -> str:
        with Session(db.engine) as session:
            return core.get_fx_rate(session, query)

    @mcp.tool(name="list_accounts", description="List accounts with their balance and currency.")
    def list_accounts() -> str:
        with Session(db.engine) as session:
            return core.list_accounts(session)

    @mcp.tool(name="list_categories", description="List categories and their group.")
    def list_categories() -> str:
        with Session(db.engine) as session:
            return core.list_categories(session)

    @mcp.tool(name="list_tags", description="List existing tags.")
    def list_tags() -> str:
        with Session(db.engine) as session:
            return core.list_tags(session)


def register_temporal_tools(mcp) -> None:
    """Register the 7 P3 temporal tools on the given FastMCP instance."""

    @mcp.tool(name="create_recurring", description="Create a recurring expense/income (every-N interval).")
    def create_recurring(item: CreateRecurringInput) -> str:
        with Session(db.engine) as session:
            return temporal.create_recurring(session, item)

    @mcp.tool(name="list_recurring", description="List recurring items (optionally filter by active).")
    def list_recurring(filters: ListRecurringInput) -> str:
        with Session(db.engine) as session:
            return temporal.list_recurring(session, filters)

    @mcp.tool(name="plan_payment", description="Plan a one-off future payment (lands in to-pay).")
    def plan_payment(payment: PlanPaymentInput) -> str:
        with Session(db.engine) as session:
            return temporal.plan_payment(session, payment)

    @mcp.tool(name="confirm_payment", description="Confirm a planned payment (planned -> posted).")
    def confirm_payment(confirmation: ConfirmPaymentInput) -> str:
        with Session(db.engine) as session:
            return temporal.confirm_payment(session, confirmation)

    @mcp.tool(name="skip_payment", description="Skip/cancel a planned payment.")
    def skip_payment(skip: SkipPaymentInput) -> str:
        with Session(db.engine) as session:
            return temporal.skip_payment(session, skip)

    @mcp.tool(name="skip_recurring", description="Skip a single occurrence of a recurring item.")
    def skip_recurring(skip: SkipRecurringInput) -> str:
        with Session(db.engine) as session:
            return temporal.skip_recurring(session, skip)

    @mcp.tool(name="to_pay", description="What's still to pay in a date window (the confirmation queue).")
    def to_pay(window: ToPayInput) -> str:
        with Session(db.engine) as session:
            return temporal.to_pay(session, window)

    @mcp.tool(name="update_recurring", description="Edit a recurring item (future occurrences only).")
    def update_recurring(item: UpdateRecurringInput) -> str:
        with Session(db.engine) as session:
            return temporal.update_recurring(session, item)

    @mcp.tool(name="delete_recurring", description="Deactivate a recurring item (soft, reversible).")
    def delete_recurring(item: DeleteRecurringInput) -> str:
        with Session(db.engine) as session:
            return temporal.delete_recurring(session, item)


def register_planning_tools(mcp) -> None:
    """Register the P4 planning tools (budgets + goals) on the FastMCP instance."""

    @mcp.tool(name="assign_budget", description="Assign (set) a category envelope for a month.")
    def assign_budget(item: AssignBudgetInput) -> str:
        with Session(db.engine) as session:
            return planning.assign_budget(session, item)
