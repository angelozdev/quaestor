"""MCPClient — thin async wrapper around `fastmcp.Client`.

Use as `async with MCPClient(mcp) as client:`. One in-memory `Client` per
request; no subprocess, no TCP.

The wrapper exists so the agentic loop never imports `fastmcp` directly;
swapping to a remote streamable-HTTP transport later means changing this
file, nothing else.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastmcp import Client as FastMCPClient
from mcp.server.fastmcp import FastMCP

from ..llm.provider import ToolNotFoundError


@dataclass
class CallToolResult:
    """Subset of fastmcp's CallToolResult that the agentic loop needs."""

    output: str  # joined text content
    is_error: bool


class MCPClient:
    def __init__(self, mcp: FastMCP) -> None:
        self._mcp = mcp
        self._client: FastMCPClient | None = None

    async def __aenter__(self) -> "MCPClient":
        self._client = FastMCPClient(self._mcp)
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client is not None:
            await self._client.__aexit__(exc_type, exc, tb)
            self._client = None

    async def list_tools(self) -> list[Any]:
        assert self._client is not None, "use `async with MCPClient(...)`"
        return await self._client.list_tools()

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> CallToolResult:
        assert self._client is not None, "use `async with MCPClient(...)`"
        # list_tools is cached inside fastmcp.Client for the in-memory
        # transport, so this `hasattr` probe is cheap.
        known = {t.name for t in await self._client.list_tools()}
        if name not in known:
            raise ToolNotFoundError(name)

        result = await self._client.call_tool(name, arguments)
        # fastmcp returns structured content; coerce to a single text blob.
        is_error = bool(getattr(result, "is_error", False))
        chunks: list[str] = []
        for item in getattr(result, "content", []) or []:
            text = getattr(item, "text", None)
            if text is not None:
                chunks.append(text)
        return CallToolResult(output="\n".join(chunks), is_error=is_error)
