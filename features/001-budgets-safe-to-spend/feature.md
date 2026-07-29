---
title: "Hybrid budget: envelopes with rollover + safe-to-spend"
slug: budgets-safe-to-spend
number: 001
status: done
autonomy_level: medium
branch: budgets-safe-to-spend
area: budget
owner: angelo
assignee: local
tracker_ref: local
roadmap_ref: hybrid-budget
relevant_adrs: [0006, 0028]
created: 2026-07-28
intake: onboarding
---

# Hybrid budget: envelopes with rollover + safe-to-spend

## Outcome

The user assigns money to per-category monthly envelopes whose unspent balance
rolls over into the next month, and sees a single global **safe-to-spend**
headline — the money not yet assigned to any envelope — computed so no peso is
ever counted twice (assignment cascade: forecast income − committed −
assigned-to-envelopes = safe-to-spend).

## Scope

- `PUT /budgets` envelope upsert per category × calendar month.
- Rollover semantics on month close (positive-only rollover).
- `GET /budgets/safe-to-spend` headline integrating recurring + planned +
  proposed goal contributions ("committed").
- MCP read parity (`mcp/tools/budgets_reads.py`).
- Budgets page + dashboard safe-to-spend card.

Out: month-close orchestration itself (feature `month-close-rollover`),
goal proposal hooks (feature `goal-contribution-hooks`).

## Source links

- Product decisions: ADR-002 (hybrid budget), ADR-003 (safe-to-spend =
  unassigned money), ADR-004, ADR-005 — `docs/decisions/product-decisions.md`.
- Technical: `docs/adr/0006-goals-and-budgets-write-api-with-mcp-parity.md`,
  `docs/adr/0028-bounded-query-read-path-for-monthly-aggregates.md`.
- Design spec (pre-DAE): P4 sections in `docs/superpowers/specs/`.

## Code co-locations

- Backend: `backend/src/quaestor/services/budgets.py`,
  `backend/src/quaestor/api/routers/budgets.py`,
  `backend/src/quaestor/mcp/tools/budgets_reads.py`,
  `backend/src/quaestor/services/month_aggregate.py` (read path).
- Frontend: `frontend/app/(app)/budgets/page.tsx`, dashboard STS card in
  `frontend/app/(app)/page.tsx`.

## Notes

Shipped before DAE adoption (onboarding intake 2026-07-28). Product
differentiator — first in the consolidation backlog. Next step:
`/engineer.discover-acs` in reverse-engineer mode.
