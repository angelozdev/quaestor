"""Round-trip the in-memory fastmcp.Client against the real build_mcp()."""
from __future__ import annotations

import pytest

from quaestor.chat.mcp.client import MCPClient, ToolNotFoundError
from quaestor.mcp.builder import build_mcp


@pytest.mark.asyncio
async def test_list_tools_returns_registered_tools():
    mcp = build_mcp()
    async with MCPClient(mcp) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools}
        # Spot-check a handful of core + parity tools (ADR-0009).
        assert "record_expense" in names
        assert "list_transactions" in names
        assert "monthly_report" in names


@pytest.mark.asyncio
async def test_call_tool_returns_text_output(engine, session, seeded, monkeypatch):
    # Build an isolated MCP server bound to the test engine/session.
    from quaestor import db
    from quaestor.mcp.builder import build_mcp

    # Brief verbatim omitted this monkeypatch but the comment above states
    # the intent ("bound to the test engine"). Without it, build_mcp()'s
    # registered tools resolve `db.engine` to the global file-based engine
    # and miss the seeded in-memory data. Same pattern as test_server.py.
    monkeypatch.setattr(db, "engine", engine)
    mcp = build_mcp()
    async with MCPClient(mcp) as client:
        result = await client.call_tool(
            "list_accounts", {}
        )
    assert result.is_error is False
    assert "Bancolombia" in result.output


@pytest.mark.asyncio
async def test_call_tool_unknown_name_raises():
    mcp = build_mcp()
    async with MCPClient(mcp) as client:
        with pytest.raises(ToolNotFoundError):
            await client.call_tool("does_not_exist", {})
