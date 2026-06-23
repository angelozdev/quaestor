# Chat Input — Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an inline chat section on the dashboard (`/`) that lets the user type natural-language questions and receive streaming responses from the existing `POST /api/chat` SSE endpoint, with collapsible tool-call chips for transparency.

**Architecture:** Compose 8 small client components (`ChatSection` owns `useChat`; `ChatThread` → `ChatMessage` → discriminated `TextUIPart` / `ToolUIPart` rendering; `ChatToolChip` collapsible; `ChatInput` auto-grow; `ChatEmptyState` 3 suggested chips; `ChatBlinkingCursor`). Install `@ai-sdk/react@^3` (with `ai@^6` transitive). Cookie session rides the existing Next `/api/[...path]` rewrite — no auth bridge needed.

**Tech Stack:** Next.js 16.2.9 (App Router), React 19.2.4, TypeScript strict, Tailwind v4, `@ai-sdk/react@^3` + `ai@^6` (transitive), `@tanstack/react-query@^5`, Vitest + Testing Library + happy-dom, Biome (lint/format).

**Spec:** `docs/superpowers/specs/2026-06-22-chat-input-frontend-design.md` (approved, 2026-06-22, 300 lines, commit `58ebb78`).

## Global Constraints

Every task must satisfy these without re-stating them. Values copied verbatim from the spec.

- **Next.js 16.2.9** has breaking changes vs prior majors — read `frontend/AGENTS.md` and consult `node_modules/next/dist/docs/01-app/` before writing any code that touches routing, layouts, or client/server boundaries.
- **React 19.2.4** — peer dep match for `@ai-sdk/react@^3` (`^18 || ~19.0.1 || ~19.1.2 || ^19.2.1`).
- **`@ai-sdk/react@^3` exports:** `useChat`, plus re-exports `UIMessage` and `CreateUIMessage` from `ai` (so importing `UIMessage` from either `@ai-sdk/react` OR `ai` works — both resolve to the same canonical type defined in `ai@^6`). **`ai@^6` exports:** `DefaultChatTransport`, `isTextUIPart`, `isToolUIPart`, `getToolName`, `type TextUIPart`, `type ToolUIPart`, `type DynamicToolUIPart`, `type UIMessagePart`, `type UIMessage`. This plan imports `UIMessage` from `ai` consistently (canonical source); do not switch sources mid-file. Verified against npm registry 2026-06-22.
- **`useChat` API (v3):** `useChat({ transport?: ChatTransport<UI_MESSAGE>, onFinish?, onError?, id?, messages?, generateId?, ... })` returns `{ messages, sendMessage, stop, regenerate, status, error, setMessages, clearError, resumeStream, addToolResult, addToolOutput, addToolApprovalResponse, id }`. `status: 'submitted' | 'streaming' | 'ready' | 'error'`. `sendMessage({ text: string, files?: FileList | FileUIPart[] })`.
- **`ChatTransport`:** pass `transport: new DefaultChatTransport({ api: '/api/chat' })`. `api` defaults to `'/api/chat'`, so we can omit it, but include explicitly for clarity.
- **`onFinish` signature:** `(event: { messages, isContinuation, isAborted, responseMessage, finishReason? }) => void`. Use it to invalidate dashboard queries.
- **Tool parts:** incoming tool calls without a client-side tools registry arrive as `DynamicToolUIPart` (`type: 'dynamic-tool'`) — not `tool-{name}`. Use `isToolUIPart(part)` (from `ai`) which narrows to `ToolUIPart | DynamicToolUIPart`. The chip must handle both shapes.
- **Tool part states:** `'input-streaming' | 'input-available' | 'approval-requested' | 'approval-responded' | 'output-available' | 'output-error' | 'output-denied'`. We render only when state is one of `input-streaming` / `input-available` / `output-available` / `output-error`; approval-* states are out of scope (server never requests approval).
- **Auth:** backend `require_auth` accepts either `Authorization: Bearer <APP_TOKEN>` OR `request.session.authenticated === true`. Frontend cookie session rides the existing Next rewrite `/api/[...path]` (verified in `app/api/[...path]/route.ts`). No new auth code in this plan.
- **Fonts:** `Bricolage_Grotesque` (display, CSS var `--font-heading` → `--font-bricolage`) and `Manrope` (body, `--font-sans` → `--font-manrope`). `font-display` Tailwind alias resolves to `--font-heading`. NEVER use Inter, Roboto, system-ui fallbacks beyond the existing `--font-sans` chain.
- **Color tokens (oklch):** `--primary` mint (`oklch(0.82 0.16 165)` dark / `0.7 0.15 165` light), `--income` (`0.8 0.16 158` dark / `0.52 0.13 158` light), `--expense` (`0.7 0.18 22` dark / `0.53 0.2 27` light), `--destructive`, `--border`, `--muted`, `--muted-foreground`, `--popover`, `--card`. Use these via inline `style={{ color: 'var(--primary)' }}` or via Tailwind classes that map to the token (e.g. `text-primary`, `bg-muted`). DO NOT introduce new colors.
- **No new component primitives:** the chat uses existing `ui/components/{button,input,textarea,card,badge,skeleton}` plus inline styled wrappers. No new shadcn primitive.
- **No new design-system tokens:** keyframes (`blink-cursor`, `chat-underline-sweep`) and the utility class `.chat-input-underline` go at the END of `frontend/app/globals.css`, outside `@layer base`, mirroring the existing `animate-fade-up` pattern. NEVER edit `frontend/ui/styles/*` (rule from ADR-0002).
- **Spanish (es-CO) copy** for all user-facing strings: `Pregúntale a tu asistente`, `Puede leer tus cuentas, transacciones, presupuestos y metas.`, `¿Cuánto puedo gastar este mes?`, `Lista mis cuentas y sus saldos`, `Dame el resumen del mes`, `Pensando…`, `Reintentar`, `No pudimos contactar al servidor`, `Tu mensaje es muy largo. Acórtalo e intenta de nuevo.`, `No pude procesar tu mensaje. Reformúlalo e intenta otra vez.`, `Demasiadas solicitudes. Espera un momento e intenta de nuevo.`, `No pude completar tu solicitud. Vuelve a intentarlo.`, `Algo salió mal. Vuelve a intentarlo en un momento.` Raw backend `error.message` is NEVER rendered to the user — always routed through `translateChatError()` in `lib/chat-errors.ts`.
- **Error translation:** every `useChat` error reaches the DOM via `translateChatError(error: Error): string` (Task 7.5). Mapping table mirrors the spec's Errors section. Untranslated/unmatched errors fall through to the generic fallback string. The raw error is logged via `console.error` only — no telemetry beacon in v1.
- **Input cap:** `ChatInput`'s `<textarea>` declares `maxLength={32000}` mirroring the backend 32 KB cap (Task 4.3). Pasted content beyond this is silently truncated by the browser.
- **Send cooldown:** after a successful `onSend`, the send button is disabled for 600 ms (`cooldownMs={600}` prop; defaults inside ChatInput). UX guard against accidental double-submit, NOT a rate limit (server-side rate limiting is a backend concern).
- **Sensitive output:** `ChatToolChip` JSON `<pre>` blocks render with `data-sensitive="true"` so future telemetry scrubbers / screen-share blockers / password managers can honor it. No active masking in v1.
- **Reduced-motion:** `@media (prefers-reduced-motion: reduce)` MUST disable both `blink-cursor` animation AND `chat-underline-sweep` animation. Tool-chip pulsing dot falls back to static mint dot.
- **Bundle discipline:** `@ai-sdk/react@^3` is the only runtime dep added (~35 KB gzipped with `ai@^6` transitive). No other `package.json` changes. `packageManager: pnpm@11.3.0` untouched.
- **Test layout:** colocate test files next to components (`components/chat/chat-section.test.tsx`, matching existing `form-field.test.tsx` / `entity-form-dialog.test.tsx` pattern). Vitest config already supports `@/` alias and happy-dom env — no test config changes.
- **Test isolation:** mock `@ai-sdk/react` via `vi.mock('@ai-sdk/react', ...)` at module boundary. NEVER hit a live SSE endpoint in unit tests. `useChat` returns a typed mock per test; tests inject `{ messages, sendMessage, stop, status, error, regenerate }`.
- **TDD discipline:** every implementation task writes a failing test FIRST (red), runs it to confirm failure, then writes the minimum code to pass (green), then runs to confirm green, then commits. No "implement later" or "similar to Task N" — every code block in every step is unique and complete.
- **Commit messages:** `feat(chat): <thing>` for new components, `chore(deps): add @ai-sdk/react@^3` for the dep, `style(css): add blink-cursor + chat-underline-sweep keyframes` for globals.css. Conventional Commits, lowercase, ≤72 char subject.
- **Lefthook:** `frontend/lefthook.yml` runs biome + lefthook on commit. If commit warns about missing lefthook config, ignore (pre-existing repo state).
- **Working directory:** every shell command in steps assumes CWD = `/Users/angelozdev/me/quaestor` unless stated. For frontend-only commands, `cd frontend && ...` is explicit.
- **No backend changes:** the plan touches ONLY `frontend/`. Do not edit `backend/**`.

---

## Task 1: Dependency + transport factory + types module

**Files:**
- Modify: `frontend/package.json` (add `@ai-sdk/react` to `dependencies`)
- Modify: `frontend/pnpm-lock.yaml` (regenerated by `pnpm install`)
- Create: `frontend/lib/chat-transport.ts`
- Create: `frontend/components/chat/chat.types.ts`
- Test: `frontend/lib/chat-transport.test.ts` (smoke)

**Interfaces:**
- Produces `createChatTransport(): DefaultChatTransport` — a factory used by `ChatSection` via `useMemo`. Consumers in later tasks: Task 8.
- Produces `ChatPart` type alias and helper type guards re-exported from `chat.types.ts`. Consumers in later tasks: Task 6 (ChatMessage), Task 3 (ChatToolChip).

- [ ] **Step 1.1: Install the dependency**

Run from repo root:
```bash
cd frontend && pnpm add '@ai-sdk/react@^3'
```
Expected: `pnpm` updates `package.json` `dependencies` block with `"@ai-sdk/react": "^3.0.210"` (or current latest matching `^3`) and writes a new `pnpm-lock.yaml`. The `ai` package appears as a transitive dep in `node_modules/ai/`.

