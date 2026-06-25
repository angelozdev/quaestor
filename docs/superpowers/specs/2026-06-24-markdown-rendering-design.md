# 2026-06-24 — Markdown rendering in the chat surface

## Context

The Quaestor chat assistant emits markdown — both as free-form prose
(per the coach persona in `backend/src/quaestor/chat/prompts.py:14-64`,
which uses `**bold**`, lists, and `## ` headings) and as structured
reports (per `backend/src/quaestor/domain/report_markdown.py:27-138`,
which uses H1/H2 headings, GFM pipe tables, and bullet lists).

The frontend today renders assistant text as raw text inside
`<p className="whitespace-pre-wrap">` (`frontend/components/chat/chat-message.tsx:50`).
That means:

1. A `**bold**` from the LLM shows up to the user as literal asterisks.
2. The monthly report's pipe tables arrive as `| Category | Total | % |`
   with no formatting.
3. The "Resumiendo:" lines from the coach persona lose their
   `**cifra**` emphasis.
4. There is no sanitization layer; the LLM could emit a raw `<script>`
   tag and the browser would execute it inside our origin.

ADR-0018 just adopted the Vercel template's wire format and AI Elements
patterns. The natural next step is to adopt Vercel's `streamdown` — a
drop-in replacement for `react-markdown` built for streaming LLM output,
already used by the AI Elements `Message` component we mirror.

The current `react-markdown`-less state is also a tech-debt signal:
every chat improvement has to invent formatting from scratch, and the
LLM prompt wastes tokens describing formatting that never reaches the
user.

## Decision

Add `streamdown` as the markdown renderer for any markdown arriving
from the backend. Wrap it in a single `<Markdown>` component so the
rest of the app does not depend on the library directly. Style every
element via a `components` map that uses our existing dark-first
design tokens (no new tokens, no `@tailwindcss/typography`).

### Library choice — `streamdown`

Evaluated against `react-markdown`, `marked + DOMPurify`, and
`streamdown`:

- `react-markdown` is the most popular, but it does not handle
  unterminated markdown (open `**`, half-written tables) — every
  streaming token re-runs a full parse and the cursor "snaps"
  jarringly.
- `marked + DOMPurify` is lighter but pushes AST management to us;
  we would reinvent what `remend` already does inside streamdown.
- `streamdown` is Vercel's stream-first markdown renderer, drop-in
  for `react-markdown`, built for the AI SDK's `useChat` hook.
  Includes `remend` for unterminated blocks, `rehype-harden` for
  sanitization, and matches the AI Elements `Message` styling we
  already model. Stack fit: Next.js 16 + React 19 + shadcn + Tailwind
  4 + AI SDK 6 — all first-class in the streamdown README.

### Scope — every surface that receives markdown

A single `<Markdown>` component lives at
`frontend/components/markdown/markdown.tsx`. Call-sites:

- `chat-message.tsx` — assistant text parts (the LLM prose).
- `chat-tool-chip.tsx` — when a tool returns a markdown string (the
  monthly report tool already does, per `report_markdown.py`).
- Any future screen that consumes backend markdown (e.g. a `/reports`
  view that wants the same formatting as the in-chat report) imports
  the same component.

User messages stay as plain `<p>` text — the user types into a
textarea, not a markdown field.

### Styling — components map with design tokens

`frontend/components/markdown/components.tsx` exports a map from
HTML element names to styled React components. Every color comes from
an existing CSS variable (no new tokens):

