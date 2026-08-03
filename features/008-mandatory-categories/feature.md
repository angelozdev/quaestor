---
title: "Category becomes mandatory on every expense and income"
slug: mandatory-categories
number: 008
status: ready
autonomy_level: medium
branch: mandatory-categories
area: core
owner: angelo
assignee: local
tracker_ref: local
roadmap_ref: mandatory-categories
relevant_adrs: [0028]
created: 2026-08-02
intake: discuss
---

# Category becomes mandatory on every expense and income

## Outcome

Every expense and every income carries a category — the app refuses to store one
without it, and no historical row is left uncategorised. Transfers carry none,
by rule. Every peso the owner moves in or out becomes visible to per-category
reports, monthly averages and any future envelope, because there is no longer a
silent bucket for money to fall into.

## Scope

- **The rule.** `expense` and `income` MUST carry a category. `transfer` MUST
  NOT. Enforced in the services layer (the single write path for API, MCP and
  UI alike) and pinned by a migration.
- **Backfill** the posted rows that predate the rule, and the 10 active
  recurring items missing a category.
- **Product decision** recorded in `docs/decisions/product-decisions.md`.
- **Direction.** A category belongs to one direction: income categories are
  offered only when recording money coming in, expense categories only when
  recording money going out. Decided at AC time 2026-08-02 — see `acs.md`.
- **Out of scope:** re-categorising rows that already have a category, and any
  change to the category taxonomy itself. `skipped` rows are **in** scope — the
  owner's rule admits no exception for charges that never happened.

## Why transfers are the exception

A transfer between the owner's own accounts is not spending — net worth does not
change. Categorising one would count the same money twice: once moving from
Nu Débito into Emergency Fund, and again when it is finally spent out of
Emergency Fund. All 39 existing transfers are correctly uncategorised and must
stay that way; the rule has to distinguish by transaction type, not apply
blanket NOT NULL.

## The gap, measured in production 2026-08-02 — since closed

**Backfilled the same day** (see `acs.md` AC-19). Every figure below is now
zero except the transfer row, which is the rule working. Kept as the record of
why the feature exists.


Read-only counts against the local Postgres (ADR-0030):

| | Rows | Uncategorised |
|---|---|---|
| `expense` posted | 477 | **28** |
| `expense` planned | 5 | 4 |
| `expense` skipped | 66 | 64 |
| `income` posted | 22 | **7** |
| `income` skipped | 28 | 28 |
| `transfer` (all) | 39 | 39 — correct, leave alone |

Money invisible to every report, posted and confirmed:

```
expense    14 movements    $2.072.854 COP
expense    14 movements    US$7.486,68
income      2 movements    $7.003.101 COP
income      5 movements   US$10.495,55
```

Active recurring items missing a category: **10 of 14** — all 3 incomes (Ubidots
Salary, Keystone Salary, Ubidots Bonus) despite `💼 Salary` existing, plus
Hogaru, EPM, Internet Hogar, Plan de datos, Plan de datos Mamá, Smart Fit and
DolarApp Premium.

## Source links

- Surfaced during the 2026-08-02 `discuss` session on `003-sinking-funds`, when
  the funding-rule proposal could only derive 3 envelopes from recurring items
  instead of 8.
- `docs/adr/0028-bounded-query-read-path-for-monthly-aggregates.md` — the read
  path that consumes `category_id`.

## Code co-locations

- `backend/src/quaestor/domain/models.py` — `Transaction.category_id`,
  `RecurringItem.category_id` (both nullable today).
- `backend/src/quaestor/services/transactions.py`,
  `services/recurring.py`, `services/planned.py` — the write paths.
- `backend/src/quaestor/migrations/` — the enforcing revision. Autonomy drops to
  `low` here per the manifest path override; the migration touches real data and
  needs a fresh backup first (`just backup`, ADR-0030).

## Notes

- **Sequencing:** lands before `003-sinking-funds`. With categories in place the
  funding-rule engine derives 8 envelopes from recurring items instead of 3, and
  Internet resolves to its exact $85.000 recurring amount instead of a $149.585
  three-month average inflated by uncategorised rows.
- Owner's framing, 2026-08-02: *"Todos los pagos recurrentes deberían tener
  categoría. Cualquier cosa que yo haga debe entrar en una categoría, debe."*
- **Both AC-time questions resolved 2026-08-02.** A missing category is created
  from the movement form without leaving it (the `4x1000` charges were the real
  case that forced it); `skipped` rows carry a category like everything else.
- **Historical backfill done 2026-08-02**, after a fresh backup
  (`quaestor-local-2026-08-02.dump`). 131 rows resolved — 101 by setting the 10
  recurring items that lacked a category, 30 individually. Seven new categories
  created. The remaining work is the rule and the migration, not the data.
- **Parked, not part of this feature:** transfer categories (Monarch and Lunch
  Money both have them; the owner improvised `🔄 Payment / Transfer`),
  splitting one movement into two, duplicate `skipped` rows produced by the
  recurring engine, and negative `amount` values used as refunds. Full list in
  `acs.md`.