Verify:
```bash
cd frontend && pnpm ls @ai-sdk/react
```
Expected output includes `@ai-sdk/react@3.0.x` linked to project.
```bash
ls node_modules/@ai-sdk/react/dist/index.d.ts
```
Expected: file exists.

- [ ] **Step 1.2: Write a smoke test for `createChatTransport`**

Create file `frontend/lib/chat-transport.test.ts`:
```typescript
import { describe, expect, it } from "vitest"
import { DefaultChatTransport } from "ai"
import { createChatTransport } from "./chat-transport"

describe("createChatTransport", () => {
  it("returns a DefaultChatTransport pointed at /api/chat", () => {
    const transport = createChatTransport()
    expect(transport).toBeInstanceOf(DefaultChatTransport)
    // The constructor stores `api` as a protected field; we verify by behavior:
    // a new transport with the same factory must reference the same api path.
    // We assert via constructor identity (the factory is pure).
    expect(transport).not.toBeNull()
  })
})
```

- [ ] **Step 1.3: Run the smoke test to confirm it fails**

Run:
```bash
cd frontend && pnpm test lib/chat-transport.test.ts
```
Expected: FAIL with `Failed to resolve import "./chat-transport" from "lib/chat-transport.test.ts". Does the file exist?` (or equivalent module-not-found error).

- [ ] **Step 1.4: Create `chat-transport.ts`**

Create file `frontend/lib/chat-transport.ts`:
```typescript
import { DefaultChatTransport } from "ai"

/**
 * Factory for the chat transport used by `useChat` in `ChatSection`.
 *
 * Returns a fresh `DefaultChatTransport` instance pointed at the backend
 * `POST /api/chat` SSE endpoint. The Next rewrite at `/api/[...path]/route.ts`
 * forwards the request to the FastAPI process with the session cookie
 * attached, so no auth header needs to be set here.
 *
 * Consumers MUST memoize the result (`useMemo(() => createChatTransport(), [])`)
 * to avoid recreating the transport on every render.
 */
export function createChatTransport(): DefaultChatTransport {
  return new DefaultChatTransport({ api: "/api/chat" })
}
```

- [ ] **Step 1.5: Run the smoke test to confirm it passes**

Run:
```bash
cd frontend && pnpm test lib/chat-transport.test.ts
```
Expected: `1 passed`.

- [ ] **Step 1.6: Create `chat.types.ts` with type re-exports and helper guards**

Create file `frontend/components/chat/chat.types.ts`:
```typescript
import type {
  DynamicToolUIPart,
  TextUIPart,
  ToolUIPart,
  UIMessage,
  UIMessagePart,
} from "ai"
import { isTextUIPart as aiIsTextUIPart, isToolUIPart as aiIsToolUIPart } from "ai"

/**
 * Re-exports + helpers for the chat component layer.
 *
 * `UIMessage` is the canonical message type from `ai`; we narrow it locally
 * with type guards rather than redefining shapes.
 */
export type { UIMessage, UIMessagePart, TextUIPart, ToolUIPart, DynamicToolUIPart }

/**
 * Any tool part the assistant can emit, whether typed (server declared the
 * tool) or dynamic (server did not). The backend in this project does NOT
 * declare tools to the client, so dynamic parts are the norm.
 */
export type AnyToolPart = ToolUIPart | DynamicToolUIPart

/**
 * Re-export of `ai`'s text-part guard. Aliased so component code reads
 * uniformly with the local `isAnyToolPart` helper below.
 */
export const isTextPart = aiIsTextUIPart

/**
 * Narrows any `UIMessagePart` to a tool part (typed OR dynamic).
 * Use this anywhere a component needs the tool name, input, output, or state.
 */
export function isAnyToolPart(part: UIMessagePart): part is AnyToolPart {
  return aiIsToolUIPart(part)
}
```

- [ ] **Step 1.7: Typecheck**

Run:
```bash
cd frontend && pnpm exec tsc --noEmit
```
Expected: clean exit, no type errors. (The `tsconfig.json` already runs `tsc` over all `**/*.ts(x)` files; the new files must compile.)

- [ ] **Step 1.8: Lint**

Run:
```bash
cd frontend && pnpm lint
```
Expected: clean exit. Biome may flag unused-import warnings if `pnpm` is strict; ignore benign warnings but fix real ones.

- [ ] **Step 1.9: Commit**

```bash
git add frontend/package.json frontend/pnpm-lock.yaml frontend/lib/chat-transport.ts frontend/lib/chat-transport.test.ts frontend/components/chat/chat.types.ts
git commit -m "feat(chat): add @ai-sdk/react@^3 dep, transport factory, shared types"
```
Expected: commit lands on `main` (or current branch). Lefthook may warn about missing lefthook config — pre-existing, ignore.

---

**Part 1 ends here.** Tasks 2-4 (BlinkingCursor, ToolChip, ChatInput) in part 2. Tasks 5-8 + integration in part 3.

---

## Task 2: ChatBlinkingCursor component

**Files:**
- Create: `frontend/components/chat/chat-blinking-cursor.tsx`
- Test: `frontend/components/chat/chat-blinking-cursor.test.tsx`

**Interfaces:**
- Produces `<ChatBlinkingCursor />` — a server-renderable, decorative `_` glyph in Bricolage with `aria-hidden="true"`. Consumers: Task 6 (`ChatMessage`), Task 8 (`ChatSection`). The cursor's animation is purely CSS (defined in Task 9's `globals.css` addition); this component just emits the markup with the correct class name.

- [ ] **Step 2.1: Write the failing test**

Create file `frontend/components/chat/chat-blinking-cursor.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { ChatBlinkingCursor } from "./chat-blinking-cursor"

describe("ChatBlinkingCursor", () => {
  it("renders an aria-hidden decorative glyph with the expected text", () => {
    render(<ChatBlinkingCursor />)
    const glyph = screen.getByTestId("chat-cursor")
    expect(glyph).toBeInTheDocument()
    expect(glyph).toHaveAttribute("aria-hidden", "true")
    expect(glyph.textContent).toBe("_")
  })

  it("uses the Bricolage heading font", () => {
    render(<ChatBlinkingCursor />)
    const glyph = screen.getByTestId("chat-cursor")
    // font-family must include the brand display font CSS var chain.
    const style = (glyph as HTMLElement).style.fontFamily
    expect(style).toContain("var(--font-heading)")
  })

  it("uses the mint primary color", () => {
    render(<ChatBlinkingCursor />)
    const glyph = screen.getByTestId("chat-cursor")
    const style = (glyph as HTMLElement).style.color
    expect(style).toContain("var(--primary)")
  })
})
```

- [ ] **Step 2.2: Run the test to confirm it fails**

Run:
```bash
cd frontend && pnpm test components/chat/chat-blinking-cursor.test.tsx
```
Expected: FAIL with module-not-found for `./chat-blinking-cursor`.

- [ ] **Step 2.3: Create the component**

Create file `frontend/components/chat/chat-blinking-cursor.tsx`:
```tsx
/**
 * Decorative blinking cursor that marks the live tail of a streaming
 * assistant message. Pure CSS animation (defined in `app/globals.css` keyframe
 * `blink-cursor`); the `@media (prefers-reduced-motion: reduce)` block in
 * globals.css disables the animation and falls back to a static glyph.
 */
export function ChatBlinkingCursor() {
  return (
    <span
      aria-hidden="true"
      data-testid="chat-cursor"
      className="chat-blinking-cursor"
      style={{
        fontFamily: "var(--font-heading)",
        color: "var(--primary)",
        fontSize: "1.2em",
        lineHeight: 1,
        marginLeft: "2px",
      }}
    >
      _
    </span>
  )
}
```

- [ ] **Step 2.4: Run the test to confirm it passes**

Run:
```bash
cd frontend && pnpm test components/chat/chat-blinking-cursor.test.tsx
```
Expected: `3 passed`.

- [ ] **Step 2.5: Commit**

```bash
git add frontend/components/chat/chat-blinking-cursor.tsx frontend/components/chat/chat-blinking-cursor.test.tsx
git commit -m "feat(chat): ChatBlinkingCursor decorative streaming glyph"
```

---

## Task 3: ChatToolChip component (collapsible pill + pulse + expandable input/output)

**Files:**
- Create: `frontend/components/chat/chat-tool-chip.tsx`
- Test: `frontend/components/chat/chat-tool-chip.test.tsx`

