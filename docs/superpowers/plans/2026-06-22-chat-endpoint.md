# Chat Endpoint (LLM → MCP bridge) Implementation Plan

> **For agentic workers:** REQUIRED SUB-KILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `POST /api/chat` SSE route to the FastAPI process that lets a browser type natural language, lets an LLM interpret it and call MCP tools on the user's behalf, and streams a final answer back as Vercel AI SDK UI Message Stream SSE — reusing the existing `build_mcp()` server through an in-memory `fastmcp.Client`.

**Architecture:** A new `backend/src/quaestor/chat/` package isolates the agentic loop from HTTP. Three seams:
1. `LLMProvider` Protocol + `LLMEvent` dataclasses — the only thing the agentic loop knows about the model. `LiteLLMProvider` is the one implementation; future providers swap in without touching the loop.
2. `MCPClient` (wraps `fastmcp.Client(build_mcp())`) — the only thing the loop knows about tools. In-memory transport, no subprocess.
3. `events.py` — translates `LLMEvent`s into Vercel AI SDK UI Message Stream SSE bytes (`start`, `text-*`, `tool-input-*`, `tool-output-available`, `start-step`, `finish-step`, `finish`, `[DONE]`, with header `x-vercel-ai-ui-message-stream: v1`).

`ChatService.stream()` is the agentic loop (max `CHAT_MAX_ITERATIONS`). `api/chat.py` mounts `StreamingResponse(generator(), media_type="text/event-stream")` inside the existing FastAPI app, gated by `BearerAuthMiddleware`-equivalent (reuses `require_auth`). Tailnet-only posture extends ADR-0011.

**Tech Stack:** Python 3.12 · `litellm>=1.40` (new dep) · `mcp>=1.28,<2` (existing; in-memory `fastmcp.Client`) · FastAPI `StreamingResponse` · Vercel AI SDK v5 (`useChat` + `DefaultChatTransport`) on the frontend · pytest + Starlette `TestClient` · SQLite in-memory.

## Global Constraints

Copied verbatim from `docs/superpowers/specs/2026-06-22-chat-endpoint-design.md` and the verified Vercel AI SDK UI Message Stream protocol. Every task implicitly includes these.

- **HTTP route:** `POST /api/chat`, body `{"messages":[...]}`, response `text/event-stream` with header `x-vercel-ai-ui-message-stream: v1`. Wire format follows the **current** Vercel AI SDK UI Message Stream protocol (confirmed against `ai-sdk.dev/docs/ai-sdk-ui/stream-protocol`), NOT the spec's earlier draft event names (`message_start` / `tool_call` / `tool_result` / `text_delta` / `message_stop`).
- **SSE event vocabulary (exact names):** `start`, `start-step`, `finish-step`, `text-start`, `text-delta`, `text-end`, `tool-input-start`, `tool-input-delta`, `tool-input-available`, `tool-output-available`, `error`, `finish`, plus the literal terminator `data: [DONE]`. Each event's `data:` line is a JSON object whose `type` field matches the event name.
- **Default `LLM_MODEL`:** `anthropic/MiniMax-M3` (set verbatim per spec). Provider-swap invariant: changing `LLM_MODEL` (or `LLM_PROVIDER`) is the only knob needed to swap providers.
- **Env vars (new):** `LLM_PROVIDER` (default `litellm`), `LLM_MODEL` (default `anthropic/MiniMax-M3`), `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL` (default `https://api.minimax.io/anthropic`), `CHAT_MAX_ITERATIONS` (default `8`), `CHAT_REQUEST_TIMEOUT_S` (default `120`). All flow through `.env` / `.env.local`; nothing hardcoded.
- **Unknown `LLM_PROVIDER` value → fail startup** with a clear error listing recognized values.
- **Request limits:** max 200 messages per request, max 32 KB per message content, reject if `sum(len(content) for m in messages) // 4 > 100_000` with HTTP `413`. Malformed body → HTTP `400`.
- **Tool schema caching:** `chat.mcp.schema._tools_cache: list | None` and `_openai_tools_cache: list | None` — module-level lazy singletons. First request runs `MCPClient.list_tools()` once and converts; subsequent requests hit memory only. No cross-process sharing; process restart invalidates.
- **Agentic loop cap:** `iterations >= CHAT_MAX_ITERATIONS` → emit a final `text-delta` "loop limit reached", `text-end`, `finish` with `finishReason: "length"`. No retry.
- **Auth:** `require_auth` dependency (existing, in `api/deps.py`). Same `APP_TOKEN` (bearer) or session cookie as everywhere else. Bearer-only callers (curl, MCP agents) use the bearer; the web UI uses the session cookie from the browser. Tailnet-only posture (extends ADR-0011); Caddyfile returns `404` for public `/api/chat`.
- **Money/cents/language:** unchanged from P0–P6 — integer cents, English code, names resolved via existing services, MCP tool names from ADR-0009.
- **No modification to any existing MCP tool, service, schema, or router.** This plan only **adds** files and mounts one new router.
- **Stateless per request:** frontend owns history (no server-side persistence). The `messages` list grows by assistant+tool messages inside one request only.
- **Work on branch `feat/chat-endpoint`** created from `main` after the spec is approved.

---

## File Structure

**Create (backend package):**
- `backend/src/quaestor/chat/__init__.py` — empty (marks package).
- `backend/src/quaestor/chat/llm/__init__.py` — empty.
- `backend/src/quaestor/chat/llm/provider.py` — `LLMProvider` Protocol + `LLMEvent` dataclasses + `LLMEventType` enum.
- `backend/src/quaestor/chat/llm/litellm_provider.py` — `LiteLLMProvider` (streaming + tool-call delta accumulator).
- `backend/src/quaestor/chat/llm/factory.py` — `build_llm_provider()` selecting by `LLM_PROVIDER`.
- `backend/src/quaestor/chat/mcp/__init__.py` — empty.
- `backend/src/quaestor/chat/mcp/client.py` — `MCPClient` wrapping `fastmcp.Client`.
- `backend/src/quaestor/chat/mcp/schema.py` — `to_openai_tools()` + cached singletons.
- `backend/src/quaestor/chat/events.py` — SSE event dataclasses + serializer (Vercel UI Message Stream shape).
- `backend/src/quaestor/chat/service.py` — `ChatService.stream()` agentic loop.
- `backend/src/quaestor/api/chat.py` — FastAPI router + `POST /api/chat` with `StreamingResponse`.

**Modify:**
- `backend/pyproject.toml` — add `litellm>=1.40`.
- `backend/.env.example` — add the five new env vars (only if file exists; see Task 1).
- `backend/src/quaestor/api/__init__.py` — include the chat router under `Depends(require_auth)`.
- `Caddyfile` — `route /api/chat*` returns `404` publicly; tailnet proxy routes to backend.
- `docs/adr/0014-chat-endpoint-with-litellm-and-mcp-bridge.md` — ADR recording the choices below.

**Create (tests):**
- `backend/tests/chat/__init__.py` — empty.
- `backend/tests/chat/conftest.py` — engine/session/seeded fixtures + scriptable fake `LLMProvider`/`MCPClient`.
- `backend/tests/chat/test_events.py` — SSE event serialization (Vercel shape).
- `backend/tests/chat/test_schema_converter.py` — MCP `inputSchema` → OpenAI `tools=[]`.
- `backend/tests/chat/test_mcp_client.py` — `Client(build_mcp())` round-trip via real FastMCP.
- `backend/tests/chat/test_litellm_provider.py` — `AsyncMock` of `litellm.acompletion` → `LLMEvent` mapping + tool-call delta assembly.
- `backend/tests/chat/test_service.py` — agentic loop end-to-end (fake provider + fake MCPClient).
- `backend/tests/chat/test_api_limits.py` — `413` oversize, `400` malformed.
- `backend/tests/chat/test_api_auth.py` — bearer/cookie auth (mirrors `tests/mcp/test_core_writes.py` patterns).
- `backend/tests/chat/test_api.py` — `POST /api/chat` end-to-end via `TestClient`, scripted events.

