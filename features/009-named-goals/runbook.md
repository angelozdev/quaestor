---
slug: 009-named-goals
checkpoint: 4
created: 2026-08-08
status: partial
steps:
  - id: backup-before-0013
    description: "Fresh pg_dump of the local production Postgres to iCloud, dated today (ADR-0030)"
    owner: human
    command: "just backup"
    evidence: "quaestor-local-2026-08-08.dump, 47K, in iCloud QuaestorBackups"
    completed: true
    blocking_acs:
      - migration-0013

  - id: migration-0013
    description: "Additive migration — meta, meta_contribution, transaction.meta_id, category.counts_as_saving. Nothing dropped."
    owner: human
    command: "just migrate"
    evidence: "alembic_version 0012 -> 0013, applied 2026-08-08. Rehearsed up and down on a throwaway SQLite first; downgrade verified to remove all four objects."
    completed: true
    blocking_acs:
      - AC-1
      - AC-6
      - AC-41

  - id: verify-0013
    description: "Confirm the schema landed and no row moved: the four objects exist, fund still has 0 rows, transaction still has 635"
    owner: agent
    command: "docker exec -i quaestor-db-1 psql -U quaestor -d quaestor -c \"SET default_transaction_read_only = on; SELECT COUNT(*) AS metas FROM meta; SELECT COUNT(*) AS funds FROM fund; SELECT COUNT(*) AS movs FROM \\\"transaction\\\";\""
    evidence: "635 movements, 43 categories, 0 funds, 14 recurring items, 7 accounts — all unchanged. meta 0, meta_contribution 0, linked movements 0, saving-marked categories 0. `exclude_from_budget` still true on Payment/Transfer and Refund."
    completed: true
    blocking_acs: []

  - id: backup-before-0014
    description: "Second fresh backup, dated the day 0014 runs — 0014 is the destructive one"
    owner: human
    command: "just backup"
    evidence: null
    completed: false
    blocking_acs:
      - migration-0014

  - id: confirm-no-dated-funds
    description: "Re-confirm no fund uses the dated rule immediately before dropping it. Read-only. Expected: 0 rows."
    owner: agent
    command: "docker exec -i quaestor-db-1 psql -U quaestor -d quaestor -c \"SET default_transaction_read_only = on; SELECT rule, COUNT(*) FROM fund GROUP BY rule;\""
    evidence: null
    completed: false
    blocking_acs:
      - migration-0014

  - id: migration-0014
    description: "Destructive migration — drop fund.target_amount, fund.target_month and the target_by_date enum value. Runs only after the withdrawal code is merged."
    owner: human
    command: "just migrate"
    evidence: null
    completed: false
    blocking_acs:
      - AC-40
---

# runbook — 009 named-goals

Two migrations on **real data**. CHARTER §7 requires the owner in person for
both; the manifest caps `backend/src/quaestor/migrations/**` at autonomy `low`
regardless of this feature's level; ADR-0030 requires a fresh dump before each.

## Why two and not one

`0013` **adds only**. The app keeps running on the code that exists today, so
if anything goes wrong it goes wrong before any behaviour depends on it.

`0014` **drops** `fund.target_amount`, `fund.target_month` and the
`target_by_date` enum value. It runs **after** the withdrawal code is merged,
never before — the reverse order would leave the app reading columns that are
gone.

## What is at risk, stated plainly

Production on 2026-08-08: **635 movements, 43 categories, 14 recurring items,
7 accounts, 0 funds**. `0014` touches the `fund` table, which is empty, and the
`fundrule` enum. Nothing is converted and no row is rewritten — but a dropped
column does not come back, and `0012`'s own docstring is the standing reminder:
*"the way back is the dump, not the downgrade."*

`just migrate` is already backup-gated — it refuses to run without a dump dated
today — so the gate is enforced by the recipe, not only by this file.

## Order

```
1  just backup                    ← owner
2  just migrate  (0013, additive) ← owner
3  verify 0013                    ← agent, read-only
   … phases 1–4 implement against the new schema …
   … phase 5's withdrawal code is written and merged …
4  just backup                    ← owner, a second, fresh dump
5  confirm no dated funds         ← agent, read-only
6  just migrate  (0014, drops)    ← owner
```

**Nothing in Phase 1 begins until step 2 is checked off.** Acceptance scenarios
for AC-1, AC-6 and AC-41 cannot claim green before the schema they read exists.

## If the api container is running

`just dev-prod` starts the api, and the api runs `alembic upgrade head` on
startup. That is a migration by another name. When only a read is needed, start
the database alone:

```
QUAESTOR_ENV_FILE=backend/.env.local.postgres docker compose \
  --env-file backend/.env.local.postgres --profile pg up -d --wait db
```

and stop it again afterwards. That is how the 2026-08-08 survey was taken
without writing anything.
