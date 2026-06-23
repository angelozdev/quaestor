# Chat input — frontend (Vercel AI SDK UI Message Stream consumer)

**Date:** 2026-06-22
**Status:** design (pending approval)
**Depends on:** `2026-06-22-chat-endpoint-design.md` (backend `POST /api/chat` SSE), ADR-0014 (chat endpoint + LitellM + MCP bridge), ADR-0004 (fintech dark/mint aesthetic), ADR-0002 (design-system token contract)
**New ADR:** none — extends existing ADRs only

---

## Objective

Give the user an inline chat section on the dashboard where they type natural-language questions about their finances and the LLM-driven MCP assistant responds with streaming text, calling tools transparently when needed.

This is the **frontend counterpart** to the already-shipped `POST /api/chat` SSE endpoint. The backend exists and is verified working (52 MCP tools exposed, full agentic loop). This spec covers only the client-side consumption layer.

## Scope

- One new section on the existing dashboard page (`app/(app)/page.tsx`), below the 4 cards.
- New `components/chat/*` package (9 files) holding the section, thread, message, tool chip, input, empty state, blinking cursor, error banner, and shared types.
- Install `@ai-sdk/react@^3` (peer dep `ai@^6`, installed transitively).
- New keyframes + utility class in `app/globals.css` for two distinctive micro-interactions (blinking Bricolage cursor, animated input underline).
- 8 unit tests colocated at `components/chat/chat-section.test.tsx` (Vitest + Testing Library) + a small `lib/chat-errors.test.ts` covering the error translator.
- Touch two existing files: `app/(app)/page.tsx` (insert `<DashboardChatSection />` at the bottom of the existing JSX) and `lib/query.ts` (add `chatAssistantTurn` invalidation group).

**Out of scope:**
- Conversation persistence (decided: in-memory only; lost on navigation/reload).
- Multi-thread / conversation list.
- Edit / regenerate / copy individual messages.
- Markdown rendering of assistant text (plain text only for v1).
- Code highlighting in tool outputs.
- Token counter, model picker, temperature slider.
- New sidebar entry — chat lives inline on dashboard per product decision.
- Backend changes — endpoint already ships Vercel AI SDK UI Message Stream format.

## Architecture

```
DashboardPage (existing client component, "use client")
  └─ <ChatSection />            ← appended at the bottom of the existing JSX
                                    (no wrapper component; lives directly in page.tsx)

ChatSection ("use client")
  └─ useChat({ transport: new DefaultChatTransport({ api: '/api/chat' }) })
       │
       ├─ if messages.length === 0 && status === 'ready' → <ChatEmptyState />
       ├─ else                                         → <ChatThread />
       │      └─ messages.map → <ChatMessage />
       │            ├─ role=user      → right-aligned bubble, --secondary bg
       │            ├─ role=assistant → left-aligned, parts discriminated:
       │            │     ├─ isTextUIPart(part)        → <p>{part.text}</p>
       │            │     ├─ isToolUIPart(part)         → <ChatToolChip part={part} />
       │            │     │   (covers both `tool-{name}` and `dynamic-tool` types;
       │            │     │    JSON <pre> blocks tagged data-sensitive="true")
       │            │     └─ if status==='streaming' && last message → <ChatBlinkingCursor />
       │            └─ role=system/tool → ignored (tool messages get collapsed into the chip's output)
       ├─ if status === 'error'      → <ChatErrorBanner error={error} onRetry={regenerate} />
       │                                (translated es-CO copy via translateChatError, close × dismissable)
       └─ <ChatInput onSend={sendMessage} onStop={stop} status={status} maxLength={32000} cooldownMs={600} />
```

### File map

