import asyncio

from mcp.server.fastmcp import FastMCP

from quaestor import db
from quaestor.mcp.registry import CORE_TOOL_NAMES, register_core_tools


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
