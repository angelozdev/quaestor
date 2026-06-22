"""MCP server assembly + entry point (`python -m quaestor.mcp`).

Builds a FastMCP instance, registers the core tools, exposes the streamable-HTTP
transport at `/mcp`, and wraps it with the bearer-auth middleware. We do NOT use
`mcp.run()` because we apply our own auth layer; we run uvicorn over the
auth-wrapped app instead.
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from .. import db
from .auth import BearerAuthMiddleware
from .registry import (
    register_accounts_tools,
    register_budgets_reads_tools,
    register_category_groups_tools,
    register_categories_tools,
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
    """A FastMCP instance with every P2/P3/P4/P5/ADR-0009 tool registered."""
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


def build_app():
    """The auth-wrapped streamable-HTTP ASGI app served at `/mcp`.

    `streamable_http_app()` returns a Starlette app whose lifespan runs the MCP
    session manager, so adding our middleware keeps that lifespan intact.
    """
    db.init_db(db.engine)
    mcp = build_mcp()
    app = mcp.streamable_http_app()
    app.add_middleware(BearerAuthMiddleware)
    return app


def main() -> None:
    import uvicorn

    host = os.environ.get("MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_PORT", "9000"))
    uvicorn.run(build_app(), host=host, port=port)