| Path | Status | Purpose |
|---|---|---|
| `frontend/components/chat/chat-section.tsx` | NEW | `"use client"`. Owns `useChat`. Composes thread + empty state + error + input. |
| `frontend/components/chat/chat-thread.tsx` | NEW | Scrollable list of messages. Handles auto-scroll-on-append (skipping if user scrolled up). |
| `frontend/components/chat/chat-message.tsx` | NEW | Memoized single message renderer. Discriminates `parts`. |
| `frontend/components/chat/chat-tool-chip.tsx` | NEW | Collapsible pill: tool name + pulsing mint dot when running, click to expand input/output JSON. |
| `frontend/components/chat/chat-empty-state.tsx` | NEW | Title + subtitle + 3 suggested-prompt chips. |
| `frontend/components/chat/chat-input.tsx` | NEW | Auto-grow textarea + send/stop button (one button, label flips). |
| `frontend/components/chat/chat-blinking-cursor.tsx` | NEW | Bricolage `_` glyph, `aria-hidden`. |
| `frontend/components/chat/chat-error-banner.tsx` | NEW | `ChatErrorBanner`: `<div role="alert">` with translated message, close `×`, and optional Reintentar. Owns the `dismissed` local state per spec contract. |
| `frontend/components/chat/chat.types.ts` | NEW | Re-export `UIMessage`, `ToolUIPart` from `@ai-sdk/react` (which re-exports from `ai`; either source works at runtime) plus local helper type guards. |
| `frontend/lib/chat-errors.ts` | NEW | `translateChatError(error: Error): string` — maps raw `useChat` errors to es-CO copy per the Errors table. |
| `frontend/lib/chat-transport.ts` | NEW | Exports a factory `createChatTransport()` returning `new DefaultChatTransport({ api: '/api/chat' })`. Consumed inside `ChatSection` via `useMemo(() => createChatTransport(), [])` so the instance is stable across renders. |
| `frontend/lib/query.ts` | MOD | Add `chatAssistantTurn` group to `INVALIDATION` (entity roots the chat may touch). |
| `frontend/app/globals.css` | MOD | Add `@keyframes blink-cursor`, `@keyframes chat-underline-sweep`, and utility class `.chat-input-underline`. |
| `frontend/app/(app)/page.tsx` | MOD | Append `<DashboardChatSection />` at the bottom of the existing JSX (after the grid). |
| `frontend/package.json` | MOD | Add `@ai-sdk/react@^3` to `dependencies`. |
| `frontend/components/chat/chat-section.test.tsx` | NEW | 6 unit tests covering render, suggested-prompt click, user/assistant alignment, tool chip collapse, cursor visibility. Colocated with the component (matches existing `form-field.test.tsx` / `entity-form-dialog.test.tsx` pattern). |

### What is NOT touched

- Backend (already ships the SSE protocol this spec consumes).
- Sidebar (`components/app-shell.tsx`) — chat has no nav entry.
- Axios client (`lib/api/client.ts`) — chat uses `useChat`'s own transport, not the axios stack.
- Auth — `require_auth` on `POST /api/chat` accepts cookie session (verified in `api/deps.py`); the existing Next rewrite `/api/[...path]` forwards the cookie. No bridge needed.
- Other dashboard cards, other pages.

## Data flow

1. `ChatSection` mounts → `useChat({ transport })` returns `{ messages, sendMessage, stop, status, error, regenerate }`.
2. User types in `ChatInput`. `Enter` (without `Shift`) → `sendMessage({ text: input })`. `Shift+Enter` → newline.
3. `useChat` issues `POST /api/chat` with `{ messages: [...history, userMsg] }`. Cookie session forwarded automatically via Next rewrite.
4. Backend returns `text/event-stream` with header `x-vercel-ai-ui-message-stream: v1`. `useChat` parses the protocol internally and updates `messages` incrementally.
5. As assistant message streams: `parts` populates with `type: 'text'` deltas and (if LLM chose to call a tool) `type: 'tool-{name}'` parts. `ChatMessage` re-renders the discriminated parts.
6. When `status === 'streaming'` and there is an in-flight assistant message, `ChatBlinkingCursor` appears at the end of the latest text part.
7. On `finish` event: `status` returns to `'ready'`. `ChatInput` button switches back to "send".
8. On tool-call round-trip: the `tool-output-available` event lands as `part.state === 'output-available'` (or `output-error`). `ChatToolChip` reads `state` to decide pulsing vs static dot.

### On-finish side effect

After the final assistant message lands, invalidate the entity roots the
assistant could have mutated. **Use the existing `INVALIDATION` registry +
`invalidate(qc, group)` helper in `lib/query.ts`** — never call
`qc.invalidateQueries()` with no arguments (that invalidates the entire
TanStack store, including settings/preferences the assistant cannot touch,
and deviates from the codebase pattern enforced by `to-pay-widget.tsx` and
every other mutation hook).

