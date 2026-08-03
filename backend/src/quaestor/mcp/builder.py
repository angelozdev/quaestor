"""Build the in-process FastMCP instance used by the chat agentic loop.

Single factory function. Tools are declared in `quaestor.mcp.registry` and
registered here. No HTTP, no auth — the chat endpoint (`quaestor.api.chat`)
imports `build_mcp` and passes the result to `MCPClient`, which talks to it
in-memory via `fastmcp.Client`.

If external MCP access is ever reintroduced, a new module (e.g. `http.py`)
should wrap this `FastMCP` with `streamable_http_app()` + auth middleware —
do NOT regress this file.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .registry import (
    register_accounts_tools,
    register_budgets_reads_tools,
    register_categories_tools,
    register_category_groups_tools,
    register_core_tools,
    register_goals_reads_tools,
    register_planning_tools,
    register_recurring_restore_tools,
    register_reports_tools,
    register_settings_tools,
    register_tags_tools,
    register_temporal_tools,
    register_transactions_writes_tools,
)


def build_mcp() -> FastMCP:
    """A FastMCP instance with every Quaestor tool registered.

    The result is consumed in-process by `quaestor.chat.mcp.MCPClient`.
    """
    mcp = FastMCP("Quaestor", json_response=True)
    register_core_tools(mcp)
    register_temporal_tools(mcp)
    register_planning_tools(mcp)
    register_accounts_tools(mcp)
    register_categories_tools(mcp)
    register_category_groups_tools(mcp)
    register_tags_tools(mcp)
    register_transactions_writes_tools(mcp)
    register_settings_tools(mcp)
    register_budgets_reads_tools(mcp)
    register_goals_reads_tools(mcp)
    register_reports_tools(mcp)
    register_recurring_restore_tools(mcp)
    return mcp
