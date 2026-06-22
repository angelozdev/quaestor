from collections.abc import AsyncIterator
from typing import Any

import pytest

from quaestor.chat.llm.provider import (
    LLMEvent,
    LLMEventType,
    LLMProvider,
)


def test_llm_event_text_delta_carries_delta():
    ev = LLMEvent(type=LLMEventType.TEXT_DELTA, delta="hola")
    assert ev.type == LLMEventType.TEXT_DELTA
    assert ev.delta == "hola"


def test_llm_event_tool_input_available_carries_arguments_dict():
    args = {"date_from": "2026-06-01", "date_to": "2026-06-30"}
    ev = LLMEvent(
        type=LLMEventType.TOOL_INPUT_AVAILABLE,
        tool_call_id="tc_1",
        tool_name="list_transactions",
        arguments=args,
    )
    assert ev.tool_call_id == "tc_1"
    assert ev.tool_name == "list_transactions"
    assert ev.arguments == args


def test_llm_provider_protocol_is_runtime_checkable():
    class Fake:
        async def stream(
            self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
        ) -> AsyncIterator[LLMEvent]:
            if False:
                yield  # pragma: no cover

    assert isinstance(Fake(), LLMProvider)
