---
title: "Transactions CRUD with tags, categories and FX"
slug: transactions-crud
number: 002
status: done
autonomy_level: medium
branch: transactions-crud
area: core
owner: angelo
assignee: local
tracker_ref: local
roadmap_ref: transactions-core
relevant_adrs: [0021, 0027, 0031, 0032]
created: 2026-07-28
intake: onboarding
---

# Transactions CRUD with tags, categories and FX

## Outcome

The user records, edits, permanently deletes (balance-reversing) and filters
expenses, incomes and transfers; each transaction carries optional category
and free-form tags manageable from every surface, COP figures are computed at
read time (feature 005), and lists render newest-activity-first with
URL-driven filters. Mistaken transfers are deletable as an atomic pair.

## Scope

- CRUD endpoints (`api/routers/transactions.py`) + service layer.
- Tags M2M (add/remove on create and edit, UI + API + agent — AC-6, target),
  optional category, read-time COP equivalent (ADR-0031).
- Transfer pair deletion with direction stored (AC-5, target — schema change,
  ADR due at plan time).
- Default listing order `date DESC, id DESC`, planned rows visible (ADR-0021).
- URL query params as filter source of truth (ADR-0027).
- Transactions page + create/edit dialogs.

Out: CSV bulk import (parked feature `csv-importer`), recurring
materialization (feature `recurring-engine`).

## Source links

- Design specs (pre-DAE): P0/P1 sections in `docs/superpowers/specs/`.
- `docs/adr/0021-default-transaction-listing-order-created-at-desc.md`,
  `docs/adr/0027-url-query-params-as-filter-source-of-truth.md`.

## Code co-locations

- Backend: `backend/src/quaestor/services/transactions.py`,
  `backend/src/quaestor/api/routers/transactions.py`,
  `backend/src/quaestor/domain/models.py`.
- Frontend: `frontend/app/(app)/transactions/page.tsx`,
  `frontend/components/transaction-create-dialog.tsx`,
  `frontend/components/transaction-edit-dialog.tsx`,
  `frontend/lib/use-url-filters.ts`.

## Notes

Shipped before DAE adoption (onboarding intake 2026-07-28). Core data surface.
ACs discovered 2026-07-31 with four user decisions: full tagging on every
surface (new), permanent delete confirmed (the old "soft-deletes" outcome
wording was drift), transfers deletable as a pair (new; schema + migration),
transfer sides independent but pair always visible. Next step:
`/engineer.atdd` (Checkpoint 3).
