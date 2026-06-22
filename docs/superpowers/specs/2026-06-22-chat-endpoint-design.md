# Chat endpoint — natural-language HTTP bridge to MCP

**Date:** 2026-06-22
**Status:** design (pending approval)
**Depends on:** P2 MCP server (all 52 tools registered, ADR-0009), ADR-0006 (HTTP/MCP parity), ADR-0011 (tailnet-only posture)
**New ADR:** `0014-chat-endpoint-with-litellm-and-mcp-bridge.md`

---

## Objective

Let the user type a natural-language message in the web frontend and have the LLM interpret it, call MCP tools on the user's behalf, and stream a final answer back as **server-sent events**. The backend becomes an **LLM-driven orchestrator** over the existing MCP server: same tools, same auth posture, same data.

This is **not** a replacement for the MCP server. It is an HTTP frontend to the LLM that drives it. The MCP server (P2) remains the source of truth for what tools exist and what they do.

## Scope

- New HTTP route `POST /api/chat` in the FastAPI process, returns SSE (`text/event-stream`).
- New `chat` package under `backend/src/quaestor/chat/` with strict module boundaries.
- LLM provider abstraction (`LLMProvider` Protocol) — today only `LiteLLMProvider` is implemented; the Protocol is the documented seam for future providers (`AnthropicNativeProvider`, `OpenAIProvider`, …). The active provider is selected by `LLM_PROVIDER` env var.
- Reuse the existing `build_mcp()` + `Client(build_mcp())` (in-memory transport) to list tools and call them.
- Frontend (Next.js) uses Vercel AI SDK's `useChat()` hook with `DefaultChatTransport` pointing at `/api/chat`.
- Tailnet-only exposure (extends ADR-0011).

**Out of scope:**
- Server-side conversation persistence — frontend sends full message history each request (per user choice).
- Streaming tool output (LLM-side progress) — only the tool result is streamed.
- Multi-user chat — single-user app, same `APP_TOKEN` as everything else.
- Voice / multimodal input — text only.
- Modifying any existing MCP tool or service.

## Architecture

```
Browser (Next.js)
  └─ useChat()  ←  Vercel AI SDK
      └─ DefaultChatTransport → POST /api/chat  (SSE)

FastAPI process
  └─ POST /api/chat → BearerAuthMiddleware → ChatService.stream()
       ├─ MCPClient (wraps Client(build_mcp()))  → list_tools() / call_tool()
       ├─ schema.to_openai_tools()                (MCP → OpenAI tools[])
       └─ LiteLLMProvider                         (LLMProvider Protocol impl)
            └─ litellm.acompletion(model=..., stream=True)
                 → model="anthropic/MiniMax-M3"
                 → ANTHROPIC_BASE_URL=https://api.minimax.io/anthropic
```

`ChatService` knows about SSE shapes and the agentic loop. `LLMProvider` and `MCPClient` are the only things it touches. Swapping the LLM (MiniMax → Claude → GPT-5) means changing `LLM_MODEL`, nothing else.

## Components

```
backend/src/quaestor/
├── api/
│   └── chat.py                       # NEW: FastAPI router
├── chat/                             # NEW package
│   ├── service.py                    # ChatService — agentic loop + SSE shaping
│   ├── events.py                     # SSE event types
│   ├── llm/
│   │   ├── provider.py               # LLMProvider Protocol + LLMEvent dataclass
│   │   └── litellm_provider.py      # LiteLLMProvider impl
│   └── mcp/
│       ├── client.py                 # MCPClient wrapper around fastmcp.Client
│       └── schema.py                 # MCP inputSchema → OpenAI tools[] converter
├── mcp/server.py                     # (existing) build_mcp() — already public
├── mcp/auth.py                       # (existing) BearerAuthMiddleware reused
└── main.py                           # (existing) include chat router
```