| Element    | Classes                                                                                 |
| ---------- | --------------------------------------------------------------------------------------- |
| `h1`       | `font-display text-xl font-semibold tracking-tight mt-3 mb-1.5 first:mt-0`             |
| `h2`       | `font-display text-lg font-semibold tracking-tight mt-3 mb-1`                           |
| `h3`       | `font-display text-base font-semibold mt-2.5 mb-1`                                      |
| `h4-h6`    | `font-display text-sm font-semibold mt-2 mb-0.5`                                        |
| `p`        | `text-sm leading-relaxed my-1.5 first:mt-0 last:mb-0`                                   |
| `strong`   | `font-semibold`                                                                         |
| `em`       | `italic`                                                                                |
| `ul`       | `my-1.5 ml-5 list-disc space-y-0.5`                                                     |
| `ol`       | `my-1.5 ml-5 list-decimal space-y-0.5`                                                  |
| `li`       | `pl-0.5`                                                                                |
| `a`        | `text-[color:var(--primary)] underline underline-offset-2 hover:opacity-80` (with `target="_blank" rel="noopener noreferrer"`) |
| `code`     | `rounded bg-[color:var(--muted)] px-1 py-0.5 text-[0.85em] font-mono`                   |
| `pre`      | `my-2 overflow-x-auto rounded-md border border-[color:var(--border)] bg-[color:var(--muted)]/40 p-3 text-xs` |
| `blockquote` | `my-1.5 border-l-2 border-[color:var(--primary)]/40 pl-3 text-[color:var(--muted-foreground)] italic` |
| `hr`       | `my-3 border-[color:var(--border)]`                                                     |
| `table`    | `my-2 w-full text-xs`                                                                   |
| `thead`    | `border-b border-[color:var(--border)]`                                                 |
| `th`       | `text-left font-semibold py-1.5 px-2`                                                   |
| `td`       | `py-1.5 px-2 align-top border-t border-[color:var(--border)]/50`                        |
| `del`      | `text-[color:var(--muted-foreground)] line-through`                                     |

The wrapper element is the `<Streamdown>` root, which gets the
`className` prop passthrough so call-sites can adjust density.

### Sanitization

`rehype-harden` is enabled by default in streamdown. We do **not**
add DOMPurify on top — one sanitizer, one source of truth, matches
streamdown's threat model. LLM output is "trusted-ish" (we own the
system prompt and the tool surface). If we ever accept
user-supplied markdown, revisit and add a layer.

### Streaming and cursor

