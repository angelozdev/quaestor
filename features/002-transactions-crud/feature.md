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
relevant_adrs: [0021, 0027]
created: 2026-07-28
intake: onboarding
---

# Transactions CRUD with tags, categories and FX

## Outcome

The user records, edits, soft-deletes and filters expenses, incomes and
transfers; each transaction carries optional category, free-form tags and an
FX conversion to the base currency, and lists render newest-first with
URL-driven filters.

## Scope

- CRUD endpoints (`api/routers/transactions.py`) + service layer.
- Tags M2M, optional category, FX-to-base per transaction.
- Default listing order `created_at desc` (ADR-0021).
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
Next step: `/engineer.discover-acs` in reverse-engineer mode.