Add a new group to `lib/query.ts`:

```typescript
chatAssistantTurn: [
  [ROOTS.transactions], [ROOTS.planned], [ROOTS.accounts],
  [ROOTS.budgets], [ROOTS.goals], [ROOTS.reports], [ROOTS.recurring],
],
```

Implementation: pass `onFinish` to `useChat` and call
`invalidate(qc, 'chatAssistantTurn')`. The group is intentionally broad
(every entity any of the 52 MCP tools can touch) but scoped — `settings`,
`fx`, `tags`, `categories`, `categoryGroups` are excluded because no chat
tool mutates them in v1. Revisit the group when adding tool surfaces.

## Visual states

| `status` | `messages.length` | Render |
|---|---|---|
| `ready` | 0 | `ChatEmptyState` (3 chips + copy) |
| `ready` | ≥1 | `ChatThread` + `ChatInput` (button = Send) |
| `submitted` | ≥1 | `ChatThread` + `ChatInput` (button = Stop, label "Pensando…", textarea disabled) |
| `streaming` | ≥1 | `ChatThread` with `ChatBlinkingCursor` on last assistant message + input with Stop |
| `error` | * | Banner above `ChatInput` with error.message + "Reintentar" button calling `regenerate()` |

## Distinctive micro-interactions

These two motions are the "remember this" detail. They share the same restrained aesthetic as the rest of the app — they are not loud, but they are unique to this section.

### 1. Blinking Bricolage cursor on streaming text

A `_` glyph in `font-family: var(--font-heading)` (Bricolage Grotesque), `1.2em`, color `var(--primary)`. Animation `blink-cursor 1s steps(2) infinite` defined in `globals.css`:

```css
@keyframes blink-cursor {
  0%, 50% { opacity: 1; }
  50.01%, 100% { opacity: 0; }
}
```

Honors `prefers-reduced-motion: reduce` (animation: none → static `_`).

### 2. Animated gradient underline on input

Input bottom-border animates a left-to-right gradient sweep while focused:

```css
@keyframes chat-underline-sweep {
  0%   { background-position: -100% 0; }
  100% { background-position: 200% 0; }
}
.chat-input-underline {
  background-image: linear-gradient(
    90deg,
    transparent 0%,
    var(--primary) 50%,
    transparent 100%
  );
  background-size: 50% 1px;
  background-repeat: no-repeat;
  background-position: -100% 100%;
  transition: background-position 0s;
}
.chat-input-underline:focus-within {
  animation: chat-underline-sweep 1.6s linear infinite;
}
@media (prefers-reduced-motion: reduce) {
  .chat-input-underline:focus-within {
    animation: none;
    background-image: linear-gradient(90deg, var(--primary), var(--primary));
  }
}
```

Applied to the wrapper `<div>` around the textarea, not the textarea itself (so the gradient is on the section edge, not behind the caret).

### 3. Pulsing mint dot on running tool chip

While a tool call is in flight (`part.state === 'input-streaming' || part.state === 'input-available'` without output yet), the dot pulses and three trailing dots fade in/out in sequence. When output arrives, dot goes static and the trailing dots collapse.

## Tool chip — collapse / expand

- **Collapsed (default):** horizontal pill. Left: dot (animated if running, static if done, red if error). Center: tool name in `font-mono text-xs`. Right: chevron `▸`. Background `var(--muted)`, border `1px solid var(--border)`, radius `--radius`.
- **Expanded:** slide-down 180ms `ease-out` (CSS `transition: max-height 180ms ease-out, opacity 180ms ease-out`). Reveals two blocks:
  1. **Input** (always shown if present): `<pre>` with JSON pretty-printed (2-space indent), `max-height: 160px; overflow-y: auto`, background `var(--popover)`.
  2. **Output** (always shown): same `<pre>` styling. Markdown output preserved verbatim (we do not parse it for v1). If `state === 'output-error'`: left border `3px solid var(--destructive)`, message shown verbatim in the output region.
- **ARIA:** `<button aria-expanded={isOpen} aria-controls={`tool-output-${toolCallId}`}>`. The output region has `role="region"` and `id="tool-output-${toolCallId}"`.

