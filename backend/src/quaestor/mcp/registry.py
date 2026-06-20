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
from .tools import core
from .tools.core import (
    GetFxRateInput,
    ListTransactionsInput,
    RecordExpenseInput,
    RecordIncomeInput,
    SetFxRateInput,
    TransferInput,
)

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
