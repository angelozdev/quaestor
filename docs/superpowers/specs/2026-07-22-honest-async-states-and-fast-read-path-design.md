# Honest Async States + Fast Read Path — Design

**Date:** 2026-07-22
**Status:** Approved (brainstorming); revised 2026-07-22 after adversarial review

## Problem

Two symptoms with one shared root: async UI states are dishonest, and the
monthly read-path is slow.

- **Budgets page renders blank while loading.** `app/(app)/budgets/page.tsx`
  handles `sts.isError` and `sts.data` but has **no loading branch**. While the
  query is in flight, `isError` is false and `data` is undefined, so the page
  renders nothing. The `lines` (envelopes) query has no loading/empty/error
  handling either.
- **Reports page skeleton is invisible in dark mode.** It renders a real
  `animate-pulse` skeleton, but the pulse over `var(--muted)` is so faint it
  reads as empty boxes — and it lingers because the backend is slow. Its
  "Sobres" / "Por categoría" / "Por grupo" sections are gated on
  `length > 0 &&`, so an empty month makes whole sections vanish silently.
- **Dashboard duplicates primitives.** `app/(app)/page.tsx` defines its own
  local `Skeleton` instead of the shared one, uses inline "Sin datos" strings,
  and the hero renders "No disponible" for what is actually an error state.
- **`EmptyState` is bare text** — a centered muted `<p>`, no icon, no CTA.
- **The monthly read-path re-queries per category and per month.** The running
  API points at remote Render Postgres (Oregon), so every *distinct* SELECT is
  a network round-trip. The dominant cost is `services/budgets.py::_available`,
  which recurses month-by-month into the past issuing 2 queries per frame per
  category; `list_budgets` runs it for every category, `reports.py::
  _envelope_lines` re-runs `budget_status` (recursion included) per budget, and
  `safe_to_spend::_sum_overspend` walks it all again. `_has_envelope` adds one
  query per recurring item, planned tx, and unbudgeted posted tx. (Note:
  repeated `session.get(Category, id)` calls inside loops are mostly served by
  SQLAlchemy's per-Session identity map after the first load of each id — they
  are *not* the bottleneck; the distinct SELECTs above are.) `monthly_report`
  composes all of it → the multi-second hang observed in the browser.

## Goals

1. The **budgets, reports, and dashboard** pages render an honest state for
   loading / error / empty / success through one shared `QueryBoundary`
   component, which becomes the recorded convention (ADR) for every future
   page. Remaining pages (accounts, categories, category-groups, goals,
   recurring, settings, tags, to-pay, transactions, and the `ToPayWidget`)
   keep their hand-rolled states for now and migrate incrementally as
   follow-up work — nothing enforces the convention mechanically yet, and this
   spec does not claim otherwise.
2. The monthly read-path (`monthly_report`, `safe_to_spend`, `list_budgets`)
   issues a **fixed number of queries with respect to transaction count and
   months of history**, and transfers a bounded number of rows: history
   arrives as `GROUP BY` sums (rows ≈ categories × active months), and full
   transaction rows are loaded only for the report month and its previous
   month. **Known remaining linearities** (small, user-curated sets; accepted
   and documented, not hidden): one FX-rate lookup per non-COP recurring due
   date, one query per active goal (`goals_progress`), and one account lookup
   per account with pending items. The query-count tests seed goals and
   recurring items so the asserted bounds include these paths.

## Non-goals (queued as separate specs)

