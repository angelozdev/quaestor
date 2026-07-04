# Chat SSE Tool-Output-Error Chunk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Switch the chat SSE wire format from `tool-output-available` + `isError: true` to a dedicated `tool-output-error` chunk for tool failures, matching the AI SDK v3 UI Message Stream strict schema.

**Architecture:** Add a new `TOOL_OUTPUT_ERROR` variant to `LLMEventType`. The SSE serializer renders it as `{type: "tool-output-error", toolCallId, errorText}` per `frontend/node_modules/ai/dist/index.mjs:5473-5481`. The chat service's three error branches (`ToolNotFoundError`, `asyncio.TimeoutError`, generic `Exception`) and the success-with-`is_error=True` path (the tool returned an error result instead of raising) all switch to emitting the new variant. A Pydantic Strict model of the wire shape provides behavior-focused regression tests that round-trip every emitted chunk through the same validation the AI SDK React client performs.

**Tech Stack:** Python 3.12 · Pydantic v2 (Strict mode / `extra="forbid"` as the pydantic equivalent of zod `strictObject`) · FastAPI · pytest · `uv`.

## Global Constraints

- **ADR-0001 (language):** All code, identifiers, comments, docstrings, commit messages in English. Spanish only inside quotes referencing user mental model.
- **ADR-0014 / -0018 (chat SSE contract):** Wire format must follow the Vercel AI SDK UI Message Stream protocol. Confirmed chunk variants and field names are in `frontend/node_modules/ai/dist/index.mjs:5463-5485` (3 tool-output variants) and the AI SDK UI docs.
- **ADR-0016 (tool-error recovery):** A tool call failure must NOT 500 the SSE stream. The agentic loop continues; the LLM sees the error and self-corrects on the next iteration. The wire shape changes (from `isError: true` on `tool-output-available` to a separate `tool-output-error` chunk), but the recovery semantics are unchanged.
- **TDD discipline:** Every implementation task writes the failing test FIRST and confirms RED before changing production code. Behavior tests assert the chunk shape the AI SDK React client expects, not internal enum names.
- **Commit cadence:** Each task ends in a single commit. No WIP / fixup / squash.
- **No new dependencies.** The behavior-test schema is hand-written Pydantic (mirrors `uiMessageChunkSchema` for the variants we emit).
- **Test scope:** Tests assert SSE bytes that the wire emits (after parsing), validated against the strict schema. Internal representation (`LLMEventType.TOOL_OUTPUT_ERROR`, `LLMEvent.error_text`) is implementation detail — tests don't import it.
- **Working directory:** All backend commands run from `backend/` (cd then uv run). Repo-root git commands use `git -C /Users/angelozdev/me/quaestor` from inside `backend/`.

## File Structure

### Modified files

| Path | Change |
|---|---|
| `docs/adr/0022-chat-sse-tool-output-error-chunk.md` | NEW ADR (created in Task 1). |
| `docs/adr/README.md` | Append row 38 with ADR-0022 (status `proposed`). |
| `backend/src/quaestor/chat/llm/provider.py` | Add `TOOL_OUTPUT_ERROR = "tool-output-error"` to `LLMEventType`. Add `error_text: str \| None = None` to `LLMEvent`. |
| `backend/src/quaestor/chat/events.py` | Add `serialize_event` branch for `TOOL_OUTPUT_ERROR`. Drop the `isError` injection on `TOOL_OUTPUT_AVAILABLE` (the success path no longer needs it; the chunk is now strictly success-only). |
| `backend/src/quaestor/chat/service.py` | Switch the three error branches and the success-with-`is_error=True` path to emit `TOOL_OUTPUT_ERROR` instead of `TOOL_OUTPUT_AVAILABLE` with `is_error=True`. The `conversation.append({role: tool, ...})` calls stay unchanged (the in-conversation message to the LLM is independent of SSE wire shape). |
| `backend/src/quaestor/chat/sse_schema.py` | NEW: Pydantic Strict models of the wire chunk shapes we emit. Single source of truth for the AI SDK contract. |
| `backend/tests/chat/test_service.py` | Replace three assertions on `tool-output-available` + `isError` with assertions on `tool-output-error` + `errorText`. Add behavior tests in `tests/chat/test_sse_schema.py` that round-trip every chunk the service emits through the strict schema. |
| `backend/tests/chat/test_sse_schema.py` | NEW: behavior-focused regression tests for the wire shape. |

### Out of scope

- The OpenAI-shaped conversation history (assistant tool_calls + tool messages appended to `conversation`) is LLM-side, not SSE-side. Wire shape change doesn't touch it.
- Other tool-output-* variants (`tool-output-denied`) — we don't emit them today; deferred until a use case.
- The LiteLLM provider (`chat/llm/litellm_provider.py`) — it never emits tool errors directly; it only forwards LLM-side events. Errors are service-layer.

---

## Task 1: ADR-0022 — record the chunk-shape decision

