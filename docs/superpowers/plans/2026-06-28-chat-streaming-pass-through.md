# Chat Streaming Pass-Through Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the buffering Next.js rewrite proxy with a streaming pass-through so the chat assistant renders tokens in real time, the way ChatGPT does. Secondary: enable `mode="streaming"` on Streamdown so partial markdown renders without flicker.

**Architecture:** Strategy pattern with two `ResponsePolicy` implementations (`StreamingResponsePolicy`, `BufferedResponsePolicy`) selected by upstream `content-type`. A single `createProxy(req, path)` orchestrator builds the target URL, copies request headers, calls `fetch` with `signal: req.signal`, and delegates response shaping to the chosen policy. Header forwarding (request + response) lives in two isolated modules so the cross-proxy policy is one source of truth.

**Tech Stack:** Next.js 16 (`NextRequest`, `NextResponse`, route handlers), Web Streams (`ReadableStream`, `Response`), Vitest (default env: `happy-dom`; per-test override to `node` when needed for stream iteration), Streamdown 2.5+, React 19.

**Reference spec:** `docs/superpowers/specs/2026-06-28-chat-streaming-pass-through-design.md`

## File Structure

| File | Responsibility |
|---|---|
| `frontend/app/api/[...path]/route.ts` | Thin route handlers (GET/POST/PATCH/DELETE) → `createProxy` |
| `frontend/lib/proxy/create-proxy.ts` | Orchestrator: URL build + fetch + signal + policy selection |
| `frontend/lib/proxy/build-target-url.ts` | Compose backend URL from path + query |
| `frontend/lib/proxy/policies/response-policy.ts` | `ResponsePolicy` interface (Strategy) |
| `frontend/lib/proxy/policies/streaming-response-policy.ts` | SSE / `text/*` pass-through |
| `frontend/lib/proxy/policies/buffered-response-policy.ts` | JSON / 204 / 304 / 205 |
| `frontend/lib/proxy/policies/select-response-policy.ts` | Pick policy by upstream `content-type` |
| `frontend/lib/proxy/forwarding/request-headers.ts` | Request → upstream header copy |
| `frontend/lib/proxy/forwarding/response-headers.ts` | Upstream → response header copy |
| `frontend/lib/proxy/create-proxy.test.ts` | Co-located test (vitest, see env notes) |
| `frontend/lib/proxy/build-target-url.test.ts` | Co-located test |
| `frontend/lib/proxy/policies/select-response-policy.test.ts` | Co-located test |
| `frontend/lib/proxy/policies/streaming-response-policy.test.ts` | Co-located test |
| `frontend/lib/proxy/policies/buffered-response-policy.test.ts` | Co-located test |
| `frontend/lib/proxy/forwarding/request-headers.test.ts` | Co-located test |
| `frontend/lib/proxy/forwarding/response-headers.test.ts` | Co-located test |
| `frontend/components/markdown/markdown.tsx` | Modify: add `mode="streaming"` |

## Global Constraints

- **Code, identifiers, comments, runbooks are English** (ADR-0001). UI strings stay in Spanish.
- **Next 16 docs are required reading** before touching `NextResponse` / route handlers. `frontend/AGENTS.md` warns of breaking changes. Read `node_modules/next/dist/docs/` (route handlers, response APIs, streaming) and verify the `Response(ReadableStream)` API before writing code. If the docs dir is absent in this checkout, use `WebFetch` against the official Next 16 docs page for the corresponding feature.
- **Vitest default env:** `happy-dom`. For any test that iterates a `ReadableStream`, use `// @vitest-environment node` at the top of the file.
- **Tests are co-located** next to source files (`*.test.ts`).
- **Commit frequently.** One commit per task. Conventional commits (`feat:`, `test:`, `refactor:`, `docs:`, `fix:`).
- **Biome formatting** via `pnpm exec biome check --write` before each commit (ADR-0007).
- **No new dependencies.** All code uses built-ins + already-installed libs (`vitest`, `happy-dom`).

---

### Task 1: Header forwarding — request side

**Files:**
- Create: `frontend/lib/proxy/forwarding/request-headers.ts`
- Create: `frontend/lib/proxy/forwarding/request-headers.test.ts`

**Interfaces:**
- Consumes: `NextRequest` from `next/server`.
- Produces: `forwardRequestHeaders(req: NextRequest): Headers` — Headers that downstream code passes to `fetch`.

- [ ] **Step 1: Write the failing test**

