# 0021. Default transaction listing order: created_at desc

- **Status:** proposed
- **Date:** 2026-06-28
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

The `/transactions` page is the primary surface for reviewing recent activity.
The user's mental model is "qué pasó más reciente + lo que está en planned"
— most-recent logical date on top, with both posted and upcoming (planned)
transactions visible. The original default (`date ASC`, oldest-first)
required scrolling past old entries to find new activity; a proposed flip
to `created_at DESC` was rejected after seeing it produce chronological-date
disorder when transactions are backdated or imported (a 12-jun parking
charge imported today lands below a 20-jun Uber ride logged earlier today,
even though the 20-jun ride happened later in calendar terms). The fix is
to sort by logical `date` descending, the field that actually corresponds
to "when did this happen", and include `planned` rows by default so
upcoming obligations are visible in the same view.

## Decision drivers

- UX expectation: when reviewing activity, "what happened most recently"
  should be on top, and upcoming planned obligations should be visible
  alongside posted transactions.
- Consistency: one default across MCP, REST, and any internal report that
  re-uses the service.
- Reversibility: medium — adding a `sort`/`order` opt-in param is cheap if
  a future caller needs a different ordering semantic.
- Test stability: existing tests under `backend/tests/` do not assert a
  specific order from `list_transactions` outside the new explicit sort
  tests, so the change is contained.

## Considered options

1. Change the default of `services.transactions.list_transactions` to
   `date DESC, id DESC` (id as deterministic tiebreaker). The default
   filter is no `status` filter, so both posted and planned rows return.
   Callers needing a different ordering pass explicit `sort`/`order`
   kwargs. Affects every caller of the service — MCP, REST, frontend,
   internal reports.
2. Add `sort` / `order` query params (REST) and tool input fields (MCP);
   pass them through to the service. Keep the service default as
   `date ASC`. Callers opt in to a different order.
3. Sort client-side in `frontend/components/data-table.tsx`. Zero backend
   change. Only the `/transactions` page is affected.

## Decision outcome

Chosen option: **1 + 2 combined** — the service default flips to
`date DESC, id DESC`, and a `sort` / `order` keyword-only kwargs pair is
added to `services.transactions.list_transactions` so callers whose
ordering semantics differ from the listing default can declare their
intent explicitly. Today only `planned.to_pay` opts out (it passes
`sort="date", order="asc"` so the due-date confirmation queue stays
chronological — without that opt-out, flipping the default would silently
invert the `/to-pay` queue from "next due" to "most recently planned").

Option 2 alone (keep the service default as `date ASC`, add the kwargs,
let REST/MCP pass them) was rejected because every new caller would have
to know to opt in, and the `/transactions` page — the primary motivation
— would remain chronological-ascending, which puts today's activity at
the bottom. Option 1 alone (flip to `created_at DESC, id DESC` with no
escape hatch) was rejected after a working preview exposed the
chronological-date disorder described in Context: backdated and imported
transactions land in the wrong logical-date position. Option 3 fixes
only the UI and leaves MCP / REST exposing the surprise.

The `sort` / `order` plumbing is implemented through a `SortSpec` value
object (`backend/src/quaestor/domain/sort.py`) backed by a per-service
column registry — adding a third sortable field later is one line in
the registry plus one Literal member in the domain module.

If a future caller needs a third ordering semantic (e.g. `amount` desc),
add it to `_TRANSACTION_SORTABLE` in `services/transactions.py` and to the
`SortField` Literal in `domain/sort.py`. Do not change the default.

### Pros and cons of the options

**1 + 2 combined. Service default → `date DESC, id DESC`; `sort`/`order` kwargs added; planned included by default**
- Good, because one default applies everywhere; no caller can accidentally
  get the "wrong" order — and "wrong" is now defined against logical
  transaction date, not against row creation time.
- Good, because backdated and imported transactions land in their
  correct chronological position rather than wherever the import order
  placed them.
- Good, because `planned` rows surface at their due-date position
  without a separate filter — upcoming obligations are visible in the
  main view alongside posted activity.
- Good, because the `sort`/`order` escape hatch means each future
  caller can declare its ordering semantics explicitly instead of
  inheriting whatever the default happens to be.
