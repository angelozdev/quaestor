"""ChatService agentic-loop tests with fake LLMProvider and fake MCPClient.

The loop is exercised end-to-end (text-only, tool-then-text, tool error,
loop cap) and the SSE bytes are inspected with the same parser the frontend
would use.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest

from quaestor.chat.llm.provider import (
    LLMEvent,
    LLMEventType,
    LLMProvider,
    ToolNotFoundError,
    UpstreamLLMError,
)
from quaestor.chat.mcp.client import CallToolResult, MCPClient
from quaestor.chat.service import ChatService


# --- fakes -----------------------------------------------------------------


class ScriptedProvider(LLMProvider):
    """Yields a pre-scripted list of LLMEvent sequences, one per stream() call."""

    def __init__(self, scripts: list[list[LLMEvent]]) -> None:
        self._scripts = list(scripts)
        self.calls = 0

    async def stream(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AsyncIterator[LLMEvent]:
        idx = min(self.calls, len(self._scripts) - 1)
        self.calls += 1
        for ev in self._scripts[idx]:
            yield ev


class FakeMCPClient:
    """Stand-in for MCPClient that returns canned tool results."""

    def __init__(self, results: dict[str, CallToolResult]) -> None:
        self._results = results
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def __aenter__(self) -> "FakeMCPClient":
        return self

    async def __aexit__(self, *exc) -> None:
        return None

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> CallToolResult:
        self.calls.append((name, arguments))
        if name not in self._results:
            raise ToolNotFoundError(name)
        return self._results[name]

    async def list_tools(self) -> list[Any]:
        return []


# --- helpers ---------------------------------------------------------------


def _parse_sse(blob: bytes) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for chunk in blob.split(b"\n\n"):
        if not chunk:
            continue
        for line in chunk.splitlines():
            if line.startswith(b"data: "):
                body = line.removeprefix(b"data: ")
                if body.strip() == b"[DONE]":
                    out.append({"type": "__DONE__"})
                else:
                    out.append(json.loads(body))
    return out


@pytest.fixture
def fake_mcp(monkeypatch):
    """Patch MCPClient in the service module to return our fake."""
    holder: dict[str, FakeMCPClient] = {
        "client": FakeMCPClient(
            {
                "list_transactions": CallToolResult(
                    output='[{"id":1,"payee":"Café","amount":15000}]', is_error=False
                )
            }
        )
    }

    def factory(*args, **kwargs):
        return holder["client"]

    monkeypatch.setattr("quaestor.chat.service.MCPClient", factory)
    return holder


# --- tests -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_text_only_iteration_emits_full_sse_sequence(fake_mcp):
    provider = ScriptedProvider(
        [
            [
                LLMEvent(type=LLMEventType.MESSAGE_START, message_id="m1", model="MiniMax-M3"),
                LLMEvent(type=LLMEventType.TEXT_START, content_index=0),
                LLMEvent(type=LLMEventType.TEXT_DELTA, delta="Hola"),
                LLMEvent(type=LLMEventType.TEXT_END, content_index=0),
                LLMEvent(type=LLMEventType.STEP_FINISH),
                LLMEvent(
                    type=LLMEventType.MESSAGE_FINISH, stop_reason="end_turn", iterations=1
                ),
            ]
        ]
    )
    service = ChatService(provider=provider, mcp=None, max_iterations=4)  # mcp unused
    blob = b""
    async for chunk in service.stream(messages=[{"role": "user", "content": "hola"}]):
        blob += chunk

    events = _parse_sse(blob)
    types = [e["type"] for e in events]
    assert types[0] == "start"
    assert types[-1] == "__DONE__"
    assert "finish" in types
    text_deltas = [e for e in events if e["type"] == "text-delta"]
    assert "".join(e["delta"] for e in text_deltas) == "Hola"


@pytest.mark.asyncio
async def test_tool_call_then_text_calls_mcp_and_streams_results(fake_mcp):
    provider = ScriptedProvider(
        [
            [
                LLMEvent(type=LLMEventType.MESSAGE_START, message_id="m1", model="MiniMax-M3"),
                LLMEvent(
                    type=LLMEventType.TOOL_INPUT_AVAILABLE,
                    tool_call_id="tc_1",
                    tool_name="list_transactions",
                    arguments={"date_from": "2026-06-01"},
                ),
                LLMEvent(type=LLMEventType.STEP_FINISH),
                LLMEvent(
                    type=LLMEventType.MESSAGE_FINISH, stop_reason="tool_use", iterations=1
                ),
            ],
            [
                LLMEvent(type=LLMEventType.MESSAGE_START, message_id="m2", model="MiniMax-M3"),
                LLMEvent(type=LLMEventType.TEXT_START, content_index=0),
                LLMEvent(type=LLMEventType.TEXT_DELTA, delta="Tienes 1 gasto."),
                LLMEvent(type=LLMEventType.TEXT_END, content_index=0),
                LLMEvent(type=LLMEventType.STEP_FINISH),
                LLMEvent(
                    type=LLMEventType.MESSAGE_FINISH, stop_reason="end_turn", iterations=1
                ),
            ],
        ]
    )
    service = ChatService(provider=provider, mcp=None, max_iterations=4)
    blob = b""
    async for chunk in service.stream(messages=[{"role": "user", "content": "gastos de junio"}]):
        blob += chunk

    events = _parse_sse(blob)
    tool_input = [e for e in events if e["type"] == "tool-input-available"]
    tool_output = [e for e in events if e["type"] == "tool-output-available"]
    assert len(tool_input) == 1 and tool_input[0]["toolName"] == "list_transactions"
    assert len(tool_output) == 1 and "Café" in tool_output[0]["output"]
    assert fake_mcp["client"].calls == [("list_transactions", {"date_from": "2026-06-01"})]


@pytest.mark.asyncio
async def test_tool_error_emits_is_error_and_loop_continues(fake_mcp):
    fake_mcp["client"] = FakeMCPClient(
        {
            "list_transactions": CallToolResult(
                output="account not found", is_error=True
            )
        }
    )

    provider = ScriptedProvider(
        [
            [
                LLMEvent(type=LLMEventType.MESSAGE_START, message_id="m1", model="MiniMax-M3"),
                LLMEvent(
                    type=LLMEventType.TOOL_INPUT_AVAILABLE,
                    tool_call_id="tc_1",
                    tool_name="list_transactions",
                    arguments={},
                ),
                LLMEvent(type=LLMEventType.STEP_FINISH),
                LLMEvent(type=LLMEventType.MESSAGE_FINISH, stop_reason="tool_use", iterations=1),
            ],
            [
                LLMEvent(type=LLMEventType.MESSAGE_START, message_id="m2", model="MiniMax-M3"),
                LLMEvent(type=LLMEventType.TEXT_START, content_index=0),
                LLMEvent(type=LLMEventType.TEXT_DELTA, delta="No pude."),
                LLMEvent(type=LLMEventType.TEXT_END, content_index=0),
                LLMEvent(type=LLMEventType.STEP_FINISH),
                LLMEvent(type=LLMEventType.MESSAGE_FINISH, stop_reason="end_turn", iterations=1),
            ],
        ]
    )
    service = ChatService(provider=provider, mcp=None, max_iterations=4)
    blob = b""
    async for chunk in service.stream(messages=[{"role": "user", "content": "?"}]):
        blob += chunk

    events = _parse_sse(blob)
    outputs = [e for e in events if e["type"] == "tool-output-available"]
    assert outputs and outputs[0].get("isError") is True


@pytest.mark.asyncio
async def test_loop_cap_emits_length_finish(fake_mcp):
    # Always emit a tool call, never an end_turn — must hit the cap.
    provider = ScriptedProvider(
        [
            [
                LLMEvent(type=LLMEventType.MESSAGE_START, message_id="m1", model="MiniMax-M3"),
                LLMEvent(
                    type=LLMEventType.TOOL_INPUT_AVAILABLE,
                    tool_call_id="tc_x",
                    tool_name="list_transactions",
                    arguments={},
                ),
                LLMEvent(type=LLMEventType.STEP_FINISH),
                LLMEvent(type=LLMEventType.MESSAGE_FINISH, stop_reason="tool_use", iterations=1),
            ]
        ]
    )
    service = ChatService(provider=provider, mcp=None, max_iterations=2)
    blob = b""
    async for chunk in service.stream(messages=[{"role": "user", "content": "?"}]):
        blob += chunk

    events = _parse_sse(blob)
    finishes = [e for e in events if e["type"] == "finish"]
    assert finishes and finishes[-1]["finishReason"] == "length"
    deltas = [e for e in events if e["type"] == "text-delta"]
    assert any("loop limit reached" in d["delta"] for d in deltas)


@pytest.mark.asyncio
async def test_upstream_error_emits_error_event(fake_mcp):
    class Boom(LLMProvider):
        async def stream(self, messages, tools):
            raise UpstreamLLMError("rate limited")
            yield  # pragma: no cover

    service = ChatService(provider=Boom(), mcp=None, max_iterations=4)
    blob = b""
    async for chunk in service.stream(messages=[{"role": "user", "content": "?"}]):
        blob += chunk

    events = _parse_sse(blob)
    err = [e for e in events if e["type"] == "error"]
    assert err and "rate limited" in err[0]["errorText"]
