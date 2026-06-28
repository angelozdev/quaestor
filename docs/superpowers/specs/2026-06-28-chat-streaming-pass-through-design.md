# 2026-06-28 — Chat streaming pass-through (rewrite proxy fix)

## Context

The Quaestor chat assistant must stream LLM tokens to the browser in real
time, the way ChatGPT does. Today it does not. The user sees no partial
text until the assistant turn finishes, then the whole response dumps at
once.

The backend already streams correctly end-to-end:

- `ChatService.stream` (`backend/src/quaestor/chat/service.py:42`) is an
  async generator that yields each `LLMEvent` as the LLM produces it.
- `serialize_event` (`backend/src/quaestor/chat/events.py:41`) writes one
  SSE frame per event in the Vercel AI SDK UI Message Stream wire format
  (ADR-0014).
- `LiteLLMProvider` (`backend/src/quaestor/chat/llm/litellm_provider.py:69`)
  calls `litellm.acompletion(..., stream=True)` and emits per-token
  `TEXT_DELTA` events.

The frontend transport is also correct: `DefaultChatTransport` in
`frontend/lib/chat-transport.ts:24` consumes the SSE stream and feeds
`useChat`, which dispatches deltas into `messages[].parts` so React
re-renders incrementally (`chat-message.tsx:46-66`).

The buffer is introduced by the Next.js rewrite at
`frontend/app/api/[...path]/route.ts:32`, which does
`new NextResponse(await upstream.text(), ...)`. `await upstream.text()`
drains the FastAPI `StreamingResponse` to completion before any byte
reaches `NextResponse`, so the browser sees one big chunk at `[DONE]`.
The SSE content-type is preserved, but the streaming semantics are
destroyed at this hop.

Secondary issue: `frontend/components/markdown/markdown.tsx:14` renders
markdown via `<Streamdown>` without `mode="streaming"`. Without that
flag, Streamdown treats every delta as final markdown and re-parses from
scratch each time, so even after the buffering fix the user would see
flicker on bold/list/code-fence boundaries while tokens arrive.

The current rewrite is also a god-function: one ~37-line `proxy()`
handles URL building, request header copy, request body read, fetch,
response body read, response header copy, and 204/205/304 detection. It
cannot distinguish streaming from non-streaming, does not propagate
`AbortSignal`, and has no tests. Adding any new streaming endpoint in
the future would re-introduce the same buffering bug silently.

## Decision

Replace the god-function rewrite with a small proxy module that uses a
Strategy pattern for response-body handling. Two response policies:

- **Streaming policy** — pass `upstream.body` (a `ReadableStream`)
  straight into `new Response(...)`. Zero copy. Used for SSE and any
  `text/*` response.
- **Buffered policy** — `await upstream.text()` then construct a
  `Response` with the string. Used for JSON and other discrete payloads.

A selector picks the policy from the upstream `content-type` header.
The route handler becomes a thin dispatcher.

Apply `mode="streaming"` to the Streamdown component so partial
markdown renders incrementally without re-parse flicker.

Propagate `req.signal` to upstream `fetch` so client disconnects abort
the LLM call and stop the token burn.

Keep header forwarding (cookie, CSRF, Authorization) centralized in two
small modules so the policy for what crosses the proxy boundary lives
in one place.

## Architecture

```
frontend/app/api/[...path]/route.ts              thin route handlers
frontend/lib/proxy/
  create-proxy.ts                                orchestrates URL + fetch + signal + policy
  build-target-url.ts                            URL composition (testable, no magic strings)
  policies/
    response-policy.ts                           Strategy interface
    streaming-response-policy.ts                 SSE / text/* pass-through
    buffered-response-policy.ts                  JSON / 204 / await text
    select-response-policy.ts                    content-type → policy
  forwarding/
    request-headers.ts                           request → upstream header copy
    response-headers.ts                          upstream → response header copy
frontend/components/markdown/markdown.tsx        + mode="streaming"
frontend/lib/proxy/create-proxy.test.ts       streaming path test (co-located)
```

