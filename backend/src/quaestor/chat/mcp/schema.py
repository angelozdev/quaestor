"""MCP `inputSchema` → OpenAI `tools[]` conversion + module-level cache.

`build_mcp()` registers all 52 tools at import time; the tool list never
changes between requests within one process. We fetch once on the first
chat request and cache both the raw MCP list and the OpenAI-shaped list.

`to_openai_tools()` is pure — easy to test without spinning up FastMCP.
"""
from __future__ import annotations

import asyncio
from typing import Any

from .client import MCPClient

_EMPTY_SCHEMA = {"type": "object", "properties": {}}


def to_openai_tools(mcp_tools: list[Any]) -> list[dict[str, Any]]:
    """Convert MCP tool descriptors to OpenAI `tools=[]` shape.

    Each entry: `{"type": "function", "function": {"name", "description",
    "parameters"}}`. The `parameters` value is the MCP `inputSchema` passed
    through verbatim — LiteLLM/Anthropic tolerate `$ref` and `anyOf` here.
    """
    out: list[dict[str, Any]] = []
    for tool in mcp_tools:
        params = getattr(tool, "inputSchema", None) or _EMPTY_SCHEMA
        out.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": params,
                },
            }
        )
    return out


_tools_cache: list[Any] | None = None
_openai_tools_cache: list[dict[str, Any]] | None = None
_lock: asyncio.Lock | None = None


async def get_cached_tools(mcp_client: MCPClient) -> list[dict[str, Any]]:
    """Return the OpenAI-shaped tool list, populating the cache on first call."""
    global _tools_cache, _openai_tools_cache, _lock
    if _openai_tools_cache is not None:
        return _openai_tools_cache

    if _lock is None:
        _lock = asyncio.Lock()
    async with _lock:
        if _openai_tools_cache is not None:
            return _openai_tools_cache
        _tools_cache = await mcp_client.list_tools()
        _openai_tools_cache = to_openai_tools(_tools_cache)
        return _openai_tools_cache


def _reset_cache_for_tests() -> None:
    """Clear module-level caches. Tests-only; never call from production."""
    global _tools_cache, _openai_tools_cache, _lock
    _tools_cache = None
    _openai_tools_cache = None
    _lock = None


def filter_for_llm(
    tools: list[dict[str, Any]],
    allowed: frozenset[str],
) -> list[dict[str, Any]]:
    """Return the subset of `tools` whose `function.name` is in `allowed`.

    Pure: no side effects, easy to test in isolation. The chat service
    passes `LLM_ALLOWED_TOOLS` from `mcp.registry` so destructive tools
    (transfer, delete_*, archive_*, update_settings, delete_tag) never
    appear in the tool list the LLM sees — closing QUA-LLM06-01.
    """
    return [t for t in tools if t.get("function", {}).get("name") in allowed]  # noqa: E501
