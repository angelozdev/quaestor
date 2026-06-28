"""Strict-shape mirror of the AI SDK v3 UI Message Stream chunk schema.

The AI SDK React client (`DefaultChatTransport.processResponseStream`,
`frontend/node_modules/ai/dist/index.mjs`) validates every incoming SSE
chunk through `uiMessageChunkSchema`. Every variant in that schema is a
`z7.strictObject` (rejects unknown keys). The Python equivalent is a
Pydantic model with `model_config = ConfigDict(extra="forbid")`.

This module is the single source of truth for the wire shape we emit
from `quaestor.chat.events.serialize_event`. The behavior test in
`tests/chat/test_sse_schema.py` round-trips every chunk the service
emits through `UIMessageChunk.model_validate(...)` — that's the same
validation the AI SDK React client performs in production, minus the
network. A drift in the wire shape (e.g. re-introducing `isError` on
`tool-output-available`) is caught immediately.

We only mirror the variants we emit today. Reasoning-* and other
future chunks are added when we emit them — YAGNI.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class _StrictModel(BaseModel):
    """Pydantic equivalent of zod's strictObject: unknown keys rejected."""

    model_config = ConfigDict(extra="forbid")


# Discriminated union over the wire `type` field. Mirrors
# `uiMessageChunkSchema` for the variants we emit.
#
# Fields follow the Vercel UI Message Stream naming (camelCase:
# `toolCallId`, `errorText`, `messageId`, `finishReason`, etc.).


class StartChunk(_StrictModel):
    type: Literal["start"]
    messageId: str


class TextStartChunk(_StrictModel):
    type: Literal["text-start"]
    id: str


class TextDeltaChunk(_StrictModel):
    type: Literal["text-delta"]
    id: str
    delta: str


class TextEndChunk(_StrictModel):
    type: Literal["text-end"]
    id: str


class ToolInputStartChunk(_StrictModel):
    type: Literal["tool-input-start"]
    toolCallId: str
    toolName: str


class ToolInputDeltaChunk(_StrictModel):
    type: Literal["tool-input-delta"]
    toolCallId: str
    inputTextDelta: str


class ToolInputAvailableChunk(_StrictModel):
    type: Literal["tool-input-available"]
    toolCallId: str
    toolName: str
    input: dict[str, Any]


class ToolOutputAvailableChunk(_StrictModel):
    """Success only. Tool errors go through ToolOutputErrorChunk."""

    type: Literal["tool-output-available"]
    toolCallId: str
    output: Any  # AI SDK v3: z7.unknown()


class ToolOutputErrorChunk(_StrictModel):
    """Failure: tool raised, timed out, was not found, or returned
    `is_error=True`. Mirrors the SDK's strictObject at
    `frontend/node_modules/ai/dist/index.mjs:5473-5481`."""

    type: Literal["tool-output-error"]
    toolCallId: str
    errorText: str


class FinishStepChunk(_StrictModel):
    type: Literal["finish-step"]


class FinishChunk(_StrictModel):
    type: Literal["finish"]
    finishReason: str
    messageMetadata: dict[str, Any] | None = None


class ErrorChunk(_StrictModel):
    type: Literal["error"]
    errorText: str


# Discriminated union — `model_validate` dispatches on the `type` field.
# A bare `X | Y` union and `Annotated[Union[...], Field(discriminator=...)]`
# BOTH fail to expose `model_validate` (it lives on `BaseModel`, not on
# `types.UnionType`/`typing.Union`). We use `TypeAdapter` for the actual
# dispatch and expose `UIMessageChunk.model_validate(...)` via a thin
# wrapper so callers (and the AI SDK v3 mirror contract) use a
# `BaseModel`-shaped API.
class _UIMessageChunkAdapter:
    """Thin facade that exposes `model_validate(...)` over the union
    `TypeAdapter`. Routes by `type` thanks to the discriminator."""

    def __init__(self) -> None:
        self._adapter: TypeAdapter = TypeAdapter(
            Annotated[
                Union[
                    StartChunk,
                    TextStartChunk,
                    TextDeltaChunk,
                    TextEndChunk,
                    ToolInputStartChunk,
                    ToolInputDeltaChunk,
                    ToolInputAvailableChunk,
                    ToolOutputAvailableChunk,
                    ToolOutputErrorChunk,
                    FinishStepChunk,
                    FinishChunk,
                    ErrorChunk,
                ],
                Field(discriminator="type"),
            ]
        )

    def model_validate(self, data: Any) -> Any:  # noqa: ANN401 — mirror of BaseModel API
        return self._adapter.validate_python(data)


UIMessageChunk = _UIMessageChunkAdapter()