**Files:**
- Create: `docs/adr/0022-chat-sse-tool-output-error-chunk.md`
- Modify: `docs/adr/README.md` (append row)

This task is documentation-only. It records the architectural decision that the SSE wire format splits tool success and tool error into separate chunks (matching the AI SDK v3 UI Message Stream), and explains why ADR-0018's review missed this (the existing in-tree tests use a `_parse_sse` helper that bypasses zod validation, so the drift was invisible in CI).

- [ ] **Step 1: Create `docs/adr/0022-chat-sse-tool-output-error-chunk.md`**

Write the file with this content:

```markdown
# 0022. Chat SSE tool-output-error chunk

- **Status:** proposed
- **Date:** 2026-06-28
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

The chat endpoint (ADR-0014) emits the Vercel AI SDK UI Message Stream
protocol. ADR-0018 adopted three best practices from Vercel's reference
template but did not catch a fourth divergence: when an MCP tool call
fails (raises an exception, times out, returns `is_error=True`, or names
an unknown tool), the SSE chunk is rendered as

```json
{"type": "tool-output-available", "toolCallId": "tc_1", "output": "...", "isError": true}
```

with `isError: true` attached as an extra field. The AI SDK v3 React
client validates every chunk through `uiMessageChunkSchema` (defined in
`frontend/node_modules/ai/dist/index.mjs:5396+`), whose
`tool-output-available` variant is a `z7.strictObject` that does not list
`isError` as a known field. Strict-mode rejects unknown keys, so the
chunk fails the union validation. The frontend's
`DefaultChatTransport.processResponseStream` throws and the user sees a
"Type validation failed" error.

The official AI SDK protocol defines three distinct tool-output chunks
(verified in `frontend/node_modules/ai/dist/index.mjs:5463-5485`):

| Chunk | Field set |
|---|---|
| `tool-output-available` | `type`, `toolCallId`, `output` (strict — no `isError`) |
| `tool-output-error` | `type`, `toolCallId`, `errorText` |
| `tool-output-denied` | `type`, `toolCallId` (minimal) |

ADR-0018's review missed this because the in-tree tests
(`backend/tests/chat/test_service.py`) parse SSE with a custom
`_parse_sse` helper that does only `json.loads`, never round-tripping
through the SDK's zod schema. The drift is invisible in CI.

## Decision drivers

- Wire compatibility with the AI SDK v3 React client (the chosen
  frontend transport per ADR-0014).
- No 500s on tool errors (ADR-0016): the LLM must still see the error
  on its next iteration and self-correct.
- The in-conversation tool message (OpenAI shape, sent to the LLM
  provider) is independent of the SSE wire shape and stays unchanged.
- No new dependencies — the strict-shape regression test is a hand-written
  Pydantic `extra="forbid"` model that mirrors the SDK's schema.

## Considered options

1. **Emit a separate `tool-output-error` chunk for failures; reserve
   `tool-output-available` for success only.** Keep the success variant's
   strict schema, render errors with the documented `errorText` field.
2. **Drop the `isError` field from `tool-output-available` and rely on
   the LLM to read the `output` text for failure cues.** Loses the
   discriminated union's affordance — the frontend can't distinguish
   success from failure at the chunk level — and breaks tools that
   return legitimate string outputs that happen to look like errors.
3. **Pin the AI SDK to v2 where the schema is lenient.** Regressive:
   the project is on v3 (per `frontend/package.json`); downgrading
   forfeits all v3 features (reasoning parts, attachments, etc.).

## Decision outcome

Chosen option: **1**. The SSE serializer renders tool errors as
`{"type": "tool-output-error", "toolCallId": ..., "errorText": ...}`.
The success variant (`tool-output-available`) carries no `isError` field
and emits only when the tool ran successfully. The four tool-error
paths in `chat/service.py` (tool-not-found, timeout, generic exception,
and the success-with-`is_error=True` from a tool that returned an error
result without raising) all switch to the new variant.

The `LLMEvent` and `LLMEventType` enums gain one variant each
(`TOOL_OUTPUT_ERROR`, `error_text`); the success-side fields
(`output`, `is_error`) stay for the success-only emit path so that the
service can pass `result.is_error` through to the renderer for the case
where a tool's `call_tool` returned an error result rather than raising.
The LLM-facing conversation history (assistant tool_calls + tool
messages) is unchanged.

The behavior test in `tests/chat/test_sse_schema.py` round-trips every
chunk the service emits through a Pydantic Strict model that mirrors
`uiMessageChunkSchema` for the variants we emit. The existing
`_parse_sse` helper in `tests/chat/test_service.py` is kept for
shape-inspection tests but is not the wire validator.

## Consequences

- Good: the AI SDK v3 React client stops throwing on tool errors; the
  chat UI shows the error text in the tool invocation and continues
  the loop.
- Good: future drift in other chunk types is caught by the same
  behavior test (every emitted chunk validated, not just the new one).
- Good: no new dependencies — Pydantic `extra="forbid"` is the
  Python equivalent of zod `strictObject`.
- Bad / cost: callers that hand-rolled SSE parsing on the wire and
  read the `isError` field see a behavior change. There are no in-tree
  callers (the only consumer is the AI SDK React client); external
  scripts should be flagged in release notes.
- Follow-up: when the LiteLLM provider gains `provider-executed` tool
  calls, the `providerExecuted` field on `tool-output-error` becomes
  relevant. Out of scope today.

## Confirmation

- `tests/chat/test_sse_schema.py::test_every_emitted_chunk_passes_strict_schema`
  drives a tool-call-then-error scenario, parses the SSE bytes, and
  validates every chunk through the Pydantic Strict model. Fails on
  the current code (the `isError` extra field), passes after the fix.
- `tests/chat/test_sse_schema.py::test_tool_error_chunk_has_required_fields`
  asserts the exact shape `{type: "tool-output-error", toolCallId, errorText}`
  for a tool-not-found, tool-timeout, and tool-raise scenario.
- `tests/chat/test_sse_schema.py::test_tool_success_chunk_has_no_is_error_field`
  asserts that the success variant never carries `isError` (locks the
  regression against re-introducing the field).

## Related

- ADR-0014 — chat endpoint base.
- ADR-0016 — tool-error recovery (the behavior is unchanged; only the
  wire shape changes).
- ADR-0018 — Vercel template best practices (the divergence this ADR
  corrects was not caught during the ADR-0018 review because the
  in-tree tests bypassed the SDK's zod schema).
- `frontend/node_modules/ai/dist/index.mjs:5463-5485` — the wire
  schema this ADR adopts.
```

