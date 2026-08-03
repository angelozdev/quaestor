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
from quaestor.chat.mcp.client import CallToolResult
from quaestor.chat.service import ChatService

# --- fakes -----------------------------------------------------------------


class ScriptedProvider(LLMProvider):
    """Yields a pre-scripted list of LLMEvent sequences, one per stream() call."""

    def __init__(self, scripts: list[list[LLMEvent]]) -> None:
        self._scripts = list(scripts)
        self.calls = 0

    async def stream(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> AsyncIterator[LLMEvent]:
        idx = min(self.calls, len(self._scripts) - 1)
        self.calls += 1
        for ev in self._scripts[idx]:
            yield ev


class FakeMCPClient:
    """Stand-in for MCPClient that returns canned tool results."""

    def __init__(self, results: dict[str, CallToolResult]) -> None:
        self._results = results
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def __aenter__(self) -> FakeMCPClient:
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
            {"list_transactions": CallToolResult(output='[{"id":1,"payee":"Café","amount":15000}]', is_error=False)}
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
                LLMEvent(type=LLMEventType.MESSAGE_FINISH, stop_reason="stop", iterations=1),
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
                LLMEvent(type=LLMEventType.MESSAGE_FINISH, stop_reason="tool-calls", iterations=1),
            ],
            [
                LLMEvent(type=LLMEventType.MESSAGE_START, message_id="m2", model="MiniMax-M3"),
                LLMEvent(type=LLMEventType.TEXT_START, content_index=0),
                LLMEvent(type=LLMEventType.TEXT_DELTA, delta="Tienes 1 gasto."),
                LLMEvent(type=LLMEventType.TEXT_END, content_index=0),
                LLMEvent(type=LLMEventType.STEP_FINISH),
                LLMEvent(type=LLMEventType.MESSAGE_FINISH, stop_reason="stop", iterations=1),
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
async def test_tool_error_emits_error_chunk_and_loop_continues(fake_mcp):
    fake_mcp["client"] = FakeMCPClient({"list_transactions": CallToolResult(output="account not found", is_error=True)})

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
                LLMEvent(type=LLMEventType.MESSAGE_FINISH, stop_reason="tool-calls", iterations=1),
            ],
            [
                LLMEvent(type=LLMEventType.MESSAGE_START, message_id="m2", model="MiniMax-M3"),
                LLMEvent(type=LLMEventType.TEXT_START, content_index=0),
                LLMEvent(type=LLMEventType.TEXT_DELTA, delta="No pude."),
                LLMEvent(type=LLMEventType.TEXT_END, content_index=0),
                LLMEvent(type=LLMEventType.STEP_FINISH),
                LLMEvent(type=LLMEventType.MESSAGE_FINISH, stop_reason="stop", iterations=1),
            ],
        ]
    )
    service = ChatService(provider=provider, mcp=None, max_iterations=4)
    blob = b""
    async for chunk in service.stream(messages=[{"role": "user", "content": "?"}]):
        blob += chunk

    events = _parse_sse(blob)
    errs = [e for e in events if e["type"] == "tool-output-error"]
    assert errs and "account not found" in errs[0]["errorText"]


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
                LLMEvent(type=LLMEventType.MESSAGE_FINISH, stop_reason="tool-calls", iterations=1),
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


@pytest.mark.asyncio
async def test_provider_timeout_emits_error_and_dones(fake_mcp):
    """When provider.stream stalls past request_timeout_s, the service must
    emit a code='timeout' error event and a [DONE] sentinel, then stop.
    """

    class StallProvider(LLMProvider):
        async def stream(self, messages, tools):
            # Sleep longer than the test timeout so wait_for trips.
            import asyncio

            await asyncio.sleep(1.0)
            yield LLMEvent(type=LLMEventType.MESSAGE_START, message_id="x")  # pragma: no cover

    service = ChatService(provider=StallProvider(), mcp=None, max_iterations=2, request_timeout_s=0.05)
    blob = b""
    async for chunk in service.stream(messages=[{"role": "user", "content": "?"}]):
        blob += chunk

    events = _parse_sse(blob)
    errs = [e for e in events if e["type"] == "error"]
    assert errs and errs[0]["errorText"] == "upstream timeout"
    # Last event must be the [DONE] sentinel.
    assert events[-1]["type"] == "__DONE__"


