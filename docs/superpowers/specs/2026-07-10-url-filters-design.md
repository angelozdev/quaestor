# URL Query Params as Filter Source of Truth — Design

- **Date:** 2026-07-10
- **Status:** approved
- **Related ADR:** 0027 — URL query params as the filter source of truth (custom hook over nuqs)

## Problem

List views filter server-side, but every filter lives in local `useState`. Consequences:

- Filters are lost on reload.
- Filtered views are not shareable (the URL carries no filter state).
- Back/forward do nothing useful for filters.
- Each view re-implements its own filter plumbing.

We want the URL query string to be the single source of truth for filters, and one
agnostic, reusable hook that every filtered view uses.

## Scope

Views with genuine server-side list filters:

- **transactions** — 7 filters: `date_from`, `date_to`, `account_id`, `category_id`,
  `tag` (id in URL, mapped to name for the API), `type`, `status`.
- **accounts**, **categories**, **category-groups** — one boolean each: `archived`
  (currently `showArchived`).

Out of scope: goals, recurring, to-pay, settings — their `listAccounts(false)`-style
calls are fixed data-loading arguments inside forms, not user-facing filters.

## Approach

Custom hook on Next.js 16 App Router primitives (`useSearchParams`, `useRouter`,
`usePathname`) plus Zod for validation. No new dependency.

`nuqs` is the industry-standard library for this, but was rejected: it adds a
dependency, needs a `NuqsAdapter` provider, and currently hits an unresolved
adapter-detection bug on Next 16 (47ng/nuqs#1263). Our filter shapes are simple
(strings, ints, enums, a boolean), and Zod + TanStack Query are already present, so
a ~90-line hook covers the need with zero risk. See ADR-0027.

## The hook — `lib/use-url-filters.ts`

Exports a `Codec` type, a codec registry `p`, and `useUrlFilters`.

A **codec** folds parsing, validation, defaults, and clear-on-default into one object:

```ts
export type Codec<T> = {
  decode: (raw: string | null) => T   // raw from searchParams.get(); resolves default + validates
  encode: (value: T) => string | null // null => omit the param (value is default/empty)
}
```

Registry (validation via Zod where a value space exists):

- `p.str(default = null)` — free strings (dates as ISO strings).
- `p.int(default = null)` — integer ids; `z.coerce.number().int()`, invalid → default.
- `p.enum(values, default = null)` — `z.enum(values)`, unknown → default.
- `p.bool(default = false)` — `"true"`/`"false"`; default omitted from URL.

Hook API:

```ts
const { values, patch, clear } = useUrlFilters(schema)
```

- `values` — `useMemo` over `searchParams`; each key `codec.decode(searchParams.get(key))`,
  fully typed and default-filled.
- `patch(partial)` — rebuild `URLSearchParams`, `encode` each changed key (omit when
  `encode` returns `null`), then `router.replace(pathname?qs, { scroll: false })`.
- `clear()` — delete only this schema's keys (unrelated params preserved), then replace.

History is **replace** (filter changes don't stack history entries; the URL stays
shareable/reloadable). `scroll: false` prevents scroll jumps.

**Schema must be a module-level constant** so `useMemo`/`useCallback` dependencies stay
referentially stable.

## Domain schemas — `lib/filter-schemas.ts`

- `TX_FILTER_SCHEMA` — the 7 transaction filters, param names matching the API.
- `ARCHIVED_FILTER_SCHEMA` — `{ archived: p.bool(false) }`, shared by the three archive views.

## Data flow (single source of truth)

```
URL ─useSearchParams→ useUrlFilters → typed values ─useMemo→ API filter obj ─→ qk.*(filters) ─→ react-query
        ▲                                                                                            │
        └──────────────── router.replace(new URL) ◄── patch/clear ◄── filter inputs ────────────────┘
```

All filter `useState` is removed. `lib/query.ts` is unchanged — `qk.*` already accepts
the typed filter values.

## Integration

- **transactions** — drop the 7 `useState` and `clear()`. Inputs read `values.*`;
  `onChange → patch({...})`; `Limpiar → clear()`. The `TransactionFilters` build
  (including `tag` id→name) is unchanged, sourced from `values`.
- **accounts / categories / category-groups** — replace `showArchived` `useState` with
  `values.archived`; checkbox `onChange → patch({ archived })`; `qk.*`/`list*` read
  `values.archived`.

## Behavior / edge cases

- Default or empty value → param omitted from the URL (clean URLs).
- Invalid param (`?type=banana`, `?account_id=abc`) → `decode` returns the default → filter
  unset, no crash.
- Reload / shared link → filters hydrate from the URL.
- These pages are already `"use client"` and dynamically rendered; `useSearchParams` needs
  no extra Suspense boundary. Confirmed against `node_modules/next/dist/docs/`; `pnpm build`
  is the final check.

## Testing

Vitest + Testing Library (`renderHook`/`render`), mocking `next/navigation`:

- Codec round-trips: encode∘decode identity; default fill; invalid input → default;
  clear-on-default omits.
- Hook: `values` derived from `searchParams`; `patch` calls `router.replace` with the
  correct URL; `clear` removes only schema keys.
- Transactions wiring: initial `?type=expense` → `listTransactions` called with
  `{ type: "expense" }`; `Limpiar` → `router.replace` to pathname without query.
- Archive wiring (accounts): `?archived=true` → `listAccounts(true)`; toggling checkbox →
  `router.replace` with `?archived=true`.

## Out of scope

nuqs; pagination/sorting (absent today); debounce (no free-text filter exists — add if a
search input appears later); cross-route filter persistence.