Create `frontend/lib/proxy/forwarding/request-headers.test.ts` with `// @vitest-environment node` at the top (happy-dom's Headers polyfill drops the `cookie` header — verified; production Next runtime is fine, but tests must use node env for NextRequest to expose cookies correctly):

```ts
// @vitest-environment node
import { describe, expect, it } from "vitest"
import { NextRequest } from "next/server"
import { forwardRequestHeaders } from "./request-headers"

function req(headers: Record<string, string>): NextRequest {
  return new NextRequest(new Request("http://localhost/api/x", { headers }))
}

describe("forwardRequestHeaders", () => {
  it("copies content-type when present", () => {
    const out = forwardRequestHeaders(req({ "content-type": "application/json" }))
    expect(out.get("content-type")).toBe("application/json")
  })

  it("copies cookie when present", () => {
    const out = forwardRequestHeaders(req({ cookie: "session=abc" }))
    expect(out.get("cookie")).toBe("session=abc")
  })

  it("copies x-csrf-token when present", () => {
    const out = forwardRequestHeaders(req({ "x-csrf-token": "tok" }))
    expect(out.get("x-csrf-token")).toBe("tok")
  })

  it("copies authorization when present", () => {
    const out = forwardRequestHeaders(req({ authorization: "Bearer app-token" }))
    expect(out.get("authorization")).toBe("Bearer app-token")
  })

  it("omits headers that are absent", () => {
    const out = forwardRequestHeaders(req({}))
    expect(out.has("content-type")).toBe(false)
    expect(out.has("cookie")).toBe(false)
    expect(out.has("x-csrf-token")).toBe(false)
    expect(out.has("authorization")).toBe(false)
  })

  it("does not forward unrelated headers like x-custom", () => {
    const out = forwardRequestHeaders(req({ "x-custom": "drop-me" }))
    expect(out.has("x-custom")).toBe(false)
  })
})
```

- [ ] **Step 2: Run the test, verify it fails**

Run: `cd frontend && pnpm vitest run lib/proxy/forwarding/request-headers.test.ts`
Expected: FAIL — module `./request-headers` does not exist.

- [ ] **Step 3: Implement**

Create `frontend/lib/proxy/forwarding/request-headers.ts`:

```ts
import type { NextRequest } from "next/server"

/**
 * Build the header set forwarded from the incoming request to the upstream
 * backend. Centralized here so the cross-proxy policy is a single source
 * of truth: cookie (session auth), x-csrf-token (CSRF double-submit
 * cookie, ADR-0020), authorization (APP_TOKEN fallback), content-type.
 * Other headers do not cross the boundary.
 */
export function forwardRequestHeaders(req: NextRequest): Headers {
  const out = new Headers()
  const contentType = req.headers.get("content-type")
  if (contentType) out.set("content-type", contentType)
  const cookie = req.headers.get("cookie")
  if (cookie) out.set("cookie", cookie)
  const csrf = req.headers.get("x-csrf-token")
  if (csrf) out.set("x-csrf-token", csrf)
  const auth = req.headers.get("authorization")
  if (auth) out.set("authorization", auth)
  return out
}
```

- [ ] **Step 4: Run the test, verify it passes**

Run: `cd frontend && pnpm vitest run lib/proxy/forwarding/request-headers.test.ts`
Expected: PASS, 6 tests passing.

- [ ] **Step 5: Format and commit**

```bash
cd frontend && pnpm exec biome check --write lib/proxy/forwarding/
git add frontend/lib/proxy/forwarding/request-headers.ts frontend/lib/proxy/forwarding/request-headers.test.ts
git commit -m "feat(proxy): forwardRequestHeaders — request header policy"
```

---

### Task 2: Header forwarding — response side

**Files:**
- Create: `frontend/lib/proxy/forwarding/response-headers.ts`
- Create: `frontend/lib/proxy/forwarding/response-headers.test.ts`

**Interfaces:**
- Consumes: `upstream: Response`.
- Produces: `forwardResponseHeaders(upstream: Response): Headers` — Headers that the policy attaches to the outgoing Response.

- [ ] **Step 1: Write the failing test**

Create `frontend/lib/proxy/forwarding/response-headers.test.ts`:

```ts
import { describe, expect, it } from "vitest"
import { forwardResponseHeaders } from "./response-headers"

describe("forwardResponseHeaders", () => {
  it("copies content-type from upstream", () => {
    const upstream = new Response("body", { headers: { "content-type": "application/json" } })
    const out = forwardResponseHeaders(upstream)
    expect(out.get("content-type")).toBe("application/json")
  })

  it("preserves every set-cookie value as separate header", () => {
    const upstream = new Response(null, {
      headers: [
        ["set-cookie", "quaestor_csrf=abc; Path=/"],
        ["set-cookie", "session=xyz; HttpOnly"],
      ],
    })
    const out = forwardResponseHeaders(upstream)
    const cookies = out.getSetCookie()
    expect(cookies).toEqual([
      "quaestor_csrf=abc; Path=/",
      "session=xyz; HttpOnly",
    ])
  })

  it("returns empty Headers when upstream has no relevant headers", () => {
    // Use `null` body so Node's Response constructor doesn't auto-inject
    // `content-type: text/plain;charset=UTF-8` for string bodies.
    const upstream = new Response(null)
    const out = forwardResponseHeaders(upstream)
    expect(out.has("content-type")).toBe(false)
    expect(out.getSetCookie()).toEqual([])
  })
})
```

- [ ] **Step 2: Run the test, verify it fails**

Run: `cd frontend && pnpm vitest run lib/proxy/forwarding/response-headers.test.ts`
Expected: FAIL — module `./response-headers` does not exist.

- [ ] **Step 3: Implement**

Create `frontend/lib/proxy/forwarding/response-headers.ts`:

```ts
/**
 * Build the header set forwarded from the upstream backend to the outgoing
 * browser response. Copies content-type and every set-cookie value
 * (preserving multiplicity — Headers.getSetCookie returns the full array).
 */
export function forwardResponseHeaders(upstream: Response): Headers {
  const out = new Headers()
  const contentType = upstream.headers.get("content-type")
  if (contentType) out.set("content-type", contentType)
  for (const cookie of upstream.headers.getSetCookie()) {
    out.append("set-cookie", cookie)
  }
  return out
}
```

- [ ] **Step 4: Run the test, verify it passes**

Run: `cd frontend && pnpm vitest run lib/proxy/forwarding/response-headers.test.ts`
Expected: PASS, 3 tests passing.

- [ ] **Step 5: Format and commit**

```bash
cd frontend && pnpm exec biome check --write lib/proxy/forwarding/
git add frontend/lib/proxy/forwarding/response-headers.ts frontend/lib/proxy/forwarding/response-headers.test.ts
git commit -m "feat(proxy): forwardResponseHeaders — upstream→browser header policy"
```

---

### Task 3: buildTargetUrl

**Files:**
- Create: `frontend/lib/proxy/build-target-url.ts`
- Create: `frontend/lib/proxy/build-target-url.test.ts`

**Interfaces:**
- Consumes: `path: string[]`, `search: string`, `API_URL` env.
- Produces: `buildTargetUrl(path: string[], search: string): string`.

- [ ] **Step 1: Write the failing test**

Create `frontend/lib/proxy/build-target-url.test.ts`:

```ts
// @vitest-environment node
import { describe, expect, it } from "vitest"
import { buildTargetUrl } from "./build-target-url"

describe("buildTargetUrl", () => {
  it("joins path segments under /api", () => {
    const url = buildTargetUrl(["chat"], "")
    expect(url).toBe("http://localhost:8000/api/chat")
  })

  it("joins nested path segments", () => {
    const url = buildTargetUrl(["accounts", "42"], "")
    expect(url).toBe("http://localhost:8000/api/accounts/42")
  })

  it("appends search string verbatim", () => {
    const url = buildTargetUrl(["categories"], "?limit=10&offset=0")
    expect(url).toBe("http://localhost:8000/api/categories?limit=10&offset=0")
  })

  it("handles empty path (root)", () => {
    const url = buildTargetUrl([], "")
    expect(url).toBe("http://localhost:8000/api/")
  })

  it("respects a custom API_URL", () => {
    process.env.API_URL = "https://api.example.test"
    const url = buildTargetUrl(["chat"], "")
    expect(url).toBe("https://api.example.test/api/chat")
    process.env.API_URL = "http://localhost:8000"
  })
})
```

- [ ] **Step 2: Run the test, verify it fails**

Run: `cd frontend && pnpm vitest run lib/proxy/build-target-url.test.ts`
Expected: FAIL — module `./build-target-url` does not exist.

- [ ] **Step 3: Implement**

Create `frontend/lib/proxy/build-target-url.ts`:

```ts
/**
 * Compose the backend URL for the rewrite proxy.
 * Single source of truth for "how does /api/<x> map to upstream".
 */
export function buildTargetUrl(path: string[], search: string): string {
  const base = process.env.API_URL ?? "http://localhost:8000"
  return `${base}/api/${path.join("/")}${search}`
}
```

- [ ] **Step 4: Run the test, verify it passes**

Run: `cd frontend && pnpm vitest run lib/proxy/build-target-url.test.ts`
Expected: PASS, 5 tests passing.

- [ ] **Step 5: Format and commit**

```bash
cd frontend && pnpm exec biome check --write lib/proxy/build-target-url.ts lib/proxy/build-target-url.test.ts
git add frontend/lib/proxy/build-target-url.ts frontend/lib/proxy/build-target-url.test.ts
git commit -m "feat(proxy): buildTargetUrl — URL composition"
```

---

### Task 4: ResponsePolicy interface

**Files:**
- Create: `frontend/lib/proxy/policies/response-policy.ts`

**Interfaces:**
- Consumes: upstream `Response`.
- Produces: `ResponsePolicy` interface with `build(upstream: Response): Response | Promise<Response>`.

(No test for the interface itself — pure type. Tested via the two implementations and the selector.)

- [ ] **Step 1: Implement**

Create `frontend/lib/proxy/policies/response-policy.ts`:

```ts
/**
 * Strategy for shaping the outgoing browser response from an upstream
 * backend response. Two implementations: streaming (SSE / text/*) and
 * buffered (JSON / 204 / 304). Selected by content-type at runtime.
 */
export interface ResponsePolicy {
  build(upstream: Response): Response | Promise<Response>
}
```

- [ ] **Step 2: Commit**

```bash
cd frontend && pnpm exec biome check --write lib/proxy/policies/response-policy.ts
git add frontend/lib/proxy/policies/response-policy.ts
git commit -m "feat(proxy): ResponsePolicy interface (Strategy)"
```

---

### Task 5: StreamingResponsePolicy

**Files:**
- Create: `frontend/lib/proxy/policies/streaming-response-policy.ts`
- Create: `frontend/lib/proxy/policies/streaming-response-policy.test.ts`

**Interfaces:**
- Consumes: upstream `Response`.
- Produces: `new Response(upstream.body, { status, headers })` — body is the upstream `ReadableStream`, untouched.

- [ ] **Step 1: Write the failing test**

Create `frontend/lib/proxy/policies/streaming-response-policy.test.ts`:

```ts
// @vitest-environment node
import { describe, expect, it } from "vitest"
import { StreamingResponsePolicy } from "./streaming-response-policy"

describe("StreamingResponsePolicy", () => {
  it("passes upstream.body through unchanged as a ReadableStream", async () => {
    const upstream = new Response(
      new ReadableStream({
        start(controller) {
          controller.enqueue(new TextEncoder().encode("chunk-1\n"))
          controller.enqueue(new TextEncoder().encode("chunk-2\n"))
          controller.close()
        },
      }),
      {
        status: 200,
        headers: { "content-type": "text/event-stream" },
      },
    )
    const policy = new StreamingResponsePolicy()
    const out = await policy.build(upstream)
    expect(out.status).toBe(200)
    expect(out.headers.get("content-type")).toBe("text/event-stream")
    expect(out.body).toBeInstanceOf(ReadableStream)
    const reader = out.body!.getReader()
    const decoder = new TextDecoder()
    const parts: string[] = []
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      parts.push(decoder.decode(value))
    }
    expect(parts.join("")).toBe("chunk-1\nchunk-2\n")
  })

  it("handles upstream with null body (defensive)", async () => {
    const upstream = new Response(null, { status: 200 })
    const policy = new StreamingResponsePolicy()
    const out = await policy.build(upstream)
    expect(out.status).toBe(200)
    expect(out.body).toBeNull()
  })
})
```

- [ ] **Step 2: Run the test, verify it fails**

Run: `cd frontend && pnpm vitest run lib/proxy/policies/streaming-response-policy.test.ts`
Expected: FAIL — module `./streaming-response-policy` does not exist.

- [ ] **Step 3: Implement**

Create `frontend/lib/proxy/policies/streaming-response-policy.ts`:

```ts
import { forwardResponseHeaders } from "../forwarding/response-headers"
import type { ResponsePolicy } from "./response-policy"

/**
 * Pass-through strategy for streaming responses (SSE, text/*). Hands the
 * upstream `ReadableStream` directly to the outgoing `Response` so bytes
 * flow to the browser as the LLM emits them. Zero buffering. Status and
 * headers are forwarded via the response-headers module.
 */
export class StreamingResponsePolicy implements ResponsePolicy {
  async build(upstream: Response): Promise<Response> {
    return new Response(upstream.body, {
      status: upstream.status,
      headers: forwardResponseHeaders(upstream),
    })
  }
}
```

- [ ] **Step 4: Run the test, verify it passes**

Run: `cd frontend && pnpm vitest run lib/proxy/policies/streaming-response-policy.test.ts`
Expected: PASS, 2 tests passing.

- [ ] **Step 5: Format and commit**

```bash
cd frontend && pnpm exec biome check --write lib/proxy/policies/streaming-response-policy.ts lib/proxy/policies/streaming-response-policy.test.ts
git add frontend/lib/proxy/policies/streaming-response-policy.ts frontend/lib/proxy/policies/streaming-response-policy.test.ts
git commit -m "feat(proxy): StreamingResponsePolicy — SSE pass-through"
```

---

### Task 6: BufferedResponsePolicy

**Files:**
- Create: `frontend/lib/proxy/policies/buffered-response-policy.ts`
- Create: `frontend/lib/proxy/policies/buffered-response-policy.test.ts`

**Interfaces:**
- Consumes: upstream `Response`.
- Produces: `Response` whose body is the upstream text. 204/205/304 → `null` body.

- [ ] **Step 1: Write the failing test**

Create `frontend/lib/proxy/policies/buffered-response-policy.test.ts`:

```ts
// @vitest-environment node
import { describe, expect, it } from "vitest"
import { BufferedResponsePolicy } from "./buffered-response-policy"

describe("BufferedResponsePolicy", () => {
  it("awaits upstream text and returns it as body", async () => {
    const upstream = new Response('{"ok":true}', {
      status: 200,
      headers: { "content-type": "application/json" },
    })
    const policy = new BufferedResponsePolicy()
    const out = await policy.build(upstream)
    expect(out.status).toBe(200)
    expect(out.headers.get("content-type")).toBe("application/json")
    expect(await out.text()).toBe('{"ok":true}')
  })

  it("returns null body for 204", async () => {
    const upstream = new Response(null, { status: 204 })
    const policy = new BufferedResponsePolicy()
    const out = await policy.build(upstream)
    expect(out.status).toBe(204)
    expect(out.body).toBeNull()
  })

  it("returns null body for 304", async () => {
    const upstream = new Response(null, { status: 304 })
    const policy = new BufferedResponsePolicy()
    const out = await policy.build(upstream)
    expect(out.status).toBe(304)
    expect(out.body).toBeNull()
  })

  it("returns null body for 205", async () => {
    const upstream = new Response(null, { status: 205 })
    const policy = new BufferedResponsePolicy()
    const out = await policy.build(upstream)
    expect(out.status).toBe(205)
    expect(out.body).toBeNull()
  })

  it("forwards set-cookie headers", async () => {
    const upstream = new Response("body", {
      headers: [
        ["set-cookie", "quaestor_csrf=tok; Path=/"],
      ],
    })
    const policy = new BufferedResponsePolicy()
    const out = await policy.build(upstream)
    expect(out.headers.getSetCookie()).toEqual(["quaestor_csrf=tok; Path=/"])
  })
})
```

- [ ] **Step 2: Run the test, verify it fails**

Run: `cd frontend && pnpm vitest run lib/proxy/policies/buffered-response-policy.test.ts`
Expected: FAIL — module `./buffered-response-policy` does not exist.

- [ ] **Step 3: Implement**

Create `frontend/lib/proxy/policies/buffered-response-policy.ts`:

```ts
import { forwardResponseHeaders } from "../forwarding/response-headers"
import type { ResponsePolicy } from "./response-policy"

const NO_BODY_STATUSES = new Set([204, 205, 304])

/**
 * Buffered strategy for discrete payloads (JSON, HTML, plain text). Reads
 * the full upstream body and returns it as a string. Status codes that
 * forbid a response body (204, 205, 304) are short-circuited to `null`.
 */
export class BufferedResponsePolicy implements ResponsePolicy {
  async build(upstream: Response): Promise<Response> {
    if (NO_BODY_STATUSES.has(upstream.status)) {
      return new Response(null, {
        status: upstream.status,
        headers: forwardResponseHeaders(upstream),
      })
    }
    const text = await upstream.text()
    return new Response(text, {
      status: upstream.status,
      headers: forwardResponseHeaders(upstream),
    })
  }
}
```

- [ ] **Step 4: Run the test, verify it passes**

Run: `cd frontend && pnpm vitest run lib/proxy/policies/buffered-response-policy.test.ts`
Expected: PASS, 5 tests passing.

- [ ] **Step 5: Format and commit**

```bash
cd frontend && pnpm exec biome check --write lib/proxy/policies/buffered-response-policy.ts lib/proxy/policies/buffered-response-policy.test.ts
git add frontend/lib/proxy/policies/buffered-response-policy.ts frontend/lib/proxy/policies/buffered-response-policy.test.ts
git commit -m "feat(proxy): BufferedResponsePolicy — JSON/204/304/205"
```

---

### Task 7: selectResponsePolicy

**Files:**
- Create: `frontend/lib/proxy/policies/select-response-policy.ts`
- Create: `frontend/lib/proxy/policies/select-response-policy.test.ts`

**Interfaces:**
- Consumes: upstream `Response`.
- Produces: `selectResponsePolicy(upstream: Response): ResponsePolicy`.

- [ ] **Step 1: Write the failing test**

Create `frontend/lib/proxy/policies/select-response-policy.test.ts`:

```ts
import { describe, expect, it } from "vitest"
import { selectResponsePolicy } from "./select-response-policy"
import { StreamingResponsePolicy } from "./streaming-response-policy"
import { BufferedResponsePolicy } from "./buffered-response-policy"

describe("selectResponsePolicy", () => {
  it("returns streaming for text/event-stream", () => {
    const u = new Response(null, { headers: { "content-type": "text/event-stream" } })
    expect(selectResponsePolicy(u)).toBeInstanceOf(StreamingResponsePolicy)
  })

  it("returns streaming for text/plain", () => {
    const u = new Response(null, { headers: { "content-type": "text/plain" } })
    expect(selectResponsePolicy(u)).toBeInstanceOf(StreamingResponsePolicy)
  })

  it("returns streaming for any text/* content-type", () => {
    const u = new Response(null, { headers: { "content-type": "text/html; charset=utf-8" } })
    expect(selectResponsePolicy(u)).toBeInstanceOf(StreamingResponsePolicy)
  })

  it("returns buffered for application/json", () => {
    const u = new Response(null, { headers: { "content-type": "application/json" } })
    expect(selectResponsePolicy(u)).toBeInstanceOf(BufferedResponsePolicy)
  })

  it("returns buffered when content-type is missing", () => {
    const u = new Response(null)
    expect(selectResponsePolicy(u)).toBeInstanceOf(BufferedResponsePolicy)
  })
})
```

- [ ] **Step 2: Run the test, verify it fails**

Run: `cd frontend && pnpm vitest run lib/proxy/policies/select-response-policy.test.ts`
Expected: FAIL — module `./select-response-policy` does not exist.

- [ ] **Step 3: Implement**

Create `frontend/lib/proxy/policies/select-response-policy.ts`:

```ts
import { BufferedResponsePolicy } from "./buffered-response-policy"
import type { ResponsePolicy } from "./response-policy"
import { StreamingResponsePolicy } from "./streaming-response-policy"

/**
 * Pick a response-shaping policy from the upstream content-type. Any
 * `text/*` response (including SSE) goes through the streaming path;
 * everything else is buffered. Missing content-type falls back to
 * buffered (safe default — streaming endpoints always set the header).
 */
export function selectResponsePolicy(upstream: Response): ResponsePolicy {
  const contentType = upstream.headers.get("content-type") ?? ""
  if (contentType.toLowerCase().startsWith("text/")) {
    return new StreamingResponsePolicy()
  }
  return new BufferedResponsePolicy()
}
```

- [ ] **Step 4: Run the test, verify it passes**

Run: `cd frontend && pnpm vitest run lib/proxy/policies/select-response-policy.test.ts`
Expected: PASS, 5 tests passing.

- [ ] **Step 5: Format and commit**

```bash
cd frontend && pnpm exec biome check --write lib/proxy/policies/select-response-policy.ts lib/proxy/policies/select-response-policy.test.ts
git add frontend/lib/proxy/policies/select-response-policy.ts frontend/lib/proxy/policies/select-response-policy.test.ts
git commit -m "feat(proxy): selectResponsePolicy — content-type → policy"
```

---

### Task 8: createProxy orchestrator (the heart of the fix)

**Files:**
- Create: `frontend/lib/proxy/create-proxy.ts`
- Create: `frontend/lib/proxy/create-proxy.test.ts`

**Interfaces:**
- Consumes: `NextRequest`, `path: string[]`.
- Produces: `createProxy(req: NextRequest, path: string[]): Promise<Response>`.

- [ ] **Step 1: Write the failing test**

Create `frontend/lib/proxy/create-proxy.test.ts`:

```ts
// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { NextRequest } from "next/server"
import { createProxy } from "./create-proxy"

interface FetchCall {
  url: string
  init: RequestInit
}

let lastFetch: FetchCall | null = null
let fetchImpl: typeof fetch = vi.fn(async (input, init) => {
  lastFetch = { url: String(input), init: init ?? {} }
  return new Response("unused", { status: 500 })
})

beforeEach(() => {
  lastFetch = null
  vi.stubGlobal("fetch", fetchImpl)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function req(opts: { method?: string; headers?: Record<string, string>; body?: string; signal?: AbortSignal } = {}): NextRequest {
  const r = new Request("http://localhost/api/chat", {
    method: opts.method ?? "POST",
    headers: opts.headers ?? { "content-type": "application/json", "x-csrf-token": "csrf-tok" },
    body: opts.body,
    signal: opts.signal,
  })
  return new NextRequest(r)
}

describe("createProxy", () => {
  it("returns a Response with a ReadableStream body for text/event-stream (streaming path)", async () => {
    const upstreamStream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode("data: {\"type\":\"text-delta\"}\n\n"))
        controller.enqueue(new TextEncoder().encode("data: [DONE]\n\n"))
        controller.close()
      },
    })
    fetchImpl = vi.fn(async () =>
      new Response(upstreamStream, {
        status: 200,
        headers: { "content-type": "text/event-stream" },
      }),
    ) as typeof fetch
    vi.stubGlobal("fetch", fetchImpl)

    const response = await createProxy(req(), ["chat"])
    expect(response.headers.get("content-type")).toBe("text/event-stream")
    expect(response.body).toBeInstanceOf(ReadableStream)
    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    const out: string[] = []
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      out.push(decoder.decode(value))
    }
    expect(out.join("")).toBe("data: {\"type\":\"text-delta\"}\n\ndata: [DONE]\n\n")
  })

  it("returns a Response whose body is a string for application/json (buffered path)", async () => {
    fetchImpl = vi.fn(async () =>
      new Response('{"ok":true}', {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    ) as typeof fetch
    vi.stubGlobal("fetch", fetchImpl)

    const response = await createProxy(req(), ["accounts"])
    expect(await response.text()).toBe('{"ok":true}')
  })

  it("returns null body for 204 (buffered short-circuit)", async () => {
    fetchImpl = vi.fn(async () => new Response(null, { status: 204 })) as typeof fetch
    vi.stubGlobal("fetch", fetchImpl)

    const response = await createProxy(req({ method: "DELETE" }), ["accounts", "42"])
    expect(response.status).toBe(204)
    expect(response.body).toBeNull()
  })

  it("forwards request headers (content-type, cookie, x-csrf-token, authorization)", async () => {
    const ac = new AbortController()
    fetchImpl = vi.fn(async () => new Response(null, { status: 200 })) as typeof fetch
    vi.stubGlobal("fetch", fetchImpl)
    await createProxy(
      req({
        headers: {
          "content-type": "application/json",
          cookie: "session=abc",
          "x-csrf-token": "csrf-1",
          authorization: "Bearer app",
          "x-drop-me": "nope",
        },
        signal: ac.signal,
      }),
      ["categories"],
    )
    const call = lastFetch!
    const h = call.init.headers as Headers
    expect(h.get("content-type")).toBe("application/json")
    expect(h.get("cookie")).toBe("session=abc")
    expect(h.get("x-csrf-token")).toBe("csrf-1")
    expect(h.get("authorization")).toBe("Bearer app")
    expect(h.has("x-drop-me")).toBe(false)
  })

  it("propagates request abort signal to upstream fetch", async () => {
    const ac = new AbortController()
    fetchImpl = vi.fn(async (_input, init) => {
      return new Promise<Response>((_, reject) => {
        init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")))
      })
    }) as typeof fetch
    vi.stubGlobal("fetch", fetchImpl)
    ac.abort()
    await expect(createProxy(req({ signal: ac.signal }), ["chat"])).rejects.toThrow()
    expect((lastFetch!.init.signal as AbortSignal).aborted).toBe(true)
  })

  it("builds the target URL by joining path segments and preserving query string", async () => {
    fetchImpl = vi.fn(async () => new Response(null, { status: 200 })) as typeof fetch
    vi.stubGlobal("fetch", fetchImpl)
    await createProxy(req(), ["transactions", "list"])
    expect(lastFetch!.url).toBe("http://localhost:8000/api/transactions/list")
  })

  it("preserves set-cookie from upstream in the outgoing response", async () => {
    fetchImpl = vi.fn(async () =>
      new Response(null, {
        status: 200,
        headers: [["set-cookie", "new-cookie=value; Path=/"]],
      }),
    ) as typeof fetch
    vi.stubGlobal("fetch", fetchImpl)
    const response = await createProxy(req(), ["x"])
    expect(response.headers.getSetCookie()).toEqual(["new-cookie=value; Path=/"])
  })
})
```

- [ ] **Step 2: Run the test, verify it fails**

Run: `cd frontend && pnpm vitest run lib/proxy/create-proxy.test.ts`
Expected: FAIL — module `./create-proxy` does not exist.

- [ ] **Step 3: Implement**

Create `frontend/lib/proxy/create-proxy.ts`:

```ts
import type { NextRequest } from "next/server"
import { buildTargetUrl } from "./build-target-url"
import { forwardRequestHeaders } from "./forwarding/request-headers"
import { selectResponsePolicy } from "./policies/select-response-policy"