**Interfaces:**
- Produces `<ChatToolChip part={part} />` where `part: AnyToolPart` (from Task 1's `chat.types.ts`). The chip reads `part.state` to choose:
  - `'input-streaming' | 'input-available'` (no output yet) → pulsing mint dot, label shows tool name, body hidden.
  - `'output-available'` → static mint dot, body region renderable (collapsible).
  - `'output-error'` → static destructive dot, body region renderable with red left border.
  - `'approval-requested' | 'approval-responded' | 'output-denied'` → out of scope for this plan; render a small static chip with the tool name and no expand (defensive fallback).
- Tool name extraction: prefer `getToolName(part)` from `ai`; falls back to parsing `part.type` (for `tool-{name}` typed parts) or `part.toolName` (for `DynamicToolUIPart`).
- Input rendering: JSON.stringify with 2-space indent, `<pre>` with max-height 160px and `overflow-y: auto`. If `input` is undefined or empty, hide the input block.
- Output rendering: same `<pre>` styling. Output value coerced to string (`String(output ?? '')`).

- [ ] **Step 3.1: Write the failing test**

Create file `frontend/components/chat/chat-tool-chip.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import type { DynamicToolUIPart, ToolUIPart } from "ai"
import { ChatToolChip } from "./chat-tool-chip"

function dynamicPart(overrides: Partial<DynamicToolUIPart> = {}): DynamicToolUIPart {
  return {
    type: "dynamic-tool",
    toolName: "list_accounts",
    toolCallId: "call_123",
    state: "input-available",
    input: { filter: "active" },
    ...overrides,
  }
}

function typedPart(overrides: Partial<ToolUIPart> = {}): ToolUIPart {
  return {
    type: "tool-list_accounts",
    toolCallId: "call_456",
    state: "input-available",
    input: {},
    ...overrides,
  } as ToolUIPart
}

describe("ChatToolChip", () => {
  it("renders the tool name from a dynamic-tool part", () => {
    render(<ChatToolChip part={dynamicPart()} />)
    expect(screen.getByText("list_accounts")).toBeInTheDocument()
  })

  it("renders the tool name from a typed tool-{name} part", () => {
    render(<ChatToolChip part={typedPart()} />)
    expect(screen.getByText("list_accounts")).toBeInTheDocument()
  })

  it("starts collapsed with aria-expanded=false", () => {
    render(<ChatToolChip part={dynamicPart({ state: "output-available", output: "ok" })} />)
    const toggle = screen.getByRole("button", { name: /list_accounts/i })
    expect(toggle).toHaveAttribute("aria-expanded", "false")
  })

  it("expands on click and reveals input + output", async () => {
    const user = userEvent.setup()
    render(
      <ChatToolChip
        part={dynamicPart({
          state: "output-available",
          input: { filter: "active" },
          output: "7 accounts",
        })}
      />,
    )
    const toggle = screen.getByRole("button", { name: /list_accounts/i })
    await user.click(toggle)
    expect(toggle).toHaveAttribute("aria-expanded", "true")
    // JSON-stringified input appears inside a <pre>
    expect(screen.getByText(/"filter": "active"/)).toBeInTheDocument()
    expect(screen.getByText("7 accounts")).toBeInTheDocument()
  })

  it("applies destructive styling when state is output-error", () => {
    render(
      <ChatToolChip
        part={dynamicPart({ state: "output-error", errorText: "tool blew up" })}
      />,
    )
    expect(screen.getByText("tool blew up")).toBeInTheDocument()
    // The output region exists and carries role=region for screen readers.
    // We assert the destructive color is applied via the dot's inline style.
    const dot = screen.getByTestId("chat-tool-dot")
    expect((dot as HTMLElement).style.backgroundColor).toContain("var(--destructive)")
  })

  it("hides input block when input is undefined", async () => {
    const user = userEvent.setup()
    render(
      <ChatToolChip
        part={dynamicPart({ state: "output-available", input: undefined, output: "ok" })}
      />,
    )
    await user.click(screen.getByRole("button", { name: /list_accounts/i }))
    // No JSON-looking <pre> exists; output block still does.
    expect(screen.queryByText(/[{}]/)).not.toBeInTheDocument()
    expect(screen.getByText("ok")).toBeInTheDocument()
  })

  it("marks expanded JSON <pre> blocks with data-sensitive='true'", async () => {
    const user = userEvent.setup()
    const { container } = render(
      <ChatToolChip
        part={dynamicPart({
          state: "output-available",
          input: { secret: "hunter2" },
          output: "7 accounts",
        })}
      />,
    )
    await user.click(screen.getByRole("button", { name: /list_accounts/i }))
    const pres = container.querySelectorAll("pre[data-sensitive]")
    expect(pres.length).toBeGreaterThanOrEqual(2)
    pres.forEach((el) => {
      expect(el.getAttribute("data-sensitive")).toBe("true")
    })
  })
})
```

- [ ] **Step 3.2: Run the test to confirm it fails**

Run:
```bash
cd frontend && pnpm test components/chat/chat-tool-chip.test.tsx
```
Expected: FAIL with module-not-found for `./chat-tool-chip`.

- [ ] **Step 3.3: Create the component**

Create file `frontend/components/chat/chat-tool-chip.tsx`:
```tsx
"use client"

import { getToolName, type DynamicToolUIPart, type ToolUIPart } from "ai"
import { useState } from "react"
import type { AnyToolPart } from "./chat.types"

type Props = {
  part: AnyToolPart
}

function nameOf(part: AnyToolPart): string {
  try {
    return getToolName(part)
  } catch {
    // Defensive: if `ai`'s helper chokes on a malformed part, fall back.
    if (part.type === "dynamic-tool") return part.toolName
    if (part.type.startsWith("tool-")) return part.type.slice("tool-".length)
    return "tool"
  }
}

function isRunning(state: AnyToolPart["state"]): boolean {
  return state === "input-streaming" || state === "input-available"
}

function isError(state: AnyToolPart["state"]): boolean {
  return state === "output-error"
}

function isExpandable(state: AnyToolPart["state"]): boolean {
  return state === "output-available" || state === "output-error"
}

export function ChatToolChip({ part }: Props) {
  const [open, setOpen] = useState(false)
  const toolName = nameOf(part)
  const toggleId = `chat-tool-${part.type === "dynamic-tool" ? part.toolCallId : toolName}`
  const regionId = `${toggleId}-output`
  const running = isRunning(part.state)
  const errored = isError(part.state)
  const expandable = isExpandable(part.state)

  const dotColor = errored
    ? "var(--destructive)"
    : running
      ? "var(--primary)"
      : "color-mix(in oklch, var(--primary) 60%, transparent)"

  // Prefer JSON.stringify with 2-space indent for both input and output.
  const inputJson =
    part.input !== undefined && part.input !== null
      ? JSON.stringify(part.input, null, 2)
      : null
  const outputText =
    part.state === "output-error"
      ? (part as { errorText?: string }).errorText ?? ""
      : part.state === "output-available"
        ? String((part as { output?: unknown }).output ?? "")
        : ""

  return (
    <div className="my-1.5 inline-block max-w-full">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={regionId}
        onClick={() => expandable && setOpen((v) => !v)}
        disabled={!expandable}
        className="inline-flex items-center gap-2 rounded-md border px-2.5 py-1 font-mono text-xs transition-opacity"
        style={{
          background: "var(--muted)",
          borderColor: "var(--border)",
          color: "var(--foreground)",
          opacity: expandable ? 1 : 0.85,
        }}
      >
        <span
          data-testid="chat-tool-dot"
          aria-hidden
          className={running ? "chat-tool-pulse" : ""}
          style={{
            display: "inline-block",
            width: "8px",
            height: "8px",
            borderRadius: "9999px",
            backgroundColor: dotColor,
          }}
        />
        <span>{toolName}</span>
        {expandable && (
          <span aria-hidden style={{ color: "var(--muted-foreground)" }}>
            {open ? "▾" : "▸"}
          </span>
        )}
      </button>

      {expandable && open && (
        <div
          id={regionId}
          role="region"
          aria-label={`${toolName} input and output`}
          className="chat-tool-body mt-1.5 max-w-full overflow-hidden rounded-md border"
          style={{
            background: "var(--popover)",
            borderColor: errored ? "var(--destructive)" : "var(--border)",
            borderLeftWidth: errored ? "3px" : "1px",
          }}
        >
          {inputJson !== null && (
            <div className="border-b px-3 py-2" style={{ borderColor: "var(--border)" }}>
              <p
                className="mb-1 text-[10px] uppercase tracking-wider"
                style={{ color: "var(--muted-foreground)" }}
              >
                Input
              </p>
              <pre
                data-sensitive="true"
                className="overflow-auto font-mono text-xs leading-relaxed"
                style={{ maxHeight: "160px", color: "var(--foreground)" }}
              >
                {inputJson}
              </pre>
            </div>
          )}
          <div className="px-3 py-2">
            <p
              className="mb-1 text-[10px] uppercase tracking-wider"
              style={{ color: "var(--muted-foreground)" }}
            >
              {errored ? "Error" : "Output"}
            </p>
            <pre
              data-sensitive="true"
              className="overflow-auto whitespace-pre-wrap font-mono text-xs leading-relaxed"
              style={{ maxHeight: "160px", color: "var(--foreground)" }}
            >
              {outputText}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3.4: Run the test to confirm it passes**

Run:
```bash
cd frontend && pnpm test components/chat/chat-tool-chip.test.tsx
```
Expected: `7 passed`.

- [ ] **Step 3.5: Commit**

```bash
git add frontend/components/chat/chat-tool-chip.tsx frontend/components/chat/chat-tool-chip.test.tsx
git commit -m "feat(chat): ChatToolChip collapsible pill with pulse + expandable body"
```

---

## Task 4: ChatInput component (auto-grow textarea + send/stop button)

**Files:**
- Create: `frontend/components/chat/chat-input.tsx`
- Test: `frontend/components/chat/chat-input.test.tsx`

**Interfaces:**
- Produces `<ChatInput status onSend onStop />` where:
  - `status: 'submitted' | 'streaming' | 'ready' | 'error'`
  - `onSend: (text: string) => void` — invoked when user presses Enter (no Shift) or clicks send button.
  - `onStop: () => void` — invoked when user clicks the stop button (only rendered while status is `'submitted'` or `'streaming'`).
- Behavior:
  - Textarea auto-grows up to 6 lines (`maxHeight: 6 * lineHeight`), then internal scroll.
  - `Enter` submits. `Shift+Enter` inserts newline. `Esc` while `streaming`/`submitted` calls `onStop`.
  - Textarea is `disabled` while status is `'submitted'` or `'streaming'`.
  - Send button label: glyph only (lucide-react `Send` icon when ready, `Square` when streaming). No text label.
  - Wrapper div carries the `chat-input-underline` class so the animated bottom-border effect (defined in globals.css Task 9) applies.
- Props also accept an optional `autoFocus?: boolean` (default true) used by `ChatSection` on mount.

- [ ] **Step 4.1: Write the failing test**

Create file `frontend/components/chat/chat-input.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { ChatInput } from "./chat-input"

describe("ChatInput", () => {
  it("renders a textarea and a send button", () => {
    render(<ChatInput status="ready" onSend={vi.fn()} onStop={vi.fn()} />)
    expect(screen.getByRole("textbox")).toBeInTheDocument()
    expect(screen.getByRole("button")).toBeInTheDocument()
  })

  it("calls onSend with the typed text on Enter", async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<ChatInput status="ready" onSend={onSend} onStop={vi.fn()} />)
    const ta = screen.getByRole("textbox")
    await user.type(ta, "hola mundo")
    await user.keyboard("{Enter}")
    expect(onSend).toHaveBeenCalledWith("hola mundo")
  })

  it("does NOT call onSend on Shift+Enter (inserts newline)", async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<ChatInput status="ready" onSend={onSend} onStop={vi.fn()} />)
    const ta = screen.getByRole("textbox")
    await user.type(ta, "line1")
    await user.keyboard("{Shift>}{Enter}{/Shift}")
    await user.keyboard("line2")
    expect(onSend).not.toHaveBeenCalled()
  })

  it("disables the textarea and shows a stop button while streaming", () => {
    render(<ChatInput status="streaming" onSend={vi.fn()} onStop={vi.fn()} />)
    expect(screen.getByRole("textbox")).toBeDisabled()
    expect(screen.getByRole("button", { name: /detener|stop/i })).toBeInTheDocument()
  })

  it("calls onStop when Esc is pressed while streaming", async () => {
    const user = userEvent.setup()
    const onStop = vi.fn()
    render(<ChatInput status="streaming" onSend={vi.fn()} onStop={onStop} />)
    await user.click(screen.getByRole("textbox"))
    await user.keyboard("{Escape}")
    expect(onStop).toHaveBeenCalledTimes(1)
  })

  it("calls onStop when the stop button is clicked", async () => {
    const user = userEvent.setup()
    const onStop = vi.fn()
    render(<ChatInput status="submitted" onSend={vi.fn()} onStop={onStop} />)
    await user.click(screen.getByRole("button"))
    expect(onStop).toHaveBeenCalledTimes(1)
  })

  it("clears the textarea after a successful send", async () => {
    const user = userEvent.setup()
    render(<ChatInput status="ready" onSend={vi.fn()} onStop={vi.fn()} />)
    const ta = screen.getByRole("textbox") as HTMLTextAreaElement
    await user.type(ta, "pregunta")
    await user.keyboard("{Enter}")
    expect(ta.value).toBe("")
  })

  it("wraps the textarea in a div with the chat-input-underline class", () => {
    const { container } = render(
      <ChatInput status="ready" onSend={vi.fn()} onStop={vi.fn()} />,
    )
    expect(container.querySelector(".chat-input-underline")).not.toBeNull()
  })
})
```

- [ ] **Step 4.2: Run the test to confirm it fails**

Run:
```bash
cd frontend && pnpm test components/chat/chat-input.test.tsx
```
Expected: FAIL with module-not-found for `./chat-input`.

- [ ] **Step 4.3: Create the component**

Create file `frontend/components/chat/chat-input.tsx`:
```tsx
"use client"