## Empty state

Copy (es-CO):

- Title: `Pregúntale a tu asistente`
- Subtitle: `Puede leer tus cuentas, transacciones, presupuestos y metas.`
- 3 chips (each a `<button>` that calls `sendMessage({ text: <chip text> })`):
  - `¿Cuánto puedo gastar este mes?`
  - `Lista mis cuentas y sus saldos`
  - `Dame el resumen del mes`

Chips disappear as soon as `messages.length > 0` (no toggle, no animation — instant out).

## Errors

Surfaced via `useChat`'s `error: Error | undefined` and `regenerate()`.

All raw `error.message` values flow through `translateChatError(error)` in
`lib/chat-errors.ts` before reaching the DOM. The translator maps each
shape to an allowlist of es-CO strings; unmatched errors fall back to a
generic `Algo salió mal. Vuelve a intentarlo en un momento.` The raw
message is logged server-side, never echoed to the user.

| Source | Detection (regex / shape) | User-facing string (es-CO) |
|---|---|---|
| Network failure / Caddy 502 | `/fetch failed|NetworkError|Failed to fetch/i` or HTML body | `No pudimos contactar al servidor` |
| 401 (cookie expired) | status 401 (axios interceptor handles redirect) | (no banner — redirect wins) |
| 413 (request too large) | `/exceeds.*KB|too large/i` | `Tu mensaje es muy largo. Acórtalo e intenta de nuevo.` |
| 422 (validation) | status 422 | `No pude procesar tu mensaje. Reformúlalo e intenta otra vez.` |
| 429 (rate limit) | status 429 | `Demasiadas solicitudes. Espera un momento e intenta de nuevo.` |
| Backend `error` SSE event | shape `{ errorText }` | `No pude completar tu solicitud. Vuelve a intentarlo.` |
| Stream aborted by user (`stop()`) | — | (no banner — partial message remains) |
| Fallback | unmatched | `Algo salió mal. Vuelve a intentarlo en un momento.` |

`ChatErrorBanner`: `<div role="alert">` containing the translated message,
a close `×` button (sets local `dismissed=true`, hides the banner until the
next error transition), and (if `regenerate` is available) a `Reintentar`
button. The banner does not block input — the user can keep typing while
it is visible.

## Security & authorization

The chat endpoint mutates user state (LLM round-trips, MCP tool calls against
financial data) on a cookie session. This section captures the trust posture
the frontend inherits — these checks live in the backend / Caddy / Next rewrite
chain, not in this PR.

- **CSRF.** POST `/api/chat` rides the existing Next rewrite
  `app/api/[...path]/route.ts` and the same session cookie used by every
  other mutating endpoint in the app. The cookie's `SameSite` attribute (set
  in the FastAPI session middleware) is the primary defense; the implementer
  MUST verify `SameSite=Lax` or stricter is present before merging
  (`grep -r SameSite backend/` and inspect the response `Set-Cookie`).
  No CSRF token is added in this PR — chat inherits whatever posture the
  other write endpoints rely on. If that posture is "SameSite alone",
  document the gap in a follow-up ADR instead of inventing a chat-only
  token scheme.
- **Authorization.** `require_auth` on the backend accepts cookie session.
  No frontend role-based UI gating in v1 — the chat surface is available to
  any authenticated dashboard user, and the 52 MCP tools enforce their own
  per-user scoping server-side (see ADR-0014). If the app introduces
  role-based UI elsewhere, revisit this section to gate the chat entrypoint
  the same way.
- **Error message sanitization.** `useChat`'s `error.message` may contain
  raw backend error text (Pydantic validation details, server stack hints).
  Rendering it verbatim leaks internal schema. The frontend MUST route
  errors through a `translateChatError(error: Error): string` helper that
  maps to a small allowlist of user-facing es-CO strings (see Errors table).
  The raw error is logged server-side, not surfaced to the user.
- **Input cap.** Client-side `maxLength={32000}` on the textarea mirrors the
  backend 32 KB cap. Pasted content beyond this is truncated at the input
  level (fail fast, bound client memory).