Each file owns one responsibility; the package boundary at `chat/` makes the agentic loop swappable without touching `api/` or `mcp/`.

---

### Task 1: Dependency, env vars, ADR

**Files:**
- Modify: `backend/pyproject.toml` (add `litellm>=1.40`)
- Modify: `backend/.env.example` (only if it exists in the repo — see Step 1b)
- Create: `docs/adr/0014-chat-endpoint-with-litellm-and-mcp-bridge.md`
- Create: `backend/src/quaestor/chat/__init__.py` (empty), `backend/src/quaestor/chat/llm/__init__.py` (empty), `backend/src/quaestor/chat/mcp/__init__.py` (empty), `backend/tests/chat/__init__.py` (empty)

**Interfaces:**
- Produces: `litellm` importable from the backend venv; ADR-0014 at `docs/adr/0014-...md`; all chat subpackages importable (even if empty) so later tasks don't trip `ModuleNotFoundError`.

- [ ] **Step 1: Branch**

```bash
cd /Users/angelozdev/me/quaestor
git checkout main
git pull
git checkout -b feat/chat-endpoint
```

- [ ] **Step 1b: Decide env-var documentation site**

Run: `test -f backend/.env.example && echo EXISTS || echo MISSING`
Expected: `EXISTS` (P7 commit `c964894` added it). If `MISSING`, skip the `.env.example` edits and document the five vars in ADR-0014 only.

- [ ] **Step 2: Add the `litellm` dep**

```bash
cd backend
uv add 'litellm>=1.40'
```

Expected: `pyproject.toml` `[project].dependencies` now lists `litellm>=1.40`; `uv.lock` updates; `uv sync` succeeds.

- [ ] **Step 3: Verify the import resolves**

Run: `cd backend && uv run python -c "import litellm; print(litellm.__version__)"`
Expected: prints a version ≥ `1.40.0`.

- [ ] **Step 4: Create empty package + test `__init__.py` files**

Create four empty files:
- `backend/src/quaestor/chat/__init__.py`
- `backend/src/quaestor/chat/llm/__init__.py`
- `backend/src/quaestor/chat/mcp/__init__.py`
- `backend/tests/chat/__init__.py`

Each is a zero-byte file.

- [ ] **Step 5: Append new env vars to `.env.example` (only if it exists)**

If Step 1b printed `EXISTS`, append the following block at the end of `backend/.env.example` (keep a trailing newline):

```
# --- Chat endpoint (ADR-0014) -----------------------------------------
LLM_PROVIDER=litellm
LLM_MODEL=anthropic/MiniMax-M3
ANTHROPIC_BASE_URL=https://api.minimax.io/anthropic
# ANTHROPIC_API_KEY=                  # required; never commit
CHAT_MAX_ITERATIONS=8
CHAT_REQUEST_TIMEOUT_S=120
```

If Step 1b printed `MISSING`, skip — Task 1 does not create `.env.example`.

- [ ] **Step 6: Write ADR-0014**

Create `docs/adr/0014-chat-endpoint-with-litellm-and-mcp-bridge.md`:

```markdown
# 0014 — Chat endpoint with LiteLLM and an in-memory MCP bridge

- **Status:** accepted
- **Date:** 2026-06-22

## Context

The web frontend (P6) exposes a CRUD surface over HTTP, but every natural-
language question ("¿cuánto gasté en café este mes?") still has to be
answered by the user manually: filter → group → sum. To let the LLM do that
on the user's behalf, the backend needs an HTTP route that takes a chat
history, lets an LLM drive the existing MCP tool set, and streams an answer
back to the browser in real time.

The MCP server (P2 + ADR-0009 parity) is the single source of truth for what
tools exist; we must NOT fork tool definitions into a second registry. The
chat endpoint is an HTTP frontend to the LLM that drives the MCP server, not
a replacement for it.

## Decision

Ship `POST /api/chat` in the existing FastAPI process. The route:
1. Validates the body (≤ 200 messages, ≤ 32 KB each, ≤ 100 k estimated tokens).
2. Runs an agentic loop (max `CHAT_MAX_ITERATIONS`, default 8) where the LLM
   emits text + tool calls; tool calls dispatch through an in-memory
   `fastmcp.Client(build_mcp())`.
3. Streams the response as Vercel AI SDK UI Message Stream SSE
   (`text/event-stream` + header `x-vercel-ai-ui-message-stream: v1`).

### Why LiteLLM

LiteLLM is the Python equivalent of Vercel AI SDK's provider model: one
`acompletion(...)` call covers MiniMax / Anthropic / OpenAI / etc. It also
ships a streaming + tool-call-delta contract that matches the OpenAI shape
(`chunk.choices[0].delta.tool_calls` with `index`/`id`/`function.name`/
`function.arguments`), so we write one accumulator that works for every
provider behind LiteLLM. We hide LiteLLM behind an `LLMProvider` Protocol so
`AnthropicNativeProvider` (or anything else) can be swapped in without
touching the agentic loop. Provider selection is by `LLM_PROVIDER` env var;
unknown values fail startup.

### Why `fastmcp.Client(build_mcp())` in-memory

`build_mcp()` is already the public, documented seam for "the MCP server's
tool surface." Using `Client(build_mcp())` with the in-memory transport means
we:
- Never reach into FastMCP private state (`_tool_manager`, etc.).
- Get the same 52 tools the external MCP server exposes, automatically in
  sync with P2/ADR-0009.
- Are forward-compatible with splitting the MCP server into its own process:
  swap the in-memory `Client` for a streamable-HTTP one, no loop change.

### Provider-swap invariant

Changing `LLM_MODEL` (and/or `LLM_PROVIDER`) is the only knob needed to swap
the model. The agentic loop never branches on model identity.

### Conversation model

Server is stateless per request; the frontend sends the full message history
on every turn (per product decision). No persistence in this plan.

### SSE protocol

Wire format is the current Vercel AI SDK UI Message Stream protocol
(verified against `ai-sdk.dev/docs/ai-sdk-ui/stream-protocol`):
`start`, `start-step`, `finish-step`, `text-start`, `text-delta`, `text-end`,
`tool-input-start`, `tool-input-delta`, `tool-input-available`,
`tool-output-available`, `error`, `finish`, `[DONE]`. Earlier spec drafts
used `message_start` / `tool_call` / `tool_result` / `text_delta` /
`message_stop` — those are NOT valid UI Message Stream events and would
break `useChat()`'s `DefaultChatTransport`. The plan emits the correct set.

### Network posture

Extends ADR-0011: `/api/chat` joins `/mcp` on the tailnet only. Caddyfile
returns 404 for public traffic on `/api/chat`; the tailnet proxy forwards it
to the backend container. Same `APP_TOKEN` (bearer) and session cookie gate
as every other route.

## Consequences

- New dep: `litellm>=1.40`. New env vars: `LLM_PROVIDER`, `LLM_MODEL`,
  `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, `CHAT_MAX_ITERATIONS`,
  `CHAT_REQUEST_TIMEOUT_S`. None are secrets beyond `ANTHROPIC_API_KEY`.
- One new route. No changes to existing services, tools, schemas, or routers.
- Tool schema fetched once per process, cached in module singletons;
  per-request latency stays flat.
- Frontend gains a chat page using `useChat()` + `DefaultChatTransport`
  pointing at `/api/chat`. The route is tailnet-only, so a future public
  exposure would need a separate ADR.
- A `LLM_PROVIDER` value typo at startup crashes the process — preferable
  to silently using a stale provider.

## Related

- ADR-0006 — every new HTTP write ships a sibling MCP tool (chat reuses
  them, does not duplicate).
