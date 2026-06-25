# 0019 — Markdown rendering with streamdown

## Status

Accepted, 2026-06-24.

## Context

The Quaestor chat assistant emits markdown in two ways:

- LLM prose, per the coach persona
  (`backend/src/quaestor/chat/prompts.py:14-64`), using `**bold**`,
  bullet lists, and `## ` headings.
- Structured monthly reports
  (`backend/src/quaestor/domain/report_markdown.py:27-138`), using
  H1/H2, GFM pipe tables, and bullet lists.

The frontend today renders assistant text as raw text inside
`<p className="whitespace-pre-wrap">`
(`frontend/components/chat/chat-message.tsx:50`). `**bold**` shows
up as literal asterisks; pipe tables arrive as `| ... |` with no
formatting. There is no sanitization layer — a hostile LLM output
could deliver a raw `<script>` tag and the browser would execute
it inside our origin.

ADR-0018 just aligned the chat wire format with the Vercel
template. The natural next step is to adopt Vercel's `streamdown`
library, the same one used by the AI Elements `Message` component
the codebase already mirrors.

## Decision

Adopt `streamdown` as the markdown renderer for any markdown
arriving from the backend. Wrap it in a single `<Markdown>`
component at `frontend/components/markdown/markdown.tsx` so the
rest of the app does not depend on the library directly. Style
every element via a `components` map that uses the project's
existing dark-first design tokens — no new tokens, no
`@tailwindcss/typography`.

### Library: streamdown

Evaluated against `react-markdown`, `marked + DOMPurify`, and
`streamdown`:

- `react-markdown` is the most popular but does not handle
  unterminated markdown — every streaming token re-parses and the
  cursor "snaps" jarringly.
- `marked + DOMPurify` is lighter but pushes AST management to
  us; we would reinvent what `remend` already does.
- `streamdown` is Vercel's stream-first markdown renderer,
  drop-in for `react-markdown`, built for the AI SDK's `useChat`.
  Includes `remend` (unterminated blocks), `rehype-harden`
  (sanitization), and matches the AI Elements `Message` styling
  we already model. Stack fit: Next.js 16 + React 19 + shadcn +
  Tailwind 4 + AI SDK 6 — all first-class in streamdown's
  README.

### Scope

`<Markdown>` is a general primitive, not a chat-only component.
It lives at `frontend/components/markdown/`. Call-sites:

- `chat-message.tsx` — assistant text parts only. User messages
  stay as plain `<p>` text (typed input, not markdown).
- Any future surface that consumes backend markdown.

`chat-tool-chip.tsx` is deliberately left as-is in this change.
The tool chip is a debug surface that shows raw input/output as
JSON; the value there is fidelity, not formatting.

### Styling

A `components` map in
`frontend/components/markdown/markdown-elements.tsx` maps every
HTML element to a styled React component using Tailwind classes
backed by existing CSS variables (`--foreground`, `--muted`,
`--primary`, `--border`, `--muted-foreground`). No new tokens.
Headings use `font-display` (the brand heading font). Links
get `target="_blank" rel="noopener noreferrer"` defensively.

### Sanitization

`rehype-harden` is on by default in streamdown. We do not add
DOMPurify on top — one sanitizer, one source of truth, matches
streamdown's threat model. LLM output is "trusted-ish" (we own
the system prompt and the tool surface). If a future feature
ingests untrusted user-supplied markdown, revisit and add a
layer.

### Streaming and cursor

Streamdown handles incomplete markdown (open `**`, unclosed
backticks, half-written tables) via its internal `remend` pass.
No debouncing on our side. The AI SDK's `useChat` already
throttles tokens.

The blinking cursor is preserved by rendering `<Markdown>` then
a sibling `<ChatBlinkingCursor />` in the same wrapper — same
DOM position, same visual effect.

### Tailwind 4 JIT scanning

A `@source` directive pointing to
`node_modules/streamdown/dist/*.js` is added to
`frontend/app/globals.css` so Tailwind 4's JIT scanner picks up
the design-token utility classes streamdown uses internally.

## Consequences

- One new runtime dep: `streamdown`.
- One new component module: `frontend/components/markdown/`.
- New file under `docs/superpowers/specs/`:
  `2026-06-24-markdown-rendering-design.md`.
- ~10 new vitest tests in
  `frontend/components/markdown/markdown.test.tsx`.
- 1 new regression test in
  `frontend/components/chat/chat-message.test.tsx`.
- `<ChatMessage>` no longer treats assistant text as opaque
  whitespace-preserved plain text. Future chat improvements
  (citations, expandable sections, copy-as-markdown) have
  structured DOM to attach to.

## Out of scope (revisit later)

- Math (KaTeX), Mermaid diagrams, CJK — `streamdown` ships
  optional packages for these; we do not install them. Add if
  a real consumer appears.
- Shiki syntax highlighting — core `pre` styling is enough
  for now. Revisit if JSON/SQL/CSV start appearing in chat.
- Markdown toolbar in the input — the user prompt was
  "rendering", not authoring.
- Per-call-site variant props — current call-sites are
  homogeneous; YAGNI until they diverge.
- DOMPurify second layer — see Sanitization.

## Rejected alternatives

- **`@tailwindcss/typography` (prose)**: battle-tested defaults,
  ~5 lines of config, but `prose-*` classes fight with our
  custom design tokens. Mixing them leads to override wars.
- **CSS-only via `@source` + descendant selectors**: zero JS
  config but creates implicit coupling to streamdown's element
  ordering. Harder to grep "where does h1 look like this?".
- **`react-markdown` + custom streaming handling**: requires
  us to write the parser-incomplete logic that `remend` ships
  with streamdown.
- **Sanitizing user-supplied HTML with DOMPurify directly**:
  not needed today; LLM output is trusted-ish. Add when a real
  untrusted-markdown consumer appears.