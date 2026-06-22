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
- Plan: `docs/superpowers/plans/2026-06-22-chat-endpoint.md`.