- ADR-0009 — closing the MCP parity gap; chat consumes the 52 tools.
- ADR-0011 — MCP-only over Tailscale; `/api/chat` extends the posture.
- Spec: `docs/superpowers/specs/2026-06-22-chat-endpoint-design.md`.
- Plan: `docs/superpowers/plans/2026-06-22-chat-endpoint.md`.
```

- [ ] **Step 7: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock \
        backend/src/quaestor/chat/__init__.py \
        backend/src/quaestor/chat/llm/__init__.py \
        backend/src/quaestor/chat/mcp/__init__.py \
        backend/tests/chat/__init__.py \
        docs/adr/0014-chat-endpoint-with-litellm-and-mcp-bridge.md
git add backend/.env.example   # only if it existed before Step 5
git commit -m "feat(chat): scaffold chat package, add litellm dep + ADR-0014"
```

---

### Task 2: `LLMProvider` Protocol + `LLMEvent` dataclasses

**Files:**
- Create: `backend/src/quaestor/chat/llm/provider.py`
- Test: `backend/tests/chat/test_provider.py` (smoke-only; full protocol coverage in Tasks 4–5)

**Interfaces:**
- Produces (consumed by Tasks 3, 4, 7):
  - `class LLMEventType(str, Enum)`: members `MESSAGE_START`, `TEXT_START`, `TEXT_DELTA`, `TEXT_END`, `TOOL_INPUT_START`, `TOOL_INPUT_DELTA`, `TOOL_INPUT_AVAILABLE`, `TOOL_OUTPUT_AVAILABLE`, `STEP_FINISH`, `MESSAGE_FINISH`, `ERROR`.
  - `class LLMEvent` dataclass: `type: LLMEventType`, plus per-type optional fields:
    - `TEXT_DELTA`: `delta: str`
    - `TEXT_START` / `TEXT_END`: `content_index: int` (Vercel `id` field)
    - `TOOL_INPUT_START`: `tool_call_id: str`, `tool_name: str`
    - `TOOL_INPUT_DELTA`: `tool_call_id: str`, `arguments_delta: str`
    - `TOOL_INPUT_AVAILABLE`: `tool_call_id: str`, `tool_name: str`, `arguments: dict[str, Any]`
    - `TOOL_OUTPUT_AVAILABLE`: `tool_call_id: str`, `output: str`, `is_error: bool`
    - `MESSAGE_START`: `message_id: str`, `model: str`
    - `MESSAGE_FINISH`: `stop_reason: str`, `iterations: int`
    - `STEP_FINISH`: no extra fields
    - `ERROR`: `code: str`, `message: str`, `retryable: bool`
  - `class LLMProvider(Protocol)`:
    - `def stream(self, messages: list[dict], tools: list[dict]) -> AsyncIterator[LLMEvent]: ...`
  - `class LLMError(Exception)`: base; subclasses `UpstreamLLMError(LLMError)`, `ToolNotFoundError(LLMError)`, `LoopLimitError(LLMError)`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/chat/test_provider.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/chat/test_provider.py -v`
Expected: `ModuleNotFoundError: No module named 'quaestor.chat.llm.provider'`.

- [ ] **Step 3: Implement `provider.py`**

Create `backend/src/quaestor/chat/llm/provider.py`:

```python
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
from enum import Enum
from typing import Any, Protocol, runtime_checkable


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

    # message-level
    message_id: str | None = None
    model: str | None = None
    stop_reason: str | None = None
    iterations: int | None = None

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/chat/test_provider.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/chat/llm/provider.py \
        backend/tests/chat/test_provider.py
git commit -m "feat(chat): LLMProvider Protocol + LLMEvent dataclasses"
```

---

### Task 3: `LiteLLMProvider` — streaming + tool-call delta accumulator

**Files:**
- Create: `backend/src/quaestor/chat/llm/litellm_provider.py`
- Test: `backend/tests/chat/test_litellm_provider.py`

**Interfaces:**
- Consumes (Task 2): `LLMEvent`, `LLMEventType`, `LLMError`, `UpstreamLLMError`.
- Produces:
  - `class LiteLLMProvider`:
    - `def __init__(self, model: str, api_key: str | None, base_url: str | None) -> None`
    - `def stream(self, messages: list[dict], tools: list[dict]) -> AsyncIterator[LLMEvent]`
    - Emits `MESSAGE_START` first (with `message_id`, `model`), then text deltas / tool deltas, then `STEP_FINISH` + `MESSAGE_FINISH` at the end. On `litellm.{APIError, AuthenticationError, RateLimitError}` raises `UpstreamLLMError(code="upstream")`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/chat/test_litellm_provider.py`:

```python
"""Unit tests for LiteLLMProvider.

Mock `litellm.acompletion` (not the LLM API). Cover:
  - text-only stream → TEXT_DELTA events
  - tool-call stream → TOOL_INPUT_START/DELTA/AVAILABLE events with arguments reassembled
  - upstream error → UpstreamLLMError
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

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
) -> dict[str, Any]:
    out: dict[str, Any] = {"index": index}
    if id is not None:
        out["id"] = id
    if name is not None:
        out["function"] = {"name": name, "arguments": args or ""}
    elif args is not None:
        out["function"] = {"arguments": args}
    return out


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


@pytest.mark.asyncio
async def test_upstream_error_raises_upstream_llm_error():
    class FakeAPIError(Exception):
        pass

    async def fake_acompletion(**kwargs):
        raise FakeAPIError("boom")
        yield  # pragma: no cover  (generator never runs)

    with patch("litellm.acompletion", side_effect=fake_acompletion):
        provider = LiteLLMProvider(model="anthropic/MiniMax-M3", api_key="x", base_url=None)
        with pytest.raises(UpstreamLLMError):
            async for _ in provider.stream(messages=[], tools=[]):
                pass
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/chat/test_litellm_provider.py -v`
Expected: `ModuleNotFoundError: No module named 'quaestor.chat.llm.litellm_provider'`.

- [ ] **Step 3: Implement `litellm_provider.py`**

Create `backend/src/quaestor/chat/llm/litellm_provider.py`:

```python
"""LiteLLMProvider — concrete LLMProvider implementation.

Reads `chunk.choices[0].delta` (LiteLLM normalizes every provider into this
shape). Tool-call deltas are accumulated per `index` and emitted as
TOOL_INPUT_START → TOOL_INPUT_DELTA* → TOOL_INPUT_AVAILABLE once
`finish_reason` arrives.
"""
from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any

import litellm

from .provider import LLMEvent, LLMEventType, UpstreamLLMError

# Map LiteLLM raised exceptions to our UpstreamLLMError. Keep the original
# message verbatim for server-side logs.
_LITELLM_UPSTREAM_ERRORS: tuple[type[BaseException], ...] = (
    litellm.APIError,
    litellm.AuthenticationError,
    litellm.RateLimitError,
    litellm.Timeout,
    litellm.ServiceUnavailableError,
)


class LiteLLMProvider:
    """Streamed chat over LiteLLM. See module docstring."""

    def __init__(self, model: str, api_key: str | None, base_url: str | None) -> None:
        self._model = model
        self._api_key = api_key
        self._base_url = base_url

    async def stream(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AsyncIterator[LLMEvent]:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools
        if self._api_key:
            kwargs["api_key"] = self._api_key
        if self._base_url:
            kwargs["base_url"] = self._base_url

        # Track per-tool-call state across chunks.
        # accumulated[idx] = {"id": str|None, "name": str|None, "args_buf": str, "started": bool}
        accumulated: dict[int, dict[str, Any]] = {}
        message_id: str | None = None
        text_started = False

        try:
            response = await litellm.acompletion(**kwargs)
        except _LITELLM_UPSTREAM_ERRORS as exc:
            raise UpstreamLLMError(str(exc)) from exc

        try:
            async for chunk in response:
                if message_id is None:
                    message_id = getattr(chunk, "id", None) or "msg_unknown"
                    yield LLMEvent(
                        type=LLMEventType.MESSAGE_START,
                        message_id=message_id,
                        model=self._model,
                    )

                choice = chunk.choices[0]
                delta = choice.delta

                # --- text streaming ---------------------------------------------
                content_piece: str | None = getattr(delta, "content", None)
                if content_piece:
                    if not text_started:
                        text_started = True
                        yield LLMEvent(type=LLMEventType.TEXT_START, content_index=0)
                    yield LLMEvent(type=LLMEventType.TEXT_DELTA, delta=content_piece)

                # --- tool-call streaming ----------------------------------------
                raw_tool_calls = getattr(delta, "tool_calls", None) or []
                for tc in raw_tool_calls:
                    idx = tc.index
                    slot = accumulated.setdefault(
                        idx,
                        {"id": None, "name": None, "args_buf": "", "started": False},
                    )
                    if tc.id and slot["id"] is None:
                        slot["id"] = tc.id
                    func = getattr(tc, "function", None)
                    if func is not None:
                        if func.name and slot["name"] is None:
                            slot["name"] = func.name
                            if not slot["started"]:
                                slot["started"] = True
                                yield LLMEvent(
                                    type=LLMEventType.TOOL_INPUT_START,
                                    tool_call_id=slot["id"] or "",
                                    tool_name=slot["name"],
                                )
                        if func.arguments:
                            slot["args_buf"] += func.arguments
                            yield LLMEvent(
                                type=LLMEventType.TOOL_INPUT_DELTA,
                                tool_call_id=slot["id"] or "",
                                arguments_delta=func.arguments,
                            )

                # --- finish reason: flush tool calls / close text ---------------
                if choice.finish_reason:
                    if text_started:
                        yield LLMEvent(type=LLMEventType.TEXT_END, content_index=0)
                    for idx, slot in sorted(accumulated.items()):
                        # Parse accumulated arguments; if it's malformed JSON,
                        # surface it as an error rather than dropping the call.
                        try:
                            args_obj: Any = (
                                json.loads(slot["args_buf"]) if slot["args_buf"].strip() else {}
                            )
                        except json.JSONDecodeError as exc:
                            raise UpstreamLLMError(
                                f"tool_call {slot['id']} arguments not valid JSON: {exc}"
                            ) from exc
                        if not isinstance(args_obj, dict):
                            args_obj = {"value": args_obj}
                        yield LLMEvent(
                            type=LLMEventType.TOOL_INPUT_AVAILABLE,
                            tool_call_id=slot["id"] or "",
                            tool_name=slot["name"] or "",
                            arguments=args_obj,
                        )
                    yield LLMEvent(type=LLMEventType.STEP_FINISH)
                    yield LLMEvent(
                        type=LLMEventType.MESSAGE_FINISH,
                        stop_reason=str(choice.finish_reason),
                        iterations=1,
                    )
        except _LITELLM_UPSTREAM_ERRORS as exc:
            # Mid-stream upstream failure (e.g. SSE cut, 5xx mid-response).
            raise UpstreamLLMError(str(exc)) from exc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/chat/test_litellm_provider.py -v`
Expected: 3 passed. If you see `RuntimeWarning: coroutine 'fake_acompletion' was never awaited`, the patch's side_effect expects an async generator — that's correct here.

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/chat/llm/litellm_provider.py \
        backend/tests/chat/test_litellm_provider.py
git commit -m "feat(chat): LiteLLMProvider with tool-call delta accumulator"
```

---

### Task 4: `MCPClient` wrapper + in-memory transport

**Files:**
- Create: `backend/src/quaestor/chat/mcp/client.py`
- Test: `backend/tests/chat/test_mcp_client.py`

**Interfaces:**
- Consumes (existing): `fastmcp.Client`, `quaestor.mcp.server.build_mcp`.
- Produces:
  - `class MCPClient`:
    - `async def __aenter__(self) -> MCPClient`
    - `async def __aexit__(self, exc_type, exc, tb) -> None`
    - `async def list_tools(self) -> list[Any]` — returns the FastMCP tool list (each item has `name`, `description`, `inputSchema`).
    - `async def call_tool(self, name: str, arguments: dict[str, Any]) -> CallToolResult`-like dataclass with `output: str` (text) and `is_error: bool`. If the tool is unknown, raise `ToolNotFoundError`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/chat/test_mcp_client.py`:

```python
"""Round-trip the in-memory fastmcp.Client against the real build_mcp()."""
from __future__ import annotations

import pytest

from quaestor.chat.mcp.client import MCPClient, ToolNotFoundError
from quaestor.mcp.server import build_mcp


@pytest.mark.asyncio
async def test_list_tools_returns_registered_tools():
    mcp = build_mcp()
    async with MCPClient(mcp) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools}
        # Spot-check a handful of core + parity tools (ADR-0009).
        assert "record_expense" in names
        assert "list_transactions" in names
        assert "monthly_report" in names


@pytest.mark.asyncio
async def test_call_tool_returns_text_output(engine, session, seeded):
    # Build an isolated MCP server bound to the test engine/session.
    from quaestor.mcp.server import build_mcp

    mcp = build_mcp()
    async with MCPClient(mcp) as client:
        result = await client.call_tool(
            "list_accounts", {}
        )
    assert result.is_error is False
    assert "Bancolombia" in result.output


@pytest.mark.asyncio
async def test_call_tool_unknown_name_raises():
    mcp = build_mcp()
    async with MCPClient(mcp) as client:
        with pytest.raises(ToolNotFoundError):
            await client.call_tool("does_not_exist", {})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/chat/test_mcp_client.py -v`
Expected: `ModuleNotFoundError: No module named 'quaestor.chat.mcp.client'`.

- [ ] **Step 3: Add the chat conftest (engine/session/seeded mirrors)**

Create `backend/tests/chat/conftest.py`:

```python
import pytest
from sqlmodel import Session

from quaestor.db import init_db, make_engine
from quaestor.services import accounts, categories


@pytest.fixture
def engine():
    eng = make_engine(memory=True)
    init_db(eng)
    return eng


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s


@pytest.fixture
def seeded(session):
    account = accounts.create_account(
        session, "Bancolombia", "debit", "COP", balance=10_000_000
    )
    category = categories.create_category(session, "Groceries")
    return {"account": account, "category": category}
```

- [ ] **Step 4: Implement `client.py`**

Create `backend/src/quaestor/chat/mcp/client.py`:

```python
"""MCPClient — thin async wrapper around `fastmcp.Client`.

Use as `async with MCPClient(mcp) as client:`. One in-memory `Client` per
request; no subprocess, no TCP.

The wrapper exists so the agentic loop never imports `fastmcp` directly;
swapping to a remote streamable-HTTP transport later means changing this
file, nothing else.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/chat/test_mcp_client.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/src/quaestor/chat/mcp/client.py \
        backend/tests/chat/conftest.py \
        backend/tests/chat/test_mcp_client.py
git commit -m "feat(chat): MCPClient wrapper around fastmcp.Client"
```

---

### Task 5: `to_openai_tools()` — MCP `inputSchema` → OpenAI `tools=[]`

**Files:**
- Create: `backend/src/quaestor/chat/mcp/schema.py`
- Test: `backend/tests/chat/test_schema_converter.py`

**Interfaces:**
- Produces:
  - `def to_openai_tools(mcp_tools: list[Any]) -> list[dict[str, Any]]` — each MCP tool becomes `{"type": "function", "function": {"name": ..., "description": ..., "parameters": <inputSchema or fallback>}}`. Pure (no I/O).
  - Module-level lazy singletons:
    - `_tools_cache: list | None = None`
    - `_openai_tools_cache: list | None = None`
    - `_lock: asyncio.Lock | None = None`
  - `async def get_cached_tools() -> list[dict[str, Any]]` — first call fetches via `MCPClient`, subsequent calls return `_openai_tools_cache` unchanged.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/chat/test_schema_converter.py`:

```python
from types import SimpleNamespace

from quaestor.chat.mcp.schema import to_openai_tools