@pytest.mark.asyncio
async def test_tool_call_raises_is_recovered_not_500(fake_mcp):
    """Regression for ADR-0016: if an MCP tool call RAISES (not just returns
    is_error=True), the SSE stream must keep going. The LLM sees a
    tool-output-available event with isError=True and gets a chance to
    self-correct on the next iteration. The stream must end with [DONE],
    not 500.

    Reproduces the production case: LLM called `monthly_report("")` and
    fastmcp raised `ToolError: Input should be a valid dictionary...`.
    """
    from fastmcp.exceptions import ToolError

    class RaisingToolMCP(FakeMCPClient):
        async def call_tool(self, name, arguments):
            # Match fastmcp's production behavior: bad args → ToolError.
            raise ToolError(
                f"1 validation error for {name}Arguments: inp Input should be a valid dictionary, got {arguments!r}"
            )

    fake_mcp["client"] = RaisingToolMCP({})

    provider = ScriptedProvider(
        [
            [
                LLMEvent(type=LLMEventType.MESSAGE_START, message_id="m1", model="MiniMax-M3"),
                LLMEvent(
                    type=LLMEventType.TOOL_INPUT_AVAILABLE,
                    tool_call_id="tc_1",
                    tool_name="monthly_report",
                    arguments="",  # the exact production mistake
                ),
                LLMEvent(type=LLMEventType.STEP_FINISH),
                LLMEvent(type=LLMEventType.MESSAGE_FINISH, stop_reason="tool-calls", iterations=1),
            ],
            [
                LLMEvent(type=LLMEventType.MESSAGE_START, message_id="m2", model="MiniMax-M3"),
                LLMEvent(type=LLMEventType.TEXT_START, content_index=0),
                LLMEvent(
                    type=LLMEventType.TEXT_DELTA,
                    delta="No pude generar el resumen; necesito el mes en formato YYYY-MM.",
                ),
                LLMEvent(type=LLMEventType.TEXT_END, content_index=0),
                LLMEvent(type=LLMEventType.STEP_FINISH),
                LLMEvent(type=LLMEventType.MESSAGE_FINISH, stop_reason="stop", iterations=2),
            ],
        ]
    )
    service = ChatService(provider=provider, mcp=None, max_iterations=4)
    blob = b""
    async for chunk in service.stream(messages=[{"role": "user", "content": "?"}]):
        blob += chunk

    events = _parse_sse(blob)
    # The bad call produced an tool-output-error chunk (not a 500).
    errs = [e for e in events if e["type"] == "tool-output-error"]
    assert errs, "tool-output-error event missing — stream died?"
    assert "validation error" in errs[0]["errorText"]
    # The LLM's second iteration text reached the client — proof the loop survived.
    deltas = [e for e in events if e["type"] == "text-delta"]
    assert any("No pude" in d.get("delta", "") for d in deltas)
    # Stream ended cleanly with [DONE], not a 500.
    assert events[-1]["type"] == "__DONE__"


@pytest.mark.asyncio
async def test_tool_call_timeout_emits_error_chunk_and_continues(fake_mcp):
    """A timed-out MCP tool call emits tool-output-available with is_error and
    a tool message of 'timeout', then the loop keeps going (does not abort).
    """
    import asyncio

    class HangingToolMCP(FakeMCPClient):
        async def call_tool(self, name, arguments):
            await asyncio.sleep(1.0)
            return await super().call_tool(name, arguments)  # pragma: no cover

    fake_mcp["client"] = HangingToolMCP({"list_transactions": CallToolResult(output='[{"id":1}]', is_error=False)})

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
                LLMEvent(type=LLMEventType.MESSAGE_FINISH, stop_reason="tool-calls", iterations=1),
            ],
            [
                LLMEvent(type=LLMEventType.MESSAGE_START, message_id="m2", model="MiniMax-M3"),
                LLMEvent(type=LLMEventType.TEXT_START, content_index=0),
                LLMEvent(type=LLMEventType.TEXT_DELTA, delta="ok"),
                LLMEvent(type=LLMEventType.TEXT_END, content_index=0),
                LLMEvent(type=LLMEventType.STEP_FINISH),
                LLMEvent(type=LLMEventType.MESSAGE_FINISH, stop_reason="stop", iterations=1),
            ],
        ]
    )
    service = ChatService(provider=provider, mcp=None, max_iterations=4, request_timeout_s=0.05)
    blob = b""
    async for chunk in service.stream(messages=[{"role": "user", "content": "?"}]):
        blob += chunk

    events = _parse_sse(blob)
    errs = [e for e in events if e["type"] == "tool-output-error"]
    assert errs and errs[0]["errorText"] == "timeout"
    # Loop survived: a text-delta event appeared in the second iteration.
    deltas = [e for e in events if e["type"] == "text-delta"]
    assert any(d.get("delta") == "ok" for d in deltas)


# --- ADR-0017: system prompt injection -------------------------------------


