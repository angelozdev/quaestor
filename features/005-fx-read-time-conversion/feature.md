---
title: "Read-time FX: single TRM value as source of truth + cross-currency transfers"
slug: fx-read-time-conversion
number: 005
status: ready
autonomy_level: medium
branch: fx-read-time-conversion
area: core
owner: angelo
assignee: local
tracker_ref: local
roadmap_ref: fx-read-time-conversion
relevant_adrs: [0006, 0009, 0021, 0031]
created: 2026-07-30
intake: discuss
---

# Read-time FX: single TRM value as source of truth + cross-currency transfers

## Outcome

All base-currency (COP) figures are computed at read time from the single
current TRM value — never frozen per transaction. The user corrects the TRM
and every report, budget and total updates.
Transfers between accounts with different currencies are allowed by
recording the two physical amounts (sent and received) with no stored rate.

## Scope

- Drop `Transaction.to_base` and `Transaction.fx_rate` (migration on real
  data — low-autonomy gate via path override).
- TRM becomes a **single scalar value** — the dated `fx_rate` table is
  dropped in the same migration (user decision in discover-acs, amends
  ADR-0031). The daily job overwrites the value; manual set overwrites it
  too; last write wins.
- Single read-time conversion helper: `amount × current TRM`; COP is
  identity. Applied uniformly — "everything at current rate", no per-date
  semantics (user decision in discuss; IAS 21 hybrid explicitly rejected).
- No per-transaction rate override — the TRM value is the only source.
  Registration no longer requires a rate; an unset TRM raises
  `MissingRate` at read time for any base-currency read, even COP-only
  (fail loud, no silent rate-1 fallback).
- Cross-currency transfers: remove the same-currency validation; input
  takes two explicit amounts (sent, received); each leg stores its own
  `amount`/`currency`; no rate stored (implicit = ratio of the amounts).
  The dialog shows the implied rate (received ÷ sent) as reference only —
  no ratio validation.
- Update all `to_base` consumers: reports, budgets, month_aggregate,
  goals, planned, recurring + REST/MCP schemas (parity per ADR-0006/0009).
- UI: normal dialog loses the FX-rate field; transfer dialog gains a
  second amount when account currencies differ.

Out: making `Settings.base_currency` functional (COP stays hardcoded;
documented as known issue in the ADR), transfer deletion (possible unlock
noted for the plan, not committed).

## Source links

- Discuss session 2026-07-30 (handoffs/2026-07-30T*-discuss.md).
- Industry references: Beancount price-DB report-time conversion,
  Firefly III primary-currency conversion + two-amount transfers, IAS 21.
- ADR-0031 (to be written): read-time FX conversion decision.

## Code co-locations

- Backend: `backend/src/quaestor/domain/money.py`,
  `backend/src/quaestor/services/fx.py`,
  `backend/src/quaestor/services/transactions.py`,
  `backend/src/quaestor/domain/models.py`,
  `backend/src/quaestor/services/{reports,budgets,month_aggregate,goals,planned,recurring}.py`,
  `backend/src/quaestor/api/schemas.py`, `backend/src/quaestor/mcp/`.
- Frontend: `frontend/components/transaction-create-dialog.tsx`,
  `frontend/components/transaction-edit-dialog.tsx`,
  `frontend/app/(app)/transactions/page.tsx`.

## Notes

Promoted from discuss 2026-07-30. Replaces the undocumented frozen-snapshot
FX design (`to_base` frozen at registration). Key user decisions: everything
at current rate (accepting that closed months' totals move with the TRM);
no override; cross-currency transfers in scope.

Discover-acs decisions (2026-07-30): TRM is a single scalar value, dated
table dropped (amends ADR-0031); reads always require the TRM, even
COP-only; implied transfer rate shown as info only; migration = clean drop
with `just backup` immediately before.