def test_converts_minimal_tool():
    mcp_tools = [
        SimpleNamespace(
            name="list_accounts",
            description="List all accounts.",
            inputSchema={
                "type": "object",
                "properties": {"archived": {"type": "boolean"}},
                "required": [],
            },
        )
    ]
    out = to_openai_tools(mcp_tools)
    assert out == [
        {
            "type": "function",
            "function": {
                "name": "list_accounts",
                "description": "List all accounts.",
                "parameters": mcp_tools[0].inputSchema,
            },
        }
    ]


def test_converts_tool_without_input_schema_uses_empty_object():
    mcp_tools = [
        SimpleNamespace(
            name="noop", description="Does nothing.", inputSchema=None
        )
    ]
    out = to_openai_tools(mcp_tools)
    assert out[0]["function"]["parameters"] == {"type": "object", "properties": {}}


def test_preserves_anyof_and_ref_in_input_schema():
    schema = {
        "type": "object",
        "properties": {
            "tag": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "tx_id": {"$ref": "#/$defs/TxId"},
        },
    }
    mcp_tools = [SimpleNamespace(name="t", description="d", inputSchema=schema)]
    out = to_openai_tools(mcp_tools)
    assert out[0]["function"]["parameters"] == schema
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/chat/test_schema_converter.py -v`
Expected: `ModuleNotFoundError: No module named 'quaestor.chat.mcp.schema'`.

- [ ] **Step 3: Implement `schema.py`**

Create `backend/src/quaestor/chat/mcp/schema.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/chat/test_schema_converter.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/chat/mcp/schema.py \
        backend/tests/chat/test_schema_converter.py
git commit -m "feat(chat): MCP inputSchema to OpenAI tools converter + cache"
```

---

### Task 6: SSE event serializer (Vercel AI SDK UI Message Stream shape)

**Files:**
- Create: `backend/src/quaestor/chat/events.py`
- Test: `backend/tests/chat/test_events.py`

**Interfaces:**
- Produces:
  - `def serialize_event(event: LLMEvent, message_id: str) -> bytes` — returns the SSE wire bytes (event name is encoded in the JSON `type` field; the literal `event:` SSE line is omitted because Vercel's UI Message Stream consumers only read `data:` and identify by the JSON `type`).
  - `def render_sse(payload: dict) -> bytes` — helper: `b"data: <json>\\n\\n"` with `ensure_ascii=False`.
  - `def done_bytes() -> bytes` — `b"data: [DONE]\\n\\n"`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/chat/test_events.py`:

```python
import json

from quaestor.chat.events import done_bytes, render_sse, serialize_event
from quaestor.chat.llm.provider import LLMEvent, LLMEventType


def _data(text: bytes) -> dict:
    # Strip "data: " prefix and trailing "\n\n"
    assert text.startswith(b"data: "), text
    return json.loads(text.removeprefix(b"data: ").rstrip(b"\n").decode("utf-8"))


def test_serialize_message_start():
    ev = LLMEvent(
        type=LLMEventType.MESSAGE_START, message_id="msg_1", model="MiniMax-M3"
    )
    out = _data(serialize_event(ev, message_id="msg_1"))
    assert out == {"type": "start", "messageId": "msg_1"}


def test_serialize_text_delta():
    ev = LLMEvent(type=LLMEventType.TEXT_DELTA, delta="hola")
    out = _data(serialize_event(ev, message_id="m"))
    assert out == {"type": "text-delta", "id": "m", "delta": "hola"}


def test_serialize_text_start_and_end_share_content_index():
    start = _data(serialize_event(LLMEvent(type=LLMEventType.TEXT_START, content_index=0), message_id="m"))
    end = _data(serialize_event(LLMEvent(type=LLMEventType.TEXT_END, content_index=0), message_id="m"))
    assert start == {"type": "text-start", "id": "m"}
    assert end == {"type": "text-end", "id": "m"}


def test_serialize_tool_input_start():
    ev = LLMEvent(type=LLMEventType.TOOL_INPUT_START, tool_call_id="tc_1", tool_name="list_transactions")
    out = _data(serialize_event(ev, message_id="m"))
    assert out == {"type": "tool-input-start", "toolCallId": "tc_1", "toolName": "list_transactions"}


def test_serialize_tool_input_available():
    ev = LLMEvent(
        type=LLMEventType.TOOL_INPUT_AVAILABLE,
        tool_call_id="tc_1",
        tool_name="list_transactions",
        arguments={"date_from": "2026-06-01"},
    )
    out = _data(serialize_event(ev, message_id="m"))
    assert out == {
        "type": "tool-input-available",
        "toolCallId": "tc_1",
        "toolName": "list_transactions",
        "input": {"date_from": "2026-06-01"},
    }


def test_serialize_tool_output_available_with_error():
    ev = LLMEvent(
        type=LLMEventType.TOOL_OUTPUT_AVAILABLE,
        tool_call_id="tc_1",
        output="account not found",
        is_error=True,
    )
    out = _data(serialize_event(ev, message_id="m"))
    assert out["type"] == "tool-output-available"
    assert out["toolCallId"] == "tc_1"
    assert out["output"] == "account not found"
    assert out["isError"] is True


def test_serialize_step_finish_and_message_finish():
    step = _data(serialize_event(LLMEvent(type=LLMEventType.STEP_FINISH), message_id="m"))
    assert step == {"type": "finish-step"}
    msg = _data(
        serialize_event(
            LLMEvent(type=LLMEventType.MESSAGE_FINISH, stop_reason="end_turn", iterations=2),
            message_id="m",
        )
    )
    assert msg == {"type": "finish", "finishReason": "end_turn"}


def test_serialize_error_event():
    ev = LLMEvent(type=LLMEventType.ERROR, code="upstream", message="boom", retryable=True)
    out = _data(serialize_event(ev, message_id="m"))
    assert out == {"type": "error", "errorText": "boom"}


def test_render_sse_wraps_payload_with_data_prefix():
    out = render_sse({"type": "ping"})
    assert out.startswith(b"data: ")
    assert out.endswith(b"\n\n")
    assert json.loads(out.removeprefix(b"data: ").rstrip(b"\n")) == {"type": "ping"}


def test_done_bytes_literal():
    assert done_bytes() == b"data: [DONE]\n\n"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/chat/test_events.py -v`
Expected: `ModuleNotFoundError: No module named 'quaestor.chat.events'`.

- [ ] **Step 3: Implement `events.py`**

Create `backend/src/quaestor/chat/events.py`:

```python
"""SSE wire format for the chat endpoint.

We emit the Vercel AI SDK UI Message Stream (verified against
`ai-sdk.dev/docs/ai-sdk-ui/stream-protocol`): a `text/event-stream` body
where each event's `data:` line is a JSON object with a `type` field whose
value identifies the part (`start`, `text-start`, `text-delta`,
`tool-input-start`, `tool-input-available`, `tool-output-available`,
`finish-step`, `finish`, `error`, …). Termination is the literal
`data: [DONE]\\n\\n`.

Each dataclass-style event is rendered as one `data:` line — the SSE `event:`
field is intentionally NOT used because the consumer identifies events by
the JSON `type`.
"""
from __future__ import annotations

import json
from typing import Any

from .llm.provider import LLMEvent, LLMEventType


def render_sse(payload: dict[str, Any]) -> bytes:
    """Render one SSE message: `data: <json>\\n\\n`."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")


def done_bytes() -> bytes:
    """The literal `[DONE]` sentinel Vercel's parser uses to end a stream."""
    return b"data: [DONE]\n\n"


def serialize_event(event: LLMEvent, *, message_id: str) -> bytes:
    """Translate one LLMEvent to SSE bytes. Field names follow the Vercel
    UI Message Stream protocol exactly (`messageId`, `toolCallId`,
    `toolName`, `input`, `isError`, `finishReason`, `errorText`, `id`).
    """
    t = event.type
    if t == LLMEventType.MESSAGE_START:
        return render_sse({"type": "start", "messageId": message_id})

    if t == LLMEventType.TEXT_START:
        return render_sse({"type": "text-start", "id": message_id})

    if t == LLMEventType.TEXT_DELTA:
        return render_sse({"type": "text-delta", "id": message_id, "delta": event.delta or ""})

    if t == LLMEventType.TEXT_END:
        return render_sse({"type": "text-end", "id": message_id})

    if t == LLMEventType.TOOL_INPUT_START:
        assert event.tool_call_id is not None
        assert event.tool_name is not None
        return render_sse(
            {
                "type": "tool-input-start",
                "toolCallId": event.tool_call_id,
                "toolName": event.tool_name,
            }
        )

    if t == LLMEventType.TOOL_INPUT_DELTA:
        assert event.tool_call_id is not None
        return render_sse(
            {
                "type": "tool-input-delta",
                "toolCallId": event.tool_call_id,
                "inputTextDelta": event.arguments_delta or "",
            }
        )

    if t == LLMEventType.TOOL_INPUT_AVAILABLE:
        assert event.tool_call_id is not None
        assert event.tool_name is not None
        return render_sse(
            {
                "type": "tool-input-available",
                "toolCallId": event.tool_call_id,
                "toolName": event.tool_name,
                "input": event.arguments or {},
            }
        )

    if t == LLMEventType.TOOL_OUTPUT_AVAILABLE:
        assert event.tool_call_id is not None
        payload: dict[str, Any] = {
            "type": "tool-output-available",
            "toolCallId": event.tool_call_id,
            "output": event.output or "",
        }
        if event.is_error:
            payload["isError"] = True
        return render_sse(payload)

    if t == LLMEventType.STEP_FINISH:
        return render_sse({"type": "finish-step"})

    if t == LLMEventType.MESSAGE_FINISH:
        return render_sse({"type": "finish", "finishReason": event.stop_reason or "end_turn"})

    if t == LLMEventType.ERROR:
        return render_sse({"type": "error", "errorText": event.message or "unknown error"})

    raise ValueError(f"unhandled LLMEventType: {t!r}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/chat/test_events.py -v`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/chat/events.py \
        backend/tests/chat/test_events.py
git commit -m "feat(chat): SSE event serializer (Vercel UI Message Stream shape)"
```

---

### Task 7: `LLMProvider` factory

**Files:**
- Create: `backend/src/quaestor/chat/llm/factory.py`
- Test: `backend/tests/chat/test_factory.py`

**Interfaces:**
- Produces:
  - `def build_llm_provider() -> LLMProvider` — reads `LLM_PROVIDER` (default `"litellm"`), `LLM_MODEL` (default `"anthropic/MiniMax-M3"`), `ANTHROPIC_API_KEY` (optional), `ANTHROPIC_BASE_URL` (optional). Recognized `LLM_PROVIDER` values: `"litellm"`. Unknown value → raise `ValueError` listing recognized values.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/chat/test_factory.py`:

```python
import pytest

from quaestor.chat.llm.factory import build_llm_provider
from quaestor.chat.llm.litellm_provider import LiteLLMProvider
from quaestor.chat.llm.provider import LLMProvider


def test_default_provider_is_litellm(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    provider = build_llm_provider()
    assert isinstance(provider, LiteLLMProvider)


def test_provider_is_llmprovider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "litellm")
    monkeypatch.setenv("LLM_MODEL", "anthropic/MiniMax-M3")
    provider = build_llm_provider()
    assert isinstance(provider, LLMProvider)


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "magic-llm")
    with pytest.raises(ValueError, match="litellm"):
        build_llm_provider()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/chat/test_factory.py -v`
Expected: `ModuleNotFoundError: No module named 'quaestor.chat.llm.factory'`.

- [ ] **Step 3: Implement `factory.py`**

Create `backend/src/quaestor/chat/llm/factory.py`:

```python
"""LLMProvider factory — select the active provider from `LLM_PROVIDER`."""
from __future__ import annotations

import os

from .litellm_provider import LiteLLMProvider
from .provider import LLMProvider

_RECOGNIZED = {"litellm": LiteLLMProvider}


def build_llm_provider() -> LLMProvider:
    """Return the configured LLMProvider. Fails fast on unknown values."""
    name = os.environ.get("LLM_PROVIDER", "litellm").strip().lower() or "litellm"
    cls = _RECOGNIZED.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown LLM_PROVIDER={name!r}. Recognized values: {sorted(_RECOGNIZED)}"
        )
    return cls(
        model=os.environ.get("LLM_MODEL", "anthropic/MiniMax-M3"),
        api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        base_url=os.environ.get("ANTHROPIC_BASE_URL") or None,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/chat/test_factory.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/chat/llm/factory.py \
        backend/tests/chat/test_factory.py
git commit -m "feat(chat): LLMProvider factory driven by LLM_PROVIDER env"
```

---

### Task 8: `ChatService.stream()` — agentic loop

**Files:**
- Create: `backend/src/quaestor/chat/service.py`
- Test: `backend/tests/chat/test_service.py`

**Interfaces:**
- Consumes (Tasks 2, 3, 4, 5): `LLMProvider`, `LLMEvent`, `MCPClient`, `get_cached_tools`.
- Produces:
  - `class ChatService`:
    - `def __init__(self, provider: LLMProvider, mcp: FastMCP, max_iterations: int = 8) -> None`
    - `async def stream(self, messages: list[dict]) -> AsyncIterator[bytes]` — yields SSE bytes; one request's worth of `start → … → finish → [DONE]` plus the `x-vercel-ai-ui-message-stream: v1` header is set on the outer `StreamingResponse` (in Task 9), not here.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/chat/test_service.py`:

```python
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
    holder: dict[str, FakeMCPClient] = {}

    def factory(*args, **kwargs):
        client = FakeMCPClient(
            {
                "list_transactions": CallToolResult(
                    output='[{"id":1,"payee":"Café","amount":15000}]', is_error=False
                )
            }
        )
        holder["client"] = client
        return client

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/chat/test_service.py -v`
Expected: `ModuleNotFoundError: No module named 'quaestor.chat.service'`.

- [ ] **Step 3: Implement `service.py`**

Create `backend/src/quaestor/chat/service.py`:

```python
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
    ) -> None:
        self._provider = provider
        self._mcp = mcp
        self._max_iterations = max_iterations

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
                        async for event in self._provider.stream(conversation, tools):
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/chat/test_service.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/chat/service.py \
        backend/tests/chat/test_service.py
git commit -m "feat(chat): ChatService agentic loop + SSE shaping"
```

---

### Task 9: FastAPI router + `StreamingResponse`

**Files:**
- Create: `backend/src/quaestor/api/chat.py`
- Modify: `backend/src/quaestor/api/__init__.py` (include the chat router)
- Test: `backend/tests/chat/test_api.py`, `backend/tests/chat/test_api_auth.py`, `backend/tests/chat/test_api_limits.py`

**Interfaces:**
- Consumes: `build_llm_provider()`, `build_mcp()`, `ChatService`, `require_auth`.
- Produces:
  - `router = APIRouter(prefix="/chat", tags=["chat"])`
  - `POST /chat` → `ChatRequest` body (`messages: list[dict]`), returns `StreamingResponse(generator, media_type="text/event-stream", headers={"x-vercel-ai-ui-message-stream": "v1", "Cache-Control": "no-cache", "X-Accel-Buffering": "no"})`.
  - `class ChatRequest(BaseModel)` with `messages: list[ChatMessage]`, validation enforcing:
    - max 200 messages
    - max 32 KB per `content`
    - `sum(len(content) for m in messages) // 4 > 100_000` → `413`
    - schema-shaped messages (role ∈ {user, assistant, tool, system}, content is str)

- [ ] **Step 1: Update the chat conftest with API fixtures**

Replace `backend/tests/chat/conftest.py` (the Task 4 version) with:

```python
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from quaestor.api import create_app
from quaestor.db import init_db, make_engine
from quaestor.services import accounts, categories


@pytest.fixture
def engine():
    eng = make_engine(memory=True)
    init_db(eng)
    return eng


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s


@pytest.fixture
def seeded(session):
    account = accounts.create_account(
        session, "Bancolombia", "debit", "COP", balance=10_000_000
    )
    category = categories.create_category(session, "Groceries")
    return {"account": account, "category": category}


@pytest.fixture
def app(monkeypatch, engine):
    """A TestClient app bound to the in-memory engine and a stub LLM."""
    from collections.abc import AsyncIterator
    from typing import Any

    from quaestor.chat.llm.provider import LLMEvent, LLMEventType, LLMProvider

    class StubProvider(LLMProvider):
        def __init__(self) -> None:
            self.events: list[LLMEvent] = []

        async def stream(
            self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
        ) -> AsyncIterator[LLMEvent]:
            for ev in self.events:
                yield ev

    stub = StubProvider()
    monkeypatch.setattr("quaestor.chat.llm.factory.build_llm_provider", lambda: stub)
    app = create_app()
    app.dependency_overrides.clear()
    yield app, stub


@pytest.fixture
def auth_headers(monkeypatch):
    """A bearer token + session cookie for require_auth."""
    monkeypatch.setenv("APP_TOKEN", "test-token-xyz")
    return {"Authorization": "Bearer test-token-xyz"}
```

- [ ] **Step 2: Write the failing API tests**

Create `backend/tests/chat/test_api_limits.py`:

```python
import pytest
from fastapi.testclient import TestClient


def _oversize_content(n_chars: int) -> dict:
    return {"messages": [{"role": "user", "content": "x" * n_chars}]}


def test_too_many_messages_returns_413(app):
    test_app, _ = app
    client = TestClient(test_app)
    body = {"messages": [{"role": "user", "content": "x"} for _ in range(201)]}
    r = client.post("/api/chat", json=body)
    assert r.status_code == 413


def test_message_content_too_large_returns_413(app):
    test_app, _ = app
    client = TestClient(test_app)
    r = client.post("/api/chat", json=_oversize_content(33_000))
    assert r.status_code == 413


def test_total_token_estimate_too_large_returns_413(app):
    test_app, _ = app
    client = TestClient(test_app)
    # 201 * 2000 chars = 402_000 chars // 4 = 100_500 tokens (> 100k).
    body = {"messages": [{"role": "user", "content": "x" * 2000} for _ in range(201)]}
    r = client.post("/api/chat", json=body)
    assert r.status_code == 413


def test_malformed_body_returns_400(app):
    test_app, _ = app
    client = TestClient(test_app)
    r = client.post("/api/chat", json={"messages": "not-a-list"})
    assert r.status_code in (400, 422)


def test_unknown_role_returns_422(app):
    test_app, _ = app
    client = TestClient(test_app)
    r = client.post("/api/chat", json={"messages": [{"role": "wizard", "content": "x"}]})
    assert r.status_code == 422
```

Create `backend/tests/chat/test_api_auth.py`:

```python
from fastapi.testclient import TestClient


def test_chat_requires_auth(app):
    test_app, _ = app
    client = TestClient(test_app)
    r = client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 401


def test_chat_accepts_valid_bearer(app, auth_headers):
    test_app, stub = app
    client = TestClient(test_app)
    r = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "hi"}]},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
```

Create `backend/tests/chat/test_api.py`:

```python
"""End-to-end POST /api/chat via TestClient with a stub LLMProvider."""
from __future__ import annotations

from quaestor.chat.llm.provider import LLMEvent, LLMEventType


def test_happy_path_streams_text_and_done(app, auth_headers):
    test_app, stub = app
    stub.events = [
        LLMEvent(type=LLMEventType.MESSAGE_START, message_id="m1", model="MiniMax-M3"),
        LLMEvent(type=LLMEventType.TEXT_START, content_index=0),
        LLMEvent(type=LLMEventType.TEXT_DELTA, delta="Hola"),
        LLMEvent(type=LLMEventType.TEXT_END, content_index=0),
        LLMEvent(type=LLMEventType.STEP_FINISH),
        LLMEvent(type=LLMEventType.MESSAGE_FINISH, stop_reason="end_turn", iterations=1),
    ]
    from fastapi.testclient import TestClient

    client = TestClient(test_app)
    with client.stream(
        "POST",
        "/api/chat",
        json={"messages": [{"role": "user", "content": "hola"}]},
        headers=auth_headers,
    ) as r:
        assert r.status_code == 200
        assert r.headers["x-vercel-ai-ui-message-stream"] == "v1"
        assert r.headers["content-type"].startswith("text/event-stream")
        body = b"".join(r.iter_bytes())
    assert b"data: [DONE]" in body
    assert b'"type":"start"' in body
    assert b'"type":"text-delta"' in body and b'"delta":"Hola"' in body
    assert b'"type":"finish"' in body
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/chat/test_api.py tests/chat/test_api_auth.py tests/chat/test_api_limits.py -v`
Expected: failures on `ModuleNotFoundError: No module named 'quaestor.api.chat'` plus `404 Not Found` for the route until Task 9 mounts it.

- [ ] **Step 4: Implement `api/chat.py`**

Create `backend/src/quaestor/api/chat.py`:

```python
"""`POST /api/chat` — natural-language HTTP bridge to MCP.

Returns an SSE stream that conforms to the Vercel AI SDK UI Message Stream
protocol (`x-vercel-ai-ui-message-stream: v1`). Frontend consumes via
`useChat()` + `DefaultChatTransport({ api: '/api/chat' })`.

Request validation:
  - max 200 messages
  - max 32 KB per message content
  - rough token estimate = `sum(len(content)) // 4` must not exceed 100_000