**New deps (pyproject.toml):**
- `litellm>=1.40` — multi-provider abstraction (Python analogue of Vercel AI SDK's provider layer).

**New env vars:**
- `LLM_PROVIDER` — default `litellm`. Recognized values map to `LLMProvider` implementations (`litellm` → `LiteLLMProvider`). Unknown values fail startup with a clear error.
- `LLM_MODEL` — default `anthropic/MiniMax-M3`. Passed verbatim to the provider.
- `ANTHROPIC_API_KEY` — MiniMax key (Anthropic SDK env var naming for clarity, even though the provider is LiteLLM).
- `ANTHROPIC_BASE_URL` — default `https://api.minimax.io/anthropic`.
- `CHAT_MAX_ITERATIONS` — default `8`.
- `CHAT_REQUEST_TIMEOUT_S` — default `120`.

## Data flow

### Request

`POST /api/chat` body:
```json
{
  "messages": [
    {"role": "user", "content": "agrupa mis gastos de este mes por categoría"},
    {"role": "assistant", "content": "...", "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "tc_123", "content": "..."},
    {"role": "user", "content": "ahora excluye transporte"}
  ]
}
```

The frontend owns history. Backend is stateless per request. Validation: max 200 messages, max 32 KB per message, reject if total estimated tokens > 100 k (HTTP 413). Token estimate = `sum(len(content) for m in messages) // 4` — a rough approximation; exact count is the provider's job.

### Response (SSE, `text/event-stream`)

```
event: message_start
data: {"message_id":"msg_abc","model":"MiniMax-M3"}

event: tool_call
data: {"id":"tc_1","name":"list_transactions","arguments":{"date_from":"2026-06-01"}}

event: tool_result
data: {"id":"tc_1","output":"[{...47 transactions...}]","is_error":false}

event: text_delta
data: {"delta":"Tienes 47 gastos este mes. "}

event: text_delta
data: {"delta":"Los categorizo..."}

event: message_stop
data: {"stop_reason":"end_turn","iterations":2}
```

Event shapes match the Vercel AI SDK UI Message Stream protocol so `useChat()` parses them natively: `text_delta` → text chunk; `tool_call` / `tool_result` → tool-call / tool-result parts.

### Lifecycle (one request)

1. FastAPI receives POST → `BearerAuthMiddleware` validates cookie.
2. Router parses `ChatRequest` (Pydantic) → calls `ChatService.stream(req)`.
3. `ChatService` opens `async with MCPClient() as mcp:` — one in-memory Client per request (cheap; no network or subprocess).
4. `tools_schema = chat.mcp.schema.get_cached_tools()` — tool list is fetched **once per process** at first request via `await mcp.list_tools()`, then cached in a module-level lazy singleton (FastMCP tools are static after boot). Per-request work is just the in-memory lookup.
5. `tools = schema.to_openai_tools(tools_schema)` — convert MCP JSON Schemas → OpenAI `tools=[]` (also cached alongside the schema).
6. **Agentic loop** (max `CHAT_MAX_ITERATIONS`):
   ```
   while iterations < MAX:
       async for event in provider.stream(messages, tools):
           if event.type == TEXT_DELTA: yield SSE(text_delta)
           if event.type == TOOL_CALL_DONE:
               yield SSE(tool_call)
               result = await mcp.call_tool(name, args)
               yield SSE(tool_result)
               append assistant_msg(tool_calls=...) + tool_msg(tool_call_id, content) to messages
       if no tool_call this iteration: break
   yield SSE(message_stop)
   ```
7. FastAPI `StreamingResponse(generator(), media_type="text/event-stream")`.

### Tool schema caching

`tools=[]` does not change between requests (FastMCP tools are registered at import time and only change on process restart). Cache strategy:

- `chat.mcp.schema._tools_cache: list[Tool] | None` — module-level lazy singleton.
- First request: `MCPClient.list_tools()` runs once, result stored in the singleton.
- Subsequent requests: synchronous `get_cached_tools()` returns the cached list with no I/O.
- Process restart invalidates the cache (no cross-process sharing needed).
- The OpenAI-shaped `tools=[]` is cached alongside as `_openai_tools_cache`.

This keeps per-request latency flat and removes a round-trip into FastMCP on every message.

## Error handling

| Class | Examples | Behavior |
|-------|----------|----------|
| **Upstream LLM** | MiniMax 5xx, rate limit, auth failure | Catch `litellm.{APIError,AuthenticationError,RateLimitError}` → emit SSE `{"type":"error","code":"upstream","retryable":true}` → close stream cleanly. No retry; user re-sends. |
| **Tool execution** | MCP tool raises (account not found, etc.) | `mcp.call_tool()` returns `result` with `is_error=True` → append as tool result anyway (LLM must see the error to recover) → emit SSE `tool_result` with `is_error:true` → loop continues. |
| **Validation** | Malformed body, oversize messages | HTTP `400` / `413` before streaming starts. |
| **Auth** | Missing/invalid bearer | HTTP `401` (reuses `BearerAuthMiddleware`). |
| **Loop cap** | `iterations == CHAT_MAX_ITERATIONS` | Emit `text_delta` "loop limit reached" + `message_stop` with `stop_reason:"max_iterations"`. |
| **Total timeout** | Request exceeds `CHAT_REQUEST_TIMEOUT_S` | `StreamingResponse` cancels generator; client sees truncated stream. |
| **Unhandled** | Anything else | HTTP `500` with generic message; full traceback in server logs. |

Inline error events (preferred over trailer headers) so Vercel AI SDK can render them in the message stream.

## Testing

| Test file | What | How |
|-----------|------|-----|
| `tests/chat/test_service.py` | Agentic loop: streams text, handles tool_calls, respects max iter, recovers from tool errors | Fake `LLMProvider` returning scripted `LLMEvent` sequences; fake `MCPClient` returning canned results |
| `tests/chat/test_litellm_provider.py` | LiteLLM streaming chunks → `LLMEvent` mapping; tool_call deltas assembled correctly | `AsyncMock` of `litellm.acompletion` returning scripted chunk sequence |
| `tests/chat/test_mcp_client.py` | `Client(build_mcp())` round-trip — `list_tools` returns the 52 tools, `call_tool` executes | Real FastMCP instance + real in-memory Client (no mocks) |
| `tests/chat/test_schema_converter.py` | MCP `inputSchema` → OpenAI `tools[]`; edge cases: `$ref`, `anyOf`, nullable | Sample schemas from actual registered tools |
| `tests/chat/test_events.py` | SSE event serialization matches Vercel AI SDK UI Message Stream shape | Direct serializer tests |
| `tests/chat/test_api.py` | `POST /api/chat` end-to-end: TestClient posts, SSE stream parses, mocked provider returns scripted events | FastAPI `TestClient` + fake provider |
| `tests/chat/test_api_auth.py` | `/api/chat` requires bearer token (reuses existing BearerAuthMiddleware tests) | Same pattern as `tests/mcp/test_core_writes.py` |
| `tests/chat/test_api_limits.py` | 413 on oversize messages, 400 on malformed body | Body-size + schema validation tests |

**Discipline:**
- TDD throughout — failing test first, watch it fail for the right reason, then implement.
- No mocks of FastMCP internals — always test through `Client(build_mcp())`.
- Mock the LLM at the `LLMProvider` boundary (fast, deterministic), not at `litellm.acompletion` (slow, flaky).
- Coverage gate: 90%+ per project rule.

**Manual smoke (post-deploy):**
- Tiny Next.js dev page with `useChat()` → type "¿cuánto gasté en café este mes?" → see tool_call + tool_result + final text streamed.
- Verify SSE events arrive in order: `message_start → tool_call → tool_result → text_delta* → message_stop`.
- Provider swap test: set `LLM_MODEL=anthropic/claude-sonnet-4-6`, restart, same prompt works.

## Deployment / network

- Extends ADR-0011: `/api/chat` joins `/mcp` on the tailnet only.
- Caddyfile: `/api/chat` returns 404 publicly; tailnet proxy routes it to the backend container.
- No new container — the chat router mounts inside the existing FastAPI process.
- `ANTHROPIC_API_KEY` and friends added to `.env.example` (already required by ADR-0010 deployment posture).
- ADR-0010 deployment plan gets a one-line addition: "after deploy, smoke-test `/api/chat` from a tailnet client."

## ADR to file

`docs/adr/0014-chat-endpoint-with-litellm-and-mcp-bridge.md` records:
- Why LiteLLM (multi-provider abstraction, the Python equivalent of Vercel AI SDK's provider model).
- Why `fastmcp.Client(build_mcp())` in-memory transport (public API only, no `_tool_manager` reach-in, future-proof if MCP server splits into its own process).
- Tailnet-only posture (extends ADR-0011).
- Provider-swap invariant: changing `LLM_MODEL` is the only knob needed to swap providers.
- Frontend-sent history as the chosen conversation model (no server-side persistence).

## Plan to invoke

After spec approval, invoke `superpowers:writing-plans` to produce a TDD-ordered implementation plan broken into reviewable tasks:
1. Add `litellm` dep + env vars + ADR-0014.
2. `chat/llm/provider.py` — `LLMProvider` Protocol + `LLMEvent` types.
3. `chat/llm/litellm_provider.py` — LiteLLMProvider impl with streaming + tool-call delta assembly.
4. `chat/mcp/schema.py` — MCP `inputSchema` → OpenAI `tools[]` converter.
5. `chat/mcp/client.py` — MCPClient wrapper around `fastmcp.Client`.
6. `chat/events.py` — SSE event types + serializer (Vercel AI SDK UI Message Stream shape).
7. `chat/service.py` — ChatService (agentic loop + SSE shaping).
8. `api/chat.py` — FastAPI router + `StreamingResponse`.
9. Wire into `main.py`.
10. Caddyfile rule: 404 on public `/api/chat`.
11. Smoke test from tailnet.