Streamdown handles incomplete markdown (open `**`, unclosed `` ` ``,
half-written tables) via its internal `remend` pass. No debouncing
on our side. The AI SDK's `useChat` already throttles tokens.

The blinking cursor is preserved: `<Markdown>` renders the body,
then a sibling `<ChatBlinkingCursor />` follows in the same
`<ChatMessage>` wrapper. Same DOM position, same visual effect as
today.

### Memoization

`<Markdown>` is wrapped in `React.memo` keyed on the text content.
`<ChatMessage>` is already memoized at the message level
(`chat-message.tsx:72`), so the markdown component re-renders only
when the text actually changes — which is exactly when streamdown
needs to reparse.

## Files to change

| File                                                        | Change                                                                                       |
| ----------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `frontend/package.json`                                     | Add `streamdown` runtime dep.                                                                |
| `frontend/components/markdown/markdown.tsx` (new)           | Public API: `<Markdown>{text}</Markdown>`, memoized, className passthrough.                  |
| `frontend/components/markdown/components.tsx` (new)         | Element-to-className map per the table above; link element sets safe `rel`/`target`.        |
| `frontend/components/markdown/index.ts` (new)               | Re-export `<Markdown>`.                                                                     |
| `frontend/components/markdown/markdown.test.tsx` (new)      | ~10 tests (see Tests).                                                                       |
| `frontend/components/chat/chat-message.tsx`                 | Replace `<p className="whitespace-pre-wrap">{text}</p>` for assistant text parts with `<Markdown>{text}</Markdown>`. Keep cursor as a sibling. |
| `frontend/components/chat/chat-tool-chip.tsx`               | If the tool's text part is markdown, render via `<Markdown>`. (Verify what `part` carries; if it is structured data, no change needed.) |
| `frontend/app/globals.css`                                 | Add Tailwind 4 `@source` directive pointing to `node_modules/streamdown/dist/*.js` so the JIT scanner picks up the design-token utility classes that streamdown ships internally. |
| `docs/adr/0019-markdown-rendering-with-streamdown.md` (new) | Mirror of this spec, ADR-style.                                                              |
| `docs/adr/README.md`                                        | Add row for 0019.                                                                            |

## Tests

Ten fast vitest + @testing-library/react tests in
`markdown.test.tsx`, no network, no streamdown mocks (we test the
wrapper's contract, not the library's internals):

1. `renders bold` — `**x**` → `<strong>x</strong>`.
2. `renders italic` — `*x*` → `<em>x</em>`.
3. `renders gfm table` — pipe table renders `<table><thead><tr><th>`.
4. `renders unordered list` — `- a\n- b` → `<ul><li>a</li><li>b</li>`.
5. `renders ordered list` — `1. a\n2. b` → `<ol>` with two `<li>`.
6. `renders inline code` — `` `x` `` → `<code>` with token classes.
7. `renders code block` — ` ```js\nfoo\n``` ` → `<pre><code>`.
8. `opens links safely` — `[t](https://x)` → `<a target="_blank" rel="noopener noreferrer" href="https://x">`.
9. `strips dangerous url scheme` — `[t](javascript:alert(1))` → no `javascript:` href in DOM.
10. `strips script tags` — input string `<script>alert(1)</script>` → no `<script>` in rendered output, no `alert` call.
11. `handles unterminated markdown` — `**bold` (no closing) renders without throwing; output is a regression guard against future parser swaps.

Plus a render-only test in `chat-message.test.tsx` confirming that an
assistant message with a markdown text part no longer contains a raw
`<p class="whitespace-pre-wrap">` wrapper.

## Risks

- **`rehype-harden` is the only sanitizer.** Acceptable for
  LLM-authored markdown where we own the system prompt. If a future
  feature ingests untrusted user-supplied markdown, this layer must
  be re-evaluated (add DOMPurify, switch to a strict allowlist).
- **Streaming "snap" of partial formatting.** Streamdown may render
  `**bo` as plain text and then "bold the whole thing" once the
  closing `**` arrives. This is the library's intended UX and matches
  the Vercel AI Elements behavior we already mirror. The only fix
  would be debouncing on the AI SDK side, which is out of scope.
- **Bundle size.** Streamdown core is ~30 KB gzipped (per the Vercel
  template). The chat surface is already a client component that
  pulls in `@ai-sdk/react`, `axios`, `lucide-react`, etc. The
  addition is small relative to what is already shipped.
- **Tool chip may not need markdown.** If `chat-tool-chip.tsx` does
  not currently render raw markdown strings, the call-site change is
  a no-op. Verify in the implementation plan; do not force the change
  if the chip only shows structured fields.

## Consequences

- One new dep: `streamdown`.
- One new env var: none.
- One new ADR: 0019.
- Ten new tests in `markdown.test.tsx`; one update in
  `chat-message.test.tsx`. No test deletions.
- `<ChatMessage>` no longer treats assistant text as opaque
  whitespace-preserved plain text. The "no markdown in assistant
  text" assumption is gone everywhere.
- Future chat improvements (citations, expandable sections, copy-as-
  markdown button) have a structured DOM to attach to instead of a
  `<p>` blob.

## Out of scope (revisit later)

- Math (KaTeX), Mermaid diagrams, CJK — `streamdown` ships optional
  packages for these; we do not install them. Add if a real consumer
  appears.
- Shiki syntax highlighting — the core `pre` styling is enough for
  now. If we start pasting JSON/SQL/CSV into chat, revisit.
- Markdown toolbar (bold/italic buttons above the textarea) — the
  user prompt was "rendering", not authoring.
- Per-call-site variant props (e.g. `variant="chat" | "report"`) — the
  current call-sites are homogeneous. YAGNI until they diverge.
- DOMPurify second layer — see Risks.