/**
 * Orchestrator for the Next.js → FastAPI rewrite. Builds the upstream URL,
 * forwards request headers, calls `fetch` with the request's AbortSignal so
 * client disconnects cancel the LLM call, then delegates response shaping
 * to the policy chosen by upstream content-type.
 *
 * Response policies (Strategy pattern):
 *  - text/* (SSE, plain text) → StreamingResponsePolicy: hands the
 *    upstream ReadableStream straight to the browser. Zero buffering.
 *  - everything else → BufferedResponsePolicy: awaits text, returns it.
 *
 * See docs/superpowers/specs/2026-06-28-chat-streaming-pass-through-design.md
 * for the design rationale.
 */
export async function createProxy(req: NextRequest, path: string[]): Promise<Response> {
  const target = buildTargetUrl(path, req.nextUrl.search)
  const upstream = await fetch(target, {
    method: req.method,
    headers: forwardRequestHeaders(req),
    body: await readRequestBody(req),
    redirect: "manual",
    cache: "no-store",
    signal: req.signal,
  })
  const policy = selectResponsePolicy(upstream)
  return policy.build(upstream)
}

async function readRequestBody(req: NextRequest): Promise<BodyInit | undefined> {
  if (req.method === "GET" || req.method === "HEAD") return undefined
  return req.text()
}
```

- [ ] **Step 4: Run the test, verify it passes**

Run: `cd frontend && pnpm vitest run lib/proxy/create-proxy.test.ts`
Expected: PASS, 7 tests passing.

- [ ] **Step 5: Format and commit**

```bash
cd frontend && pnpm exec biome check --write lib/proxy/create-proxy.ts lib/proxy/create-proxy.test.ts
git add frontend/lib/proxy/create-proxy.ts lib/proxy/create-proxy.test.ts
git commit -m "feat(proxy): createProxy orchestrator — streaming + abort propagation"
```

---

### Task 9: Rewrite route.ts to use createProxy

**Files:**
- Modify: `frontend/app/api/[...path]/route.ts`

**Interfaces:**
- Consumes: `createProxy` from `frontend/lib/proxy/create-proxy`.
- Produces: GET, POST, PATCH, DELETE route handlers that delegate to `createProxy`.

- [ ] **Step 1: Replace the file contents**

Overwrite `frontend/app/api/[...path]/route.ts` with:

```ts
import { type NextRequest } from "next/server"
import { createProxy } from "@/lib/proxy/create-proxy"