- Bad / cost, because any consumer that iterated results assuming
  `date ASC` now sees a different sequence. The only in-tree caller in
  this category was `planned.to_pay`; it has been updated to pass
  `sort="date", order="asc"` and is locked by
  `test_to_pay_orders_by_due_date_asc`. REST consumers outside this
  codebase should be flagged in release notes.

**2. Add `sort` / `order`; service default unchanged (`date ASC`)**
- Good, because the change is opt-in and existing callers are unaffected.
- Bad, because every new caller has to know to opt in to get the useful
  order; the `/transactions` page becomes the only place with "natural"
  ordering, and today's activity still sits at the bottom of an
  ascending list.

**3. Client-side sort in DataTable**
- Good, because zero backend surface area; shipped in one frontend PR.
- Bad, because MCP and REST still expose `date ASC` — the inconsistency
  is only half fixed.

## Consequences

- Good: `/transactions` and the MCP `list_transactions` tool both show
  newest-first by logical date, with planned rows interleaved at their
  due-date position — the view the user actually wants when reviewing
  activity.
- Good: when two transactions share a `date` (same day), the `id DESC`
  tiebreaker keeps the order deterministic across calls.
- Good: the `sort` / `order` escape hatch means each future caller can
  declare its ordering semantics explicitly instead of inheriting
  whatever the default happens to be.
- Bad / cost: any consumer that iterated results assuming `date ASC`
  without an explicit sort arg now sees a different sequence. The only
  in-tree caller in this category was `planned.to_pay`; it has been
  updated to pass `sort="date", order="asc"` and is locked by
  `test_to_pay_orders_by_due_date_asc`. REST consumers outside this
  codebase should be flagged in release notes.
- Neutral / not a regression: the chat persona does not narrate raw
  transaction lists — the LLM receives the MCP tool output as data and
  composes its own narrative, so the default-order flip has no visible
  effect on chat responses.
- Follow-up: when the ledger grows past a few thousand rows, add a
  composite index `(date DESC, id DESC)` via Alembic. At current sizes
  the unordered scan + in-memory sort is negligible.
- Follow-up: the `id` tiebreaker is reliable under SQLite autoincrement
  with a single writer. If the store migrates to Postgres or another DB
  with sequence gaps from rolled-back inserts, revalidate that `id`
  remains monotonic under load (almost certainly true, but worth a note).

## Confirmation

- Service default-order test:
  `backend/tests/services/test_transactions.py::test_list_transactions_default_orders_by_date_desc`
  inserts three transactions with deliberately misleading creation order
  (mid first, old second, new third) and dates 15-jun / 1-jun / 1-jul,
  then asserts the default `list_transactions()` returns `[new, mid, old]`
  — proving the default is by logical date, not creation time.
- Planned-in-default test (same file):
  `test_list_transactions_default_includes_planned_at_due_date` posts two
  expenses (1-jun + 1-jul) and one planned payment (due 15-jun) and asserts
  the default returns `[new, Rent, old]` — proving planned surfaces at its
  due-date without a status filter.
- `to_pay` candado: `test_to_pay_orders_by_due_date_asc` in
  `backend/tests/services/test_planned.py` creates two planned payments in
  the OPPOSITE order of their due-dates and asserts `to_pay` returns the
  earlier-due one first.
- REST mirror: `backend/tests/api/test_transactions.py` carries the same
  three tests at the HTTP layer (`test_list_endpoint_default_orders_by_date_desc`,
  `test_list_endpoint_default_includes_planned_at_due_date`,
  `test_list_endpoint_invalid_sort_returns_422`).
- MCP mirror: `backend/tests/mcp/test_core_reads.py` carries
  `test_mcp_list_transactions_default_orders_by_date_desc` and
  `test_mcp_list_transactions_explicit_sort_date_asc`.
- Literal validation at the MCP boundary: a typo in `sort` or `order` is
  caught by Pydantic before reaching the service.
- Manual smoke test on `http://localhost:3000/transactions` after the
  change: enter a new transaction dated today and confirm it appears at
  the top of the list, alongside any planned txs whose due-dates fall in
  the near future.
- Code-review checklist: any new listing of transactions must either
  inherit the new default or pass an explicit sort param. The candado
  in `planned.to_pay` must not be removed without updating the test
  that locks it.