class RecordingProvider(LLMProvider):
    """Captures the `messages` list passed to each stream() call."""

    def __init__(self) -> None:
        self.calls: list[list[dict[str, Any]]] = []

    async def stream(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> AsyncIterator[LLMEvent]:
        self.calls.append(list(messages))
        yield LLMEvent(type=LLMEventType.MESSAGE_START, message_id="m")
        yield LLMEvent(type=LLMEventType.MESSAGE_FINISH, stop_reason="stop", iterations=1)


@pytest.mark.asyncio
async def test_system_prompt_prepended_when_set(fake_mcp):
    """ADR-0017: when `system_prompt` is passed, it lands as the first
    message the provider sees on every iteration."""
    provider = RecordingProvider()
    service = ChatService(
        provider=provider,
        mcp=None,
        max_iterations=2,
        system_prompt="Eres un coach.",
    )
    blob = b""
    async for chunk in service.stream(messages=[{"role": "user", "content": "hola"}]):
        blob += chunk

    assert provider.calls, "provider was never called"
    first = provider.calls[0]
    assert first[0] == {"role": "system", "content": "Eres un coach."}
    assert first[1] == {"role": "user", "content": "hola"}


@pytest.mark.asyncio
async def test_no_system_prompt_means_no_injection(fake_mcp):
    """Back-compat: `system_prompt=None` (or unset) preserves pre-ADR-0017
    behavior — the messages list reaches the provider untouched."""
    provider = RecordingProvider()
    service = ChatService(provider=provider, mcp=None, max_iterations=2)
    async for _ in service.stream(messages=[{"role": "user", "content": "hola"}]):
        pass

    assert provider.calls
    first = provider.calls[0]
    assert first == [{"role": "user", "content": "hola"}]
    assert not any(m.get("role") == "system" for m in first)


@pytest.mark.asyncio
async def test_empty_system_prompt_treated_as_unset(fake_mcp):
    """An empty string is a no-op, same as None."""
    provider = RecordingProvider()
    service = ChatService(provider=provider, mcp=None, max_iterations=2, system_prompt="")
    async for _ in service.stream(messages=[{"role": "user", "content": "hola"}]):
        pass

    assert provider.calls[0] == [{"role": "user", "content": "hola"}]


@pytest.mark.asyncio
async def test_user_supplied_system_message_kept_after_injected_one(fake_mcp):
    """If the frontend sends its own system-role message, our injected prompt
    comes first and the user's sits after it — both visible to the LLM."""
    provider = RecordingProvider()
    service = ChatService(
        provider=provider,
        mcp=None,
        max_iterations=2,
        system_prompt="server-prompt",
    )
    async for _ in service.stream(
        messages=[
            {"role": "system", "content": "client-prompt"},
            {"role": "user", "content": "hola"},
        ]
    ):
        pass

    first = provider.calls[0]
    assert first[0] == {"role": "system", "content": "server-prompt"}
    assert first[1] == {"role": "system", "content": "client-prompt"}
    assert first[2] == {"role": "user", "content": "hola"}


@pytest.mark.asyncio
async def test_system_prompt_present_on_every_iteration(fake_mcp):
    """The system message is re-prepended into the conversation every
    iteration so the LLM never loses sight of it across tool-call turns."""
    script = [
        [
            LLMEvent(type=LLMEventType.MESSAGE_START, message_id="m1"),
            LLMEvent(
                type=LLMEventType.TOOL_INPUT_AVAILABLE,
                tool_call_id="tc_1",
                tool_name="list_transactions",
                arguments={},
            ),
            LLMEvent(type=LLMEventType.STEP_FINISH),
            LLMEvent(
                type=LLMEventType.MESSAGE_FINISH,
                stop_reason="tool-calls",
                iterations=1,
            ),
        ],
        [
            LLMEvent(type=LLMEventType.MESSAGE_START, message_id="m2"),
            LLMEvent(type=LLMEventType.TEXT_START, content_index=0),
            LLMEvent(type=LLMEventType.TEXT_DELTA, delta="ok"),
            LLMEvent(type=LLMEventType.TEXT_END, content_index=0),
            LLMEvent(type=LLMEventType.STEP_FINISH),
            LLMEvent(
                type=LLMEventType.MESSAGE_FINISH,
                stop_reason="stop",
                iterations=2,
            ),
        ],
    ]

    class HybridProvider(LLMProvider):
        def __init__(self) -> None:
            self.calls: list[list[dict[str, Any]]] = []
            self._idx = 0

        async def stream(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> AsyncIterator[LLMEvent]:
            self.calls.append(list(messages))
            i = min(self._idx, len(script) - 1)
            self._idx += 1
            for ev in script[i]:
                yield ev

    provider = HybridProvider()
    service = ChatService(
        provider=provider,
        mcp=None,
        max_iterations=4,
        system_prompt="persona",
    )
    async for _ in service.stream(messages=[{"role": "user", "content": "?"}]):
        pass

    # Two stream() calls (one per iteration). Both must start with the
    # system message — proving the prepend survives the loop, not just
    # the first turn.
    assert len(provider.calls) == 2
    for call in provider.calls:
        assert call[0] == {"role": "system", "content": "persona"}
