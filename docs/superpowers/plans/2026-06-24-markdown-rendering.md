# Markdown Rendering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render backend-supplied markdown in the Quaestor chat assistant with a curated design-system look and built-in sanitization.

**Architecture:** Single shared `<Markdown>` component at `frontend/components/markdown/markdown.tsx` that wraps Vercel's `streamdown` library. Every element is styled via a `components` map using existing dark-first design tokens (no new tokens). Sanitization is `rehype-harden` (built into streamdown). One call-site initially: assistant text parts in `chat-message.tsx`. The chat-tool chip is left as-is for now (tool output is a debug surface that benefits from raw text).

**Tech Stack:** Next.js 16.2.9, React 19.2.4, Tailwind 4, shadcn 4.11, AI SDK 6, Vitest 3, Testing Library, Biome 2, streamdown (new).

## Global Constraints

- Streamdown version: latest from `pnpm` (no version pin in this plan; installer picks current).
- pnpm is the only allowed package manager (ADR-0003).
- Design tokens come exclusively from `frontend/ui/styles/tokens.css` and `frontend/app/globals.css`. Do not introduce new CSS variables.
- Biome for format+lint (ADR-0007). Run `pnpm check` before commit.
- New component lives at `frontend/components/markdown/` (not under `chat/` — it's a general primitive, mirrors `data-table.tsx` etc.).
- ADR 0019 must mirror the spec, ADR-style. Update `docs/adr/README.md` index.
- Do not modify `frontend/ui/` (ADR-0002).
- Do not modify `chat-tool-chip.tsx` in this plan (YAGNI — see spec Out of scope).
- All commits use Conventional Commits and end the worktree clean (`biome check --write` then `vitest run` then commit).

---

## File Structure

| Path                                                        | Role                                                                      |
| ----------------------------------------------------------- | ------------------------------------------------------------------------- |
| `frontend/package.json`                                     | Add `streamdown` to `dependencies`.                                       |
| `frontend/pnpm-lock.yaml`                                   | Auto-updated by pnpm.                                                     |
| `frontend/app/globals.css`                                  | Add Tailwind 4 `@source` directive for `streamdown/dist/*.js`.            |
| `frontend/components/markdown/markdown.tsx`                 | Public `<Markdown>` component, memoized.                                  |
| `frontend/components/markdown/markdown-elements.tsx`        | Streamdown `components` map with design-token classNames.                 |
| `frontend/components/markdown/index.ts`                     | Re-export `<Markdown>`.                                                   |
| `frontend/components/markdown/markdown.test.tsx`            | Vitest + RTL tests for the wrapper contract.                              |
| `frontend/components/chat/chat-message.tsx`                 | Replace `<p>` text-part wrapper with `<Markdown>`. Keep cursor sibling.   |
| `frontend/components/chat/chat-message.test.tsx`            | Add regression test: assistant text containing markdown renders structure. |
| `docs/adr/0019-markdown-rendering-with-streamdown.md`       | New ADR.                                                                  |
| `docs/adr/README.md`                                        | Add ADR 0019 row.                                                         |

---

## Task 1: Install streamdown and wire the Tailwind 4 `@source` directive

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/app/globals.css`
- Auto: `frontend/pnpm-lock.yaml`

**Goal:** Add the runtime dependency and tell Tailwind 4's JIT scanner to pick up streamdown's internal utility classes.

- [ ] **Step 1: Add streamdown via pnpm**

Run from `frontend/`:

```bash
pnpm add streamdown
```

Expected: `package.json` `dependencies` gains `"streamdown": "^<latest>"` line. `pnpm-lock.yaml` updates. No peer-dep warnings.

- [ ] **Step 2: Verify install**

Run:

```bash
pnpm list streamdown
```

Expected: lists `streamdown <version>` with no `(not found)` errors.

- [ ] **Step 3: Add `@source` directive to globals.css**

Edit `frontend/app/globals.css`. Add the line directly under the existing `@import "tailwindcss";` at the very top of the file (line 1), so it sits before all other imports and inline `/* ... */` comments stay adjacent to their `@import` lines:

```css
@import "tailwindcss";
@source "../node_modules/streamdown/dist/*.js";
```

Do not touch any other line in `globals.css`.

- [ ] **Step 4: Sanity-run existing tests and linter**

Run from `frontend/`:

```bash
pnpm test
pnpm check
```

Expected: all existing tests pass. Biome reports no new issues. If streamdown's package shape causes a Biome warning (e.g. a generated file), record the warning in a one-line code comment above the offending section and re-run.

- [ ] **Step 5: Commit**

```bash
cd ..
git add frontend/package.json frontend/pnpm-lock.yaml frontend/app/globals.css
git -c user.name="Angelo Zambrano" -c user.email="angelo@quaestor.local" commit -m "feat(markdown): install streamdown + tailwind @source"
```

---

## Task 2: TDD — Markdown component scaffold (bold test)

**Files:**
- Create: `frontend/components/markdown/markdown.tsx`
- Create: `frontend/components/markdown/markdown.test.tsx`
- Create: `frontend/components/markdown/index.ts`

**Goal:** Establish the `<Markdown>` API surface with one test, then build the minimum to pass it. Future tasks extend the elements map and add more tests.

**Interfaces produced:**
- `Markdown` (named export): `function Markdown({ children, className }: { children: string; className?: string }) => JSX.Element`

- [ ] **Step 1: Write the failing test**

Create `frontend/components/markdown/markdown.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { Markdown } from "./markdown"

describe("Markdown", () => {
  it("renders bold text as a <strong> element", () => {
    render(<Markdown>{"**hola**"}</Markdown>)
    const strong = screen.getByText("hola")
    expect(strong.tagName).toBe("STRONG")
  })
})
```

- [ ] **Step 2: Run the test, see it fail**

Run from `frontend/`:

```bash
pnpm test markdown.test
```

Expected: FAIL with `Cannot find module './markdown'` or `Markdown is not exported`. Test runner reports the new file as broken (red).

- [ ] **Step 3: Create the Markdown component (minimal)**

Create `frontend/components/markdown/markdown.tsx`:

```tsx
"use client"

import { memo } from "react"
import { Streamdown } from "streamdown"

type Props = {
  children: string
  className?: string
}

function MarkdownImpl({ children, className }: Props) {
  return (
    <Streamdown className={className}>{children}</Streamdown>
  )
}

export const Markdown = memo(MarkdownImpl)
```

- [ ] **Step 4: Create the index re-export**

Create `frontend/components/markdown/index.ts`:

```ts
export { Markdown } from "./markdown"
```

- [ ] **Step 5: Re-run the test, see it pass**

Run from `frontend/`:

```bash
pnpm test markdown.test
```

Expected: PASS. The `**hola**` input renders a `<strong>hola</strong>` element.

- [ ] **Step 6: Lint and commit**

Run from `frontend/`:

```bash
pnpm check
```

Then from the repo root:

```bash
git add frontend/components/markdown/markdown.tsx \
        frontend/components/markdown/markdown.test.tsx \
        frontend/components/markdown/index.ts
git -c user.name="Angelo Zambrano" -c user.email="angelo@quaestor.local" commit -m "feat(markdown): <Markdown> wrapper with bold test (TDD red->green)"
```

---

## Task 3: Add the elements map with design-token classNames

**Files:**
- Create: `frontend/components/markdown/markdown-elements.tsx`
- Modify: `frontend/components/markdown/markdown.tsx`

**Goal:** Replace the default Streamdown element rendering with the curated className table from the spec. No new tests; the bold test from Task 2 still passes, and we extend coverage in Task 4.

- [ ] **Step 1: Create the elements map file**

Create `frontend/components/markdown/markdown-elements.tsx`:

```tsx
import type { StreamdownProps } from "streamdown"

export const markdownComponents: NonNullable<StreamdownProps["components"]> = {
  h1: ({ children, ...rest }) => (
    <h1
      {...rest}
      className="font-display text-xl font-semibold tracking-tight mt-3 mb-1.5 first:mt-0"
    >
      {children}
    </h1>
  ),
  h2: ({ children, ...rest }) => (
    <h2
      {...rest}
      className="font-display text-lg font-semibold tracking-tight mt-3 mb-1"
    >
      {children}
    </h2>
  ),
  h3: ({ children, ...rest }) => (
    <h3 {...rest} className="font-display text-base font-semibold mt-2.5 mb-1">
      {children}
    </h3>
  ),
  h4: ({ children, ...rest }) => (
    <h4 {...rest} className="font-display text-sm font-semibold mt-2 mb-0.5">
      {children}
    </h4>
  ),
  h5: ({ children, ...rest }) => (
    <h5 {...rest} className="font-display text-sm font-semibold mt-2 mb-0.5">
      {children}
    </h5>
  ),
  h6: ({ children, ...rest }) => (
    <h6 {...rest} className="font-display text-sm font-semibold mt-2 mb-0.5">
      {children}
    </h6>
  ),
  p: ({ children, ...rest }) => (
    <p {...rest} className="text-sm leading-relaxed my-1.5 first:mt-0 last:mb-0">
      {children}
    </p>
  ),
  strong: ({ children, ...rest }) => (
    <strong {...rest} className="font-semibold">
      {children}
    </strong>
  ),
  em: ({ children, ...rest }) => (
    <em {...rest} className="italic">
      {children}
    </em>
  ),
  ul: ({ children, ...rest }) => (
    <ul {...rest} className="my-1.5 ml-5 list-disc space-y-0.5">
      {children}
    </ul>
  ),
  ol: ({ children, ...rest }) => (
    <ol {...rest} className="my-1.5 ml-5 list-decimal space-y-0.5">
      {children}
    </ol>
  ),
  li: ({ children, ...rest }) => (
    <li {...rest} className="pl-0.5">
      {children}
    </li>
  ),
  a: ({ children, href, ...rest }) => (
    <a
      {...rest}
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-[color:var(--primary)] underline underline-offset-2 hover:opacity-80"
    >
      {children}
    </a>
  ),
  code: ({ children, ...rest }) => (
    <code
      {...rest}
      className="rounded bg-[color:var(--muted)] px-1 py-0.5 text-[0.85em] font-mono"
    >
      {children}
    </code>
  ),
  pre: ({ children, ...rest }) => (
    <pre
      {...rest}
      className="my-2 overflow-x-auto rounded-md border border-[color:var(--border)] bg-[color:var(--muted)]/40 p-3 text-xs"
    >
      {children}
    </pre>
  ),
  blockquote: ({ children, ...rest }) => (
    <blockquote
      {...rest}
      className="my-1.5 border-l-2 border-[color:var(--primary)]/40 pl-3 text-[color:var(--muted-foreground)] italic"
    >
      {children}
    </blockquote>
  ),
  hr: ({ ...rest }) => (
    <hr {...rest} className="my-3 border-[color:var(--border)]" />
  ),
  table: ({ children, ...rest }) => (
    <table {...rest} className="my-2 w-full text-xs">
      {children}
    </table>
  ),
  thead: ({ children, ...rest }) => (
    <thead {...rest} className="border-b border-[color:var(--border)]">
      {children}
    </thead>
  ),
  th: ({ children, ...rest }) => (
    <th {...rest} className="text-left font-semibold py-1.5 px-2">
      {children}
    </th>
  ),
  td: ({ children, ...rest }) => (
    <td {...rest} className="py-1.5 px-2 align-top border-t border-[color:var(--border)]/50">
      {children}
    </td>
  ),
  del: ({ children, ...rest }) => (
    <del {...rest} className="text-[color:var(--muted-foreground)] line-through">
      {children}
    </del>
  ),
}
```

If the TypeScript compiler complains about `StreamdownProps` not exporting `components`, inspect the installed types:

```bash
pnpm exec tsc --noEmit frontend/components/markdown/markdown-elements.tsx
```

and adjust the import to the actual exported type name. Common variants: `Components`, `MarkdownComponents`. Pick whichever compiles.

- [ ] **Step 2: Wire the elements map into the Markdown component**

Edit `frontend/components/markdown/markdown.tsx`. Replace its entire body with:

```tsx
"use client"

import { memo } from "react"
import { Streamdown } from "streamdown"
import { markdownComponents } from "./markdown-elements"

type Props = {
  children: string
  className?: string
}

function MarkdownImpl({ children, className }: Props) {
  return (
    <Streamdown className={className} components={markdownComponents}>
      {children}
    </Streamdown>
  )
}

export const Markdown = memo(MarkdownImpl)
```

- [ ] **Step 3: Run the bold test, still green**

Run from `frontend/`:

```bash
pnpm test markdown.test
```

Expected: PASS. The `<strong>` from Task 2 still renders, now with `font-semibold` className applied.

- [ ] **Step 4: Lint and commit**

Run from `frontend/`:

```bash
pnpm check
```

Then from the repo root:

```bash
git add frontend/components/markdown/markdown-elements.tsx \
        frontend/components/markdown/markdown.tsx
git -c user.name="Angelo Zambrano" -c user.email="angelo@quaestor.local" commit -m "feat(markdown): design-token elements map"
```

---

## Task 4: Extend test coverage (tables, lists, code, links, sanitization, unterminated)

**Files:**
- Modify: `frontend/components/markdown/markdown.test.tsx`

**Goal:** Lock in the wrapper's contract across all element types we style + verify sanitization. ~9 more tests, all asserting DOM shape, no streamdown internals.

- [ ] **Step 1: Replace markdown.test.tsx with the full suite**

Overwrite `frontend/components/markdown/markdown.test.tsx` with:

```tsx
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { Markdown } from "./markdown"

describe("Markdown", () => {
  it("renders bold text as a <strong> element", () => {
    render(<Markdown>{"**hola**"}</Markdown>)
    const strong = screen.getByText("hola")
    expect(strong.tagName).toBe("STRONG")
  })

  it("renders italic text as an <em> element", () => {
    render(<Markdown>{"*hola*"}</Markdown>)
    const em = screen.getByText("hola")
    expect(em.tagName).toBe("EM")
  })

  it("renders a GFM table with thead and th cells", () => {
    const md = `| A | B |
| --- | --- |
| 1 | 2 |`
    const { container } = render(<Markdown>{md}</Markdown>)
    expect(container.querySelector("table")).toBeInTheDocument()
    expect(container.querySelector("thead")).toBeInTheDocument()
    expect(container.querySelectorAll("th").length).toBe(2)
    expect(container.querySelectorAll("tbody td").length).toBe(2)
  })

  it("renders an unordered list", () => {
    const { container } = render(<Markdown>{"- a\n- b"}</Markdown>)
    expect(container.querySelector("ul")).toBeInTheDocument()
    expect(container.querySelectorAll("li").length).toBe(2)
  })

  it("renders an ordered list", () => {
    const { container } = render(<Markdown>{"1. a\n2. b"}</Markdown>)
    expect(container.querySelector("ol")).toBeInTheDocument()
    expect(container.querySelectorAll("li").length).toBe(2)
  })

  it("renders inline code in a <code> element", () => {
    const { container } = render(<Markdown>{"usa `npm test` ahora"}</Markdown>)
    const code = container.querySelector("code")
    expect(code).toBeInTheDocument()
    expect(code?.textContent).toBe("npm test")
  })

  it("renders fenced code blocks in a <pre><code> structure", () => {
    const md = "```js\nconst x = 1\n```"
    const { container } = render(<Markdown>{md}</Markdown>)
    expect(container.querySelector("pre")).toBeInTheDocument()
    expect(container.querySelector("pre code")).toBeInTheDocument()
  })

  it("opens links with safe rel and target", () => {
    const { container } = render(<Markdown>{"[t](https://example.com)"}</Markdown>)
    const a = container.querySelector("a")
    expect(a).toBeInTheDocument()
    expect(a?.getAttribute("target")).toBe("_blank")
    expect(a?.getAttribute("rel")).toBe("noopener noreferrer")
    expect(a?.getAttribute("href")).toBe("https://example.com")
  })

  it("strips dangerous url schemes (javascript:)", () => {
    const { container } = render(
      <Markdown>{"[t](javascript:alert(1))"}</Markdown>,
    )
    // rehype-harden must drop the href or replace it with a safe value.
    const a = container.querySelector("a")
    if (a) {
      expect(a.getAttribute("href") ?? "").not.toMatch(/^javascript:/i)
    } else {
      // Equally acceptable: the entire link is stripped.
      expect(a).toBeNull()
    }
  })

  it("strips raw <script> tags from input", () => {
    const { container } = render(
      <Markdown>{"<script>alert(1)</script>"}</Markdown>,
    )
    expect(container.querySelector("script")).toBeNull()
  })

  it("handles unterminated markdown without throwing", () => {
    expect(() => render(<Markdown>{"**bold sin cerrar"}</Markdown>)).not.toThrow()
  })

  it("passes className through to the root element", () => {
    const { container } = render(
      <Markdown className="my-custom-class">{"hola"}</Markdown>,
    )
    expect(container.firstChild).not.toBeNull()
    const root = container.firstChild as HTMLElement
    expect(root.className).toContain("my-custom-class")
  })
})
```

- [ ] **Step 2: Run the full test file**

Run from `frontend/`:

```bash
pnpm test markdown.test
```

Expected: PASS for all 12 tests. If a streamdown-version-specific behavior changes (e.g. they start stripping `javascript:` hrefs to `about:blank` instead of dropping the anchor), update the assertion to match the actual safe value — the contract is "no `javascript:` href", not "no `<a>` element".

- [ ] **Step 3: Lint and commit**

Run from `frontend/`:

```bash
pnpm check
```

Then from the repo root:

```bash
git add frontend/components/markdown/markdown.test.tsx
git -c user.name="Angelo Zambrano" -c user.email="angelo@quaestor.local" commit -m "test(markdown): full coverage of elements + sanitization"
```

---

## Task 5: Wire `<Markdown>` into `chat-message.tsx`

**Files:**
- Modify: `frontend/components/chat/chat-message.tsx`

**Goal:** Replace the plain-text `<p className="whitespace-pre-wrap">` for assistant text parts with `<Markdown>`. Keep the blinking cursor as a sibling. User messages and tool parts are untouched.

- [ ] **Step 1: Add the import**

At the top of `frontend/components/chat/chat-message.tsx`, after the existing imports (line 7), add:

```tsx
import { Markdown } from "@/components/markdown"
```

If `@/components/markdown` is not resolvable (check `frontend/tsconfig.json` for the `@` alias path — it points at `frontend/`), fall back to a relative import:

```tsx
import { Markdown } from "../markdown"
```

Use whichever the project conventions dictate. The current `chat-message.tsx` already uses relative imports for siblings, so prefer the relative form.

- [ ] **Step 2: Replace the assistant text-part renderer**

In `frontend/components/chat/chat-message.tsx`, find the text-part branch (currently lines 46-54):

```tsx
if (isTextPart(part)) {
  const showTailCursor = showCursor && idx === lastTextIndex && isUser === false
  return (
    // biome-ignore lint/suspicious/noArrayIndexKey: parts don't reorder within a message
    <p key={`${message.id}-t-${idx}`} className="whitespace-pre-wrap">
      {part.text}
      {showTailCursor && <ChatBlinkingCursor />}
    </p>
  )
}
```

Replace it with:

```tsx
if (isTextPart(part)) {
  const showTailCursor = showCursor && idx === lastTextIndex && isUser === false
  // User text is typed input, not markdown. Only assistant text flows through
  // the markdown renderer (per spec 2026-06-24).
  if (isUser) {
    return (
      // biome-ignore lint/suspicious/noArrayIndexKey: parts don't reorder within a message
      <p key={`${message.id}-t-${idx}`} className="whitespace-pre-wrap">
        {part.text}
      </p>
    )
  }
  return (
    // biome-ignore lint/suspicious/noArrayIndexKey: parts don't reorder within a message
    <div key={`${message.id}-t-${idx}`}>
      <Markdown>{part.text}</Markdown>
      {showTailCursor && <ChatBlinkingCursor />}
    </div>
  )
}
```

- [ ] **Step 3: Run chat-message tests**

Run from `frontend/`:

```bash
pnpm test chat-message.test
```

Expected: 7 existing tests PASS. The "renders an assistant message left-aligned, plain text, no bubble background" test still works because `respuesta` contains no markdown and renders as `<p>respuesta</p>` inside the `<div>`.

- [ ] **Step 4: Commit**

From the repo root:

```bash
git add frontend/components/chat/chat-message.tsx
git -c user.name="Angelo Zambrano" -c user.email="angelo@quaestor.local" commit -m "feat(chat): render assistant text via <Markdown>"
```

---

## Task 6: Add regression test for markdown rendering in ChatMessage

**Files:**
- Modify: `frontend/components/chat/chat-message.test.tsx`

**Goal:** Lock in the migration: an assistant message containing markdown should render structured HTML, not the old `<p class="whitespace-pre-wrap">`.

- [ ] **Step 1: Add the new test**

In `frontend/components/chat/chat-message.test.tsx`, after the existing `"renders both text and tool parts in order"` test (line 92), add:

```tsx
it("renders assistant text containing markdown as structured HTML", () => {
  const md = "**importante**: saldo $1.250.000"
  const { container } = render(
    <ChatMessage message={assistantMessage(md)} showCursor={false} />,
  )
  const strong = container.querySelector("strong")
  expect(strong).toBeInTheDocument()
  expect(strong?.textContent).toBe("importante")
  // The old whitespace-pre-wrap <p> wrapper must be gone for assistant messages.
  const legacyP = container.querySelector("p.whitespace-pre-wrap")
  expect(legacyP).toBeNull()
})
```

- [ ] **Step 2: Run chat-message tests**

Run from `frontend/`:

```bash
pnpm test chat-message.test
```

Expected: 8 tests PASS (7 existing + 1 new).

- [ ] **Step 3: Lint and commit**

Run from `frontend/`:

```bash
pnpm check
```

Then from the repo root:

```bash
git add frontend/components/chat/chat-message.test.tsx
git -c user.name="Angelo Zambrano" -c user.email="angelo@quaestor.local" commit -m "test(chat): regression guard for assistant markdown rendering"
```

---

## Task 7: Write ADR 0019 and update the ADR index

**Files:**
- Create: `docs/adr/0019-markdown-rendering-with-streamdown.md`
- Modify: `docs/adr/README.md`

**Goal:** Record the technical decision per the project rules (CLAUDE.md — any architecturally-significant change must be an ADR).

- [ ] **Step 1: Create the ADR file**

Create `docs/adr/0019-markdown-rendering-with-streamdown.md` with the following content (mirror of the spec, ADR-style):

````markdown
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
````

- [ ] **Step 2: Add a row to the ADR index**

Read `docs/adr/README.md` to find the table format. Add a row
at the end following the same pattern as 0018. The row shape is
the title and a one-line summary. The summary for 0019 is:

> Adopt streamdown as the markdown renderer for backend-supplied markdown in the chat, behind a shared `<Markdown>` component styled with existing design tokens.

- [ ] **Step 3: Lint and commit**

Run from the repo root:

```bash
git add docs/adr/0019-markdown-rendering-with-streamdown.md \
        docs/adr/README.md
git -c user.name="Angelo Zambrano" -c user.email="angelo@quaestor.local" commit -m "docs(adr): 0019 markdown rendering with streamdown"
```

---

## Task 8: Final verification

**Files:** none. Run all gates from `frontend/`.

- [ ] **Step 1: Run the full test suite**

Run from `frontend/`:

```bash
pnpm test
```

Expected: all tests PASS, including the 12 new markdown tests, the 8 chat-message tests, and every pre-existing test in the project. If any test fails, fix the regression before continuing.

- [ ] **Step 2: Run the full linter**

Run from `frontend/`:

```bash
pnpm check
```

Expected: Biome reports no issues. If it does, run `pnpm check:ci` to confirm the same set of issues (not new ones), then fix or annotate as appropriate.

- [ ] **Step 3: Run the production build**

Run from `frontend/`:

```bash
pnpm build
```

Expected: the build succeeds. Tailwind 4's JIT compiles the streamdown `@source`-discovered classes without error. If a class is reported missing, add the literal utility to the elements map (or to a `safelist` if you have one — you don't, so the fix is in the elements map).

- [ ] **Step 4: Sanity-check the dev server**

Run from the repo root:

```bash
cd frontend && pnpm dev
```

Open the app, send a chat message that triggers a markdown response (e.g. "¿Cuánto puedo gastar este mes?"). Verify in the browser:

- Bold, italics, and lists from the LLM render with the brand fonts and the dark theme's primary color.
- A GFM table from `report_markdown.py` (ask for the monthly report) renders as a real `<table>` with thead/tbody.
- The blinking cursor appears at the end of the trailing assistant message while streaming.
- No raw `**` characters are visible in the chat.

If any check fails, the issue is in `frontend/components/markdown/markdown-elements.tsx` or `frontend/components/chat/chat-message.tsx`. Fix and re-run `pnpm test` and `pnpm check` before marking the task complete.

- [ ] **Step 5: Final commit (only if Step 4 revealed and fixed issues)**

If you changed any file in Steps 1-4, commit from the repo root:

```bash
git add -A
git -c user.name="Angelo Zambrano" -c user.email="angelo@quaestor.local" commit -m "chore(markdown): post-verification fixes"
```

If nothing changed, there is nothing to commit and the plan is complete.