type Ctx = { params: Promise<{ path: string[] }> }

const handler = async (req: NextRequest, ctx: Ctx) =>
  createProxy(req, (await ctx.params).path)

export const GET = handler
export const POST = handler
export const PATCH = handler
export const DELETE = handler
```

- [ ] **Step 2: Verify TypeScript**

Run: `cd frontend && pnpm exec tsc --noEmit`
Expected: no errors. If Next 16 has a different signature for `NextRequest` / route handler return type, adjust per the docs read in Task 1's note. Common fix: ensure `handler` returns `Promise<Response>` (which `createProxy` already does).

- [ ] **Step 3: Run the full proxy test suite**

Run: `cd frontend && pnpm vitest run lib/proxy/`
Expected: PASS — all tests across forwarding/, policies/, and create-proxy.

- [ ] **Step 4: Commit**

```bash
cd frontend && pnpm exec biome check --write app/api/
git add frontend/app/api/[...path]/route.ts
git commit -m "refactor(route): /api/[...path] delegates to createProxy"
```

---

### Task 10: Streamdown — mode="streaming"

**Files:**
- Modify: `frontend/components/markdown/markdown.tsx`

- [ ] **Step 1: Add the mode prop**

Edit `frontend/components/markdown/markdown.tsx`. Replace the Streamdown line:

```tsx
<Streamdown className={className} components={markdownComponents}>
  {children}