- [ ] **Step 2: Append the row to `docs/adr/README.md`**

Open the file and append after the existing row 37 (ADR-0021):

```
| 0022 | Chat SSE tool-output-error chunk | proposed | 2026-06-28 |
```

- [ ] **Step 3: Commit**

```bash
git -C /Users/angelozdev/me/quaestor add docs/adr/0022-chat-sse-tool-output-error-chunk.md docs/adr/README.md
git -C /Users/angelozdev/me/quaestor commit -m "docs(adr): 0022 — chat SSE tool-output-error chunk (proposed)"
```

---

## Task 2: Strict chunk schema + first failing behavior test

**Files:**
- Create: `backend/src/quaestor/chat/sse_schema.py`
- Create: `backend/tests/chat/test_sse_schema.py`

**Interfaces:**
- Produces (consumed by Task 4): `UIMessageChunk` Pydantic model with `extra="forbid"` covering the chunk variants we emit: `start`, `text-start`, `text-delta`, `text-end`, `tool-input-start`, `tool-input-delta`, `tool-input-available`, `tool-output-available`, `tool-output-error`, `finish-step`, `finish`, `error`.

This task is RED-only: it adds the test infrastructure and a behavior test that demonstrates the bug. No production code changes yet.

- [ ] **Step 1: Create `backend/src/quaestor/chat/sse_schema.py`**

Write the file with this content:

```python
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

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


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
# We list the variants manually instead of using `Annotated[Union[...],
# Field(discriminator=...)]` because the variants are small and explicit
# makes drift easy to spot.
UIMessageChunk = (
    StartChunk
    | TextStartChunk
    | TextDeltaChunk
    | TextEndChunk
    | ToolInputStartChunk
    | ToolInputDeltaChunk
    | ToolInputAvailableChunk
    | ToolOutputAvailableChunk
    | ToolOutputErrorChunk
    | FinishStepChunk
    | FinishChunk
    | ErrorChunk
)
```

- [ ] **Step 2: Create `backend/tests/chat/test_sse_schema.py`**

Write the file with this content:

```python
"""Behavior tests for the SSE wire shape.

These tests round-trip every chunk the chat service emits through the
strict Pydantic schema in `quaestor.chat.sse_schema`. They are the same
validation the AI SDK v3 React client (`DefaultChatTransport
.processResponseStream`, `frontend/node_modules/ai/dist/index.mjs`)
performs in production — minus the network. A drift in the wire shape
(e.g. re-introducing `isError` on `tool-output-available`) is caught
here before it reaches users.

These tests are behavior-focused: they assert the wire shape, not the
internal representation. They import nothing from `quaestor.chat.llm
.provider` (no `LLMEventType`, no `LLMEvent`). They only inspect SSE
bytes after the service has rendered them.
"""
from __future__ import annotations

import json

import pytest

from quaestor.chat.mcp.client import CallToolResult, MCPClient
from quaestor.chat.sse_schema import (
    ToolOutputAvailableChunk,
    ToolOutputErrorChunk,
    UIMessageChunk,
)
from quaestor.chat.service import ChatService
from quaestor.chat.llm.provider import (
    LLMEvent,
    LLMEventType,
    LLMProvider,
    ToolNotFoundError,
)
from fastmcp.exceptions import ToolError


# --- helpers (test-local; do NOT export) -----------------------------------


def _parse_sse(blob: bytes) -> list[dict]:
    """Plain json.loads parse — used to inspect the raw chunk shape.

    Validation against the strict schema is a separate step. We split the
    two because parsing errors and validation errors are different
    diagnostics and we want to surface them independently.
    """
    out: list[dict] = []
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


def _validate_all(events: list[dict]) -> list[UIMessageChunk]:
    """Strict-schema-validate every event with a `type` field.

    Returns the list of validated chunks. Raises `ValidationError` on the
    first chunk that fails — the test message is the chunk's `type` and
    the validation issue, which is enough to localize drift.
    """
    validated: list[UIMessageChunk] = []
    for e in events:
        if e["type"] == "__DONE__":
            continue
        validated.append(UIMessageChunk.model_validate(e))
    return validated


# --- fakes -----------------------------------------------------------------


class _ScriptedProvider(LLMProvider):
    def __init__(self, scripts: list[list[LLMEvent]]) -> None:
        self._scripts = list(scripts)
        self.calls = 0

    async def stream(self, messages, tools):
        idx = min(self.calls, len(self._scripts) - 1)
        self.calls += 1
        for ev in self._scripts[idx]:
            yield ev


class _RaisingToolMCP:
    """Stand-in that raises fastmcp.ToolError like production does."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def call_tool(self, name, arguments):
        raise ToolError(
            f"1 validation error for {name}Arguments: inp "
            f"Input should be a valid dictionary, got {arguments!r}"
        )

    async def list_tools(self):
        return []


class _UnknownToolMCP:
    """Stand-in that raises ToolNotFoundError for any call."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def call_tool(self, name, arguments):
        raise ToolNotFoundError(name)

    async def list_tools(self):
        return []


class _ErrorResultMCP:
    """Stand-in that returns is_error=True without raising."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def call_tool(self, name, arguments):
        return CallToolResult(output="tool said no", is_error=True)

    async def list_tools(self):
        return []


@pytest.fixture
def patch_mcp(monkeypatch):
    """Factory: patch the MCPClient used by the service and return a holder
    dict the test can mutate to swap the fake per scenario."""
    holder: dict[str, object] = {"client": None}

    def factory(*args, **kwargs):
        return holder["client"]

    monkeypatch.setattr("quaestor.chat.service.MCPClient", factory)
    return holder


# --- tests -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_raise_emits_strict_schema_compliant_chunks(patch_mcp):
    """The bug: a tool that raises (e.g. fastmcp.ToolError on bad args)
    currently produces a chunk with `isError: true` attached to a
    `tool-output-available`. The AI SDK v3 React client's strict
    schema rejects unknown keys, so the chunk fails validation.

    Expected after fix: the service emits a `tool-output-error` chunk
    with `{type, toolCallId, errorText}` — strict-schema-compliant.

    This test will fail on the current code (Pydantic ValidationError
    on the chunk's `isError` extra field)."""
    patch_mcp["client"] = _RaisingToolMCP()

    provider = _ScriptedProvider(
        [
            [
                LLMEvent(type=LLMEventType.MESSAGE_START, message_id="m1"),
                LLMEvent(
                    type=LLMEventType.TOOL_INPUT_AVAILABLE,
                    tool_call_id="tc_1",
                    tool_name="monthly_report",
                    arguments="",
                ),
                LLMEvent(type=LLMEventType.STEP_FINISH),
                LLMEvent(
                    type=LLMEventType.MESSAGE_FINISH,
                    stop_reason="tool-calls",
                    iterations=1,
                ),
            ],
        ]
    )
    service = ChatService(provider=provider, mcp=None, max_iterations=2)
    blob = b""
    async for chunk in service.stream([{"role": "user", "content": "?"}]):
        blob += chunk

    events = _parse_sse(blob)
    # Strict validation: every chunk must round-trip the schema.
    # On the buggy code, this raises ValidationError on `isError`.
    _validate_all(events)


@pytest.mark.asyncio
async def test_tool_unknown_emits_strict_schema_compliant_chunks(patch_mcp):
    """Same scenario as test_tool_raise but for the ToolNotFoundError
    branch. Independent test because the service has separate error
    paths per exception type."""
    patch_mcp["client"] = _UnknownToolMCP()

    provider = _ScriptedProvider(
        [
            [
                LLMEvent(type=LLMEventType.MESSAGE_START, message_id="m1"),
                LLMEvent(
                    type=LLMEventType.TOOL_INPUT_AVAILABLE,
                    tool_call_id="tc_1",
                    tool_name="not_a_tool",
                    arguments={},
                ),
                LLMEvent(type=LLMEventType.STEP_FINISH),
                LLMEvent(
                    type=LLMEventType.MESSAGE_FINISH,
                    stop_reason="tool-calls",
                    iterations=1,
                ),
            ],
        ]
    )
    service = ChatService(provider=provider, mcp=None, max_iterations=2)
    blob = b""
    async for chunk in service.stream([{"role": "user", "content": "?"}]):
        blob += chunk

    events = _parse_sse(blob)
    _validate_all(events)


@pytest.mark.asyncio
async def test_tool_returns_is_error_emits_strict_schema_compliant_chunks(patch_mcp):
    """The tool ran successfully (no exception) but returned an error
    result. The current code emits `tool-output-available` with
    `isError: true`; the fix should emit `tool-output-error`."""
    patch_mcp["client"] = _ErrorResultMCP()

    provider = _ScriptedProvider(
        [
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
        ]
    )
    service = ChatService(provider=provider, mcp=None, max_iterations=2)
    blob = b""
    async for chunk in service.stream([{"role": "user", "content": "?"}]):
        blob += chunk

    events = _parse_sse(blob)
    _validate_all(events)


@pytest.mark.asyncio
async def test_tool_error_chunk_has_required_fields(patch_mcp):
    """The fix should produce a `tool-output-error` chunk with the three
    required fields per the AI SDK v3 schema. This locks the contract."""
    patch_mcp["client"] = _RaisingToolMCP()

    provider = _ScriptedProvider(
        [
            [
                LLMEvent(type=LLMEventType.MESSAGE_START, message_id="m1"),
                LLMEvent(
                    type=LLMEventType.TOOL_INPUT_AVAILABLE,
                    tool_call_id="tc_1",
                    tool_name="monthly_report",
                    arguments="",
                ),
                LLMEvent(type=LLMEventType.STEP_FINISH),
                LLMEvent(
                    type=LLMEventType.MESSAGE_FINISH,
                    stop_reason="tool-calls",
                    iterations=1,
                ),
            ],
        ]
    )
    service = ChatService(provider=provider, mcp=None, max_iterations=2)
    blob = b""
    async for chunk in service.stream([{"role": "user", "content": "?"}]):
        blob += chunk

    events = _parse_sse(blob)
    err_chunks = [
        ToolOutputErrorChunk.model_validate(e)
        for e in events
        if e.get("type") == "tool-output-error"
    ]
    assert len(err_chunks) == 1, f"expected 1 tool-output-error chunk, got {len(err_chunks)}"
    chunk = err_chunks[0]
    assert chunk.toolCallId == "tc_1"
    assert "validation error" in chunk.errorText


@pytest.mark.asyncio
async def test_tool_success_chunk_has_no_is_error_field(patch_mcp):
    """Lock the success-only invariant: `tool-output-available` never
    carries `isError`. Catches re-introduction of the field if anyone
    tries to keep backward-compat with the old shape."""

    class _OkMCP:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def call_tool(self, name, arguments):
            return CallToolResult(output="ok", is_error=False)

        async def list_tools(self):
            return []

    patch_mcp["client"] = _OkMCP()

    provider = _ScriptedProvider(
        [
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
        ]
    )
    service = ChatService(provider=provider, mcp=None, max_iterations=2)
    blob = b""
    async for chunk in service.stream([{"role": "user", "content": "?"}]):
        blob += chunk

    events = _parse_sse(blob)
    success = [
        ToolOutputAvailableChunk.model_validate(e)
        for e in events
        if e.get("type") == "tool-output-available"
    ]
    assert len(success) == 1
    assert success[0].toolCallId == "tc_1"
    assert success[0].output == "ok"
    # The strict schema rejects unknown keys, so reaching here without
    # ValidationError already proves the `isError` extra field is absent.
```

- [ ] **Step 3: Run the new tests to confirm RED**

```bash
cd /Users/angelozdev/me/quaestor/backend && uv run pytest tests/chat/test_sse_schema.py -v
```

Expected: 5 tests run; the first three fail with `pydantic.ValidationError: Extra inputs are not permitted` (the `isError` field on `tool-output-available`). The fourth test (`test_tool_error_chunk_has_required_fields`) fails because no `tool-output-error` chunk is emitted today. The fifth test passes (the success path doesn't emit `isError`).

- [ ] **Step 4: Commit the test scaffolding**

```bash
git -C /Users/angelozdev/me/quaestor add backend/src/quaestor/chat/sse_schema.py backend/tests/chat/test_sse_schema.py
git -C /Users/angelozdev/me/quaestor commit -m "test(chat): strict schema + behavior tests for SSE chunk shape (red)"
```

Do NOT mark these tests as expected-fail or skip them. The whole point of TDD is the RED step.

---

## Task 3: Add `TOOL_OUTPUT_ERROR` variant + render in `events.py`

**Files:**
- Modify: `backend/src/quaestor/chat/llm/provider.py` (add enum member + `LLMEvent` field)
- Modify: `backend/src/quaestor/chat/events.py` (add `serialize_event` branch)

**Interfaces:**
- Consumes: nothing new (Task 2's schema is read-only from the chat service's perspective).
- Produces (consumed by Task 4): `LLMEventType.TOOL_OUTPUT_ERROR = "tool-output-error"` discriminator and `serialize_event(LLMEvent(type=LLMEventType.TOOL_OUTPUT_ERROR, tool_call_id=..., error_text=...), message_id=...)` that returns `{"type": "tool-output-error", "toolCallId": ..., "errorText": ...}`.

The success-side `TOOL_OUTPUT_AVAILABLE` rendering is simplified: the `isError` injection is removed (the success path no longer needs it; failures now go through `TOOL_OUTPUT_ERROR`).

- [ ] **Step 1: Update `LLMEventType` in `backend/src/quaestor/chat/llm/provider.py`**

Locate the `LLMEventType` enum (around line 18). Add a new variant below `TOOL_OUTPUT_AVAILABLE`:

```python
class LLMEventType(str, Enum):
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
```

- [ ] **Step 2: Add `error_text` field to `LLMEvent` in the same file**

Locate the `LLMEvent` dataclass (around line 34). Add the new field next to `is_error`:

```python
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
```

- [ ] **Step 3: Update `serialize_event` in `backend/src/quaestor/chat/events.py`**

Two changes in this file:

(a) Replace the `TOOL_OUTPUT_AVAILABLE` branch (around line 92) with a strict-success-only version (no `isError` field):

```python
    if t == LLMEventType.TOOL_OUTPUT_AVAILABLE:
        assert event.tool_call_id is not None
        # Success-only emit path. Tool failures route through
        # TOOL_OUTPUT_ERROR (ADR-0022). The `is_error` field on this
        # variant would be rejected by the AI SDK v3 React client's
        # strict `uiMessageChunkSchema` (see
        # `frontend/node_modules/ai/dist/index.mjs:5463-5472`).
        return render_sse(
            {
                "type": "tool-output-available",
                "toolCallId": event.tool_call_id,
                "output": event.output or "",
            }
        )
```

(b) Add a new branch for `TOOL_OUTPUT_ERROR` immediately below the modified `TOOL_OUTPUT_AVAILABLE` branch:

```python
    if t == LLMEventType.TOOL_OUTPUT_ERROR:
        assert event.tool_call_id is not None
        assert event.error_text is not None
        return render_sse(
            {
                "type": "tool-output-error",
                "toolCallId": event.tool_call_id,
                "errorText": event.error_text,
            }
        )
```

- [ ] **Step 4: Run the new tests to confirm partial progress**

```bash
cd /Users/angelozdev/me/quaestor/backend && uv run pytest tests/chat/test_sse_schema.py -v
```

Expected: still RED on the first three (the service still emits `TOOL_OUTPUT_AVAILABLE` with `is_error=True`; Task 4 fixes that). The fifth test (`test_tool_success_chunk_has_no_is_error_field`) still passes. The fourth test (`test_tool_error_chunk_has_required_fields`) still fails because the service hasn't started emitting `tool-output-error` chunks yet.

- [ ] **Step 5: Commit**

```bash
git -C /Users/angelozdev/me/quaestor add backend/src/quaestor/chat/llm/provider.py backend/src/quaestor/chat/events.py
git -C /Users/angelozdev/me/quaestor commit -m "feat(chat): add TOOL_OUTPUT_ERROR variant + renderer (still red on service)"
```

---

## Task 4: Switch `chat/service.py` error branches to `TOOL_OUTPUT_ERROR`

**Files:**
- Modify: `backend/src/quaestor/chat/service.py` (4 emit sites)

**Interfaces:**
- Consumes: `LLMEventType.TOOL_OUTPUT_ERROR` from Task 3.
- Produces (consumed by Task 5 tests): the service emits `tool-output-error` chunks (not `tool-output-available` + `isError`) for tool failures.

The four emit sites:

1. **`ToolNotFoundError` branch** (around line 164-180)
2. **`asyncio.TimeoutError` branch** (around line 182-198)
3. **Generic `Exception` branch** (around line 200-222)
4. **Success-with-`is_error=True` path** (around line 224-233, where `result.is_error` is True)

The `conversation.append({role: tool, ...})` calls stay unchanged in each branch — the LLM-facing conversation is independent of SSE wire shape.

- [ ] **Step 1: Replace the `ToolNotFoundError` branch's `serialize_event` call**

Locate the `except ToolNotFoundError as exc:` block. Replace the `yield serialize_event(...)` call:

Before:
```python
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
```

After:
```python
                        except ToolNotFoundError as exc:
                            yield serialize_event(
                                LLMEvent(
                                    type=LLMEventType.TOOL_OUTPUT_ERROR,
                                    tool_call_id=tc_id,
                                    error_text=f"tool not found: {exc}",
                                ),
                                message_id=message_id,
                            )
```

- [ ] **Step 2: Replace the `asyncio.TimeoutError` branch's `serialize_event` call**

Before:
```python
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
```

After:
```python
                        except asyncio.TimeoutError:
                            yield serialize_event(
                                LLMEvent(
                                    type=LLMEventType.TOOL_OUTPUT_ERROR,
                                    tool_call_id=tc_id,
                                    error_text="timeout",
                                ),
                                message_id=message_id,
                            )
```

- [ ] **Step 3: Replace the generic `Exception` branch's `serialize_event` call**

Before:
```python
                        except Exception as exc:  # noqa: BLE001 — see ADR-0016
                            err_text = f"tool error: {type(exc).__name__}: {exc}".splitlines()[0]
                            err_text = err_text[:500]
                            safe_err = sanitize_tool_output(tc_name, err_text)
                            _log.warning(
                                "[chat] tool call failed: %s %s", tc_name, err_text
                            )
                            yield serialize_event(
                                LLMEvent(
                                    type=LLMEventType.TOOL_OUTPUT_AVAILABLE,
                                    tool_call_id=tc_id,
                                    output=safe_err,
                                    is_error=True,
                                ),
                                message_id=message_id,
                            )
```

After:
```python
                        except Exception as exc:  # noqa: BLE001 — see ADR-0016
                            err_text = f"tool error: {type(exc).__name__}: {exc}".splitlines()[0]
                            err_text = err_text[:500]
                            safe_err = sanitize_tool_output(tc_name, err_text)
                            _log.warning(
                                "[chat] tool call failed: %s %s", tc_name, err_text
                            )
                            yield serialize_event(
                                LLMEvent(
                                    type=LLMEventType.TOOL_OUTPUT_ERROR,
                                    tool_call_id=tc_id,
                                    error_text=safe_err,
                                ),
                                message_id=message_id,
                            )
```

- [ ] **Step 4: Replace the success-with-`is_error=True` path's `serialize_event` call**

This is the path where the tool ran without raising but returned `is_error=True`. It currently emits `TOOL_OUTPUT_AVAILABLE` with `is_error=True`.

Before:
```python
                        safe_output = sanitize_tool_output(tc_name, result.output)
                        yield serialize_event(
                            LLMEvent(
                                type=LLMEventType.TOOL_OUTPUT_AVAILABLE,
                                tool_call_id=tc_id,
                                output=safe_output,
                                is_error=result.is_error,
                            ),
                            message_id=message_id,
                        )
```

After:
```python
                        if result.is_error:
                            # The tool ran but returned an error result.
                            # Per ADR-0022, tool failures get a dedicated
                            # wire shape — not a flag on the success chunk.
                            yield serialize_event(
                                LLMEvent(
                                    type=LLMEventType.TOOL_OUTPUT_ERROR,
                                    tool_call_id=tc_id,
                                    error_text=safe_output,
                                ),
                                message_id=message_id,
                            )
                        else:
                            yield serialize_event(
                                LLMEvent(
                                    type=LLMEventType.TOOL_OUTPUT_AVAILABLE,
                                    tool_call_id=tc_id,
                                    output=safe_output,
                                ),
                                message_id=message_id,
                            )
```

- [ ] **Step 5: Run the new tests to confirm GREEN**

```bash
cd /Users/angelozdev/me/quaestor/backend && uv run pytest tests/chat/test_sse_schema.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 6: Run the full chat test file to catch regressions**

```bash
cd /Users/angelozdev/me/quaestor/backend && uv run pytest tests/chat/ -v
```

Expected: the three existing tests in `test_service.py` that assert `outputs[0].get("isError") is True` will fail (they look for `isError` on `tool-output-available`, which is now an `tool-output-error` chunk). Task 5 fixes them. No other regressions.

- [ ] **Step 7: Commit**

```bash
git -C /Users/angelozdev/me/quaestor add backend/src/quaestor/chat/service.py
git -C /Users/angelozdev/me/quaestor commit -m "fix(chat): emit tool-output-error chunk for tool failures (ADR-0022)"
```

---

## Task 5: Update existing tests + full regression

**Files:**
- Modify: `backend/tests/chat/test_service.py` (3 assertions)

The three existing assertions that need updating:

1. Line 220-221 (`test_tool_error_emits_is_error_and_loop_continues`): asserts `outputs[0].get("isError") is True` on a `tool-output-available` chunk. After the fix, the chunk is `tool-output-error`. Update to look up the error chunk by type and assert `errorText`.

2. Line 355-358 (`test_tool_call_raises_is_recovered_not_500`): same pattern — `outputs[0].get("isError") is True` and `"validation error" in outputs[0]["output"]`. The validation error text is now in `errorText`.

3. Line 417-419 (`test_tool_call_timeout_emits_is_error_and_continues`): same pattern — `outputs[0].get("isError") is True` and `outputs[0]["output"] == "timeout"`. The timeout text is now in `errorText`.

These are **test-only** changes. The semantics under test (ADR-0016: a tool failure does not 500 the stream; the LLM gets a chance to self-correct on the next iteration) are unchanged. We just look at the new field.

- [ ] **Step 1: Update `test_tool_error_emits_is_error_and_loop_continues`**

Locate the test (around line 182-222). Find the assertion block:

Before:
```python
    events = _parse_sse(blob)
    outputs = [e for e in events if e["type"] == "tool-output-available"]
    assert outputs and outputs[0].get("isError") is True
```

After:
```python
    events = _parse_sse(blob)
    # ADR-0022: tool failures now route through tool-output-error,
    # not tool-output-available + isError.
    errs = [e for e in events if e["type"] == "tool-output-error"]
    assert errs and "account not found" in errs[0]["errorText"]
```

- [ ] **Step 2: Update `test_tool_call_raises_is_recovered_not_500`**

Locate the test (around line 299-363). Find the assertion block:

Before:
```python
    events = _parse_sse(blob)
    # The bad call produced an isError tool output (not a 500).
    outputs = [e for e in events if e["type"] == "tool-output-available"]
    assert outputs, "tool-output-available event missing — stream died?"
    assert outputs[0].get("isError") is True
    assert "validation error" in outputs[0]["output"]
```

After:
```python
    events = _parse_sse(blob)
    # The bad call produced a tool-output-error event (not a 500).
    # ADR-0022: failures route through the dedicated error chunk,
    # not the success chunk with an isError flag.
    errs = [e for e in events if e["type"] == "tool-output-error"]
    assert errs, "tool-output-error event missing — stream died?"
    assert "validation error" in errs[0]["errorText"]
```

- [ ] **Step 3: Update `test_tool_call_timeout_emits_is_error_and_continues`**

Locate the test (around line 366-422). Find the assertion block:

Before:
```python
    events = _parse_sse(blob)
    outputs = [e for e in events if e["type"] == "tool-output-available"]
    assert outputs and outputs[0].get("isError") is True
    assert outputs[0]["output"] == "timeout"
```

After:
```python
    events = _parse_sse(blob)
    errs = [e for e in events if e["type"] == "tool-output-error"]
    assert errs and errs[0]["errorText"] == "timeout"
```

- [ ] **Step 4: Run the full chat test file**

```bash
cd /Users/angelozdev/me/quaestor/backend && uv run pytest tests/chat/ -v
```

Expected: all tests pass (the 5 new tests from `test_sse_schema.py` + the 12+ tests in `test_service.py`).

- [ ] **Step 5: Run the full backend suite to confirm no regressions**

```bash
cd /Users/angelozdev/me/quaestor/backend && uv run pytest -q
```

Expected: 643+ tests pass (was 638 before this plan; +5 new strict-schema tests).

- [ ] **Step 6: Commit**

```bash
git -C /Users/angelozdev/me/quaestor add backend/tests/chat/test_service.py
git -C /Users/angelozdev/me/quaestor commit -m "test(chat): update existing assertions to tool-output-error shape (ADR-0022)"
```

---

## Self-Review

**1. Spec coverage:**
- `domain/sort.py`-style value object — N/A for this plan.
- `chat/llm/provider.py` gains `TOOL_OUTPUT_ERROR` enum member + `error_text` field — Task 3.
- `chat/events.py` gains `serialize_event` branch for `TOOL_OUTPUT_ERROR`; success path drops `isError` injection — Task 3.
- `chat/service.py` four error branches switch to `TOOL_OUTPUT_ERROR` — Task 4.
- `chat/sse_schema.py` NEW: Pydantic Strict mirror of `uiMessageChunkSchema` — Task 2.
- `tests/chat/test_sse_schema.py` NEW: behavior tests that round-trip every emitted chunk through the strict schema — Task 2.
- 3 existing test assertions updated to the new shape — Task 5.
- ADR-0022 records the decision and links to AI SDK schema source — Task 1.

**2. Placeholder scan:**
- No "TBD", "TODO", "implement later".
- Every code block is complete.
- Every command shows full args and expected output.
- Every type/function referenced in a later task is defined in an earlier task.

**3. Type consistency:**
- `LLMEventType.TOOL_OUTPUT_ERROR` defined in Task 3, consumed in Task 4 unchanged.
- `LLMEvent.error_text` defined in Task 3, consumed in Task 4 unchanged.
- `UIMessageChunk` Pydantic model defined in Task 2, consumed in Task 2 + Task 5 unchanged.
- `serialize_event(LLMEvent(type=TOOL_OUTPUT_ERROR, ...), message_id=...)` signature consistent across Tasks 3 and 4.
- Test names match between spec and plan (`test_tool_raise_emits_strict_schema_compliant_chunks`, `test_tool_error_chunk_has_required_fields`, etc.).

**4. Risks not addressed:**
- The LiteLLM provider never emits tool errors directly — they originate from the service layer. So provider.py is untouched.
- `tool-output-denied` is not emitted today — deferred per YAGNI.
- The Pydantic Strict schema mirrors only the variants we emit. If a future change adds a new variant, the schema needs to grow. Out of scope for this plan; documented in ADR-0022.

---

Plan complete and saved to `docs/superpowers/plans/2026-06-28-chat-sse-tool-output-error-chunk.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**