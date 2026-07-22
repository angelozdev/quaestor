# 0028. Bounded-query read path for monthly aggregates

- **Status:** accepted
- **Date:** 2026-07-22
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

The running API points at remote Render Postgres, so every distinct SELECT is a network round-trip. The dominant cost is `services/budgets.py::_available` recursing month-by-month (2 queries per frame per category); `list_budgets` runs it per category, `reports.py::_envelope_lines` re-runs `budget_status` (recursion included) per budget, `safe_to_spend::_sum_overspend` walks it again, and `_has_envelope` issues one query per recurring/planned/unbudgeted transaction. (Repeated `session.get(Category, id)` in loops is mostly served by SQLAlchemy's per-Session identity map — it is *not* the driver.) `monthly_report` composes all of it → multi-second hangs.

## Decision drivers

- Network round-trip latency: every distinct SELECT is a network round-trip to remote Postgres.
- Performance: multi-second hangs in `monthly_report` composition due to unbounded query counts.
- Query proliferation: multiple services recursively query the same data without coordination.

## Considered options

1. Load a month's data via one `MonthAggregate` unit with a bounded set of queries
2. SQL-native recursive-CTE rollover
3. Materialized/cached monthly snapshots
4. Loading all transaction rows into memory

## Decision outcome

Chosen option: **Load a month's data via one `MonthAggregate` unit with a bounded set of queries**, because it directly addresses the network latency and query proliferation drivers by fixing query count to ~8 per month, eliminating the unbounded recursion that causes multi-second hangs.

Load a month's data via one `MonthAggregate` unit in a fixed ~8 queries: expense history as one `GROUP BY (category_id, year, month)` sum query (engine-agnostic via SQLAlchemy `extract`), full transaction rows only for the two-month window `[prev month, report month]`, plus categories/groups/budgets/recurring/planned. Rollover becomes an iterative, memoized forward fold over in-memory sums — identical semantics, including the gap-month reset. Services orchestrate over it; response schemas and pure calculators are unchanged. One supporting index: `Transaction(type, status, date)`.

### Pros and cons of the options

**Load a month's data via one `MonthAggregate` unit**
- Good, because it bounds query count to a fixed ~8, eliminating the unbounded recursion that causes multi-second hangs.
- Good, because it keeps logic engine-agnostic (uses SQLAlchemy `extract` rather than SQL-specific syntax).
- Good, because response schemas and pure calculators remain unchanged; only the data-loading layer changes.

**SQL-native recursive-CTE rollover**
- Bad, because it breaks the in-memory SQLite test suite and couples logic to the engine.

**Materialized/cached monthly snapshots**
- Bad, because it adds cache-invalidation coupling; premature.

**Loading all transaction rows into memory**
- Bad, because it replaces unbounded query count with unbounded row transfer.

## Consequences

- Good: Read-path query count becomes O(1) in transactions and months of history; row transfer is bounded by categories × active months plus two months of rows.
- Good: Query-count tests (seeded with multi-month budgets, goals, and recurring items) guard regression.
- Good: `budget_status` (write path: `PUT /api/budgets`, MCP planning tool) now costs a fixed ~8 queries versus 3 + 2×(active months) before — a wash or win beyond ~2 months of history.
- Bad / cost: Known linearities remain in small user-curated sets: FX per non-COP due date, one query per goal, pendings per account.
- Bad / cost: The ~8 loads run under READ COMMITTED as separate statements, so a concurrent write (ADR-0024) can skew one aggregate against another within one response; accepted for this app and recorded here.

## Confirmation

Query-count regression tests, seeded with multi-month budgets, goals, and recurring items, will guard against sliding back to unbounded query counts. Code review will verify that new read-path code uses the `MonthAggregate` unit and that services orchestrate over it without re-introducing loops that bypass the bounded query design.