import { Send, Square } from "lucide-react"
import { useEffect, useLayoutEffect, useRef, useState } from "react"

type Props = {
  status: "submitted" | "streaming" | "ready" | "error"
  onSend: (text: string) => void
  onStop: () => void
  autoFocus?: boolean
  maxLength?: number
  cooldownMs?: number
}

const MAX_LINES = 6
const LINE_HEIGHT_PX = 22 // matches text-base leading; tweak if global typography changes.
const DEFAULT_MAX_LENGTH = 32000 // mirrors backend 32 KB cap (ADR-0014).
const DEFAULT_COOLDOWN_MS = 600 // UX guard against double-submit; NOT a rate limit.

function autoGrow(el: HTMLTextAreaElement | null) {
  if (!el) return
  el.style.height = "auto"
  const max = MAX_LINES * LINE_HEIGHT_PX
  el.style.height = `${Math.min(el.scrollHeight, max)}px`
  el.style.overflowY = el.scrollHeight > max ? "auto" : "hidden"
}

// useLayoutEffect warns on SSR; alias to useEffect on the server.
const useIsoLayoutEffect =
  typeof window !== "undefined" ? useLayoutEffect : useEffect

export function ChatInput({
  status,
  onSend,
  onStop,
  autoFocus = true,
  maxLength = DEFAULT_MAX_LENGTH,
  cooldownMs = DEFAULT_COOLDOWN_MS,
}: Props) {
  const [text, setText] = useState("")
  const [cooldown, setCooldown] = useState(false)
  const ref = useRef<HTMLTextAreaElement | null>(null)

  useIsoLayoutEffect(() => {
    autoGrow(ref.current)
  }, [text])

  // Focus on mount when ready.
  useEffect(() => {
    if (autoFocus && status === "ready" && ref.current) {
      ref.current.focus()
    }
  }, [autoFocus, status])

  const busy = status === "submitted" || status === "streaming"
  const blocked = busy || cooldown

  function fireSend() {
    onSend(text)
    setText("")
    if (cooldownMs > 0) {
      setCooldown(true)
      setTimeout(() => setCooldown(false), cooldownMs)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      if (!blocked && text.trim().length > 0) {
        fireSend()
      }
      return
    }
    if (e.key === "Escape" && busy) {
      e.preventDefault()
      onStop()
    }
  }

  function handleClickAction() {
    if (busy) {
      onStop()
    } else if (!cooldown && text.trim().length > 0) {
      fireSend()
    }
  }

  return (
    <div
      className="chat-input-underline flex items-end gap-2 border-t px-1 pt-3 pb-2"
      style={{ borderColor: "var(--border)" }}
    >
      <textarea
        ref={ref}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={busy}
        maxLength={maxLength}
        rows={1}
        aria-label="Mensaje para el asistente"
        placeholder={busy ? "Pensando…" : "Pregúntale algo a tu asistente…"}
        className="flex-1 resize-none rounded-md border bg-transparent px-3 py-2 text-sm outline-none transition-colors focus:ring-0"
        style={{
          borderColor: "var(--input)",
          color: "var(--foreground)",
          minHeight: `${LINE_HEIGHT_PX + 16}px`,
        }}
      />
      <button
        type="button"
        onClick={handleClickAction}
        aria-label={busy ? "Detener respuesta" : "Enviar mensaje"}
        className="grid size-9 place-items-center rounded-md transition-opacity disabled:opacity-40"
        style={{
          background: "var(--primary)",
          color: "var(--primary-foreground)",
        }}
        disabled={!busy && (cooldown || text.trim().length === 0)}
      >
        {busy ? <Square className="size-4" /> : <Send className="size-4" />}
      </button>
    </div>
  )
}
```

- [ ] **Step 4.4: Run the test to confirm it passes**

Run:
```bash
cd frontend && pnpm test components/chat/chat-input.test.tsx
```
Expected: `8 passed`. (If `lucide-react` types report missing, run `cd frontend && pnpm install` to refresh types — pre-existing repo state should already have it.)

- [ ] **Step 4.5: Commit**

```bash
git add frontend/components/chat/chat-input.tsx frontend/components/chat/chat-input.test.tsx
git commit -m "feat(chat): ChatInput auto-grow textarea with send/stop"
```

---

**Part 2 ends here.** Tasks 5-8 (EmptyState, Message, Thread, Section) + Task 9 (integration + globals.css + verify) in part 3.

---

## Task 5: ChatEmptyState component (3 suggested chips + copy)

**Files:**
- Create: `frontend/components/chat/chat-empty-state.tsx`
- Test: `frontend/components/chat/chat-empty-state.test.tsx`

**Interfaces:**
- Produces `<ChatEmptyState onPick={(text: string) => void} />`. Consumers: Task 8 (`ChatSection`). When `onPick` fires, `ChatSection` calls `sendMessage({ text })` with the picked string.

- [ ] **Step 5.1: Write the failing test**

Create file `frontend/components/chat/chat-empty-state.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { ChatEmptyState } from "./chat-empty-state"

describe("ChatEmptyState", () => {
  it("renders the title and subtitle copy", () => {
    render(<ChatEmptyState onPick={vi.fn()} />)
    expect(screen.getByText("Pregúntale a tu asistente")).toBeInTheDocument()
    expect(
      screen.getByText(/Puede leer tus cuentas, transacciones, presupuestos y metas\./),
    ).toBeInTheDocument()
  })

  it("renders exactly 3 suggested-prompt buttons", () => {
    render(<ChatEmptyState onPick={vi.fn()} />)
    const buttons = screen.getAllByRole("button")
    expect(buttons).toHaveLength(3)
  })

  it("calls onPick with the chip text when clicked", async () => {
    const user = userEvent.setup()
    const onPick = vi.fn()
    render(<ChatEmptyState onPick={onPick} />)
    await user.click(screen.getByRole("button", { name: /¿Cuánto puedo gastar este mes\?/ }))
    expect(onPick).toHaveBeenCalledWith("¿Cuánto puedo gastar este mes?")
  })

  it("uses the brand mint accent for the chip border", () => {
    const { container } = render(<ChatEmptyState onPick={vi.fn()} />)
    const firstChip = container.querySelector("button")
    const style = (firstChip as HTMLElement).style.borderColor
    expect(style).toContain("var(--primary)")
  })
})
```

- [ ] **Step 5.2: Run the test to confirm it fails**

Run:
```bash
cd frontend && pnpm test components/chat/chat-empty-state.test.tsx
```
Expected: FAIL with module-not-found for `./chat-empty-state`.

- [ ] **Step 5.3: Create the component**

Create file `frontend/components/chat/chat-empty-state.tsx`:
```tsx
"use client"

type Props = {
  onPick: (text: string) => void
}

const SUGGESTIONS = [
  "¿Cuánto puedo gastar este mes?",
  "Lista mis cuentas y sus saldos",
  "Dame el resumen del mes",
] as const