- Interactive envelope budgeting UI (assign per category with progress bars).
- Transactions search / filtered totals / bulk actions / payee autocomplete.
- Net worth + assets-vs-liabilities on Accounts.
- Migrating the remaining pages onto `QueryBoundary` (follow-up, see Goal 1).
- A stale/refetching indicator (`isFetching`) in the boundary contract.
- Mechanical enforcement (lint rule) of boundary usage.
- Batching FX/goal/pending lookups (bounded by small user-curated sets).
- Moving the `month` filter to URL query params (see "Relationship to
  existing ADRs" below).

These are out of scope. This spec only makes async states honest on three
pages and the read-path fast. API response contracts do not change.

## Approach

### Backend — bounded read path (low coupling)

Introduce one cohesive data-loading unit, `MonthAggregate`, that loads
everything a month's aggregates need in a **fixed** set of ~8 queries, then
computes all aggregates from in-memory structures.

- **History as sums, not rows:** one `GROUP BY` query returns
  `SUM(to_base)` per `(category_id, year, month)` over all posted expenses —
  this powers rollover with rows bounded by categories × active months. Month
  bucketing uses SQLAlchemy `extract("year"/"month", ...)`, which compiles to
  `EXTRACT` on Postgres and `strftime` on SQLite — engine-agnostic, no
  recursive CTEs.
- **Full rows only for a two-month window:** posted expense and income rows
  are loaded for `[previous month, report month]` only — these power the
  by-category/by-group sections, `usd_share`, month totals, MoM drift, and
  unbudgeted spending. Additionally: all `Category`, all `CategoryGroup`, all
  `Budget` rows (bounded by user-assigned envelopes, not transactions),
  active `RecurringItem`s, and the month's planned expense transactions.
- **Rollover without per-month queries:** `available(category_id, ym)` is an
  iterative forward fold with memoization over the in-memory sums — from the
  category's earliest active month up to `ym`, preserving the current
  semantics exactly, **including the gap-month reset** (a month with no
  assignment and no spending yields 0 and does not pass rollover forward).
  Zero queries after load; still O(months of history) CPU per category, walked
  once thanks to the memo.
- `reports.monthly_report`, `budgets.safe_to_spend`, and `budgets.list_budgets`
  become thin orchestrators over `MonthAggregate`. Pure calculators in
  `domain/rules.py` (`envelope_status_calc`, `safe_to_spend_calc`) are
  unchanged and still receive precomputed numbers.
- **Write-path cost note:** `budget_status` (called by `PUT /api/budgets` and
  the MCP planning tool) also moves onto the aggregate: a fixed ~8 queries per
  call, versus the previous 3 + 2×(active months) recursion — a wash or win
  for any category with more than ~2 months of history, and now bounded.
- **Consistency note (honest limitation):** the ~8 loads run as separate
  statements under Postgres READ COMMITTED, so each sees its own snapshot. A
  concurrent write (chat endpoint, scheduler — see ADR-0024) landing mid-load
  can skew one aggregate against another within a single response. Accepted
  for a personal-finance dashboard; recorded in the ADR, not papered over.
- **The boundary holds:** response schemas (`MonthlyReportOut`,
  `SafeToSpendOut`, `BudgetLineOut`) are unchanged, so the frontend is
  unaffected by the refactor.
- **One Alembic index:** `ix_transaction_type_status_date` on
  `Transaction(type, status, date)` — the history `GROUP BY` filters on
  `(type, status)` (prefix) and the window loads filter on
  `(type, status, date range)` (full index). No other indexes: after the
  refactor no read-path query filters on `Transaction.category_id`,
  `Budget.year_month`, or `RecurringItem(active, type)`, so those earlier
  candidates are dropped as dead weight.

### Frontend — async-state contract (high cohesion)

- **`components/query-boundary.tsx`** — one component owns state selection
  against TanStack Query v5 semantics (`isPending`, not the v4-style
  `isLoading`, so disabled/pending-without-fetch queries still show a
  skeleton instead of rendering nothing):
  - **Data-first:** if `data` is present, render `children(data)` (or the
    `empty` node when the caller's predicate matches). If `isError` is *also*
    true (a background refetch failed), keep the data visible and render a
    compact inline "No se pudo actualizar / Reintentar" alert above it — a
    failed refresh must never destroy what the user is already looking at
    (the current budgets page keeps data visible next to the error; the
    boundary must not regress that).
  - No data + `isError` → `ErrorState` (retry = `refetch`).
  - No data + `isPending` → skeleton, after the anti-flash delay.
  - Lives in `components/` (not `ui/`) because it depends on app components —
    `ui/` is app-agnostic (ADR-0002).
- **`EmptyState`** gains optional `icon` and `action` (label + `href`/`onClick`)
  for actionable empty states.
- **App-level skeleton variants** (`components/skeleton.tsx`: `SkeletonText`,
  `SkeletonCard`, `SkeletonRows`, `SkeletonBlock` for free-form shapes like
  the dashboard hero) built on the `ui` `Skeleton`, with contrast raised so
  they read clearly in dark mode and mirror content shape (less layout shift).
- **Anti-flash delay:** the boundary shows the skeleton only after ~150ms
  (default `delayMs = 150`) so fast queries don't flash. **Production pages do
  not override this to 0** — tests exercise the delay with fake timers
  (boundary unit test) and `waitFor` (page tests); the test strategy adapts to
  the behavior, never the reverse.
- **Migrate pages** to `QueryBoundary`:
  - `budgets`: both `sts` and `lines` (fixes the confirmed blank-page bug),
    with an `EmptyState` for the no-envelopes case.
  - `reports`: the single report query, **plus** honest empty states inside
    the "Sobres" / "Por categoría" / "Por grupo" sections (sections stay
    visible with an `EmptyState` instead of vanishing on `length === 0`).
  - dashboard: the hero (`sts` — replaces the dishonest "No disponible"
    string), and the four cards with their real queries: "Ingresos · Gastos ·
    Neto" (`report`), "Saldos" (`accounts`), "Metas" (`goals`), "Sobres en
    riesgo" (**`report`**, not `sts` — the at-risk card reads
    `report.data.envelopes`). The local duplicate `Skeleton` is deleted only
    after all five of its usages are replaced.

## Error handling

- Per-query isolation: each card/section has its own `QueryBoundary`, so one
  failing query renders its own `ErrorState` without blanking the page.
- Data-first on refetch failure: see the boundary contract above.
- Backend error contract is unchanged; `ValidationError` / `MissingRate`
  surface exactly as today.

## Relationship to existing ADRs

- **ADR-0002** (`ui/` app-agnostic): `QueryBoundary` and skeleton variants go
  in `components/`, not `ui/`.
- **ADR-0003** (pnpm as the sole frontend package manager): every frontend
  command in the plan uses `pnpm` — never `npm`.
- **ADR-0024** (concurrent writers): source of the READ COMMITTED torn-read
  window noted above.
- **ADR-0027** (URL query params as filter source of truth): its accepted
  scope is the four list views. The `month` filter on budgets/reports stays in
  local `useState` in this spec; moving it to the URL is a natural follow-up
  under ADR-0027's direction and is explicitly out of scope here. Page tests
  must not assert on the `useState` implementation detail, so that follow-up
  won't invalidate them.

## Testing

- **Backend correctness:** characterization (golden) tests seed a known
  dataset **spanning two months so rollover semantics are pinned** and assert
  exact `monthly_report` / `safe_to_spend` / `list_budgets` outputs. They pass
  against the current implementation and must stay green through the refactor
  (safety net).
- **Backend performance:** a `count_queries` context manager (SQLAlchemy
  `before_cursor_execute` listener) asserts the read-path issues ≤ a fixed
  bound. Seeds include multi-month budgets (to make the current recursion
  genuinely exceed the bound — the red test must actually be red), plus goals
  and recurring items so the documented linearities are inside the asserted
  bound. Runs on in-memory SQLite. The `MonthAggregate` loader has its own
  unit-level bound (≤ 10 queries) plus rollover and gap-month-reset tests.
- **Frontend:** `QueryBoundary` unit tests (each state, **including the
  anti-flash delay via fake timers and the error-with-data case**), upgraded
  `EmptyState` tests (icon + action), and page tests for budgets showing
  loading (via `waitFor`, respecting the 150ms delay), empty, and error +
  retry (Vitest + Testing Library, already in the repo).

## ADRs

- Backend: bounded-query read path via `MonthAggregate` (architecturally
  significant per CLAUDE.md) — includes the index decision and the READ
  COMMITTED consistency note.
- Frontend: async-state contract via `QueryBoundary` (module boundary /
  convention) — includes the data-first refetch-failure rule and the
  incremental-migration scope.
