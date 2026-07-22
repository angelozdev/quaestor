# 0029. Frontend async-state contract via QueryBoundary

- **Status:** accepted
- **Date:** 2026-07-22
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

Pages hand-roll `isPending`/`isError`/`data`; `budgets/page.tsx` forgot the loading branch and rendered blank; reports sections vanish on `length === 0`; `EmptyState` is bare text; the dashboard duplicates `Skeleton` and renders "No disponible" for an error.

## Decision drivers

- Consistency: all async states (pending, error, data, empty) must be handled uniformly across pages.
- Correctness: no forgotten states; failed background refetches must not destroy visible data.
- Code reuse: skeleton and empty-state rendering logic should not be duplicated.
- Maintainability: changes to async semantics should be made in one place, not scattered across pages.

## Considered options

1. Create a single `QueryBoundary` component to own state selection and rendering
2. Continue hand-rolling async state per-page
3. Create a custom hook-based wrapper around TanStack Query

## Decision outcome

Chosen option: **Create a single `QueryBoundary` component**, because it centralizes state logic, prevents forgotten states, and ensures consistent error handling across all pages.

A single `components/query-boundary.tsx` owns state selection against TanStack Query v5 semantics: data-first (data present → render it; if `isError` too, keep data visible and show a compact retry alert — a failed background refetch must not destroy visible data), else error → `ErrorState`+retry, else pending → skeleton after a 150ms anti-flash delay; `EmptyState` gains `icon`/`action`; app-level skeleton variants read clearly in dark mode; lives in `components/` because `ui/` is app-agnostic (ADR-0002).

**Scope** — budgets/reports/dashboard migrate now; remaining pages and `ToPayWidget` migrate incrementally (convention, not mechanical enforcement).

### Pros and cons of the options

**QueryBoundary component**
- Good, because it centralizes all async state logic in one place and eliminates duplication.
- Good, because it prevents forgotten states; every page that wraps a query gets all four states (pending, error, data, empty).
- Good, because it ensures consistent error handling across the app, including data-first rendering on background refetch failures.
- Bad, because it adds a new component to learn and potentially a new prop API to all query-using pages.

**Continue hand-rolling per-page**
- Good, because it requires no new abstractions.
- Bad, because it continues the pattern of forgotten states and inconsistent error handling.
- Bad, because changes to async semantics (e.g., anti-flash delays, background-refetch behavior) must be updated in multiple places.
- Bad, because skeleton and empty-state code is duplicated across pages.

**Custom hook-based wrapper**
- Good, because it encapsulates logic in a hook rather than introducing a component.
- Bad, because hooks cannot return JSX directly; consumers still need to handle state selection, risking forgotten branches.
- Bad, because it provides less structure than a component-based approach; there's no guarantee all states are rendered.

## Consequences

- Good: Migrated pages cannot forget a state.
- Good: Error isolation is per-query.
- Bad / cost: The `month` filter stays in `useState` (moving it to the URL is follow-up under ADR-0027).

## Confirmation

Code review will verify that new query-using pages wrap their queries in `QueryBoundary` rather than hand-rolling state. Tests will exercise all four async branches (pending, error, data, empty) for each query-dependent component. The component's dark-mode readability will be verified visually. Migration of remaining pages will be tracked as an incremental, convention-based effort with no hard deadline, allowing for gradual adoption.
