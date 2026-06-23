# 0015 — Frontend chat request wire-format adapter (UIMessage → {role, content})

- **Status:** accepted
- **Date:** 2026-06-22
- **Supersedes / Superseded by:** none
- **Related:** ADR-0014 (chat endpoint + LiteLLM + MCP bridge)

## Context

The backend `POST /api/chat` (FastAPI, ADR-0014) validates the request with:

```python
class ChatMessage(BaseModel):
    role: Role       # Literal["user", "assistant", "tool", "system"]
    content: str = ""  # ← expected flat string
```

…and passes each message verbatim into the LiteLLM agent loop. The LLM
provider downstream therefore expects the OpenAI / LiteLLM chat-completion
shape: `{role, content: string}`.

`@ai-sdk/react@3` `useChat` + `DefaultChatTransport` (the chat client we
adopted in the chat input frontend plan) ships its **response** wire format
in the Vercel AI SDK UI Message Stream protocol — which the backend already
emits correctly (ADR-0014 §"SSE protocol"). However, the **request** it
sends by default is the UIMessage shape:

```json
{
  "id": "...",
  "messages": [
    { "id": "...", "role": "user", "parts": [{ "type": "text", "text": "Dame el resumen del mes" }] }
  ],
  "trigger": "submit-message"
}
```

That shape does not match `ChatMessage`. Pydantic parses it with
`content=""` (the default), so the LiteLLM provider receives an empty user
turn and emits its "message came through empty" fallback. The frontend
appears to "send" successfully but the model never sees the user text.

This was not caught by the chat input frontend plan's verification (48 unit
tests, build green) because the plan verified the response protocol — the
one ADR-0014 documented — and assumed the request shape was implicit. It
was not. Manual curl against the running stack surfaced the mismatch
immediately.

## Decision

Adapt the request body on the **frontend** at the transport boundary. Do
NOT change the backend `ChatRequest` schema, the LiteLLM provider, or the
agent loop — they are correct and any change ripples through every other
chat consumer (curl, future MCP clients, e2e tests).

Use `DefaultChatTransport`'s documented `prepareSendMessagesRequest` hook
to transform the outgoing body. The hook receives the full
`{id, messages: UIMessage[], body, headers, api, trigger, messageId, ...}`
context and returns the new request envelope. We rewrite `body` to:

```ts
{
  messages: messages.map((m) => ({
    role: m.role,
    content: m.parts.filter(isTextPart).map((p) => p.text).join("\n"),
  })),
  trigger,
}
```

…where:

- `role` is passed through (UIMessage roles `user`/`assistant`/`system`
  are a subset of `ChatMessage.Role`; `tool` is never sent on the wire
  because tool calls ride on assistant tool parts and their outputs are
  flattened into the assistant's final text).
- `content` is the concatenation of every text part in the message in
  order, joined by `\n`. Non-text parts (file, image, source-url, …) are
  skipped for v1; if any are present we `console.warn` so the omission is
  observable, but we never throw — sending partial content is better than
  crashing the chat.
- `trigger` is forwarded verbatim so the backend can distinguish
  `submit-message` vs `regenerate-message` if it ever needs to.

The transform lives in `frontend/lib/chat-transport.ts` inside
`createChatTransport()`. Consumers already memoize via
`useMemo(() => createChatTransport(), [])`; the hook itself does not need
memoization because `useChat` calls it on each request, not each render.

### Why on the frontend, not the backend

- Smallest blast radius: zero backend code changes, no schema migration,
  no version bump on `ChatRequest`, no shim for backward compat.
- The shape the backend consumes is the universal OpenAI / LiteLLM
  shape; that's the shape every chat consumer (curl, OpenAI-compatible
  clients, future providers) will use. Teaching the backend to also parse
  UIMessage would be a permanent second format we have to maintain.
- If a future agent ever wants to consume the chat endpoint from a
  Vercel-AI-SDK-style client with zero glue, the backend can add an
  adapter then. Today there's exactly one client (this frontend), and we
  can change it.

### Why `prepareSendMessagesRequest`, not a custom `HttpChatTransport`

- `DefaultChatTransport`'s `prepareSendMessagesRequest` is the
  documented, stable seam for body transformation in `@ai-sdk/react@3`.
- We get streaming, retry, abort, and resume for free because
  `DefaultChatTransport` still owns the HTTP plumbing.
- A custom transport would re-implement all of the above.

## Consequences

- **New file content** in `frontend/lib/chat-transport.ts`: ~25 lines of
  transform. Smoke test in `frontend/lib/chat-transport.test.ts` grows
  from 1 to ~6 assertions covering: empty input, single-text message,
  multi-text message joined with `\n`, non-text parts filtered out with
  warn log, trigger passthrough, `role` passthrough for all four roles.
- **No backend changes.** No new deps. No new env vars. No ADR-0014
  amendment required (the SSE / response protocol is unchanged).
- **Behavior change visible to the user:** the chat now actually works
  end-to-end. Before this fix, every prompt returned the
  "message came through empty" fallback response.
- **Future parts:** when the LLM starts emitting file / image parts via
  this same endpoint (out of scope today), the adapter must be extended
  (e.g. by serializing file parts as data URLs into a future
  `attachments` field). A bare `console.warn` for unknown parts keeps the
  gap observable without breaking the chat.
- **Backend flips are easy:** if `ChatRequest` ever adopts UIMessage
  shape, delete the transform in `chat-transport.ts` — the test suite
  will flag the removed assertions as broken, which is the correct signal.

## Verification

- `pnpm test lib/chat-transport.test.ts` — new assertions cover the
  transform output shape.
- `pnpm typecheck && pnpm lint && pnpm build` — clean (no new
  suppressions needed).
- Manual curl against the running stack with a real `quaestor_session`
  cookie returns the assistant's answer instead of the empty-message
  fallback.
- All 84 existing tests remain green.

## Related

- ADR-0014 — chat endpoint (LiteLLM + MCP bridge); defines the response
  protocol and the `ChatMessage` request schema this adapter targets.
- Plan: `docs/superpowers/plans/2026-06-22-chat-input-frontend.md` —
  verified the response protocol only; this ADR closes the request-side
  gap.