</Streamdown>
```

with:

```tsx
<Streamdown mode="streaming" className={className} components={markdownComponents}>
  {children}
</Streamdown>
```

- [ ] **Step 2: Verify TypeScript**

Run: `cd frontend && pnpm exec tsc --noEmit`
Expected: no errors. If Streamdown's d.ts expects a different `mode` literal, check `streamdown` README / types and adjust. Per spec, `mode: "static" | "streaming"` is accepted as optional.

- [ ] **Step 3: Commit**

```bash
cd frontend && pnpm exec biome check --write components/markdown/markdown.tsx
git add frontend/components/markdown/markdown.tsx
git commit -m "fix(chat): enable Streamdown streaming mode for incremental markdown"
```

---

### Task 11: Manual verification

**Files:** none (verification only).

- [ ] **Step 1: Run all proxy tests**

```bash
cd frontend && pnpm vitest run lib/proxy/
```
Expected: PASS, all tests across forwarding/, policies/, and create-proxy.

- [ ] **Step 2: Type-check the whole frontend**

```bash
cd frontend && pnpm exec tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Start the app and exercise the chat**

```bash
# in backend/
cd backend && uvicorn quaestor.main:app --reload
# in frontend/  (separate terminal)
cd frontend && pnpm dev
```

- Open `http://localhost:3000`, navigate to the chat section.
- Open DevTools → Network → filter by `/api/chat`.
- Send a prompt. Expected: response rows arrive in chunks every ~100-500ms, NOT a single chunk at `[DONE]`.
- Observe the assistant text appearing token by token. Expected: bold, lists, and code fences render smoothly without re-parse flicker.

