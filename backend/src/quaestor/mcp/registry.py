"""Tool registration and the growth pattern.

`register_core_tools(mcp)` registers the P2 core tools. P3/P4/P5 add their own
`register_<feature>_tools(mcp)` and `server.py` calls each — growing the surface
means one extra line of wiring, never a change to transport or auth.

Each tool opens ONE Session per call, bound to ``db.engine`` resolved
dynamically (so tests can swap the engine), and delegates to a `core` impl that
already translates domain errors to text.

Tools are also tagged with a `ToolTier` so the chat pipeline can decide
which ones the LLM is allowed to invoke. Destructive tools stay
registered on the MCP server (curl/MCP-direct + frontend HTTP UI can use
them) but are dropped from the OpenAI-shaped tool list passed to the
LLM, removing the indirect-prompt-injection blast radius.
"""

from enum import StrEnum

from sqlmodel import Session

from .. import db
from .tools import (
    core,
    funds,
    masters,
    recurring_restore,
    reports,
    temporal,
)
from .tools import (
    settings as settings_tools,
)
from .tools import (
    transactions as tx_tools,
)
from .tools.core import (
    GetFxRateInput,
    ListTransactionsInput,
    RecordExpenseInput,
    RecordIncomeInput,
    SetFxRateInput,
    TransferInput,
)
from .tools.funds import (
    CreateFundInput,
    FundInput,
    FundStatusInput,
    MonthInput,
    PreviewFundInput,
    SetFundInput,
)
from .tools.masters import (
    ArchiveAccountInput,
    ArchiveCategoryGroupInput,
    ArchiveCategoryInput,
    CreateAccountInput,
    CreateCategoryGroupInput,
    CreateCategoryInput,
    CreateTagInput,
    DeleteTagInput,
    GetAccountInput,
    GetCategoryInput,
    RestoreAccountInput,
    RestoreCategoryGroupInput,
    RestoreCategoryInput,
    UpdateAccountInput,
    UpdateCategoryGroupInput,
    UpdateCategoryInput,
    UpdateTagInput,
)
from .tools.recurring_restore import RestoreRecurringInput
from .tools.reports import MonthlyReportInput
from .tools.settings import GetSettingsInput, UpdateSettingsInput
from .tools.temporal import (
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
from .tools.transactions import (
    DeleteTransactionInput,
    GetTransactionInput,
    UpdateTransactionInput,
)


class ToolTier(StrEnum):
    """How dangerous it is to invoke a tool without explicit human intent.

    The chat pipeline hides `WRITE_DESTRUCTIVE` tools from the LLM; the
    operator still has full access via MCP-direct curl calls and via the
    frontend HTTP UI (both of which require explicit user action).
    """

    READ = "read"
    WRITE_SAFE = "write_safe"
    WRITE_DESTRUCTIVE = "write_destructive"


_READ_ONLY_TOOLS: frozenset[str] = frozenset(
    {
        "list_transactions",
        "list_accounts",
        "list_categories",
        "list_tags",
        "get_fx_rate",
        "monthly_report",
        "get_transaction",
        "get_account",
        "get_category",
        "list_recurring",
        "pending_recurring_dates",
        "to_pay",
        "get_settings",
        "list_funds",
        "fund_status",
        "preview_fund",
        "money_available",
        "money_rates",
    }
)

_WRITE_SAFE_TOOLS: frozenset[str] = frozenset(
    {
        "record_expense",
        "record_income",
        "create_account",
        "create_category",
        "create_category_group",
        "create_tag",
        "create_recurring",
        "set_fx_rate",
        "plan_payment",
        "create_fund",
        "set_fund",
    }
)

_WRITE_DESTRUCTIVE_TOOLS: frozenset[str] = frozenset(
    {
        "transfer",
        "update_transaction",
        "delete_transaction",
        "update_account",
        "archive_account",
        "restore_account",
        "update_category",
        "archive_category",
        "restore_category",
        "update_category_group",
        "archive_category_group",
        "restore_category_group",
        "update_tag",
        "delete_tag",
        "update_recurring",
        "archive_recurring",
        "restore_recurring",
        "skip_payment",
        "restore_payment",
        "skip_recurring",
        "accept_recurring_dates",
        "decline_recurring_dates",
        "confirm_payment",
        "update_settings",
        "delete_fund",
    }
)

LLM_ALLOWED_TOOLS: frozenset[str] = _READ_ONLY_TOOLS | _WRITE_SAFE_TOOLS


def tool_tier(name: str) -> ToolTier:
    """Classify a tool. Unknown names default to `WRITE_DESTRUCTIVE`
    (deny by default — a tool we forgot to classify must not silently
    become reachable by the LLM)."""
    if name in _READ_ONLY_TOOLS:
        return ToolTier.READ
    if name in _WRITE_SAFE_TOOLS:
        return ToolTier.WRITE_SAFE
    return ToolTier.WRITE_DESTRUCTIVE


TEMPORAL_TOOL_NAMES = (
    "create_recurring",
    "list_recurring",
    "plan_payment",
    "confirm_payment",
    "skip_payment",
    "restore_payment",
    "skip_recurring",
    "pending_recurring_dates",
    "accept_recurring_dates",
    "decline_recurring_dates",
    "to_pay",
    "update_recurring",
    "archive_recurring",
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

ACCOUNTS_TOOL_NAMES = (
    "create_account",
    "update_account",
    "archive_account",
    "restore_account",
    "get_account",
)

CATEGORIES_TOOL_NAMES = (
    "create_category",
    "update_category",
    "archive_category",
    "restore_category",
    "get_category",
)

CATEGORY_GROUPS_TOOL_NAMES = (
    "create_category_group",
    "update_category_group",
    "archive_category_group",
    "restore_category_group",
)

TAGS_TOOL_NAMES = (
    "create_tag",
    "update_tag",
    "delete_tag",
)

TRANSACTIONS_WRITES_TOOL_NAMES = (
    "get_transaction",
    "update_transaction",
    "delete_transaction",
)

SETTINGS_TOOL_NAMES = (
    "get_settings",
    "update_settings",
)

FUNDS_TOOL_NAMES = (
    "create_fund",
    "preview_fund",
    "list_funds",
    "fund_status",
    "set_fund",
    "delete_fund",
    "money_available",
    "money_rates",
)

REPORTS_TOOL_NAMES = ("monthly_report",)

RECURRING_RESTORE_TOOL_NAMES = ("restore_recurring",)


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

    @mcp.tool(name="set_fx_rate", description="Set the current USD→COP exchange rate (TRM).")
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

    @mcp.tool(name="get_fx_rate", description="Get the current USD→COP exchange rate (TRM).")
    def get_fx_rate(query: GetFxRateInput = GetFxRateInput()) -> str:
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
    """Register the P3 temporal tools on the given FastMCP instance."""

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

    @mcp.tool(name="restore_payment", description="Restore a skipped planned payment back to the to-pay queue.")
    def restore_payment(restore: RestorePaymentInput) -> str:
        with Session(db.engine) as session:
            return temporal.restore_payment(session, restore)

    @mcp.tool(name="skip_recurring", description="Skip a single occurrence of a recurring item.")
    def skip_recurring(skip: SkipRecurringInput) -> str:
        with Session(db.engine) as session:
            return temporal.skip_recurring(session, skip)

    @mcp.tool(
        name="pending_recurring_dates",
        description="Passed due dates of a recurring item waiting for the user to accept or decline.",
    )
    def pending_recurring_dates(item: temporal.PendingDatesInput) -> str:
        with Session(db.engine) as session:
            return temporal.pending_recurring_dates(session, item)

    @mcp.tool(
        name="accept_recurring_dates",
        description="Record the passed due dates the user accepted, each on its own date.",
    )
    def accept_recurring_dates(answer: temporal.AnswerPendingDatesInput) -> str:
        with Session(db.engine) as session:
            return temporal.accept_recurring_dates(session, answer)

    @mcp.tool(
        name="decline_recurring_dates",
        description="Close the passed due dates the user declined; they are never charged or offered again.",
    )
    def decline_recurring_dates(answer: temporal.AnswerPendingDatesInput) -> str:
        with Session(db.engine) as session:
            return temporal.decline_recurring_dates(session, answer)

    @mcp.tool(name="to_pay", description="What's still to pay in a date window (the confirmation queue).")
    def to_pay(window: ToPayInput) -> str:
        with Session(db.engine) as session:
            return temporal.to_pay(session, window)

    @mcp.tool(name="update_recurring", description="Edit a recurring item (future occurrences only).")
    def update_recurring(item: UpdateRecurringInput) -> str:
        with Session(db.engine) as session:
            return temporal.update_recurring(session, item)

    @mcp.tool(name="archive_recurring", description="Deactivate a recurring item (soft, reversible).")
    def archive_recurring(item: ArchiveRecurringInput) -> str:
        with Session(db.engine) as session:
            return temporal.archive_recurring(session, item)


def register_accounts_tools(mcp) -> None:
    @mcp.tool(name="create_account", description="Create a new account.")
    def create_account(inp: CreateAccountInput) -> str:
        with Session(db.engine) as session:
            return masters.create_account(session, inp)

    @mcp.tool(name="update_account", description="Update an account's name or type.")
    def update_account(inp: UpdateAccountInput) -> str:
        with Session(db.engine) as session:
            return masters.update_account(session, inp)

    @mcp.tool(name="archive_account", description="Archive an account (soft, reversible).")
    def archive_account(inp: ArchiveAccountInput) -> str:
        with Session(db.engine) as session:
            return masters.archive_account(session, inp)

    @mcp.tool(name="restore_account", description="Restore an archived account.")
    def restore_account(inp: RestoreAccountInput) -> str:
        with Session(db.engine) as session:
            return masters.restore_account(session, inp)

    @mcp.tool(name="get_account", description="Fetch one account by name.")
    def get_account(inp: GetAccountInput) -> str:
        with Session(db.engine) as session:
            return masters.get_account(session, inp)


def register_categories_tools(mcp) -> None:
    @mcp.tool(name="create_category", description="Create a new category.")
    def create_category(inp: CreateCategoryInput) -> str:
        with Session(db.engine) as session:
            return masters.create_category(session, inp)

    @mcp.tool(name="update_category", description="Update a category's fields.")
    def update_category(inp: UpdateCategoryInput) -> str:
        with Session(db.engine) as session:
            return masters.update_category(session, inp)

    @mcp.tool(name="archive_category", description="Archive a category (soft, reversible).")
    def archive_category(inp: ArchiveCategoryInput) -> str:
        with Session(db.engine) as session:
            return masters.archive_category(session, inp)

    @mcp.tool(name="restore_category", description="Restore an archived category.")
    def restore_category(inp: RestoreCategoryInput) -> str:
        with Session(db.engine) as session:
            return masters.restore_category(session, inp)

    @mcp.tool(name="get_category", description="Fetch one category by name.")
    def get_category(inp: GetCategoryInput) -> str:
        with Session(db.engine) as session:
            return masters.get_category(session, inp)


def register_category_groups_tools(mcp) -> None:
    @mcp.tool(name="create_category_group", description="Create a new category group.")
    def create_category_group(inp: CreateCategoryGroupInput) -> str:
        with Session(db.engine) as session:
            return masters.create_category_group(session, inp)

    @mcp.tool(name="update_category_group", description="Update a category group's fields.")
    def update_category_group(inp: UpdateCategoryGroupInput) -> str:
        with Session(db.engine) as session:
            return masters.update_category_group(session, inp)

    @mcp.tool(name="archive_category_group", description="Archive a category group (soft, reversible).")
    def archive_category_group(inp: ArchiveCategoryGroupInput) -> str:
        with Session(db.engine) as session:
            return masters.archive_category_group(session, inp)

    @mcp.tool(name="restore_category_group", description="Restore an archived category group.")
    def restore_category_group(inp: RestoreCategoryGroupInput) -> str:
        with Session(db.engine) as session:
            return masters.restore_category_group(session, inp)


def register_tags_tools(mcp) -> None:
    @mcp.tool(name="create_tag", description="Create a tag (idempotent by name).")
    def create_tag(inp: CreateTagInput) -> str:
        with Session(db.engine) as session:
            return masters.create_tag(session, inp)

    @mcp.tool(name="update_tag", description="Rename a tag.")
    def update_tag(inp: UpdateTagInput) -> str:
        with Session(db.engine) as session:
            return masters.update_tag(session, inp)

    @mcp.tool(name="delete_tag", description="Hard-delete a tag and its transaction links.")
    def delete_tag(inp: DeleteTagInput) -> str:
        with Session(db.engine) as session:
            return masters.delete_tag(session, inp)


def register_transactions_writes_tools(mcp) -> None:
    @mcp.tool(name="get_transaction", description="Fetch one transaction by id.")
    def get_transaction(inp: GetTransactionInput) -> str:
        with Session(db.engine) as session:
            return tx_tools.get_transaction(session, inp)

    @mcp.tool(
        name="update_transaction", description="Edit a transaction's payee/notes/category/date; add or remove tags."
    )
    def update_transaction(inp: UpdateTransactionInput) -> str:
        with Session(db.engine) as session:
            return tx_tools.update_transaction(session, inp)

    @mcp.tool(name="delete_transaction", description="Delete a transaction and reverse its balance effect.")
    def delete_transaction(inp: DeleteTransactionInput) -> str:
        with Session(db.engine) as session:
            return tx_tools.delete_transaction(session, inp)


def register_settings_tools(mcp) -> None:
    @mcp.tool(name="get_settings", description="Fetch app settings.")
    def get_settings(inp: GetSettingsInput = GetSettingsInput()) -> str:
        with Session(db.engine) as session:
            return settings_tools.get_settings(session, inp)

    @mcp.tool(name="update_settings", description="Update app settings.")
    def update_settings(inp: UpdateSettingsInput) -> str:
        with Session(db.engine) as session:
            return settings_tools.update_settings(session, inp)


def register_reports_tools(mcp) -> None:
    @mcp.tool(name="monthly_report", description="Build the retrospective monthly report.")
    def monthly_report(inp: MonthlyReportInput) -> str:
        with Session(db.engine) as session:
            return reports.monthly_report(session, inp)


def register_funds_tools(mcp) -> None:
    """Register the fund tools — the assistant half of feature 003's parity (AC-28)."""

    @mcp.tool(name="create_fund", description="Create the one fund a spending category may carry.")
    def create_fund(inp: CreateFundInput) -> str:
        with Session(db.engine) as session:
            return funds.create_fund(session, inp)

    @mcp.tool(name="preview_fund", description="What a fund would ask its first month, before creating it.")
    def preview_fund(inp: PreviewFundInput) -> str:
        with Session(db.engine) as session:
            return funds.preview_fund(session, inp)

    @mcp.tool(name="list_funds", description="List every fund and the rule it follows.")
    def list_funds() -> str:
        with Session(db.engine) as session:
            return funds.list_funds(session)

    @mcp.tool(name="fund_status", description="What one fund asks and holds in a month.")
    def fund_status(inp: FundStatusInput) -> str:
        with Session(db.engine) as session:
            return funds.fund_status(session, inp)

    @mcp.tool(name="set_fund", description="Change a fund's rule, its parameters, or what it holds.")
    def set_fund(inp: SetFundInput) -> str:
        with Session(db.engine) as session:
            return funds.set_fund(session, inp)

    @mcp.tool(name="delete_fund", description="Remove a fund outright.")
    def delete_fund(inp: FundInput) -> str:
        with Session(db.engine) as session:
            return funds.delete_fund(session, inp)

    @mcp.tool(name="money_available", description="The money available for a month, with its breakdown.")
    def money_available(inp: MonthInput) -> str:
        with Session(db.engine) as session:
            return funds.money_available(session, inp)

    @mcp.tool(name="money_rates", description="What the owner earns and costs a month, and the margin.")
    def money_rates(inp: MonthInput) -> str:
        with Session(db.engine) as session:
            return funds.money_rates(session, inp)


def register_recurring_restore_tools(mcp) -> None:
    @mcp.tool(name="restore_recurring", description="Re-activate a deactivated recurring item.")
    def restore_recurring(inp: RestoreRecurringInput) -> str:
        with Session(db.engine) as session:
            return recurring_restore.restore_recurring(session, inp)