### `ResponsePolicy` (Strategy)

```ts
// frontend/lib/proxy/policies/response-policy.ts
export interface ResponsePolicy {
  build(upstream: Response): Response | Promise<Response>
}
```

- `StreamingResponsePolicy.build(upstream)` → `new Response(upstream.body, { status, headers })`. If `upstream.body` is `null` (rare), pass `null` to `Response`.
- `BufferedResponsePolicy.build(upstream)` → for 204/205/304 returns `new Response(null, { status, headers })`; otherwise `new Response(await upstream.text(), { status, headers })`.

### `selectResponsePolicy(upstream)`

Reads `upstream.headers.get("content-type")`. Returns the streaming
policy when the type starts with `text/` (covers `text/event-stream`,
`text/plain`, etc.) and the buffered policy otherwise. Centralizing
this in one selector means future streaming formats get added in one
place, not by copy-paste.

### `createProxy(req, path)`

```ts
// frontend/lib/proxy/create-proxy.ts
export async function createProxy(
  req: NextRequest,
  path: string[],
): Promise<Response> {
  const target = buildTargetUrl(path, req.nextUrl.search)
  const upstream = await fetch(target, {
    method: req.method,
    headers: forwardRequestHeaders(req),
    body: await readRequestBody(req),
    redirect: "manual",
    cache: "no-store",
    signal: req.signal,                   // abort propagates to LLM
  })
  const policy = selectResponsePolicy(upstream)
  return policy.build(upstream)
}
```

### Header forwarding policy

`forwardRequestHeaders(req)` produces a `Headers` containing:

- `content-type` when present on the request.
- `cookie` when present (session auth travels this way per ADR-0020).
- `x-csrf-token` when present (CSRF double-submit cookie, ADR-0020).
- `authorization` when present (APP_TOKEN fallback auth path).

`forwardResponseHeaders(upstream)` produces the response-side `Headers`:

- `content-type` from upstream.
- Every `set-cookie` value from `upstream.headers.getSetCookie()`,
  preserved as multiple headers (Next/Web standard: `Headers.append`).

### Route handlers

```ts
// frontend/app/api/[...path]/route.ts
type Ctx = { params: Promise<{ path: string[] }> }
const handler = async (req: NextRequest, ctx: Ctx) =>
  createProxy(req, (await ctx.params).path)

export const GET = handler
export const POST = handler
export const PATCH = handler
export const DELETE = handler
```

Single shared handler. No per-method specialization needed; the request
method is forwarded to upstream by `fetch`.

### `Markdown`

```tsx
// frontend/components/markdown/markdown.tsx
<Streamdown mode="streaming" className={className} components={markdownComponents}>
  {children}
</Streamdown>
```

`mode="streaming"` enables `parseIncompleteMarkdown` (default `true`
under that mode), which closes unclosed code fences, headings, and
list items as text arrives so the user sees stable formatting instead
of flicker on every delta. `Markdown` is already memoized.

## What does NOT change

- Backend chat code (`ChatService.stream`, `serialize_event`,
  `LiteLLMProvider`).
- Frontend chat components (`chat-section`, `chat-thread`,
  `chat-message`, `chat-input`, `chat-tool-chip`, `chat-empty-state`,
  `chat-error-banner`, `chat-blinking-cursor`).
- `createChatTransport` / `useChat` / `DefaultChatTransport` —
  consumer of the stream, not producer.
- CSRF middleware (`backend/src/quaestor/api/csrf.py`) and CSRFMiddleware integration.
- MCP tool orchestration and sanitization
  (`backend/src/quaestor/chat/service.py:151-240`,
  `backend/src/quaestor/chat/sanitize.py:59`).
- `Caddyfile` — out of scope; reported bug is local dev.
- ADRs 0014, 0015, 0016, 0019, 0020 — design is consistent with all
  five. ADR-0018 (proposed) is in the same direction.
