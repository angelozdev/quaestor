"""LLMProvider Protocol + LLMEvent types.

This is the single seam between the agentic loop and "the model". Every
LLM-driven event the loop can react to is enumerated here as an LLMEventType;
the per-event payload lives on the LLMEvent dataclass.

The mapping to Vercel AI SDK UI Message Stream SSE bytes happens in
`quaestor.chat.events` — `provider.py` does NOT know about SSE shapes.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import Any, Protocol, runtime_checkable


class LLMEventType(StrEnum):
    """Discriminator for LLMEvent. Mirrors Vercel AI SDK UI Message Stream."""

    MESSAGE_START = "start"               # → Vercel `start`
    TEXT_START = "text-start"             # → Vercel `text-start`
    TEXT_DELTA = "text-delta"             # → Vercel `text-delta`
    TEXT_END = "text-end"                 # → Vercel `text-end`
    TOOL_INPUT_START = "tool-input-start"      # → Vercel `tool-input-start`
    TOOL_INPUT_DELTA = "tool-input-delta"      # → Vercel `tool-input-delta`
    TOOL_INPUT_AVAILABLE = "tool-input-available"  # → Vercel `tool-input-available`
    TOOL_OUTPUT_AVAILABLE = "tool-output-available"  # → Vercel `tool-output-available`
    TOOL_OUTPUT_ERROR = "tool-output-error"   # → Vercel `tool-output-error` (ADR-0022)
    STEP_FINISH = "finish-step"           # → Vercel `finish-step`
    MESSAGE_FINISH = "finish"             # → Vercel `finish`
    ERROR = "error"                       # → Vercel `error`


@dataclass
class LLMEvent:
    """One streamed event from the LLM.

    Only the fields relevant to `type` are populated. Unused fields are
    left at their dataclass default (None / empty).
    """

    type: LLMEventType

    # text-*
    delta: str | None = None
    content_index: int | None = None  # Vercel `id` for text-*

    # tool-input-* / tool-output-available
    tool_call_id: str | None = None
    tool_name: str | None = None
    arguments_delta: str | None = None
    arguments: dict[str, Any] | None = None
    output: str | None = None
    is_error: bool = False
    error_text: str | None = None  # Vercel `errorText` for tool-output-error

    # message-level
    message_id: str | None = None
    model: str | None = None
    stop_reason: str | None = None
    iterations: int | None = None
    # Token usage, normalized to Vercel wire keys. `None` = provider didn't
    # report; renderer omits `messageMetadata` in that case.
    # Shape: {"promptTokens": int, "completionTokens": int, "totalTokens": int}
    usage: dict[str, int] | None = None

    # error
    code: str | None = None
    message: str | None = None
    retryable: bool = False


class LLMError(Exception):
    """Base for LLM-layer errors. `code` is one of: 'upstream', 'tool', 'loop'."""


class UpstreamLLMError(LLMError):
    """Provider returned a non-recoverable error (auth, rate limit, 5xx)."""


class ToolNotFoundError(LLMError):
    """LLM emitted a tool_call for a tool we don't know."""


class LoopLimitError(LLMError):
    """Agentic loop hit CHAT_MAX_ITERATIONS."""


@runtime_checkable
class LLMProvider(Protocol):
    """One streaming chat method. Implementations: LiteLLMProvider (today),
    AnthropicNativeProvider / OpenAIProvider (future).
    """

    def stream(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AsyncIterator[LLMEvent]:
        ...
