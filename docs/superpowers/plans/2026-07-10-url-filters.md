# URL Query Params as Filter Source of Truth — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the URL query string the single source of truth for list-view filters, via one agnostic reusable hook.

**Architecture:** A custom `useUrlFilters(schema)` hook built on Next.js 16 App Router primitives (`useSearchParams`, `useRouter`, `usePathname`) plus Zod codecs. Views declare a module-level schema of typed params; the hook derives typed values from the URL and writes changes back with `router.replace`. No new dependency; `nuqs` was rejected (see ADR-0027).

**Tech Stack:** Next.js 16 (App Router), React 19, TypeScript, Zod v4, TanStack Query, Vitest + Testing Library, Biome, pnpm.

## Global Constraints

- Package manager is **pnpm** only (ADR-0003). All commands use `pnpm`.
- All code, identifiers, and comments in **English** (ADR-0001). User-facing UI copy stays **Spanish** (existing convention).
- **Zod v4** is the validation library (ADR-0008). Import `{ z } from "zod"`.
- Format/lint via **Biome**; run `pnpm check` before each commit (ADR-0007).
- **No new npm dependencies.**
- Next.js 16 App Router: before using a Next API, consult `node_modules/next/dist/docs/` (`frontend/AGENTS.md`). Confirmed APIs: `useSearchParams()` (read-only `URLSearchParams`), `useRouter().replace(href, { scroll })`, `usePathname()` — all from `next/navigation`.
- Filter behavior: URL is source of truth; history mode is **replace**; default/empty values are **omitted** from the URL.
- All commands run from `frontend/` (the pnpm workspace root for the app).
- Test files are colocated `*.test.ts(x)`; setup is `frontend/tests/setup.ts`; environment is happy-dom; `globals: true` (so `describe`/`it`/`expect`/`vi` are global, but importing them from `vitest` is also fine and matches existing tests).

---

### Task 1: Record ADR-0027 (decision)

**Files:**
- Create: `docs/adr/0027-url-query-params-as-filter-source-of-truth.md`

**Interfaces:**
- Consumes: nothing.
- Produces: the accepted decision record referenced by the spec and later tasks.

- [ ] **Step 1: Write the ADR using the `adr` skill**

Invoke the `adr` skill and record the decision with these facts (match the format of `docs/adr/0026-local-only-posture.md`):