- Tests for the existing chat pipeline.

## Error handling

- Upstream `fetch` may reject (network error, abort). The rewrite
  surfaces the rejection by letting it bubble; Next renders the route
  error boundary. Existing behavior preserved.
- `upstream.body === null` (rare; e.g. empty 200). `StreamingResponsePolicy.build`
  must accept null and pass `null` to `new Response`. The buffered
  policy handles 204/205/304 explicitly.
- `content-type` missing on upstream response. Selector defaults to
  buffered policy — safe fallback. Streaming endpoints always set the
  header (`backend/src/quaestor/chat/service.py:107`).
- Client disconnect (tab close, navigation). `signal: req.signal`
  aborts upstream `fetch`, which cancels the FastAPI generator
  (`ChatService.stream` iterates `provider.stream`; cancelling the
  `AsyncIterator` raises `CancelledError` in the LLM provider). No
  tokens billed after disconnect.

## Testing

- `frontend/lib/proxy/create-proxy.test.ts` (vitest, co-located per repo convention):
  - Stub `globalThis.fetch` to return `new Response(stream, { headers: { "content-type": "text/event-stream" }, status: 200 })` where `stream` is a `ReadableStream` of three `data: ...\n\n` chunks.
  - Build a `NextRequest` via `new NextRequest(new Request("http://localhost/api/chat", { method: "POST", body: "{}", signal: ac.signal }))`.
  - Assert `createProxy(req, ["chat"])` returns a `Response` whose `body` is a `ReadableStream` (not a string).
  - Iterate the returned `body` and assert chunks arrive in the order produced by the upstream stream (no buffering).
  - Abort the request via `ac.abort()` and assert `fetch` was called with the matching `signal`.
  - Repeat for `content-type: application/json` → assert the buffered path returns a `Response` whose `body` is a string.
  - **Note:** if happy-dom lacks `ReadableStream` iteration semantics needed for the streaming-path test, switch that one test to `node` env via `// @vitest-environment node` at the top of the file; the buffered-path test can stay on the default env.
- Manual verification after implementation:
  - `pnpm dev` (frontend) + FastAPI backend running.
  - DevTools → Network → `/api/chat` request → assert chunks arrive
    every ~100-500ms, not one big chunk at `[DONE]`.
  - Send a message → assert tokens appear in the chat box in real
    time; assert markdown (bold, lists, code fences) renders without
    flicker.

## Constraints

- **Next 16 docs are required reading** before implementation.
  `frontend/AGENTS.md` warns that this version of Next has breaking
  changes. The implementer must read
  `node_modules/next/dist/docs/` sections on `Route Handlers`,
  `NextResponse`, and streaming before writing code. Specific
  questions to answer:
  - Is `new NextResponse(stream, ...)` (or `new Response(stream, ...)`) supported on this runtime?
  - Is `req.signal` exposed on `NextRequest`?
  - Does `NextResponse` accept `null` body for 204/205/304?
- If Next 16 has a streaming-body restriction not present in prior
  versions, fallback path is documented inline in
  `create-proxy.ts`: use `Response` (web standard) instead of
  `NextResponse` if the latter rejects streams. The orchestrator and
  policies are unchanged either way.

## Out of scope (follow-ups)

- Per-route handlers (e.g. `frontend/app/api/chat/route.ts`) replacing
  the catch-all `[...path]`. Would let chat-specific concerns (auth,
  rate limit, abort observability) live closer to the endpoint. Not
  needed today; the policy selector already isolates the streaming
  concern.
- SSE over WebSocket. SSE is sufficient: one-way, browser-native,
  works through Caddy, works with `fetch` (no `EventSource` needed
  because we already go through `fetch` via AI SDK transport).
- Streaming-aware metrics (TTFB per chat request, p50 chunk latency).
- Cancellation UX (a "stop generating" button). `useChat` exposes
  `stop` and the route already forwards `signal`; the UI to invoke
  it on user demand is a separate piece of work.