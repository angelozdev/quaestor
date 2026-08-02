---
title: "Planned payments and the to-pay confirmation queue"
slug: planned-payments-to-pay
number: 006
status: done
autonomy_level: medium
branch: planned-payments-to-pay
area: planning
owner: angelo
assignee: local
tracker_ref: local
roadmap_ref: planned-to-pay
relevant_adrs: [0021, 0023, 0031, 0032, 0034]
created: 2026-07-31
intake: onboarding
---

# Planned payments and the to-pay confirmation queue

## Outcome

The user plans a future payment, sees everything outstanding for a window split
into overdue and upcoming buckets with a single COP total at read-time FX, and
then either confirms it — adjusting the real amount and date, moving the account
balance, materializing a planned transfer into a posted pair — or skips it. The
queue is the only path from `planned` to `posted`.

## Scope

- Plan a standalone one-off `planned` expense with payee, amount, currency,
  due date, account, optional category and notes; no balance movement.
- Outstanding queue over `[since, until]`: `overdue` (due before today, capped
  at `until`) and `upcoming` (from `max(since, today)` to `until`), mutually
  exclusive by construction, each ordered by date ascending, plus the
  `retrospective` mode that empties the overdue bucket (ADR-0023).
- Read-time COP total across both buckets at the current TRM (ADR-0031).
- Confirm: `planned -> posted`, optional amount/date override, balance applied,
  post-confirm hooks fired inside the same transaction, rollback on failure.
- Confirm of a planned transfer: materialize the destination row plus a new
  source leg sharing a `transfer_group_id`, with stored leg direction
  (ADR-0032, migration `0007_correct_planned_confirm_directions`); source is the
  global `Settings.default_source_account_id`.
- Skip: `planned -> skipped`, syncing the linked recurring occurrence, and the
  reverse transition that returns a mistakenly skipped payment to the queue
  (AC-8, target — new behaviour, ADR due at plan time).
- The queue carries only obligations: planned incomes are excluded from both
  buckets and from the total (AC-15, target — defect found at AC discovery;
  the shipped queue adds a planned salary to the amount owed).
- The conversational answer states the combined amount owed across both
  buckets, matching the screen's headline figure (AC-24, target — defect found
  at spec time; the shipped answer reports per-section subtotals only).
- Surfaces: `Por pagar` page (week/month scope toggle, confirm and plan
  dialogs), dashboard to-pay widget, REST router, MCP tools `to_pay`,
  `confirm_payment`, `skip_payment`, `restore_payment`.

Out of scope, asserted only as seams (the confirm fires them; their own
behaviour belongs to their features):

- Recurring occurrence materialization and its `planned`/`posted`/`skipped`
  sync — feature `recurring-engine` (consolidation task 3).
- Goal contribution recorded by the post-confirm hook registered in
  `services/bootstrap.py` — feature `goal-contribution-hooks` (task 4).
- Retrospective monthly report consuming `to_pay(retrospective=True)` —
  feature `monthly-report` (task 5).

## Source links

- `.engineer/consolidation.md` — consolidation task 2 (this folder covers both
  the `planned-payments-to-pay` and `outstanding-queue-buckets` inventory rows;
  same surface).
- `docs/adr/0023-outstanding-queue-buckets.md`,
  `docs/adr/0031-read-time-fx-conversion-from-the-rate-table-replaces-frozen-per-transaction-snapshots.md`,
  `docs/adr/0032-stored-transfer-leg-direction-enables-atomic-pair-deletion.md`.
- Design specs (pre-DAE): P3 sections in `docs/superpowers/specs/`.

## Code co-locations

- Backend: `backend/src/quaestor/services/planned.py`,
  `backend/src/quaestor/domain/planned.py`,
  `backend/src/quaestor/api/routers/planned.py`,
  `backend/src/quaestor/mcp/tools/temporal.py`,
  `backend/src/quaestor/mcp/registry.py`,
  `backend/src/quaestor/migrations/versions/0007_correct_planned_confirm_directions.py`.
- Frontend: `frontend/app/(app)/to-pay/page.tsx`,
  `frontend/app/(app)/to-pay/to-pay.schema.ts`,
  `frontend/components/to-pay-widget.tsx`,
  `frontend/lib/api/planned.ts`.

## Notes

Shipped before DAE adoption; formalized 2026-07-31 as consolidation task 2.
Two inventory rows merged into one folder by the backlog decision — the
`OutstandingQueue` VO exists only to serve `services.planned.to_pay`, so
splitting them would split one surface across two features.

Follows `002-transactions-crud`, which established the transfer-pair and
stored-direction groundwork this feature's confirm path depends on.

ACs discovered 2026-08-01 with five user decisions: planned incomes leave the
queue (new, defect), skipping becomes reversible (new), a missing exchange rate
keeps failing loudly (feature 005's AC-9 upheld, not superseded), resolving
something twice stays a refusal, and planning a one-off income stays out of
scope. Next step: `/engineer.atdd` (Checkpoint 3).