- [ ] **Step 4: Verify abort propagation**

- Start a long-running chat request (large prompt or tool-heavy turn).
- Navigate away from the chat (or close the tab) mid-stream.
- In the backend log, expect: the LLM call ends within a few hundred ms of navigation. No full response is generated.
- If the call continues to completion, the abort signal did not propagate; revisit Task 8 and confirm `signal: req.signal` is passed.

- [ ] **Step 5: Final commit if any cleanup needed**

If the verification surfaced a fix (e.g. content-type detection tweak), commit it:

```bash
cd frontend && pnpm exec biome check --write .
git add -A
git commit -m "fix(proxy): <describe the tweak>"
```

---

## Self-Review

**1. Spec coverage:**

- Replace god-function rewrite with Strategy pattern: Tasks 1-9.
- Two policies (streaming + buffered): Tasks 4-7.
- Selector by content-type: Task 7.
- Abort signal propagation: Task 8 (orchestrator), tested in Task 8.
- Header forwarding centralized: Tasks 1, 2.
- Streamdown `mode="streaming"`: Task 10.
- Manual verification: Task 11.
- Co-located vitest tests per spec: every module's `*.test.ts`.
- Reuse happy-dom default with per-file `node` env for stream tests: applied in Tasks 5, 6, 7, 8.
- Next 16 docs caveat: noted in Global Constraints + Task 9 step 2.
- 204/205/304 short-circuit: Task 6 (BufferedResponsePolicy), tested.
- `signal: req.signal` abort: Task 8 implementation + test.

Gaps: none identified.

**2. Placeholder scan:**

- No "TBD"/"TODO"/"implement later".
- Every code step shows full code, not pseudocode.
- No "similar to Task N" — each test and impl is explicit.
- All function names match across tasks (`forwardRequestHeaders`, `forwardResponseHeaders`, `buildTargetUrl`, `StreamingResponsePolicy`, `BufferedResponsePolicy`, `selectResponsePolicy`, `createProxy`, `ResponsePolicy`).

**3. Type consistency:**

- `ResponsePolicy.build(upstream: Response): Response | Promise<Response>` — same in Tasks 4, 5, 6.
- `StreamingResponsePolicy` constructed via `new` in Task 7 selector and Task 8 orchestrator — consistent.
- `BufferedResponsePolicy` likewise — consistent.
- `NO_BODY_STATUSES = [204, 205, 304]` — used only in Task 6, no cross-task reference.
- `forwardRequestHeaders(req: NextRequest): Headers` — used in Task 8, matches Task 1's signature.
- `forwardResponseHeaders(upstream: Response): Headers` — used in Tasks 5, 6, matches Task 2's signature.
- `buildTargetUrl(path: string[], search: string): string` — used in Task 8, matches Task 3's signature.

No fixes needed.