"""
from __future__ import annotations

import os
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..chat.llm.factory import build_llm_provider
from ..chat.service import ChatService
from ..mcp.server import build_mcp
from .deps import require_auth

router = APIRouter(prefix="/chat", tags=["chat"])

_MAX_MESSAGES = 200
_MAX_MESSAGE_BYTES = 32 * 1024
_MAX_TOKEN_ESTIMATE = 100_000

Role = Literal["user", "assistant", "tool", "system"]


class ChatMessage(BaseModel):
    role: Role
    content: str = Field(default="", max_length=_MAX_MESSAGE_BYTES)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., max_length=_MAX_MESSAGES)


def _validate_token_estimate(req: ChatRequest) -> None:
    total_chars = sum(len(m.content) for m in req.messages)
    if total_chars // 4 > _MAX_TOKEN_ESTIMATE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="request token estimate exceeds 100k",
        )


@router.post("", dependencies=[Depends(require_auth)])
async def chat(req: ChatRequest) -> StreamingResponse:
    _validate_token_estimate(req)

    provider = build_llm_provider()
    mcp = build_mcp()
    max_iterations = int(os.environ.get("CHAT_MAX_ITERATIONS", "8"))
    service = ChatService(provider=provider, mcp=mcp, max_iterations=max_iterations)

    messages_payload = [m.model_dump() for m in req.messages]
    generator = service.stream(messages_payload)

    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "x-vercel-ai-ui-message-stream": "v1",
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
```

- [ ] **Step 5: Mount the router in `api/__init__.py`**

In `backend/src/quaestor/api/__init__.py`, add the chat router import + include in `_include_routers`. Locate the existing block:

```python
    from .routers import (
        accounts,
        ...
        reports,
        rollover,
        settings,
        tags,
        transactions,
    )

    app.include_router(auth.router, prefix="/api")
```

and replace with:

```python
    from . import chat as chat_module
    from .routers import (
        accounts,
        ...
        reports,
        rollover,
        settings,
        tags,
        transactions,
    )

    app.include_router(auth.router, prefix="/api")
    app.include_router(chat_module.router, prefix="/api", dependencies=protected)
```

(The router file already declares `prefix="/chat"` and `dependencies=[Depends(require_auth)]` on the route, so the extra `dependencies=protected` on `include_router` is belt-and-braces and matches the rest of the codebase.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/chat/ -v`
Expected: all chat tests pass.

- [ ] **Step 7: Run the full backend suite to confirm no regression**

Run: `cd backend && uv run pytest -v`
Expected: existing tests still green.

- [ ] **Step 8: Commit**

```bash
git add backend/src/quaestor/api/chat.py \
        backend/src/quaestor/api/__init__.py \
        backend/tests/chat/conftest.py \
        backend/tests/chat/test_api.py \
        backend/tests/chat/test_api_auth.py \
        backend/tests/chat/test_api_limits.py
git commit -m "feat(chat): POST /api/chat StreamingResponse + validation + tests"
```

---

### Task 10: Caddyfile — tailnet-only for `/api/chat`

**Files:**
- Modify: `Caddyfile`

**Interfaces:**
- Produces: a public-route block that returns `404` for `/api/chat*` on the public listener, while leaving the tailnet route in place.

- [ ] **Step 1: Inspect the existing Caddyfile**

Run: `grep -nE 'route |reverse_proxy|handle|@' /Users/angelozdev/me/quaestor/Caddyfile | head -60`
Expected: shows existing matcher/route structure (e.g. `@mcp host …`, `@tailnet …`). Capture the indentation style.

- [ ] **Step 2: Add the `/api/chat` 404 rule to the public side**

Open `Caddyfile`. Locate the public-route block (the one matched by the public-host matcher — NOT the `@tailnet` block). Add the rule **before** any `reverse_proxy` to the backend. Use the indentation style from Step 1. The shape is:

```caddy
@chat path /api/chat*
respond @chat 404
```

If the Caddyfile uses a single-route form (one `reverse_proxy` to backend), insert the two lines above that `reverse_proxy`. If it uses named-route blocks, place them inside the same route group as `/mcp` on the public side.

- [ ] **Step 3: Validate the Caddyfile locally**

Run: `docker run --rm -v "$PWD/Caddyfile:/etc/caddy/Caddyfile:ro" caddy:2 caddy validate --config /etc/caddy/Caddyfile`
Expected: prints `Valid configuration`. If `caddy` is installed natively, `caddy validate --config Caddyfile` works the same.

- [ ] **Step 4: Commit**

```bash
git add Caddyfile
git commit -m "ops(caddy): return 404 publicly for /api/chat (tailnet-only, ADR-0011)"
```

---

### Task 11: Manual smoke test (post-deploy)

**Files:** none.

- [ ] **Step 1: Start the stack (dev or prod)**

For dev: `cd /Users/angelozdev/me/quaestor && just dev` (per the 2026-06-22 dev-environment plan).
For prod: deploy via the runbook in `docs/runbooks/deploy.md`.

- [ ] **Step 2: From a tailnet client, hit the route**

```bash
APP_TOKEN=$(grep APP_TOKEN backend/.env.local | cut -d= -f2)
curl -N -X POST https://<tailnet-hostname>/api/chat \
  -H "Authorization: Bearer $APP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"hola"}]}'
```

Expected: SSE stream beginning with `data: {"type":"start","messageId":"…"}`, followed by text/tool events, ending with `data: {"type":"finish",…}` and `data: [DONE]`.

- [ ] **Step 3: Confirm public 404**

From outside the tailnet (e.g. the public DNS):
```bash
curl -s -o /dev/null -w '%{http_code}\n' https://quaestor.example.com/api/chat
```
Expected: `404`.

- [ ] **Step 4: Smoke a tool-call round-trip**

```bash
curl -N -X POST https://<tailnet-hostname>/api/chat \
  -H "Authorization: Bearer $APP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"¿cuánto gasté en café este mes?"}]}'
```
Expected: SSE contains `tool-input-available` for `list_transactions`, `tool-output-available` with the transaction JSON, then a text-delta summarising the answer.

- [ ] **Step 5: Provider swap test**

Set `LLM_MODEL=anthropic/claude-sonnet-4-6` in `backend/.env.local`, restart the api container, repeat Step 4. Expect the same wire format with text from the swapped model.

- [ ] **Step 6: Note the smoke results in the deploy runbook**

Open `docs/runbooks/deploy.md` (or create if missing) and add a one-line entry to the post-deploy checklist: "Smoke-test `/api/chat` from a tailnet client (ADR-0014)." Reference `docs/superpowers/plans/2026-06-22-chat-endpoint.md` as the canonical runbook.

- [ ] **Step 7: Commit**

```bash
git add docs/runbooks/deploy.md   # only if it changed
git commit -m "docs(runbooks): add /api/chat smoke step (ADR-0014)" || true
```

---

## Self-Review

**Spec coverage:**
- §Objective / SSE route → Tasks 8, 9.
- §Scope: chat package → Tasks 1, 4, 5, 6, 7, 8. `LLMProvider` Protocol → Task 2; `LiteLLMProvider` → Task 3; factory → Task 7.
- §Components: every file in the spec's tree is created/modified in this plan.
- §Data flow / Request (200 msg / 32 KB / 100k tok) → Task 9.
- §Response (SSE) → Tasks 6 (serializer), 8 (service), 9 (router sets header).
- §Lifecycle (agentic loop, cached tools, per-request Client) → Tasks 4, 5, 8.
- §Tool schema caching → Task 5.
- §Error handling table → Task 8 (UpstreamLLMError → SSE error event; tool is_error → TOOL_OUTPUT_AVAILABLE with isError; loop cap → finish length; validation → 413/400 before streaming; auth → 401 via require_auth).
- §Testing → Tasks 2–9 each have explicit test files matching the spec's table.
- §Deployment / network → Task 10.
- §ADR to file → Task 1 (Step 6).
- §Plan to invoke (1–11) → matches this plan's task list.

**Placeholder scan:** no "TBD"/"TODO"/"implement later". Every step shows the actual code, command, or file path.

**Type consistency:**
- `LLMEvent.type` ↔ `LLMEventType` ↔ `serialize_event` ↔ `ChatService.stream` ↔ `LiteLLMProvider.stream` all use the same enum members.
- `message_id` is propagated from `LiteLLMProvider` (`MESSAGE_START.message_id`) into every `serialize_event(..., message_id=...)` call in `ChatService`.
- `tool_call_id` is set on `TOOL_INPUT_START` (from the first delta with `id`) and reused on `TOOL_INPUT_DELTA` / `TOOL_INPUT_AVAILABLE` / `TOOL_OUTPUT_AVAILABLE` in the same iteration.
- `ChatRequest.messages` → `ChatMessage` → `messages_payload` → `ChatService.stream` → `provider.stream(messages, tools)`; the dict shape is OpenAI-compatible.
- `MCPClient.call_tool(name, arguments: dict) -> CallToolResult(output: str, is_error: bool)` consumed uniformly by `ChatService`.
- `get_cached_tools(mcp_client)` returns the same `list[dict]` (OpenAI-shaped) across the process; never returns the raw MCP list.

**Vercel event-name fix applied throughout** (verified against `ai-sdk.dev/docs/ai-sdk-ui/stream-protocol`): `start`, `text-start`, `text-delta`, `text-end`, `tool-input-start`, `tool-input-delta`, `tool-input-available`, `tool-output-available`, `finish-step`, `finish`, `error`, `[DONE]`. Header `x-vercel-ai-ui-message-stream: v1` set by `api/chat.py`.

**Out-of-scope items not addressed by this plan (per spec §Scope):** server-side persistence, streaming LLM progress, multi-user, voice/multimodal, modifications to existing MCP tools. None ship here.

---

Plan complete and saved to `docs/superpowers/plans/2026-06-22-chat-endpoint.md`. Two execution options:

1. **Subagent-Driven (recommended)** — dispatch fresh subagent per task with two-stage review between tasks. Best for parallelizable review gates.

2. **Inline Execution** — execute tasks in this session with checkpoints, switching to a fresh subagent only for tricky tasks.

Which approach?