- **Title:** `0027. URL query params as the filter source of truth`
- **Status:** accepted · **Date:** 2026-07-10 · **Deciders:** Angelo
- **Context:** List views hold filters in local `useState`, so filters are lost on reload, are not shareable, and each view re-implements its own plumbing. We want the URL query string to be the single source of truth and one agnostic hook for all views.
- **Decision drivers:** shareable/reloadable filtered views; one reusable abstraction; minimal dependency surface; simple filter shapes (strings, ints, enums, one boolean); Zod + TanStack Query already present.
- **Considered options:**
  1. **Custom `useUrlFilters` hook on Next primitives + Zod (chosen)** — ~90 lines, zero new deps, full control of serialization, plugs into existing `qk.*` query keys.
  2. **Adopt `nuqs` (rejected)** — industry standard, but adds a dependency, needs a `NuqsAdapter` provider, and currently hits an unresolved adapter-detection bug on Next 16 (47ng/nuqs#1263). More power than simple filters need.
  3. **Per-page inline `useSearchParams` (rejected)** — duplicates parsing across every view; contradicts the agnostic-hook goal.
- **Decision outcome:** Option 1. History mode is `replace`; default/empty values are omitted from the URL; invalid params fall back to defaults.
- **Consequences:** Filters become shareable and survive reload; a new shared module (`lib/use-url-filters.ts`) and per-view schemas (`lib/filter-schemas.ts`); if filter needs grow (many parsers, batched arrays, free-text debounce), reconsider `nuqs` once its Next 16 issue is resolved.

- [ ] **Step 2: Verify the file exists and is numbered 0027**

Run: `ls docs/adr/0027-*.md`
Expected: the file path prints.

- [ ] **Step 3: Commit**

```bash
git add docs/adr/0027-url-query-params-as-filter-source-of-truth.md docs/superpowers/specs/2026-07-10-url-filters-design.md docs/superpowers/plans/2026-07-10-url-filters.md
git commit -m "docs: ADR-0027 URL query params as filter source of truth + spec/plan"
```

---

### Task 2: Codec registry + `useUrlFilters` hook

**Files:**
- Create: `frontend/lib/use-url-filters.ts`
- Test: `frontend/lib/use-url-filters.test.tsx`

**Interfaces:**
- Consumes: `next/navigation` (`useSearchParams`, `useRouter`, `usePathname`), `zod`.
- Produces:
  - `type Codec<T> = { decode: (raw: string | null) => T; encode: (value: T) => string | null }`
  - `const p: { str, int, enum, bool }` — codec factories:
    - `p.str(default?: string | null): Codec<string | null>`
    - `p.int(default?: number | null): Codec<number | null>`
    - `p.enum<T extends string>(values: readonly [T, ...T[]], default?: T | null): Codec<T | null>`
    - `p.bool(default?: boolean): Codec<boolean>`
  - `function useUrlFilters<S extends Record<string, Codec<any>>>(schema: S): { values: FilterValues<S>; patch: (partial: Partial<FilterValues<S>>) => void; clear: () => void }` where `FilterValues<S>` maps each key `K` to `S[K] extends Codec<infer T> ? T : never`.

- [ ] **Step 1: Write failing codec tests**

Create `frontend/lib/use-url-filters.test.tsx`:

```tsx
import { describe, expect, it } from "vitest"
import { p } from "./use-url-filters"

describe("codec: str", () => {
  const c = p.str()
  it("decodes a value and null", () => {
    expect(c.decode("2026-07-01")).toBe("2026-07-01")
    expect(c.decode(null)).toBeNull()
    expect(c.decode("")).toBeNull()
  })
  it("encodes non-empty and omits empty", () => {
    expect(c.encode("2026-07-01")).toBe("2026-07-01")
    expect(c.encode(null)).toBeNull()
    expect(c.encode("")).toBeNull()
  })
})

describe("codec: int", () => {
  const c = p.int()
  it("decodes valid ints, defaults on garbage", () => {
    expect(c.decode("3")).toBe(3)
    expect(c.decode("abc")).toBeNull()
    expect(c.decode("1.5")).toBeNull()
    expect(c.decode(null)).toBeNull()
  })
  it("encodes numbers, omits null", () => {
    expect(c.encode(3)).toBe("3")
    expect(c.encode(null)).toBeNull()
  })
})

describe("codec: enum", () => {
  const c = p.enum(["expense", "income", "transfer"] as const)
  it("decodes known values, defaults on unknown", () => {
    expect(c.decode("expense")).toBe("expense")
    expect(c.decode("banana")).toBeNull()
    expect(c.decode(null)).toBeNull()
  })
  it("encodes known values, omits null", () => {
    expect(c.encode("income")).toBe("income")
    expect(c.encode(null)).toBeNull()
  })
})

describe("codec: bool", () => {
  const c = p.bool(false)
  it("decodes true/false with default false", () => {
    expect(c.decode("true")).toBe(true)
    expect(c.decode("false")).toBe(false)
    expect(c.decode(null)).toBe(false)
  })
  it("omits the default, encodes the non-default", () => {
    expect(c.encode(false)).toBeNull()
    expect(c.encode(true)).toBe("true")
  })
})
```

- [ ] **Step 2: Run codec tests to verify they fail**

Run: `pnpm test -- use-url-filters`
Expected: FAIL — `Cannot find module './use-url-filters'` (or `p is not defined`).

- [ ] **Step 3: Implement the codec registry and hook**

Create `frontend/lib/use-url-filters.ts`:

```tsx
"use client"

import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { useCallback, useMemo } from "react"
import { z } from "zod"

// A codec folds parse/validate/default and clear-on-default into one object.
// `encode` returning null means "omit this param from the URL".
export type Codec<T> = {
  decode: (raw: string | null) => T
  encode: (value: T) => string | null
}

const str = (fallback: string | null = null): Codec<string | null> => ({
  decode: (raw) => (raw && raw.length > 0 ? raw : fallback),
  encode: (value) => (value && value.length > 0 && value !== fallback ? value : null),
})

const int = (fallback: number | null = null): Codec<number | null> => {
  const schema = z.coerce.number().int()
  return {
    decode: (raw) => {
      if (raw === null || raw === "") return fallback
      const parsed = schema.safeParse(raw)
      return parsed.success ? parsed.data : fallback
    },
    encode: (value) => (value === null ? null : String(value)),
  }
}

const enumOf = <T extends string>(
  values: readonly [T, ...T[]],
  fallback: T | null = null,
): Codec<T | null> => {
  const schema = z.enum(values)
  return {
    decode: (raw) => {
      if (raw === null) return fallback
      const parsed = schema.safeParse(raw)
      return parsed.success ? parsed.data : fallback
    },
    encode: (value) => (value && value !== fallback ? value : null),
  }
}

const bool = (fallback = false): Codec<boolean> => ({
  decode: (raw) => (raw === null ? fallback : raw === "true"),
  encode: (value) => (value === fallback ? null : String(value)),
})

// Codec factories. Domain views compose these into a schema (see lib/filter-schemas.ts).
export const p = { str, int, enum: enumOf, bool }

type FilterValues<S extends Record<string, Codec<unknown>>> = {
  [K in keyof S]: S[K] extends Codec<infer T> ? T : never
}

// Reads typed filter values from the URL (source of truth) and writes changes back
// via router.replace. `schema` MUST be a module-level constant for stable memoization.
export function useUrlFilters<S extends Record<string, Codec<unknown>>>(schema: S) {
  const searchParams = useSearchParams()
  const router = useRouter()
  const pathname = usePathname()

  const values = useMemo(() => {
    const out = {} as FilterValues<S>
    for (const key in schema) {
      out[key] = schema[key].decode(searchParams.get(key)) as FilterValues<S>[typeof key]
    }
    return out
  }, [schema, searchParams])

  const replaceWith = useCallback(
    (params: URLSearchParams) => {
      const query = params.toString()
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false })
    },
    [router, pathname],
  )

  const patch = useCallback(
    (partial: Partial<FilterValues<S>>) => {
      const params = new URLSearchParams(searchParams.toString())
      for (const key in partial) {
        const encoded = schema[key].encode(partial[key] as never)
        if (encoded === null) params.delete(key)
        else params.set(key, encoded)
      }
      replaceWith(params)
    },
    [schema, searchParams, replaceWith],
  )

  const clear = useCallback(() => {
    const params = new URLSearchParams(searchParams.toString())
    for (const key in schema) params.delete(key)
    replaceWith(params)
  }, [schema, searchParams, replaceWith])

  return { values, patch, clear }
}
```

- [ ] **Step 4: Run codec tests to verify they pass**

Run: `pnpm test -- use-url-filters`
Expected: PASS (codec suites green).

- [ ] **Step 5: Add failing hook tests (append to the same test file)**

Append to `frontend/lib/use-url-filters.test.tsx`:

```tsx
import { renderHook } from "@testing-library/react"
import { beforeEach, vi } from "vitest"
import { useUrlFilters } from "./use-url-filters"

const replace = vi.fn()
let currentParams = new URLSearchParams("")

vi.mock("next/navigation", () => ({
  useSearchParams: () => currentParams,
  useRouter: () => ({ replace }),
  usePathname: () => "/transactions",
}))

const SCHEMA = {
  type: p.enum(["expense", "income", "transfer"] as const),
  account_id: p.int(),
  archived: p.bool(false),
}

describe("useUrlFilters", () => {
  beforeEach(() => {
    replace.mockReset()
    currentParams = new URLSearchParams("")
  })

  it("derives typed values from the URL", () => {
    currentParams = new URLSearchParams("type=expense&account_id=3")
    const { result } = renderHook(() => useUrlFilters(SCHEMA))
    expect(result.current.values.type).toBe("expense")
    expect(result.current.values.account_id).toBe(3)
    expect(result.current.values.archived).toBe(false)
  })

  it("patch replaces the URL with the encoded param", () => {
    const { result } = renderHook(() => useUrlFilters(SCHEMA))
    result.current.patch({ type: "income" })
    expect(replace).toHaveBeenCalledWith("/transactions?type=income", { scroll: false })
  })

  it("patch to a default/null value omits the param", () => {
    currentParams = new URLSearchParams("type=expense")
    const { result } = renderHook(() => useUrlFilters(SCHEMA))
    result.current.patch({ type: null })
    expect(replace).toHaveBeenCalledWith("/transactions", { scroll: false })
  })

  it("clear removes only schema keys, preserving others", () => {
    currentParams = new URLSearchParams("type=expense&other=keep")
    const { result } = renderHook(() => useUrlFilters(SCHEMA))
    result.current.clear()
    expect(replace).toHaveBeenCalledWith("/transactions?other=keep", { scroll: false })
  })
})
```

- [ ] **Step 6: Run the full test file to verify hook tests pass**

Run: `pnpm test -- use-url-filters`
Expected: PASS (codec + hook suites green).

- [ ] **Step 7: Lint/format, then commit**

Run: `pnpm check`
Expected: no errors.

```bash
git add frontend/lib/use-url-filters.ts frontend/lib/use-url-filters.test.tsx
git commit -m "feat(filters): add agnostic useUrlFilters hook with Zod codecs"
```

---

### Task 3: Domain filter schemas

**Files:**
- Create: `frontend/lib/filter-schemas.ts`
- Test: `frontend/lib/filter-schemas.test.ts`

**Interfaces:**
- Consumes: `p` and `Codec` from `lib/use-url-filters`.
- Produces:
  - `TX_FILTER_SCHEMA` — `{ date_from, date_to, account_id, category_id, tag, type, status }` (codecs). `type` values `["expense","income","transfer"]`; `status` values `["planned","posted","skipped"]`.
  - `ARCHIVED_FILTER_SCHEMA` — `{ archived: Codec<boolean> }`.

- [ ] **Step 1: Write failing schema tests**

Create `frontend/lib/filter-schemas.test.ts`:

```ts
import { describe, expect, it } from "vitest"
import { ARCHIVED_FILTER_SCHEMA, TX_FILTER_SCHEMA } from "./filter-schemas"

describe("TX_FILTER_SCHEMA", () => {
  it("decodes each param to the right type", () => {
    expect(TX_FILTER_SCHEMA.account_id.decode("7")).toBe(7)
    expect(TX_FILTER_SCHEMA.type.decode("expense")).toBe("expense")
    expect(TX_FILTER_SCHEMA.status.decode("posted")).toBe("posted")
    expect(TX_FILTER_SCHEMA.type.decode("banana")).toBeNull()
    expect(TX_FILTER_SCHEMA.date_from.decode("2026-07-01")).toBe("2026-07-01")
  })
})

describe("ARCHIVED_FILTER_SCHEMA", () => {
  it("defaults archived to false and omits it when false", () => {
    expect(ARCHIVED_FILTER_SCHEMA.archived.decode(null)).toBe(false)
    expect(ARCHIVED_FILTER_SCHEMA.archived.encode(false)).toBeNull()
    expect(ARCHIVED_FILTER_SCHEMA.archived.encode(true)).toBe("true")
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `pnpm test -- filter-schemas`
Expected: FAIL — `Cannot find module './filter-schemas'`.

- [ ] **Step 3: Implement the schemas**

Create `frontend/lib/filter-schemas.ts`:

```ts
import { type Codec, p } from "./use-url-filters"

// Transaction list filters. URL param names match the API filter names 1:1
// so the page maps values straight into TransactionFilters.
export const TX_FILTER_SCHEMA = {
  date_from: p.str(),
  date_to: p.str(),
  account_id: p.int(),
  category_id: p.int(),
  tag: p.int(),
  type: p.enum(["expense", "income", "transfer"] as const),
  status: p.enum(["planned", "posted", "skipped"] as const),
} satisfies Record<string, Codec<unknown>>

// Shared by the archive-toggle views (accounts, categories, category-groups).
export const ARCHIVED_FILTER_SCHEMA = {
  archived: p.bool(false),
} satisfies Record<string, Codec<unknown>>
```

- [ ] **Step 4: Run to verify pass**

Run: `pnpm test -- filter-schemas`
Expected: PASS.

- [ ] **Step 5: Lint/format, then commit**

Run: `pnpm check`
Expected: no errors.

```bash
git add frontend/lib/filter-schemas.ts frontend/lib/filter-schemas.test.ts
git commit -m "feat(filters): add transaction and archived filter schemas"
```

---

### Task 4: Wire the transactions page to the URL

**Files:**
- Modify: `frontend/app/(app)/transactions/page.tsx`
- Test: `frontend/app/(app)/transactions/page.test.tsx`

**Interfaces:**
- Consumes: `useUrlFilters` from `lib/use-url-filters`, `TX_FILTER_SCHEMA` from `lib/filter-schemas`.
- Produces: a transactions page whose filters are read from and written to the URL.

- [ ] **Step 1: Write the failing wiring test**

Create `frontend/app/(app)/transactions/page.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import TransactionsPage from "./page"

const listTransactions = vi.fn()
let currentParams = new URLSearchParams("")

vi.mock("next/navigation", () => ({
  useSearchParams: () => currentParams,
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/transactions",
}))
vi.mock("@/lib/api/transactions", () => ({
  listTransactions: (...a: unknown[]) => listTransactions(...a),
  deleteTransaction: vi.fn(),
}))
vi.mock("@/lib/api/accounts", () => ({ listAccounts: vi.fn().mockResolvedValue([]) }))
vi.mock("@/lib/api/categories", () => ({ listCategories: vi.fn().mockResolvedValue([]) }))
vi.mock("@/lib/api/tags", () => ({ listTags: vi.fn().mockResolvedValue([]) }))

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe("TransactionsPage URL filters", () => {
  beforeEach(() => {
    listTransactions.mockReset().mockResolvedValue([])
    currentParams = new URLSearchParams("")
  })

  it("passes URL filters to listTransactions", async () => {
    currentParams = new URLSearchParams("type=expense&account_id=3")
    render(<TransactionsPage />, { wrapper })
    await waitFor(() =>
      expect(listTransactions).toHaveBeenCalledWith({ type: "expense", account_id: 3 }),
    )
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `pnpm test -- transactions/page`
Expected: FAIL — the current page reads local `useState`, so `listTransactions` is called with `{}`.

- [ ] **Step 3: Replace filter state with the hook**

In `frontend/app/(app)/transactions/page.tsx`:

Add imports near the other `@/lib` imports:

```tsx
import { TX_FILTER_SCHEMA } from "@/lib/filter-schemas"
import { useUrlFilters } from "@/lib/use-url-filters"
```

Delete these seven lines (the local filter state):

```tsx
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")
  const [accountId, setAccountId] = useState<number | null>(null)
  const [categoryId, setCategoryId] = useState<number | null>(null)
  const [tag, setTag] = useState<number | null>(null)
  const [type, setType] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
```

Insert in their place:

```tsx
  const { values, patch, clear } = useUrlFilters(TX_FILTER_SCHEMA)
```

- [ ] **Step 4: Rebuild the `filters` memo from `values`**

Replace the existing `filters` `useMemo` block with:

```tsx
  const filters: TransactionFilters = useMemo(() => {
    const f: TransactionFilters = {}
    if (values.date_from) f.date_from = values.date_from
    if (values.date_to) f.date_to = values.date_to
    if (values.account_id !== null) f.account_id = values.account_id
    if (values.category_id !== null) f.category_id = values.category_id
    if (values.tag !== null) {
      const tagged = tags.data?.find((t) => t.id === values.tag)?.name
      if (tagged) f.tag = tagged
    }
    if (values.type) f.type = values.type
    if (values.status) f.status = values.status
    return f
  }, [values, tags.data])
```

- [ ] **Step 5: Point the filter-bar inputs at the hook**

In the `filterBar` JSX, change each control's value/handler:

```tsx
        <Input
          id="tx-from"
          type="date"
          value={values.date_from ?? ""}
          onChange={(e) => patch({ date_from: e.target.value })}
          className="w-36"
        />
```

```tsx
        <Input
          id="tx-to"
          type="date"
          value={values.date_to ?? ""}
          onChange={(e) => patch({ date_to: e.target.value })}
          className="w-36"
        />
```

```tsx
        <EntitySelect
          id="tx-account"
          value={values.account_id}
          onChange={(v) => patch({ account_id: v })}
          queryKey={qk.accounts(true)}
          queryFn={() => listAccounts(true)}
          allowNullLabel="Todas"
        />
```

```tsx
        <EntitySelect
          id="tx-category"
          value={values.category_id}
          onChange={(v) => patch({ category_id: v })}
          queryKey={qk.categories(true)}
          queryFn={() => listCategories(true)}
          allowNullLabel="Todas"
        />
```

```tsx
        <EntitySelect
          id="tx-tag"
          value={values.tag}
          onChange={(v) => patch({ tag: v })}
          queryKey={qk.tags()}
          queryFn={() => listTags()}
          allowNullLabel="Todas"
          disabled={tags.isLoading}
        />
```

```tsx
        <Select
          id="tx-type"
          value={values.type ?? ALL}
          onValueChange={(v) => patch({ type: v === ALL ? null : (v as TxType) })}
          items={TYPE_ITEMS}
          placeholder="Todos"
        />
```

```tsx
        <Select
          id="tx-status"
          value={values.status ?? ALL}
          onValueChange={(v) => patch({ status: v === ALL ? null : (v as TxStatus) })}
          items={STATUS_ITEMS}
          placeholder="Todos"
        />
```

- [ ] **Step 6: Replace the `clear` handler and remove the old one**

Delete the local `clear` function:

```tsx
  const clear = () => {
    setDateFrom("")
    setDateTo("")
    setAccountId(null)
    setCategoryId(null)
    setTag(null)
    setType(null)
    setStatus(null)
  }
```

The `Limpiar` button already calls `clear`; it now resolves to the hook's `clear`. Leave `onClick={clear}` as-is.

- [ ] **Step 7: Remove now-unused `useState` import if unused**

Check whether `useState` is still used (it is — `creating`, `editing`, `deleting`). Keep the import. Confirm `useMemo` is still imported (it is).

- [ ] **Step 8: Run the wiring test to verify pass**

Run: `pnpm test -- transactions/page`
Expected: PASS.

- [ ] **Step 9: Typecheck and lint**

Run: `pnpm check`
Expected: no errors. If TypeScript flags `patch({ type: ... })`, confirm `TX_FILTER_SCHEMA.type` value type is `TxType | null` — `type`/`status` string literals must match `TxType`/`TxStatus` from `@/lib/api/types`.

- [ ] **Step 10: Commit**

```bash
git add frontend/app/\(app\)/transactions/page.tsx frontend/app/\(app\)/transactions/page.test.tsx
git commit -m "feat(transactions): drive filters from URL query params"
```

---

### Task 5: Wire the archive-toggle views to the URL

**Files:**
- Modify: `frontend/app/(app)/accounts/page.tsx`
- Modify: `frontend/app/(app)/categories/page.tsx`
- Modify: `frontend/app/(app)/category-groups/page.tsx`
- Test: `frontend/app/(app)/accounts/page.test.tsx`

**Interfaces:**
- Consumes: `useUrlFilters`, `ARCHIVED_FILTER_SCHEMA`.
- Produces: three views whose `archived` toggle is read from and written to the URL.

- [ ] **Step 1: Write the failing accounts wiring test**

Create `frontend/app/(app)/accounts/page.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import AccountsPage from "./page"

const listAccounts = vi.fn()
let currentParams = new URLSearchParams("")

vi.mock("next/navigation", () => ({
  useSearchParams: () => currentParams,
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/accounts",
}))
vi.mock("@/lib/api/accounts", () => ({
  listAccounts: (...a: unknown[]) => listAccounts(...a),
  createAccount: vi.fn(),
  updateAccount: vi.fn(),
  archiveAccount: vi.fn(),
  restoreAccount: vi.fn(),
}))

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe("AccountsPage URL archived filter", () => {
  beforeEach(() => {
    listAccounts.mockReset().mockResolvedValue([])
    currentParams = new URLSearchParams("")
  })

  it("reads archived=true from the URL", async () => {
    currentParams = new URLSearchParams("archived=true")
    render(<AccountsPage />, { wrapper })
    await waitFor(() => expect(listAccounts).toHaveBeenCalledWith(true))
  })

  it("defaults to archived=false when absent", async () => {
    render(<AccountsPage />, { wrapper })
    await waitFor(() => expect(listAccounts).toHaveBeenCalledWith(false))
  })
})
```

> Note: confirm the account API export names in `frontend/lib/api/accounts.ts` before finalizing the mock; adjust the `vi.mock` object to match the file's actual exports (the test only asserts on `listAccounts`).

- [ ] **Step 2: Run to verify failure**

Run: `pnpm test -- accounts/page`
Expected: FAIL — page uses `useState(false)`, so `listAccounts` is called with `false` even when the URL says `archived=true`.

- [ ] **Step 3: Edit `accounts/page.tsx`**

Add imports:

```tsx
import { ARCHIVED_FILTER_SCHEMA } from "@/lib/filter-schemas"
import { useUrlFilters } from "@/lib/use-url-filters"
```

Replace:

```tsx
  const [showArchived, setShowArchived] = useState(false)
```

with:

```tsx
  const { values, patch } = useUrlFilters(ARCHIVED_FILTER_SCHEMA)
```

Replace the query's use of `showArchived`:

```tsx
    queryKey: qk.accounts(values.archived),
    queryFn: () => listAccounts(values.archived),
```

Replace the checkbox:

```tsx
        <input
          type="checkbox"
          checked={values.archived}
          onChange={(e) => patch({ archived: e.target.checked })}
        />
```

Remove the `useState` import if no other `useState` remains in the file; keep it otherwise.

- [ ] **Step 4: Edit `categories/page.tsx` (same transformation)**

Add the same two imports. Replace `const [showArchived, setShowArchived] = useState(false)` with `const { values, patch } = useUrlFilters(ARCHIVED_FILTER_SCHEMA)`. Update the categories query:

```tsx
    queryKey: qk.categories(values.archived),
    queryFn: () => listCategories(values.archived),
```

Replace the checkbox:

```tsx
        <input
          type="checkbox"
          checked={values.archived}
          onChange={(e) => patch({ archived: e.target.checked })}
        />
```

Leave the unrelated `listCategoryGroups(false)` / `listCategoryGroups(true)` calls unchanged. Keep the `useState` import (the page still uses `useState` for `creating`/`editing`/`archiving`).

- [ ] **Step 5: Edit `category-groups/page.tsx` (same transformation)**

Add the same two imports. Replace `const [showArchived, setShowArchived] = useState(false)` with `const { values, patch } = useUrlFilters(ARCHIVED_FILTER_SCHEMA)`. Update the query:

```tsx
    queryKey: qk.categoryGroups(values.archived),
    queryFn: () => listCategoryGroups(values.archived),
```

Replace the checkbox:

```tsx
        <input
          type="checkbox"
          checked={values.archived}
          onChange={(e) => patch({ archived: e.target.checked })}
        />
```

Remove the `useState` import only if no other `useState` remains; keep it otherwise.

- [ ] **Step 6: Run the accounts test to verify pass**

Run: `pnpm test -- accounts/page`
Expected: PASS (both cases).

- [ ] **Step 7: Typecheck and lint**

Run: `pnpm check`
Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add "frontend/app/(app)/accounts/page.tsx" "frontend/app/(app)/accounts/page.test.tsx" "frontend/app/(app)/categories/page.tsx" "frontend/app/(app)/category-groups/page.tsx"
git commit -m "feat(views): drive archived toggle from URL query params"
```

---

### Task 6: Full verification

**Files:** none (verification only).

**Interfaces:**
- Consumes: all prior tasks.
- Produces: a green build/test/lint run confirming no Suspense/prerender regression.

- [ ] **Step 1: Run the whole test suite**

Run: `pnpm test`
Expected: PASS, including `use-url-filters`, `filter-schemas`, `transactions/page`, `accounts/page`.

- [ ] **Step 2: Lint/format check**

Run: `pnpm check:ci`
Expected: no errors.

- [ ] **Step 3: Production build (catches Suspense/prerender issues with `useSearchParams`)**

Run: `pnpm build`
Expected: build succeeds. If it fails with a `useSearchParams() should be wrapped in a suspense boundary` error on a route, wrap that page's content in `<Suspense fallback={null}>` (import `Suspense` from `react`) or confirm the route is dynamically rendered; then re-run.

- [ ] **Step 4: Manual smoke (optional but recommended)**

Use the `run` skill (or `pnpm dev`) and verify on `/transactions`: setting a filter updates the URL; reloading keeps the filter; sharing the URL reproduces the filtered view; `Limpiar` clears the query string. Repeat the reload check on `/accounts` with the "Mostrar archivadas" checkbox.

- [ ] **Step 5: Final commit (if Step 3 required a Suspense wrap)**

```bash
git add -A
git commit -m "fix(filters): wrap client search-params pages in Suspense for build"
```

---

## Self-Review

**Spec coverage:**
- Hook (`lib/use-url-filters.ts`) → Task 2. ✓
- Codec registry (str/int/enum/bool) → Task 2. ✓
- Domain schemas (tx + archived) → Task 3. ✓
- Transactions wiring, tag id→name preserved → Task 4. ✓
- Archive views (accounts/categories/category-groups) → Task 5. ✓
- History=replace, clear-on-default omit, invalid→default → Task 2 (implementation + tests). ✓
- Suspense/build check → Task 6. ✓
- ADR-0027 (CLAUDE.md mandate) → Task 1. ✓
- Testing per behavior → Tasks 2–5. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code. ✓

**Type consistency:** `Codec<T>` uses `decode`/`encode` everywhere; `useUrlFilters` returns `{ values, patch, clear }` used identically in Tasks 4–5; `patch`/`clear`/`values` names consistent; schema names `TX_FILTER_SCHEMA` / `ARCHIVED_FILTER_SCHEMA` consistent across Tasks 3–5. `type`/`status` typed as `TxType`/`TxStatus` — Step 9 of Task 4 flags the cast to keep them aligned. ✓
