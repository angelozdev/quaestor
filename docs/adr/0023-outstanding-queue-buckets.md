# 0023. Outstanding queue: overdue + upcoming buckets

- **Status:** accepted
- **Date:** 2026-07-03
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

`services.planned.to_pay(session, since, until)` filtered with
`date_from=since`. The widget and the `/to-pay` page compute
`since = startOfWeek(now, Mon)` or `since = startOfMonth(now)`. When
today's date crosses a week or month boundary, planned items with
`date < since` disappear from the response. The user discovered this on
2026-07-02: four pending payments due 2026-06-27/28 (Tigo, Claro, Uber,
CC San Diego) vanished from the dashboard "Por pagar" widget and the
`/to-pay` page. Verified by querying
`GET /api/planned/to-pay?since=2026-06-29&until=2026-07-05` (4 items, the
4 reported missing) vs. `?since=2026-06-15&until=2026-07-31` (9 items,
the 4 included).

The user's contract is "lo que está vencido debe aparecer SIEMPRE hasta
que se resuelva" — overdue items must remain visible until confirmed
(`confirm_payment`) or skipped (`skip_payment`). The current `date_from`
filter violates that contract for items that age out of the window.

## Decision drivers

- Operational visibility: the widget, `/to-pay` page, and MCP `to_pay`
  tool all show the user what they owe or are about to owe. Overdue
  items belong in this view without fail.
- Retrospective integrity: the monthly report (line 201 of
  `services/reports.py`) is a retrospective of a specific month. An
  item overdue from a prior month belongs to that prior month's
  retrospective, not this one's.
- One domain object, two callers: the same `to_pay` function serves
  both views. The caller declares its intent via a kwarg.
- SOLID: the operational and retrospective views are two strategies
  over the same underlying data. The cleanest separation is at the
  call site (one kwarg), not at the function (two functions).

## Considered options

1. Add a `?include_overdue=true` query param at the REST layer and pass
   it through to a `?include_overdue` param at the service layer. The
   widget/page/MCP pass `true`; the monthly report passes `false`.
2. Add a separate `/planned/overdue` endpoint that returns only the
   overdue bucket. The widget composes both endpoints. The monthly
   report calls only `/to-pay`. Zero changes to the existing `to_pay`
   contract.
3. Make `to_pay` return `{overdue, upcoming, total_base}` (a single
   structured response) with a kwarg `retrospective: bool = False`
   controlling whether the overdue bucket contains items overdue from
   before `since`. The widget renders both buckets as sections; the
   monthly report calls with `retrospective=True` and reads
   only `queue.upcoming`.
4. Always include overdue (remove `since` from the service). Each
   caller filters post-hoc if it wants a narrower window.

## Decision outcome

Chosen option: **3 — structured `OutstandingQueue` value object with
two mutually-exclusive buckets.** The service produces
`OutstandingQueue(overdue=[...], upcoming=[...])`. The overdue bucket
contains planned txs with `date < today AND date <= until` when
`retrospective=False` (the default for the operational view);
empty otherwise. The upcoming bucket always contains planned txs with
`date in [max(since, today), until]`. The two ranges are disjoint by
construction, so the buckets are mutually exclusive.

Option 1 (boolean query param) is functionally equivalent to 3 but
leaks the visibility policy to the wire format — every new caller
would have to know to opt in. Option 2 (separate endpoint) is
defensible but splits the "outstanding queue" domain concept across
two endpoints with no shared object. Option 4 (remove `since` from the
service) pushes the window policy to every caller, duplicating logic
across the widget, the page, the MCP, and any future consumer.

The `OutstandingQueue` is a frozen dataclass with two slots-based
fields plus two `@property` derived values (`total_base`, `is_empty`)
and a `from_lists()` classmethod. It depends on nothing but
`Transaction`. Adding a third bucket later (e.g. `forecast` for items
due > until) is additive: a new field on the VO, a new query branch
in `to_pay`, zero changes to existing callers.

### Pros and cons of the options

**3. OutstandingQueue value object + `retrospective` kwarg**
- Good, because "outstanding queue" is a single domain concept and
  the VO captures it.
- Good, because the wire format and the renderer both reflect the
  same shape; no translation layers.