- **Send cooldown.** After `sendMessage`, the send button is disabled for
  600 ms. This is not a rate limit (server-side rate limiting is the
  backend's responsibility, tracked in ADR-0014) — it is a UX guard against
  accidental double-submit while the request is in flight.
- **Sensitive output.** `ChatToolChip` renders MCP tool output (which may
  contain account balances, transaction lists, PII). The component sets
  `data-sensitive="true"` on the JSON `<pre>` blocks so future telemetry
  scrubbers, screen-share blockers, and password-manager extensions can
  honor it. No active masking in v1 — masking is deferred to a follow-up
  once the product decides which fields are sensitive.
- **MCP tool trust.** The frontend trusts the tool name + input + output
  emitted by the SSE stream. Content sanitization of tool output strings
  (e.g., stripping phishing URLs, suppressing system-prompt-mimicking text)
  is a backend concern (allowlist of tool names + output filter). The
  frontend MUST NOT pass tool output to `dangerouslySetInnerHTML`, a
  markdown renderer, or a linkifier in v1.

## Accessibility

- **Focus:**
  - On mount, `ChatInput`'s textarea gets `autoFocus`.
  - After `sendMessage`, focus returns to the textarea (not the button).
  - On `status === 'submitted' | 'streaming'`, textarea `disabled` so user cannot interleave.
- **Keyboard:**
  - `Enter` → submit.
  - `Shift+Enter` → newline (textarea auto-grow up to 6 lines, then internal scroll).
  - `Esc` during `streaming`/`submitted` → `stop()`.
- **ARIA:**
  - `<section aria-live="polite" aria-label="Conversación con asistente">` on `ChatThread`. New messages announced without interrupting.
  - `ChatToolChip` is a `<button>` with `aria-expanded` + `aria-controls`.
  - Empty state chips are `<button>`s with `aria-label="Enviar sugerencia: <text>"`.
  - `ChatBlinkingCursor`: `aria-hidden="true"`.
- **Reduced motion:** `prefers-reduced-motion: reduce` disables both `blink-cursor` and `chat-underline-sweep`. Tool chip pulse falls back to a static dot. Implemented via two `@media` blocks in `globals.css`.

## Performance

- **`React.memo` on `ChatMessage`** keyed by `message.id`. Streaming text updates only the last message.
- **No virtualization** — realistic thread length is <50 messages. `react-virtuoso` is out of scope; revisit if usage data shows longer threads.
- **Textarea auto-grow** with manual `scrollHeight` measurement in `onChange`. No library.
- **Cookie session** rides the existing Next rewrite `/api/[...path]`. No new auth code.
- **Bundle:** `@ai-sdk/react@^3` is the only new runtime dep (~35 KB gzipped including `ai@^6` transitive). Acceptable.
- **`onFinish` invalidation:** coarse `qc.invalidateQueries()` on dashboard keys. Per-tool selective invalidation is YAGNI for v1.

## Testing

`frontend/components/chat/chat-section.test.tsx` — Vitest + Testing Library + happy-dom. **No live SSE.** `useChat` is mocked at the module boundary via `vi.mock("@ai-sdk/react", ...)`. The mock MUST be hoisted (`vi.hoisted` or factory closure with `beforeEach` reset) so per-test state does not leak. **8 tests total** — the 6 originals plus 2 error-banner tests added during review (see Errors section + ChatErrorBanner contract):

| # | Test | Asserts |
|---|---|---|
| 1 | Empty state visible when `messages.length===0 && status==='ready'` | Title, subtitle, 3 chips rendered |
| 2 | Click suggested-prompt chip | `sendMessage` called once with `{ text: <chip text> }` |
| 3 | User message renders right-aligned with `--secondary` bg | class names + inline style contain expected values |
| 4 | Assistant text message renders left-aligned, plain text (no markdown) | text content equals input verbatim; no `<a>` or `<strong>` injected |
| 5 | Tool chip collapses by default; click expands and reveals input + output JSON | `aria-expanded` flips `false → true`; output region has expected text |
| 6 | `ChatBlinkingCursor` present in last assistant message when `status==='streaming'`; absent when `status==='ready'` | `queryByTestId('chat-cursor')` reflects state |
| 7 | Error banner renders translated es-CO copy (not raw `error.message`); Reintentar calls `regenerate` | `getByRole('alert')` text equals `translateChatError(err)` output; `regenerate` called once on click |
| 8 | Error banner close `×` dismisses until next error transition | initial banner visible → click `×` → banner gone; setting a new `mockError` shows it again |

In addition, `lib/chat-errors.test.ts` covers `translateChatError` mapping per row of the Errors table (one assertion per source row, plus the fallback case). The `onFinish` invalidation side effect MUST also be covered: the mocked `useChat` accepts and invokes the `onFinish` callback, and the test asserts `invalidate(qc, 'chatAssistantTurn')` (or the underlying `qc.invalidateQueries` calls) fire on completion.

Coverage target: ≥80% statements in `components/chat/` and 100% on `lib/chat-errors.ts` (small translator, trivial to fully cover).

## Dependencies (additions only)

| Package | Version | Why |
|---|---|---|
| `@ai-sdk/react` | `^3.0.210` | `useChat`, `DefaultChatTransport`, types (`UIMessage`, `ToolUIPart`). Latest verified via npm registry today. |
| `ai` | (transitive via `@ai-sdk/react`) | Not added explicitly; pulled as `ai@6.0.208` transitively. |

No other dep changes. `package.json` `packageManager` field (`pnpm@11.3.0`) untouched.

## Open questions (none remaining)

All scoping decisions resolved during brainstorming:

1. Placement → inline on dashboard.
2. Persistence → in-memory only.
3. SSE client → `@ai-sdk/react` `useChat` (over hand-rolled).
4. Tool display → colapsable chip with output.
5. Aesthetic → refined-mint-extended with two distinctive micro-interactions.
6. Empty state → 3 suggested prompts.
7. Layout approach → console embebida (section full-width, internal scroll).
8. Auth → cookie session (no bridge).

## Risks

| Risk | Mitigation |
|---|---|
| `@ai-sdk/react@3` API differs from memory of v2/v1 | Use only documented stable API: `useChat({ transport })`, `sendMessage`, `stop`, `regenerate`, `status`, `error`, `messages`. Confirm exact return shape against `node_modules/@ai-sdk/react/dist/index.d.ts` during implementation. |
| `useChat` type signatures for `parts` discriminate unexpectedly (e.g., `type: 'dynamic-tool'`) | Inspect generated message JSON via a Vitest test that hits a local fake transport. |
| `onFinish` invalidation over-invalidates → flash of loading skeletons on dashboard cards | Use `qc.invalidateQueries()` without `refetchType: 'all'` default; TanStack Query refetches active queries only. |
| Streaming produces 1000+ re-renders on long assistant message | `React.memo` on `ChatMessage`; tailwind classes are static per message. Verified by existing dashboard cards already using the pattern. |
| Reduced-motion users miss the cursor/underline affordance | Fallback: cursor remains visible as static glyph; underline becomes solid `var(--primary)`. Both convey "active" without motion. |

## What ships in this PR

1. `pnpm-lock.yaml` updated for `@ai-sdk/react`.
2. 9 new files under `frontend/components/chat/` (8 components + 1 error banner) and 1 new file `frontend/lib/chat-errors.ts`.
3. 1 new file `frontend/lib/chat-transport.ts`.
4. 1 new file `frontend/components/chat/chat-section.test.tsx` (8 tests) and 1 new file `frontend/lib/chat-errors.test.ts`.
5. 3 modified files: `frontend/app/(app)/page.tsx`, `frontend/app/globals.css`, `frontend/lib/query.ts` (add `chatAssistantTurn` group).
6. 1 modified `frontend/package.json`.

No backend changes. No ADR. No runbook changes.

## Verification plan (implementation phase)

- `pnpm typecheck` → clean.
- `pnpm lint` → clean (biome).
- `pnpm test` → all green, 6 new chat tests passing.
- Manual: dev stack running (api + frontend), navigate to `/`, see empty state with 3 chips, click "¿Cuánto puedo gastar este mes?", confirm:
  - User bubble appears right-aligned.
  - Tool chip collapses → expands if assistant calls a tool.
  - Streaming text with blinking cursor.
  - Final assistant message visible.
  - Banner appears on a forced 422 (e.g., empty messages array from devtools).
- Accessibility: Lighthouse a11y score ≥95 on `/`.
- Reduced-motion: toggle `prefers-reduced-motion: reduce` in DevTools → cursor static, underline solid.