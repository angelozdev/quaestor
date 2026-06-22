"""MCP server assembly + entry point (`python -m quaestor.mcp`).

Builds a FastMCP instance, registers the core tools, exposes the streamable-HTTP
transport at `/mcp`, and wraps it with the bearer-auth middleware. We do NOT use
`mcp.run()` because we apply our own auth layer; we run uvicorn over the
auth-wrapped app instead.
"""
from __future__ import annotations

import os
from collections.abc import Mapping

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


_TRUTHY = {"1", "true", "yes"}


def _uvicorn_kwargs_from_env(env: Mapping[str, str]) -> dict:
    """Translate env vars into kwargs for uvicorn.run().

    `MCP_RELOAD` in {"1", "true", "yes"} (case-insensitive) enables uvicorn's
    autoreload, watching `/app/src` so edits to backend source trigger a
    restart. In production this env var is unset and reload is off.
    """
    reload_raw = env.get("MCP_RELOAD", "")
    reload = reload_raw.strip().lower() in _TRUTHY
    return {
        "factory": True,
        "host": env.get("MCP_HOST", "0.0.0.0"),
        "port": int(env.get("MCP_PORT", "9000")),
        "reload": reload,
        "reload_dirs": ["/app/src"] if reload else None,
    }


def main() -> None:
    import uvicorn

    uvicorn.run("quaestor.mcp.server:build_app", **_uvicorn_kwargs_from_env(os.environ))