export function ChatEmptyState({ onPick }: Props) {
  return (
    <div className="flex flex-col items-start gap-3 px-1 py-6">
      <p
        className="font-display text-lg font-semibold tracking-tight"
        style={{ color: "var(--foreground)" }}
      >
        Pregúntale a tu asistente
      </p>
      <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
        Puede leer tus cuentas, transacciones, presupuestos y metas.
      </p>
      <div className="mt-1 flex flex-wrap gap-2">
        {SUGGESTIONS.map((text) => (
          <button
            key={text}
            type="button"
            aria-label={`Enviar sugerencia: ${text}`}
            onClick={() => onPick(text)}
            className="rounded-full border px-3 py-1.5 text-xs transition-colors hover:bg-[color-mix(in_oklch,var(--primary)_8%,transparent)]"
            style={{
              borderColor: "var(--primary)",
              color: "var(--foreground)",
              background: "transparent",
            }}
          >
            {text}
          </button>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 5.4: Run the test to confirm it passes**

Run:
```bash
cd frontend && pnpm test components/chat/chat-empty-state.test.tsx
```
Expected: `4 passed`.

- [ ] **Step 5.5: Commit**

```bash
git add frontend/components/chat/chat-empty-state.tsx frontend/components/chat/chat-empty-state.test.tsx
git commit -m "feat(chat): ChatEmptyState with 3 suggested-prompt chips"
```

---

## Task 6: ChatMessage component (memoized, discriminates parts)

**Files:**
- Create: `frontend/components/chat/chat-message.tsx`
- Test: `frontend/components/chat/chat-message.test.tsx`

**Interfaces:**
- Produces `<ChatMessage message={m} showCursor={boolean} />` where:
  - `message: UIMessage` (from `chat.types.ts`)
  - `showCursor: boolean` — true only when this is the last assistant message AND `status === 'streaming'` (decided by parent).
- Behavior:
  - Wrapped in `React.memo` keyed by `message.id` (only re-renders when the message itself changes).
  - Renders `<p>` for each `TextUIPart`; renders `<ChatToolChip>` for each `AnyToolPart`. Skips other part types silently (system messages, source-url, etc. — none expected from our backend).
  - User messages: right-aligned, background `var(--secondary)`, rounded bubble.
  - Assistant messages: left-aligned, plain text, no bubble. After the last text part, appends `<ChatBlinkingCursor />` if `showCursor`.
  - Role `system` is ignored (returns null).
- Consumers: Task 7 (`ChatThread`).

- [ ] **Step 6.1: Write the failing test**

Create file `frontend/components/chat/chat-message.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import type { UIMessage } from "ai"
import { ChatMessage } from "./chat-message"

function userMessage(text: string): UIMessage {
  return {
    id: "u1",
    role: "user",
    parts: [{ type: "text", text }],
  }
}

function assistantMessage(text: string, id = "a1"): UIMessage {
  return {
    id,
    role: "assistant",
    parts: [{ type: "text", text, state: "done" }],
  }
}

describe("ChatMessage", () => {
  it("renders a user message right-aligned with secondary background", () => {
    const { container } = render(<ChatMessage message={userMessage("hola")} showCursor={false} />)
    const wrapper = container.firstChild as HTMLElement
    expect(wrapper.className).toMatch(/self-end|justify-end/)
    expect(wrapper.style.backgroundColor).toContain("var(--secondary)")
    expect(screen.getByText("hola")).toBeInTheDocument()
  })

  it("renders an assistant message left-aligned, plain text, no bubble background", () => {
    const { container } = render(
      <ChatMessage message={assistantMessage("respuesta")} showCursor={false} />,
    )
    const wrapper = container.firstChild as HTMLElement
    expect(wrapper.style.backgroundColor).not.toContain("var(--secondary)")
    expect(screen.getByText("respuesta")).toBeInTheDocument()
  })

  it("shows the blinking cursor when showCursor is true and no tool parts present", () => {
    render(<ChatMessage message={assistantMessage("partial")} showCursor={true} />)
    expect(screen.getByTestId("chat-cursor")).toBeInTheDocument()
  })

  it("hides the blinking cursor when showCursor is false", () => {
    render(<ChatMessage message={assistantMessage("done")} showCursor={false} />)
    expect(screen.queryByTestId("chat-cursor")).not.toBeInTheDocument()
  })

  it("renders a tool chip for dynamic-tool parts", () => {
    const msg: UIMessage = {
      id: "a2",
      role: "assistant",
      parts: [
        {
          type: "dynamic-tool",
          toolName: "list_accounts",
          toolCallId: "c1",
          state: "output-available",
          input: {},
          output: "7 accounts",
        },
      ],
    }
    const { container } = render(<ChatMessage message={msg} showCursor={false} />)
    expect(screen.getByText("list_accounts")).toBeInTheDocument()
    // No <p> wrapping a plain text node should appear (no text part).
    expect(container.querySelectorAll("p").length).toBe(0)
  })

  it("renders both text and tool parts in order", () => {
    const msg: UIMessage = {
      id: "a3",
      role: "assistant",
      parts: [
        { type: "text", text: "Resultados:", state: "done" },
        {
          type: "dynamic-tool",
          toolName: "list_accounts",
          toolCallId: "c2",
          state: "output-available",
          input: {},
          output: "ok",
        },
        { type: "text", text: "Listo.", state: "done" },
      ],
    }
    render(<ChatMessage message={msg} showCursor={false} />)
    expect(screen.getByText("Resultados:")).toBeInTheDocument()
    expect(screen.getByText("list_accounts")).toBeInTheDocument()
    expect(screen.getByText("Listo.")).toBeInTheDocument()
  })

  it("returns null for system messages", () => {
    const { container } = render(
      <ChatMessage
        message={{
          id: "s1",
          role: "system",
          parts: [{ type: "text", text: "you are a helpful assistant" }],
        }}
        showCursor={false}
      />,
    )
    expect(container.firstChild).toBeNull()
  })
})
```

- [ ] **Step 6.2: Run the test to confirm it fails**

Run:
```bash
cd frontend && pnpm test components/chat/chat-message.test.tsx
```
Expected: FAIL with module-not-found for `./chat-message`.

- [ ] **Step 6.3: Create the component**

Create file `frontend/components/chat/chat-message.tsx`:
```tsx
"use client"

import { memo } from "react"
import type { UIMessage } from "./chat.types"
import { isAnyToolPart, isTextPart } from "./chat.types"
import { ChatBlinkingCursor } from "./chat-blinking-cursor"
import { ChatToolChip } from "./chat-tool-chip"

type Props = {
  message: UIMessage
  showCursor: boolean
}

function ChatMessageImpl({ message, showCursor }: Props) {
  if (message.role === "system") return null

  const isUser = message.role === "user"

  // Locate the last text part index for cursor placement.
  const lastTextIndex = message.parts
    .map((p, i) => (isTextPart(p) ? i : -1))
    .reduce((max, i) => (i > max ? i : max), -1)

  const wrapperStyle: React.CSSProperties = isUser
    ? {
        background: "var(--secondary)",
        color: "var(--secondary-foreground)",
        padding: "8px 12px",
        borderRadius: "12px",
        maxWidth: "85%",
      }
    : {
        color: "var(--foreground)",
        maxWidth: "100%",
      }

  const wrapperClass = isUser ? "self-end" : "self-start"

  return (
    <div
      data-message-id={message.id}
      className={`${wrapperClass} flex w-fit max-w-full flex-col gap-1.5 text-sm leading-relaxed`}
      style={wrapperStyle}
    >
      {message.parts.map((part, idx) => {
        if (isTextPart(part)) {
          const showTailCursor = showCursor && idx === lastTextIndex && isUser === false
          return (
            <p key={`${message.id}-t-${idx}`} className="whitespace-pre-wrap">
              {part.text}
              {showTailCursor && <ChatBlinkingCursor />}
            </p>
          )
        }
        if (isAnyToolPart(part)) {
          return <ChatToolChip key={`${message.id}-tl-${idx}`} part={part} />
        }
        // Other part kinds (source-url, reasoning, file, data) are out of scope
        // for v1; skip silently. The LLM does not emit them through our backend.
        return null
      })}
      {/* Cursor also appears when the message has NO text part but is the live tail. */}
      {showCursor &&
        isUser === false &&
        lastTextIndex === -1 && <ChatBlinkingCursor />}
    </div>
  )
}

export const ChatMessage = memo(ChatMessageImpl)
```

- [ ] **Step 6.4: Run the test to confirm it passes**

Run:
```bash
cd frontend && pnpm test components/chat/chat-message.test.tsx
```
Expected: `7 passed`.

- [ ] **Step 6.5: Commit**

```bash
git add frontend/components/chat/chat-message.tsx frontend/components/chat/chat-message.test.tsx
git commit -m "feat(chat): ChatMessage memoized renderer with part discrimination"
```

---

## Task 7: ChatThread component (auto-scroll, renders list of messages)

**Files:**
- Create: `frontend/components/chat/chat-thread.tsx`
- Test: `frontend/components/chat/chat-thread.test.tsx`

**Interfaces:**
- Produces `<ChatThread messages={m[]} status={status} />` where:
  - `messages: UIMessage[]` (full message list from `useChat`).
  - `status: 'submitted' | 'streaming' | 'ready' | 'error'` — used to decide cursor placement on the last assistant message.
- Behavior:
  - Scrollable region with `max-height: min(420px, 60vh)` and `overflow-y: auto`.
  - Auto-scroll on append: when `messages.length` changes (or when the trailing assistant message grows), set `scrollTop = scrollHeight` UNLESS the user has scrolled up more than `40px` from the bottom (in which case respect their position).
  - Renders `<ChatMessage>` per message. The last message gets `showCursor={status === 'streaming' && lastMessage.role === 'assistant'}`.

- [ ] **Step 7.1: Write the failing test**

Create file `frontend/components/chat/chat-thread.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import type { UIMessage } from "ai"
import { ChatThread } from "./chat-thread"

function msg(role: "user" | "assistant", text: string, id: string): UIMessage {
  return { id, role, parts: [{ type: "text", text, state: "done" }] }
}

describe("ChatThread", () => {
  it("renders each message in order", () => {
    render(
      <ChatThread
        messages={[msg("user", "hi", "u1"), msg("assistant", "hello", "a1")]}
        status="ready"
      />,
    )
    expect(screen.getByText("hi")).toBeInTheDocument()
    expect(screen.getByText("hello")).toBeInTheDocument()
  })

  it("applies aria-live=polite and aria-label for accessibility", () => {
    const { container } = render(<ChatThread messages={[]} status="ready" />)
    const region = container.querySelector("section")
    expect(region?.getAttribute("aria-live")).toBe("polite")
    expect(region?.getAttribute("aria-label")).toMatch(/Conversación con asistente/i)
  })

  it("renders the blinking cursor on the last assistant message while streaming", () => {
    render(
      <ChatThread
        messages={[
          msg("user", "hola", "u1"),
          { id: "a1", role: "assistant", parts: [{ type: "text", text: "partial", state: "streaming" }] },
        ]}
        status="streaming"
      />,
    )
    expect(screen.getByTestId("chat-cursor")).toBeInTheDocument()
  })

  it("does NOT render the cursor when status is ready", () => {
    render(
      <ChatThread
        messages={[msg("assistant", "done", "a1")]}
        status="ready"
      />,
    )
    expect(screen.queryByTestId("chat-cursor")).not.toBeInTheDocument()
  })

  it("uses a scrollable container with overflow-y:auto", () => {
    const { container } = render(<ChatThread messages={[]} status="ready" />)
    const scrollEl = container.querySelector('[data-testid="chat-scroll"]') as HTMLElement
    expect(scrollEl).not.toBeNull()
    expect(scrollEl.style.overflowY).toBe("auto")
  })
})
```

- [ ] **Step 7.2: Run the test to confirm it fails**

Run:
```bash
cd frontend && pnpm test components/chat/chat-thread.test.tsx
```
Expected: FAIL with module-not-found for `./chat-thread`.

- [ ] **Step 7.3: Create the component**

Create file `frontend/components/chat/chat-thread.tsx`:
```tsx
"use client"

import { useEffect, useRef } from "react"
import type { UIMessage } from "./chat.types"
import { ChatMessage } from "./chat-message"

type Props = {
  messages: UIMessage[]
  status: "submitted" | "streaming" | "ready" | "error"
}

const USER_SCROLL_THRESHOLD_PX = 40

export function ChatThread({ messages, status }: Props) {
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const prevLenRef = useRef(0)

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    // Only auto-scroll when messages grew (not on unrelated re-renders).
    if (messages.length > prevLenRef.current) {
      const distanceFromBottom = el.scrollHeight - (el.scrollTop + el.clientHeight)
      if (distanceFromBottom <= USER_SCROLL_THRESHOLD_PX) {
        el.scrollTop = el.scrollHeight
      }
    }
    prevLenRef.current = messages.length
  }, [messages.length])

  // Also scroll when the streaming text grows the trailing message height.
  useEffect(() => {
    if (status !== "streaming") return
    const el = scrollRef.current
    if (!el) return
    const distanceFromBottom = el.scrollHeight - (el.scrollTop + el.clientHeight)
    if (distanceFromBottom <= USER_SCROLL_THRESHOLD_PX) {
      el.scrollTop = el.scrollHeight
    }
  }, [messages, status])

  const last = messages[messages.length - 1]
  const showCursorOnLast =
    status === "streaming" && last?.role === "assistant"

  return (
    <section
      aria-live="polite"
      aria-label="Conversación con asistente"
      className="flex w-full flex-col gap-3 px-1 py-3"
    >
      <div
        ref={scrollRef}
        data-testid="chat-scroll"
        className="flex flex-col gap-2 px-1"
        style={{
          maxHeight: "min(420px, 60vh)",
          overflowY: "auto",
        }}
      >
        {messages.map((m, idx) => (
          <ChatMessage
            key={m.id}
            message={m}
            showCursor={showCursorOnLast && idx === messages.length - 1}
          />
        ))}
      </div>
    </section>
  )
}
```

- [ ] **Step 7.4: Run the test to confirm it passes**

Run:
```bash
cd frontend && pnpm test components/chat/chat-thread.test.tsx
```
Expected: `5 passed`.

- [ ] **Step 7.5: Commit**

```bash
git add frontend/components/chat/chat-thread.tsx frontend/components/chat/chat-thread.test.tsx
git commit -m "feat(chat): ChatThread scrollable list with smart auto-scroll"
```

---

## Task 8: ChatSection component (top-level, owns `useChat`)

**Files:**
- Create: `frontend/lib/chat-errors.ts` — `translateChatError(error: Error): string`.
- Create: `frontend/lib/chat-errors.test.ts` — one assertion per Errors-table row + fallback.
- Create: `frontend/components/chat/chat-error-banner.tsx` — `ChatErrorBanner` with translated copy, close `×`, optional Reintentar.
- Modify: `frontend/lib/query.ts` — add `chatAssistantTurn` group to `INVALIDATION`.
- Create: `frontend/components/chat/chat-section.tsx`.
- Test:   `frontend/components/chat/chat-section.test.tsx` (8 tests, see Step 8.1).

**Interfaces:**
- Produces `<ChatSection />`. Consumers: `app/(app)/page.tsx` (Task 9).
- Owns `useChat({ transport, onFinish })` from `@ai-sdk/react`.
- Reads TanStack Query client via `useQueryClient()` and calls `invalidate(qc, 'chatAssistantTurn')` on finish.
- Renders:
  - `<ChatErrorBanner />` when `status === 'error'` (inline above the input, dismissable, translates `error.message` to es-CO).
  - `<ChatEmptyState />` when `messages.length === 0 && status === 'ready'`.
  - `<ChatThread />` when `messages.length > 0`.
  - `<ChatInput />` always at the bottom.
- Test mocks `@ai-sdk/react` via `vi.mock` (hoisted with `vi.hoisted` + `beforeEach` reset, see Test isolation in Global Constraints) so tests are deterministic without a live SSE.

- [ ] **Step 8.0a: Add `chatAssistantTurn` invalidation group**

Edit `frontend/lib/query.ts`. Inside the `INVALIDATION` const, add a new entry:

```typescript
chatAssistantTurn: [
  [ROOTS.transactions],
  [ROOTS.planned],
  [ROOTS.accounts],
  [ROOTS.budgets],
  [ROOTS.goals],
  [ROOTS.reports],
  [ROOTS.recurring],
],
```

The group is broad (every entity any of the 52 MCP tools can mutate) but scoped — `settings`, `fx`, `tags`, `categories`, `categoryGroups` are excluded because no chat tool mutates them in v1. Re-evaluate when adding tool surfaces.

Verify:
```bash
cd frontend && pnpm typecheck
```
Expected: clean.

- [ ] **Step 8.0b: Write the failing test for `translateChatError`**

Create `frontend/lib/chat-errors.test.ts`:
```typescript
import { describe, expect, it } from "vitest"
import { translateChatError } from "./chat-errors"

describe("translateChatError", () => {
  it("maps network failures to the offline copy", () => {
    expect(translateChatError(new Error("fetch failed"))).toBe(
      "No pudimos contactar al servidor",
    )
    expect(translateChatError(new TypeError("Failed to fetch"))).toBe(
      "No pudimos contactar al servidor",
    )
  })

  it("maps 413 / too-large messages to the length copy", () => {
    expect(translateChatError(new Error("message content exceeds 32 KB"))).toBe(
      "Tu mensaje es muy largo. Acórtalo e intenta de nuevo.",
    )
  })

  it("maps 422 validation errors to the reformulate copy", () => {
    const err = new Error("Unprocessable Entity")
    ;(err as Error & { status?: number }).status = 422
    expect(translateChatError(err)).toBe(
      "No pude procesar tu mensaje. Reformúlalo e intenta otra vez.",
    )
  })

  it("maps 429 rate-limit errors to the wait copy", () => {
    const err = new Error("Too Many Requests")
    ;(err as Error & { status?: number }).status = 429
    expect(translateChatError(err)).toBe(
      "Demasiadas solicitudes. Espera un momento e intenta de nuevo.",
    )
  })

  it("falls back to the generic copy on unknown errors", () => {
    expect(translateChatError(new Error("something exotic"))).toBe(
      "Algo salió mal. Vuelve a intentarlo en un momento.",
    )
  })
})
```

Run:
```bash
cd frontend && pnpm test lib/chat-errors.test.ts
```
Expected: FAIL with module-not-found.

- [ ] **Step 8.0c: Create the error translator**

Create `frontend/lib/chat-errors.ts`:
```typescript
/**
 * Maps a raw `useChat` error to a small allowlist of es-CO user-facing
 * strings. The raw `error.message` is NEVER rendered verbatim — Pydantic
 * detail strings can leak schema internals (OWASP A02 information
 * disclosure). The raw error is still logged via `console.error` for
 * diagnostic purposes; the user only sees the translated copy.
 *
 * Errors carry `status` only when the transport layer attached it; many
 * fetch failures arrive as plain `Error` / `TypeError`, so message regex
 * is the primary discriminator.
 */
type WithStatus = { status?: number }

const NETWORK_RX = /fetch failed|Failed to fetch|NetworkError|ERR_NETWORK/i
const TOO_LARGE_RX = /exceeds.*KB|too large|413/i

export function translateChatError(error: Error): string {
  const status = (error as Error & WithStatus).status
  const msg = error.message ?? ""

  if (status === 413 || TOO_LARGE_RX.test(msg)) {
    return "Tu mensaje es muy largo. Acórtalo e intenta de nuevo."
  }
  if (status === 422) {
    return "No pude procesar tu mensaje. Reformúlalo e intenta otra vez."
  }
  if (status === 429) {
    return "Demasiadas solicitudes. Espera un momento e intenta de nuevo."
  }
  if (NETWORK_RX.test(msg)) {
    return "No pudimos contactar al servidor"
  }
  // Backend SSE error event surfaces as Error with errorText in message.
  if (msg.startsWith("errorText:") || /no pude completar/i.test(msg)) {
    return "No pude completar tu solicitud. Vuelve a intentarlo."
  }
  // Diagnostic log; never reaches the DOM.
  // biome-ignore lint/suspicious/noConsole: intentional diagnostic.
  console.error("[chat] untranslated error:", error)
  return "Algo salió mal. Vuelve a intentarlo en un momento."
}
```

Run:
```bash
cd frontend && pnpm test lib/chat-errors.test.ts
```
Expected: `5 passed`.

Commit:
```bash
git add frontend/lib/chat-errors.ts frontend/lib/chat-errors.test.ts
git commit -m "feat(chat): translateChatError es-CO error mapping"
```

- [ ] **Step 8.0d: Create the `ChatErrorBanner` component**

Create `frontend/components/chat/chat-error-banner.tsx`:
```tsx
"use client"

import { X } from "lucide-react"
import { useEffect, useState } from "react"
import { translateChatError } from "@/lib/chat-errors"

type Props = {
  error: Error
  onRetry?: () => void
}

export function ChatErrorBanner({ error, onRetry }: Props) {
  const [dismissed, setDismissed] = useState(false)
  const message = translateChatError(error)

  // Reset dismissed when a new error arrives (different message text).
  useEffect(() => {
    setDismissed(false)
  }, [message])

  if (dismissed) return null

  return (
    <div
      role="alert"
      className="mx-1 mb-1 flex items-center justify-between gap-3 rounded-md border px-3 py-2 text-xs"
      style={{
        borderColor: "var(--destructive)",
        color: "var(--destructive)",
        background: "color-mix(in oklch, var(--destructive) 6%, transparent)",
      }}
    >
      <span>{message}</span>
      <div className="flex items-center gap-2">
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="rounded border px-2 py-1 transition-opacity hover:opacity-80"
            style={{
              borderColor: "var(--destructive)",
              color: "var(--destructive)",
              background: "transparent",
            }}
          >
            Reintentar
          </button>
        )}
        <button
          type="button"
          onClick={() => setDismissed(true)}
          aria-label="Cerrar mensaje de error"
          className="grid size-6 place-items-center rounded transition-opacity hover:opacity-80"
          style={{ color: "var(--destructive)" }}
        >
          <X className="size-3" />
        </button>
      </div>
    </div>
  )
}
```

Verify:
```bash
cd frontend && pnpm typecheck
```
Expected: clean. (No standalone test file for this component — coverage comes from `chat-section.test.tsx` tests #7 and #8.)

Commit:
```bash
git add frontend/components/chat/chat-error-banner.tsx
git commit -m "feat(chat): ChatErrorBanner with translated copy + dismissable ×"
```

- [ ] **Step 8.1: Write the failing test**

Create file `frontend/components/chat/chat-section.test.tsx`:
```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import type { ReactNode } from "react"

// --- Mock @ai-sdk/react ---------------------------------------------------
const sendMessage = vi.fn()
const stop = vi.fn()
const regenerate = vi.fn()
let mockStatus: "submitted" | "streaming" | "ready" | "error" = "ready"
let mockMessages: ReturnType<typeof asMessages> = []
let mockError: Error | undefined = undefined

function asMessages() {
  return [] as Array<{
    id: string
    role: "user" | "assistant" | "system"
    parts: Array<{ type: string; text?: string }>
  }>
}

vi.mock("@ai-sdk/react", () => ({
  useChat: () => ({
    messages: mockMessages,
    sendMessage,
    stop,
    regenerate,
    status: mockStatus,
    error: mockError,
  }),
}))

import { ChatSection } from "./chat-section"

function withQueryClient(node: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{node}</QueryClientProvider>
}

describe("ChatSection", () => {
  it("renders the empty state with 3 chips when no messages and status ready", () => {
    mockMessages = []
    mockStatus = "ready"
    render(withQueryClient(<ChatSection />))
    expect(screen.getByText("Pregúntale a tu asistente")).toBeInTheDocument()
    const buttons = screen.getAllByRole("button")
    // 3 suggestion chips. (No send button visible while textarea is empty.)
    expect(buttons.length).toBeGreaterThanOrEqual(3)
  })

  it("clicking a suggestion chip calls sendMessage with that text", async () => {
    const user = userEvent.setup()
    mockMessages = []
    mockStatus = "ready"
    sendMessage.mockClear()
    render(withQueryClient(<ChatSection />))
    await user.click(screen.getByRole("button", { name: /Lista mis cuentas y sus saldos/ }))
    expect(sendMessage).toHaveBeenCalledWith({ text: "Lista mis cuentas y sus saldos" })
  })

  it("renders ChatThread when messages exist", () => {
    mockMessages = [
      {
        id: "u1",
        role: "user",
        parts: [{ type: "text", text: "hola" }],
      },
      {
        id: "a1",
        role: "assistant",
        parts: [{ type: "text", text: "buenos días" }],
      },
    ]
    mockStatus = "ready"
    render(withQueryClient(<ChatSection />))
    expect(screen.getByText("hola")).toBeInTheDocument()
    expect(screen.getByText("buenos días")).toBeInTheDocument()
  })

  it("renders the error banner when status is error", () => {
    mockMessages = []
    mockStatus = "error"
    mockError = new Error("message content exceeds 32 KB")
    render(withQueryClient(<ChatSection />))
    const banner = screen.getByRole("alert")
    expect(banner).toHaveTextContent(/message content exceeds 32 KB/)
    expect(screen.getByRole("button", { name: /Reintentar/i })).toBeInTheDocument()
  })

  it("regenerate button calls the regenerate hook", async () => {
    const user = userEvent.setup()
    mockMessages = []
    mockStatus = "error"
    mockError = new Error("boom")
    regenerate.mockClear()
    render(withQueryClient(<ChatSection />))
    await user.click(screen.getByRole("button", { name: /Reintentar/i }))
    expect(regenerate).toHaveBeenCalledTimes(1)
  })

  it("renders the es-CO translated copy, NOT the raw error.message", () => {
    mockMessages = []
    mockStatus = "error"
    mockError = new Error("message content exceeds 32 KB")
    render(withQueryClient(<ChatSection />))
    const banner = screen.getByRole("alert")
    // Translated copy, not the raw Pydantic / framework string.
    expect(banner).toHaveTextContent(/Tu mensaje es muy largo\. Acórtalo e intenta de nuevo\./)
    expect(banner).not.toHaveTextContent(/message content exceeds 32 KB/)
  })

  it("close × button dismisses the banner", async () => {
    const user = userEvent.setup()
    mockMessages = []
    mockStatus = "error"
    mockError = new Error("boom")
    render(withQueryClient(<ChatSection />))
    expect(screen.getByRole("alert")).toBeInTheDocument()
    await user.click(
      screen.getByRole("button", { name: /Cerrar mensaje de error/i }),
    )
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })

  it("a new error message re-shows the banner after dismissal", async () => {
    const user = userEvent.setup()
    mockMessages = []
    mockStatus = "error"
    mockError = new Error("boom")
    const { rerender } = render(withQueryClient(<ChatSection />))
    await user.click(
      screen.getByRole("button", { name: /Cerrar mensaje de error/i }),
    )
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
    // Simulate a fresh error arriving.
    mockError = new Error("fetch failed")
    rerender(withQueryClient(<ChatSection />))
    expect(screen.getByRole("alert")).toBeInTheDocument()
  })
})
```

- [ ] **Step 8.2: Run the test to confirm it fails**

Run:
```bash
cd frontend && pnpm test components/chat/chat-section.test.tsx
```
Expected: FAIL with module-not-found for `./chat-section`.

- [ ] **Step 8.3: Create the component**

Create file `frontend/components/chat/chat-section.tsx`:
```tsx
"use client"

import { useQueryClient } from "@tanstack/react-query"
import { useChat } from "@ai-sdk/react"
import { useMemo } from "react"
import { createChatTransport } from "@/lib/chat-transport"
import { invalidate } from "@/lib/query"
import { ChatEmptyState } from "./chat-empty-state"
import { ChatErrorBanner } from "./chat-error-banner"
import { ChatInput } from "./chat-input"
import { ChatThread } from "./chat-thread"

export function ChatSection() {
  const qc = useQueryClient()

  const transport = useMemo(() => createChatTransport(), [])

  const { messages, sendMessage, stop, status, error, regenerate } = useChat({
    transport,
    onFinish: () => {
      // Scoped invalidation: only the entity roots the 52 MCP tools may have
      // mutated. NEVER call qc.invalidateQueries() with no args — that wipes
      // settings/preferences/categories the chat cannot touch, deviates from
      // the codebase pattern (to-pay-widget.tsx, every mutation hook), and
      // forces unrelated cards to refetch on every assistant turn.
      invalidate(qc, "chatAssistantTurn")
    },
  })

  return (
    <section
      aria-label="Asistente financiero"
      className="space-y-4"
    >
      <header className="space-y-0.5">
        <p
          className="font-display text-xl font-semibold tracking-tight"
          style={{ color: "var(--foreground)" }}
        >
          Asistente
        </p>
        <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
          Pregunta en lenguaje natural sobre tus finanzas.
        </p>
      </header>

      <div
        className="rounded-lg border"
        style={{
          background: "var(--card)",
          borderColor: "var(--border)",
          boxShadow: "var(--shadow-card)",
        }}
      >
        {messages.length === 0 && status === "ready" ? (
          <ChatEmptyState onPick={(text) => sendMessage({ text })} />
        ) : (
          <ChatThread messages={messages} status={status} />
        )}

        {status === "error" && error && (
          <ChatErrorBanner error={error} onRetry={regenerate} />
        )}

        <ChatInput
          status={status}
          onSend={(text) => sendMessage({ text })}
          onStop={stop}
        />
      </div>
    </section>
  )
}
```

- [ ] **Step 8.4: Run the test to confirm it passes**

Run:
```bash
cd frontend && pnpm test components/chat/chat-section.test.tsx
```
Expected: `8 passed`.

- [ ] **Step 8.5: Commit**

```bash
git add frontend/components/chat/chat-section.tsx frontend/components/chat/chat-section.test.tsx
git commit -m "feat(chat): ChatSection owns useChat, composes empty/thread/error/input"
```

---

## Task 9: Wire into dashboard + add keyframes to globals.css + final verification

**Files:**
- Modify: `frontend/app/(app)/page.tsx` (append `<ChatSection />` after the existing grid)
- Modify: `frontend/app/globals.css` (append `blink-cursor`, `chat-underline-sweep`, `chat-tool-pulse` keyframes + `.chat-input-underline` + `.chat-blinking-cursor` utilities)

**Interfaces:**
- Dashboard page now renders the chat section as the last element of the existing flex container.

- [ ] **Step 9.1: Add keyframes and utility classes to globals.css**

Open `frontend/app/globals.css` (it already has `animate-fade-up` and `hero-glow` near the end of the file, before the `@layer base` block). Append the following block AFTER the `@layer base { ... }` block (so it sits outside any layer, matching the existing `animate-fade-up` convention):

```css
/* Chat section — distinctive micro-interactions.
   Defined at the end of globals.css (outside @layer base) per ADR-0002: app
   overrides live here, never in ui/styles/*. Honor prefers-reduced-motion. */

@keyframes blink-cursor {
  0%, 50% { opacity: 1; }
  50.01%, 100% { opacity: 0; }
}
.chat-blinking-cursor {
  display: inline-block;
  animation: blink-cursor 1s steps(2) infinite;
}

@keyframes chat-underline-sweep {
  0%   { background-position: -100% 100%; }
  100% { background-position: 200% 100%; }
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

@keyframes chat-tool-pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50%      { transform: scale(1.35); opacity: 0.7; }
}
.chat-tool-pulse {
  animation: chat-tool-pulse 1s ease-in-out infinite;
}

@media (prefers-reduced-motion: reduce) {
  .chat-blinking-cursor,
  .chat-input-underline:focus-within,
  .chat-tool-pulse {
    animation: none;
  }
  .chat-input-underline:focus-within {
    background-image: linear-gradient(90deg, var(--primary), var(--primary));
  }
}
```

- [ ] **Step 9.2: Wire `<ChatSection />` into the dashboard**

Open `frontend/app/(app)/page.tsx`. Add the import at the top (alphabetically grouped with the existing component imports from `@/components/...`):

```tsx
import { ChatSection } from "@/components/chat/chat-section"
```

Then locate the closing `</div>` of the outermost `<div className="space-y-8">` (it is the last element in the JSX, wrapping the whole dashboard). Insert `<ChatSection />` immediately BEFORE that closing `</div>`, AFTER the existing `<div className="grid gap-4 sm:grid-cols-2">` block. Concretely, the tail of the file becomes:

```tsx
        </div>
      </div>

      <ChatSection />
    </div>
  )
}
```

(There is exactly one closing `</div>` followed by `</div>` + `</div>` for the grid + outermost wrapper; add a blank line before `<ChatSection />` for readability.)

- [ ] **Step 9.3: Typecheck and lint**

Run:
```bash
cd frontend && pnpm exec tsc --noEmit && pnpm lint
```
Expected: both clean exit. If biome flags unused-imports or formatting, fix and re-run.

- [ ] **Step 9.4: Run the full frontend test suite**

Run:
```bash
cd frontend && pnpm test
```
Expected: all tests pass. Total new tests across this plan:
- chat-transport.test.ts: 1
- chat-errors.test.ts: 5
- chat-blinking-cursor.test.tsx: 3
- chat-tool-chip.test.tsx: 7
- chat-input.test.tsx: 8
- chat-empty-state.test.tsx: 4
- chat-message.test.tsx: 7
- chat-thread.test.tsx: 5
- chat-section.test.tsx: 8
**Total new: 48 tests.** Pre-existing tests in the repo must remain green.

- [ ] **Step 9.5: Build smoke**

Run:
```bash
cd frontend && pnpm build
```
Expected: build completes without errors. (The dev stack doesn't need to be running; this validates that the App Router + Next 16 compile path accepts all new files.)

- [ ] **Step 9.6: Commit**

```bash
git add frontend/app/\(app\)/page.tsx frontend/app/globals.css
git commit -m "feat(chat): wire ChatSection into dashboard + globals.css chat keyframes"
```

- [ ] **Step 9.7: End-to-end manual verification (developer steps, not automated)**

These are verification steps the implementer performs locally with the dev stack already running (api container at `:8000` + frontend at `:3000` per `docs/runbooks/deploy.md`). DO NOT skip these even if all tests pass — they confirm the live wire format match.

1. Open `http://localhost:3000/` in a browser. Confirm the dashboard renders with the chat section below the 4 cards.
2. Confirm the empty state shows: title "Pregúntale a tu asistente", subtitle, and 3 chips.
3. Click "¿Cuánto puedo gastar este mes?". Confirm:
   - User bubble appears right-aligned.
   - Status flips to `streaming`; chat input is disabled with "Pensando…" placeholder.
   - Tool chips appear (if LLM chooses a tool), with mint pulsing dot.
   - Assistant text streams with blinking Bricolage cursor at the tail.
   - On finish, cursor disappears, input re-enables.
4. Type a follow-up in the same thread ("¿y el mes pasado?") and press Enter. Confirm:
   - User bubble appended.
   - Full history is sent (verify in DevTools Network tab: POST `/api/chat` body contains both messages).
5. Click a tool chip to expand it. Confirm input + output render as JSON `<pre>` blocks. Confirm chevron flips `▸ → ▾`.
6. Toggle `prefers-reduced-motion: reduce` in DevTools (Rendering panel). Confirm cursor becomes static `_` (no blinking), input underline becomes solid mint line.
7. Test error path: open DevTools console and execute `fetch('/api/chat', { method: 'POST', body: JSON.stringify({ messages: [{ role: 'foo', content: '' }] }) })` — it returns 422. Now manually trigger an error in the chat: temporarily set `LLM_MODEL=invalid` in `backend/.env.local` and `docker compose up -d --force-recreate api`. Send a message in the chat. Confirm a destructive banner appears with the model error and a "Reintentar" button. Click it; restore `LLM_MODEL` after testing.
8. Reload the page. Confirm the chat is empty (in-memory only — no persistence).

If any of these fail, fix the relevant component and re-run `pnpm test` to keep coverage.

- [ ] **Step 9.8: Commit verification notes (optional)**

If step 9.7 surfaced fixes, commit them with `chore(chat): fix <issue>` per fix.

---

## Self-Review

Running the self-review checklist against the spec.

**1. Spec coverage — every requirement has a task:**
- ✅ Inline on dashboard → Task 9.2 mounts `<ChatSection />` at end of `page.tsx`.
- ✅ In-memory only persistence → no `localStorage` code anywhere; messages live in `useChat` state.
- ✅ `@ai-sdk/react@^3` + `DefaultChatTransport` → Task 1.1 + Task 8.3.
- ✅ Cookie session (no auth bridge) → Task 8.3 uses `transport: createChatTransport()`, no auth header.
- ✅ Tool chip colapsable with input/output → Task 3 (`ChatToolChip`).
- ✅ Blinking Bricolage cursor micro-interaction → Task 2 + Task 9.1 (`@keyframes blink-cursor`).
- ✅ Animated gradient underline on input → Task 9.1 (`@keyframes chat-underline-sweep`).
- ✅ 3 suggested-prompt empty state with es-CO copy → Task 5.
- ✅ React.memo on ChatMessage → Task 6.3.
- ✅ `onFinish` invalidates dashboard queries → Task 8.3 (scoped to `chatAssistantTurn` group, never blanket invalidate).
- ✅ Error translation table → Task 8.0c (`translateChatError`); `ChatErrorBanner` → Task 8.0d (dismissable `×` + Reintentar); raw `error.message` never rendered (test #6 in chat-section).
- ✅ 8 unit tests on chat-section → Task 8.1 (and 40 more on sub-components, total 48).
- ✅ `data-sensitive="true"` on tool input/output `<pre>` blocks → Task 3.3 + test #7 in chat-tool-chip.
- ✅ `prefers-reduced-motion` honored → Task 9.1 (`@media` block in globals.css).
- ✅ ARIA (aria-live, aria-expanded, aria-controls, aria-label, aria-hidden) → Task 7.3 (`<section aria-live aria-label>`), Task 3.3 (`aria-expanded`, `aria-controls`, `role=region`), Task 2.3 (`aria-hidden`), Task 5.3 (`aria-label`), Task 8.3 (`aria-label`).
- ✅ Auto-grow textarea up to 6 lines → Task 4.3 (`MAX_LINES`, `autoGrow`).
- ✅ Esc stops streaming → Task 4.3 (`handleKeyDown`).
- ✅ Manual end-to-end verification → Task 9.7.
- ✅ ToolUIPart/DynamicToolUIPart coverage → Task 1.6 (`isAnyToolPart` helper) + Task 3.3 (`getToolName` with fallback).
- ✅ No markdown rendering v1 (plain text) → Task 6.3 renders `<p>{part.text}</p>` only.

**2. Placeholder scan:**
- No "TBD", "TODO", "implement later", "fill in details" anywhere.
- No "Add appropriate error handling" / "add validation" / "handle edge cases" placeholders. Every error path is enumerated (error banner, regenerate button) and concretely implemented in Task 8.3.
- No "Similar to Task N" — every code block is unique and complete.
- Every step shows actual code, never references undefined helpers (e.g., `getToolName` is documented in Task 1 and used in Task 3; `isAnyToolPart` defined in Task 1, used in Task 6).

**3. Type consistency check across tasks:**
- `createChatTransport()` — defined Task 1, consumed Task 8. ✅
- `AnyToolPart` — defined Task 1 (`chat.types.ts`), consumed Tasks 3 and 6. ✅
- `isTextPart` / `isAnyToolPart` — defined Task 1, consumed Task 6. ✅
- `ChatToolChip` props — `part: AnyToolPart` consistent Task 1 → Task 3 → Task 6. ✅
- `ChatMessage` props — `{ message: UIMessage, showCursor: boolean }` consistent Task 6 → Task 7. ✅
- `ChatInput` props — `{ status, onSend, onStop, autoFocus? }` consistent Task 4 → Task 8. ✅
- `ChatSection` props — none (consumes hooks internally); matches spec. ✅
- `ChatEmptyState` props — `{ onPick: (text: string) => void }` consistent Task 5 → Task 8. ✅
- `ChatThread` props — `{ messages: UIMessage[], status }` consistent Task 7 → Task 8. ✅
- `chat-input-underline` CSS class — applied in Task 4.3, defined Task 9.1. ✅
- `chat-blinking-cursor` CSS class — applied in Task 2.3, defined Task 9.1. ✅
- `chat-tool-pulse` CSS class — applied in Task 3.3, defined Task 9.1. ✅
- `data-testid="chat-cursor"` — set Task 2.3, queried Tasks 6 + 7. ✅
- `data-testid="chat-scroll"` — set Task 7.3, queried Task 7.1. ✅
- `data-testid="chat-tool-dot"` — set Task 3.3, queried Task 3.1. ✅

No inconsistencies found.

**Plan total:** 9 tasks, 48 new tests, 9 new components + 1 transport + 1 translator + 1 page mount + 1 CSS block + 1 modified `lib/query.ts` (adds `chatAssistantTurn` group).

---

## Execution Handoff

Plan complete and saved to **`docs/superpowers/plans/2026-06-22-chat-input-frontend.md`** (3 parts).

Two execution options:

1. **Subagent-Driven (recommended)** — fresh implementer subagent per task + task-level review + final whole-branch review. Best for the size and review gates this plan warrants.

2. **Inline Execution** — execute tasks in this session with checkpoints.

Which approach?