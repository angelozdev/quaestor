"""ChatService — the agentic loop + SSE shaping.

Public surface: `ChatService(provider, mcp, max_iterations).stream(messages)`
yields SSE bytes that match the Vercel AI SDK UI Message Stream protocol.

The service:
  1. opens `async with MCPClient(mcp)` once for the request
  2. fetches the (cached) OpenAI-shaped tool list
  3. loops `provider.stream(...)` until no tool calls arrive or the cap is hit
  4. on each tool call, dispatches via `mcp_client.call_tool(...)` and emits
     `tool-output-available` (with `isError:true` when the tool flagged an error)
  5. appends assistant+tool messages to the in-request conversation list so
     the LLM sees its own prior tool calls on the next iteration
  6. emits a final `finish` event and the `[DONE]` sentinel
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from mcp.server.fastmcp import FastMCP

from .events import done_bytes, serialize_event
from .llm.provider import (
    LLMEvent,
    LLMEventType,
    LLMProvider,
    LoopLimitError,
    ToolNotFoundError,
    UpstreamLLMError,
)
from .mcp.client import MCPClient
from .mcp.schema import get_cached_tools


class ChatService:
    def __init__(
        self,
        provider: LLMProvider,
        mcp: FastMCP,
        max_iterations: int = 8,
        request_timeout_s: float | None = None,
    ) -> None:
        self._provider = provider
        self._mcp = mcp
        self._max_iterations = max_iterations
        self._request_timeout_s = request_timeout_s

    async def stream(self, messages: list[dict[str, Any]]) -> AsyncIterator[bytes]:
        message_id = "msg_unknown"
        tools: list[dict[str, Any]] = []
        conversation: list[dict[str, Any]] = list(messages)

        try:
            async with MCPClient(self._mcp) as mcp_client:
                tools = await get_cached_tools(mcp_client)

                for iteration in range(1, self._max_iterations + 1):
                    tool_calls_this_iter: list[dict[str, Any]] = []

                    try:
                        provider_iter = self._provider.stream(conversation, tools)
                        if self._request_timeout_s is not None:
                            provider_iter = _timeout_iter(
                                provider_iter, self._request_timeout_s
                            )
                        async for event in provider_iter:
                            if event.type == LLMEventType.MESSAGE_START and event.message_id:
                                message_id = event.message_id
                            if event.type == LLMEventType.TOOL_INPUT_AVAILABLE:
                                tool_calls_this_iter.append(
                                    {
                                        "id": event.tool_call_id,
                                        "type": "function",
                                        "function": {
                                            "name": event.tool_name,
                                            "arguments": event.arguments or {},
                                        },
                                    }
                                )
                            yield serialize_event(event, message_id=message_id)
                    except UpstreamLLMError as exc:
                        yield serialize_event(
                            LLMEvent(
                                type=LLMEventType.ERROR,
                                code="upstream",
                                message=str(exc),
                                retryable=True,
                            ),
                            message_id=message_id,
                        )
                        yield done_bytes()
                        return
                    except asyncio.TimeoutError:
                        yield serialize_event(
                            LLMEvent(
                                type=LLMEventType.ERROR,
                                code="timeout",
                                message="upstream timeout",
                                retryable=True,
                            ),
                            message_id=message_id,
                        )
                        yield done_bytes()
                        return

                    if not tool_calls_this_iter:
                        # No tool calls → end of this turn.
                        break

                    # Append the assistant message carrying the tool calls so the
                    # LLM sees them on the next iteration. We model the message
                    # in OpenAI's tool-call shape.
                    conversation.append(
                        {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": tc["id"],
                                    "type": "function",
                                    "function": {
                                        "name": tc["function"]["name"],
                                        "arguments": _json_dumps(tc["function"]["arguments"]),
                                    },
                                }
                                for tc in tool_calls_this_iter
                            ],
                        }
                    )

                    # Dispatch each tool call and append its result.
                    for tc in tool_calls_this_iter:
                        tc_id = tc["id"]
                        tc_name = tc["function"]["name"]
                        tc_args = tc["function"]["arguments"]
                        try:
                            if self._request_timeout_s is not None:
                                result = await asyncio.wait_for(
                                    mcp_client.call_tool(tc_name, tc_args),
                                    timeout=self._request_timeout_s,
                                )
                            else:
                                result = await mcp_client.call_tool(tc_name, tc_args)
                        except ToolNotFoundError as exc:
                            yield serialize_event(
                                LLMEvent(
                                    type=LLMEventType.TOOL_OUTPUT_AVAILABLE,
                                    tool_call_id=tc_id,
                                    output=f"tool not found: {exc}",
                                    is_error=True,
                                ),
                                message_id=message_id,
                            )
                            conversation.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tc_id,
                                    "content": f"tool not found: {exc}",
                                }
                            )
                            continue
                        except asyncio.TimeoutError:
                            yield serialize_event(
                                LLMEvent(
                                    type=LLMEventType.TOOL_OUTPUT_AVAILABLE,
                                    tool_call_id=tc_id,
                                    output="timeout",
                                    is_error=True,
                                ),
                                message_id=message_id,
                            )
                            conversation.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tc_id,
                                    "content": "timeout",
                                }
                            )
                            continue
                        yield serialize_event(
                            LLMEvent(
                                type=LLMEventType.TOOL_OUTPUT_AVAILABLE,
                                tool_call_id=tc_id,
                                output=result.output,
                                is_error=result.is_error,
                            ),
                            message_id=message_id,
                        )
                        conversation.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc_id,
                                "content": result.output,
                            }
                        )
                else:
                    # Loop exhausted (didn't `break`). Emit the loop-limit notice.
                    yield serialize_event(
                        LLMEvent(type=LLMEventType.TEXT_START, content_index=0),
                        message_id=message_id,
                    )
                    yield serialize_event(
                        LLMEvent(
                            type=LLMEventType.TEXT_DELTA, delta="loop limit reached"
                        ),
                        message_id=message_id,
                    )
                    yield serialize_event(
                        LLMEvent(type=LLMEventType.TEXT_END, content_index=0),
                        message_id=message_id,
                    )
                    yield serialize_event(
                        LLMEvent(
                            type=LLMEventType.MESSAGE_FINISH,
                            stop_reason="length",
                            iterations=self._max_iterations,
                        ),
                        message_id=message_id,
                    )

        except LoopLimitError:
            # Defensive — currently raised nowhere, kept for future invariants.
            yield serialize_event(
                LLMEvent(
                    type=LLMEventType.ERROR,
                    code="loop",
                    message="loop limit reached",
                    retryable=False,
                ),
                message_id=message_id,
            )

        yield done_bytes()


def _json_dumps(obj: Any) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False)


async def _timeout_iter(
    source: AsyncIterator[LLMEvent], timeout_s: float
) -> AsyncIterator[LLMEvent]:
    """Yield events from `source`, aborting with asyncio.TimeoutError when the
    gap between events exceeds `timeout_s`.

    `asyncio.wait_for` cannot wrap an async generator directly, so we drain
    events one-by-one via `wait_for(anext(source), timeout_s)`. A long idle
    upstream (e.g. a stalled SSE connection) raises TimeoutError, which the
    caller turns into the `error` SSE event.
    """
    while True:
        try:
            event = await asyncio.wait_for(anext(source), timeout=timeout_s)
        except StopAsyncIteration:
            return
        yield event
