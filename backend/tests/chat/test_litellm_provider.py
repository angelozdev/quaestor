"""Unit tests for LiteLLMProvider.

Mock `litellm.acompletion` (not the LLM API). Cover:
  - text-only stream → TEXT_DELTA events
  - tool-call stream → TOOL_INPUT_START/DELTA/AVAILABLE events with arguments reassembled
  - upstream error → UpstreamLLMError
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import litellm
import pytest

from quaestor.chat.llm.litellm_provider import LiteLLMProvider
from quaestor.chat.llm.provider import (
    LLMEventType,
    UpstreamLLMError,
)


def _chunk(
    *,
    content: str | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
    finish_reason: str | None = None,
) -> Any:
    """Build a minimal litellm chunk-shaped object (a SimpleNamespace is enough)."""
    from types import SimpleNamespace

    delta: dict[str, Any] = {}
    if content is not None:
        delta["content"] = content
    if tool_calls is not None:
        delta["tool_calls"] = tool_calls
    return SimpleNamespace(
        id="msg_test_1",
        choices=[
            SimpleNamespace(
                index=0,
                delta=SimpleNamespace(**delta) if delta else SimpleNamespace(),
                finish_reason=finish_reason,
            )
        ],
    )


def _tool_call_delta(
    *, index: int, id: str | None = None, name: str | None = None, args: str | None = None
) -> Any:
    from types import SimpleNamespace

    func: SimpleNamespace | None = None
    if name is not None:
        func = SimpleNamespace(name=name, arguments=args or "")
    elif args is not None:
        func = SimpleNamespace(name=None, arguments=args)
    return SimpleNamespace(
        index=index,
        id=id,
        function=func,
    )


async def _collect(gen):
    return [ev async for ev in gen]


@pytest.mark.asyncio
async def test_text_only_stream_emits_message_start_then_deltas_then_finish():
    chunks = [
        _chunk(content=""),
        _chunk(content="Hola"),
        _chunk(content=" mundo"),
        _chunk(content=None, finish_reason="stop"),
    ]

    async def fake_acompletion(**kwargs):
        for c in chunks:
            yield c

    with patch("litellm.acompletion", side_effect=fake_acompletion):
        provider = LiteLLMProvider(model="anthropic/MiniMax-M3", api_key="x", base_url=None)
        events = await _collect(
            provider.stream(messages=[{"role": "user", "content": "hola"}], tools=[])
        )

    types = [e.type for e in events]
    assert types[0] == LLMEventType.MESSAGE_START
    assert types[-1] == LLMEventType.MESSAGE_FINISH
    assert LLMEventType.STEP_FINISH in types
    text_deltas = [e.delta for e in events if e.type == LLMEventType.TEXT_DELTA]
    assert "".join(d for d in text_deltas if d) == "Hola mundo"


@pytest.mark.asyncio
async def test_tool_call_stream_assembles_arguments_from_deltas():
    chunks = [
        _chunk(
            tool_calls=[_tool_call_delta(index=0, id="tc_1", name="list_transactions", args="")]
        ),
        _chunk(tool_calls=[_tool_call_delta(index=0, args='{"date_')]),
        _chunk(tool_calls=[_tool_call_delta(index=0, args='from":')]),
        _chunk(tool_calls=[_tool_call_delta(index=0, args='"2026-06-01"}')]),
        _chunk(content=None, finish_reason="tool_calls"),
    ]

    async def fake_acompletion(**kwargs):
        for c in chunks:
            yield c

    with patch("litellm.acompletion", side_effect=fake_acompletion):
        provider = LiteLLMProvider(model="anthropic/MiniMax-M3", api_key="x", base_url=None)
        events = await _collect(
            provider.stream(
                messages=[{"role": "user", "content": "gastos de junio"}],
                tools=[{"type": "function", "function": {"name": "list_transactions"}}],
            )
        )

    available = [e for e in events if e.type == LLMEventType.TOOL_INPUT_AVAILABLE]
    assert len(available) == 1
    assert available[0].tool_call_id == "tc_1"
    assert available[0].tool_name == "list_transactions"
    assert available[0].arguments == {"date_from": "2026-06-01"}

    starts = [e for e in events if e.type == LLMEventType.TOOL_INPUT_START]
    assert len(starts) == 1
    assert starts[0].tool_call_id == "tc_1"
    assert starts[0].tool_name == "list_transactions"

    # finish_reason mapping: LiteLLM "tool_calls" → Vercel "tool-calls" (hyphen).
    finishes = [e for e in events if e.type == LLMEventType.MESSAGE_FINISH]
    assert len(finishes) == 1
    assert finishes[0].stop_reason == "tool-calls"


@pytest.mark.asyncio
async def test_finish_reason_mapping_to_vercel_enum():
    """The Vercel AI SDK UI Message Stream enum is strict:
    `stop | length | content-filter | tool-calls | error | other`.
    We must map provider-specific values here, not in the renderer.
    """
    from quaestor.chat.llm.litellm_provider import _to_vercel_finish_reason

    # OpenAI/LiteLLM spellings
    assert _to_vercel_finish_reason("stop") == "stop"
    assert _to_vercel_finish_reason("length") == "length"
    assert _to_vercel_finish_reason("tool_calls") == "tool-calls"
    assert _to_vercel_finish_reason("content_filter") == "content-filter"
    # Anthropic spellings
    assert _to_vercel_finish_reason("end_turn") == "stop"
    assert _to_vercel_finish_reason("max_tokens") == "length"
    assert _to_vercel_finish_reason("tool_use") == "tool-calls"
    assert _to_vercel_finish_reason("stop_sequence") == "stop"
    # Null / unknown
    assert _to_vercel_finish_reason(None) == "stop"
    assert _to_vercel_finish_reason("wat") == "other"


@pytest.mark.asyncio
async def test_message_id_is_uuid4_not_msg_unknown():
    """Per the Vercel UI Message Stream spec, messageId is an opaque
    identifier for the whole message. Generate it locally with uuid4 so it
    works even when the upstream chunk lacks `.id` (Anthropic native).
    """
    import re

    chunks = [
        # Deliberately NO `id` field on the chunk — simulates Anthropic.
        _chunk(content="Hola"),
        _chunk(content=None, finish_reason="stop"),
    ]

    async def fake_acompletion(**kwargs):
        for c in chunks:
            yield c

    with patch("litellm.acompletion", side_effect=fake_acompletion):
        provider = LiteLLMProvider(model="anthropic/MiniMax-M3", api_key="x", base_url=None)
        events = await _collect(
            provider.stream(messages=[{"role": "user", "content": "hola"}], tools=[])
        )

    starts = [e for e in events if e.type == LLMEventType.MESSAGE_START]
    assert len(starts) == 1, f"expected exactly one MESSAGE_START, got {len(starts)}"
    assert starts[0].message_id is not None
    assert re.fullmatch(r"msg-[0-9a-f]{32}", starts[0].message_id), (
        f"message_id should be 'msg-<32 hex chars>', got {starts[0].message_id!r}"
    )


@pytest.mark.asyncio
async def test_upstream_error_raises_upstream_llm_error():
    def fake_api_error(message: str) -> litellm.APIError:
        return litellm.APIError(500, message, "fake", "fake-model")

    async def fake_acompletion(**kwargs):
        raise fake_api_error("boom")
        yield  # pragma: no cover  (generator never runs)

    with patch("litellm.acompletion", side_effect=fake_acompletion):
        provider = LiteLLMProvider(model="anthropic/MiniMax-M3", api_key="x", base_url=None)
        with pytest.raises(UpstreamLLMError):
            async for _ in provider.stream(messages=[], tools=[]):
                pass