- Good, because the mutual-exclusion invariant is structural (the
  two date ranges don't overlap by construction).
- Good, because adding a third bucket later is additive.
- Bad / cost, because the wire format of `GET /planned/to-pay` changes
  from `{items, total_base}` to `{overdue, upcoming, total_base}`.
  This is a breaking change for any external consumer. The only
  in-tree consumer is the frontend; the only MCP consumer is
  `to_pay_table` (which is updated in the same change). REST consumers
  outside this codebase should be flagged in release notes.

**1. `?include_overdue=true` boolean param**
- Good, because the change is small and localized.
- Bad, because the visibility policy leaks to the wire format. Every
  new consumer must know to opt in, and a forgetting caller gets the
  "wrong" view silently.

**2. Separate `/planned/overdue` endpoint**
- Good, because the existing `to_pay` contract is unchanged.
- Bad, because "outstanding queue" is one concept; splitting it across
  two endpoints is a leaky abstraction. The widget must compose both
  and present them as one UI.

**4. Remove `since` from the service**
- Good, because the service is the simplest it can be.
- Bad, because the "compute the right window" logic gets duplicated
  in every caller. If the visibility rule ever changes (e.g. "exclude
  items older than 90 days"), every caller updates.

## Consequences

- Good: `to_pay` always surfaces overdue items in the operational view
  (widget, page, MCP, REST). The user's contract "vencido = siempre
  visible" is enforced in the service, not in the UI.
- Good: the monthly report continues to be a true retrospective of
  its month; the overdue bucket is empty by construction.
- Good: `OutstandingQueue` is a frozen value object — its invariants
  are encoded in the type (frozen, mutually-exclusive buckets via
  construction discipline).
- Good: adding a third bucket later is additive (one new field, one
  new query branch).
- Bad / cost: breaking change at the REST boundary. No external
  consumer in this repo; flag in release notes of the deploy.
- Bad / cost: the MCP `to_pay` markdown output changes from a single
  table to two sections. The chat persona receives a different tool
  output; tested for backward compat in `test_temporal.py`.
- Follow-up: if a `forecast` bucket is wanted (items due > until, e.g.
  for "next 90 days" planning), add it as a third field on the VO
  without breaking the contract.
- Follow-up: when the ledger grows past a few thousand planned rows,
  consider an index on `transaction(status, date)` to make the two
  bucket queries fast. Defer until data warrants.

## Confirmation

- VO invariants:
  `backend/tests/domain/test_planned_queue.py::test_outstanding_queue_*`
  cover mutual exclusion, total sum, is_empty, all_items ordering,
  and frozen-ness.
- Service behavior + bug reproduction:
  `backend/tests/services/test_planned.py::test_to_pay_includes_overdue_before_since`
  inserts an item dated `today - 10 days`, calls `to_pay(since=today+5,
  until=today+10, retrospective=False)`, and asserts the item
  appears in `queue.overdue`. The pre-fix service would have returned
  an empty `items` list (date < since).
- Monthly report retrospective:
  `backend/tests/services/test_planned.py::test_to_pay_retrospective_true_omits_overdue_bucket`
  inserts a prior-month overdue and an in-month planned; the report's
  call with `retrospective=True` produces an empty overdue
  bucket.
- REST wire format:
  `backend/tests/api/test_planned.py::test_to_pay_response_includes_overdue_before_since`
  reproduces the user's bug at the HTTP layer.
- MCP markdown:
  `backend/tests/mcp/test_temporal.py::test_to_pay_table_renders_two_sections`
  asserts "## ⚠️ Overdue" and "## Upcoming" both appear when both
  buckets are present.
- Frontend sections:
  `frontend/components/to-pay-widget.test.tsx::renders_overdue_section_when_overdue_items_present`
  asserts the "Vencidos" header renders when the response has overdue
  items; the negative case asserts it does not.
- Code-review checklist: any new caller of `to_pay` must either accept
  the default `retrospective=False` (operational) or pass
  `True` explicitly (retrospective). The candado is the kwarg name.

## Confirmation (landed)

The plan `docs/superpowers/plans/2026-07-03-outstanding-queue.md` was
executed task-by-task. Every "Confirmation" reference in the proposed
ADR (above) is now backed by a green test:

- VO invariants: `tests/domain/test_planned_queue.py` — 5 tests green.
- Service behavior + bug reproduction:
  `tests/services/test_planned.py::test_to_pay_includes_overdue_before_since` —
  green (pre-fix would have dropped the item).
- Monthly report retrospective:
  `tests/services/test_planned.py::test_to_pay_retrospective_true_omits_overdue_bucket` —
  green.
- REST wire format:
  `tests/api/test_planned.py::test_to_pay_response_includes_overdue_before_since` —
  green.
- MCP markdown: `tests/mcp/test_temporal.py::test_to_pay_table_renders_two_sections`
  + 3 sibling tests — green.
- Frontend sections: `frontend/components/to-pay-widget.test.tsx` — 5 tests green.
