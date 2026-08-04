import asyncio

from mcp.server.fastmcp import FastMCP
from quaestor import db
from quaestor.mcp import builder
from quaestor.mcp.registry import (
    ACCOUNTS_TOOL_NAMES,
    CATEGORIES_TOOL_NAMES,
    CATEGORY_GROUPS_TOOL_NAMES,
    CORE_TOOL_NAMES,
    FUNDS_TOOL_NAMES,
    RECURRING_RESTORE_TOOL_NAMES,
    REPORTS_TOOL_NAMES,
    SETTINGS_TOOL_NAMES,
    TAGS_TOOL_NAMES,
    TRANSACTIONS_WRITES_TOOL_NAMES,
    register_accounts_tools,
    register_categories_tools,
    register_category_groups_tools,
    register_core_tools,
    register_funds_tools,
    register_recurring_restore_tools,
    register_reports_tools,
    register_settings_tools,
    register_tags_tools,
    register_transactions_writes_tools,
)


def _tool_names(mcp):
    return {t.name for t in asyncio.run(mcp.list_tools())}


def test_register_core_tools_exposes_all_nine():
    mcp = FastMCP("test")
    register_core_tools(mcp)
    assert _tool_names(mcp) == set(CORE_TOOL_NAMES)
    assert len(CORE_TOOL_NAMES) == 9


def test_growth_pattern_extra_register_does_not_touch_transport():
    """A sibling register_*_tools mounts alongside core without any transport change."""
    mcp = FastMCP("test")
    register_core_tools(mcp)

    def register_demo_tools(mcp):
        @mcp.tool(name="demo_ping", description="demo")
        def demo_ping() -> str:
            return "pong"

    register_demo_tools(mcp)
    names = _tool_names(mcp)
    assert "demo_ping" in names
    assert set(CORE_TOOL_NAMES) <= names  # core still present


def test_registered_tool_runs_against_db_engine(monkeypatch, engine):
    """The wrapper resolves db.engine dynamically; a tool call hits the DB and returns text."""
    from quaestor.services import accounts

    monkeypatch.setattr(db, "engine", engine)
    from sqlmodel import Session

    with Session(engine) as s:
        accounts.create_account(s, "Bancolombia", "debit", "COP", balance=10_000_000)

    mcp = FastMCP("test")
    register_core_tools(mcp)
    result = asyncio.run(mcp.call_tool("list_accounts", {}))
    assert "Bancolombia" in str(result)


def test_empty_input_tools_accept_no_args(monkeypatch, engine):
    """Regression: a tool with an empty Input model must still accept `{}`.

    The LLM naturally calls them with `{}` (no fields to fill). The wrapper
    used to declare `inp: XxxInput` as required, so FastMCP raised
    `inp Field required` and the chat endpoint 500'd. Defaulting `inp` in the
    wrapper signature fixes it.
    """
    monkeypatch.setattr(db, "engine", engine)

    mcp = FastMCP("test")
    register_settings_tools(mcp)
    result = asyncio.run(mcp.call_tool("get_settings", {}))
    # Pydantic-validated call returns text; no ToolError raised.
    text = str(result)
    assert "ToolError" not in text, f"get_settings raised: {text}"
    assert text, "get_settings returned empty result"


def test_register_accounts_tools_exposes_all_five():
    mcp = FastMCP("test")
    register_accounts_tools(mcp)
    names = _tool_names(mcp)
    assert set(ACCOUNTS_TOOL_NAMES) <= names
    assert len(ACCOUNTS_TOOL_NAMES) == 5


def test_register_categories_tools_exposes_all_five():
    mcp = FastMCP("test")
    register_categories_tools(mcp)
    assert set(CATEGORIES_TOOL_NAMES) <= _tool_names(mcp)
    assert len(CATEGORIES_TOOL_NAMES) == 5


def test_register_category_groups_tools_exposes_all_four():
    mcp = FastMCP("test")
    register_category_groups_tools(mcp)
    assert set(CATEGORY_GROUPS_TOOL_NAMES) <= _tool_names(mcp)
    assert len(CATEGORY_GROUPS_TOOL_NAMES) == 4


def test_register_tags_tools_exposes_all_three():
    mcp = FastMCP("test")
    register_tags_tools(mcp)
    assert set(TAGS_TOOL_NAMES) <= _tool_names(mcp)
    assert len(TAGS_TOOL_NAMES) == 3


def test_register_transactions_writes_tools_exposes_all_three():
    mcp = FastMCP("test")
    register_transactions_writes_tools(mcp)
    assert set(TRANSACTIONS_WRITES_TOOL_NAMES) <= _tool_names(mcp)
    assert len(TRANSACTIONS_WRITES_TOOL_NAMES) == 3


def test_register_settings_tools_exposes_both():
    mcp = FastMCP("test")
    register_settings_tools(mcp)
    assert set(SETTINGS_TOOL_NAMES) <= _tool_names(mcp)
    assert len(SETTINGS_TOOL_NAMES) == 2


def test_register_reports_tools_exposes_one():
    mcp = FastMCP("test")
    register_reports_tools(mcp)
    assert set(REPORTS_TOOL_NAMES) <= _tool_names(mcp)
    assert len(REPORTS_TOOL_NAMES) == 1


def test_register_funds_tools_exposes_all_eight():
    mcp = FastMCP("test")
    register_funds_tools(mcp)
    assert set(FUNDS_TOOL_NAMES) <= _tool_names(mcp)
    assert len(FUNDS_TOOL_NAMES) == 8


def test_register_recurring_restore_tools_exposes_one():
    mcp = FastMCP("test")
    register_recurring_restore_tools(mcp)
    assert set(RECURRING_RESTORE_TOOL_NAMES) <= _tool_names(mcp)
    assert len(RECURRING_RESTORE_TOOL_NAMES) == 1


def test_build_mcp_registers_every_new_group():
    import asyncio

    mcp = builder.build_mcp()
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    for grp in (
        ACCOUNTS_TOOL_NAMES,
        CATEGORIES_TOOL_NAMES,
        CATEGORY_GROUPS_TOOL_NAMES,
        TAGS_TOOL_NAMES,
        TRANSACTIONS_WRITES_TOOL_NAMES,
        SETTINGS_TOOL_NAMES,
        REPORTS_TOOL_NAMES,
        FUNDS_TOOL_NAMES,
        RECURRING_RESTORE_TOOL_NAMES,
    ):
        assert set(grp) <= names, f"missing tools: {set(grp) - names}"
    # And the renamed one is present, not the old name.
    assert "archive_recurring" in names
    assert "delete_recurring" not in names
    # And the surfaces feature 003 removed are not reachable through the assistant.
    assert not [n for n in names if "goal" in n or "budget" in n]
