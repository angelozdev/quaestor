# 0027. URL query params as the filter source of truth

- **Status:** accepted
- **Date:** 2026-07-10
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

List views (transactions, accounts, categories, category-groups) hold their filters in
local `useState`. Filters are lost on reload, cannot be shared via URL, and each view
re-implements its own parsing/serialization plumbing. We want the URL query string to be
the single source of truth for list-view filters, driven by one agnostic, reusable hook
rather than per-page state. Spec: `docs/superpowers/specs/2026-07-10-url-filters-design.md`.

## Decision drivers

- Shareable and reloadable filtered views (URL fully describes view state).
- One reusable abstraction instead of per-view filter plumbing.
- Minimal dependency surface — no new npm dependency.
- Filter shapes are simple: strings, ints, enums, one boolean.
- Zod and TanStack Query are already present and plug in naturally.

## Considered options

1. Custom `useUrlFilters` hook built on Next.js primitives (`useSearchParams`,
   `useRouter`, `usePathname`) plus Zod codecs.
2. Adopt `nuqs`.
3. Per-page inline `useSearchParams` parsing.

## Decision outcome

Chosen option: **Custom `useUrlFilters` hook on Next primitives + Zod**, because it needs
zero new dependencies, is ~90 lines, gives full control over serialization, and plugs
directly into the existing `qk.*` query-key factories — satisfying all five decision
drivers without adding a dependency or working around an unresolved upstream bug.

Concrete shape:

- History mode is `replace` (filtering never grows the back-button stack).
- Default/empty values are omitted from the URL (`encode` returns `null` → param deleted).
- Invalid params fall back to their codec's default rather than throwing.
- A codec registry (`p.str`, `p.int`, `p.enum`, `p.bool`) folds parse/validate/default
  into one object per param; views compose these into a module-level schema
  (`lib/filter-schemas.ts`) and pass it to `useUrlFilters(schema)`.

### Pros and cons of the options

**Custom `useUrlFilters` hook on Next primitives + Zod (chosen)**
- Good, because it adds zero new dependencies.
- Good, because it gives full control over serialization/defaulting rules
  (replace-history, omit-on-default, invalid-falls-back-to-default).
- Good, because it plugs straight into the existing `qk.*` query-key factories used by
  TanStack Query.
- Bad, because it's a small bespoke abstraction we own and must maintain ourselves,
  instead of an audited library.

**Adopt `nuqs` (rejected)**
- Good, because it's the industry-standard URL-state library for Next.js, with a much
  larger feature set (batching, debouncing, array/JSON parsers).
- Bad, because it adds a new dependency and requires wiring a `NuqsAdapter` provider.
- Bad, because it currently hits an unresolved adapter-detection bug on Next 16
  (47ng/nuqs#1263).
- Bad, because it's more power than our simple filter shapes (strings, ints, enums, one
  boolean) need right now.

**Per-page inline `useSearchParams` (rejected)**
- Good, because it requires no shared abstraction at all.
- Bad, because it duplicates parsing/serialization logic across every list view.
- Bad, because it directly contradicts the agnostic-reusable-hook goal.

## Consequences

- Good: filters on transactions, accounts, categories, and category-groups become
  shareable and survive reload — the URL fully describes the filtered view.
- Good: one shared module (`frontend/lib/use-url-filters.ts`) plus per-view schemas
  (`frontend/lib/filter-schemas.ts`) replace bespoke `useState` filter plumbing in every
  list view.
- Bad / cost: we own and maintain a small bespoke hook instead of delegating to an
  audited library.
- Bad / cost: if filter needs grow (many parsers, batched arrays, free-text debounce),
  we should reconsider `nuqs` once its Next 16 adapter-detection issue
  (47ng/nuqs#1263) is resolved.

## Confirmation

- `frontend/lib/use-url-filters.test.tsx` and `frontend/lib/filter-schemas.test.ts` cover
  the codec registry, the hook's `values`/`patch`/`clear` contract, replace-history,
  omit-on-default, and invalid-falls-back-to-default behavior.
- `frontend/app/(app)/transactions/page.test.tsx` and
  `frontend/app/(app)/accounts/page.test.tsx` confirm the views read filters from and
  write filters back to the URL via the hook.
- `pnpm build` confirms no Suspense/prerender regression from `useSearchParams` usage in
  the wired pages.
