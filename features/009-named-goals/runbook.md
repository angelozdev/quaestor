---
slug: 009-named-goals
checkpoint: 4
created: 2026-08-08
status: done
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

  - id: backup-before-0015
    description: "Fresh backup dated the day 0015 runs — 0015 is the destructive one"
    owner: human
    command: "just backup"
    evidence: "quaestor-local-2026-08-09.dump, 53K, in iCloud QuaestorBackups, written 15:07. `just migrate` refuses without a dump dated today, so the guard was in force as well as the habit."
    completed: true
    blocking_acs:
      - migration-0015

  - id: confirm-no-dated-funds
    description: "Re-confirm no fund uses the dated rule immediately before dropping it. Read-only. Expected: 0 rows."
    owner: agent
    command: "docker exec -i quaestor-db-1 psql -U quaestor -d quaestor -c \"SET default_transaction_read_only = on; SELECT rule, COUNT(*) FROM fund GROUP BY rule;\""
    evidence: "2026-08-08, read-only: `SELECT count(*) FROM fund` = 0 and `SELECT count(*) FROM fund WHERE rule = 'target_by_date'` = 0. 0015 will not refuse. Re-run on the day it is applied — this is a same-day check, and the SQLite sandbox proves the guard bites: it holds one dated fund and 0015 aborted that container's startup with the intended message."
    completed: true
    blocking_acs:
      - migration-0015

  - id: migration-0015
    description: "Destructive migration — drop fund.target_amount, fund.target_month and the target_by_date enum value. The withdrawal code is merged; 0015 refuses on its own if any fund still uses the rule."
    owner: human
    command: "just migrate"
    evidence: "Applied 2026-08-09 by the owner. `alembic upgrade head` ran 0013 -> 0016 in one go, so 0014 (meta.cancelled_month) and 0016 (meta_amendment) landed with it. `SELECT version_num FROM alembic_version` = 0016."
    completed: true
    blocking_acs:
      - AC-40

  - id: verify-after-0016
    description: "Confirm the schema landed and no row moved: the dated rule is gone from the enum, the three meta tables exist, and every count is what it was."
    owner: agent
    command: "QUAESTOR_ENV_FILE=backend/.env.local.postgres docker compose --env-file backend/.env.local.postgres --profile pg exec -T db sh -c 'psql -U \"${POSTGRES_USER:-quaestor}\" -d \"${POSTGRES_DB:-quaestor}\" -tAc \"...\"'"
    evidence: "2026-08-09, read-only. `alembic_version` = 0016. Enum `fundrule` = fixed, average, from_recurring — `target_by_date` gone. Tables meta, meta_contribution, meta_amendment all present; `meta` carries stated_opening, closed, archived, cancelled_month. Counts UNCHANGED from the 0013 check: 635 movements, 7 accounts, 43 categories, 0 funds, 14 recurring items. New tables empty and 0 categories marked as saving, which is the expected cold start. `fund.anchor_month`/`anchor_amount` remain and should — they are product ADR-041's statement of what a fund already holds, not the dated rule's."
    completed: true
    blocking_acs: []
---

# runbook — 009 named-goals

Two migrations on **real data**. CHARTER §7 requires the owner in person for
both; the manifest caps `backend/src/quaestor/migrations/**` at autonomy `low`
regardless of this feature's level; ADR-0030 requires a fresh dump before each.

## Why two and not one

`0013` **adds only**. The app keeps running on the code that exists today, so
if anything goes wrong it goes wrong before any behaviour depends on it.

`0014` adds `meta.cancelled_month` — the one thing about a cancellation that
cannot be derived. Also additive, also already applied.

`0015` **drops** `fund.target_amount`, `fund.target_month` and the
`target_by_date` enum value. It runs **after** the withdrawal code is merged,
never before — the reverse order would leave the app reading columns that are
gone. The code is merged now, so this is the only step left.

It refuses on its own if any fund still uses the rule, with a message saying
why: each one is a decision about what the owner was saving for, and a
migration cannot make it.

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
✓ 1  just backup                       ← owner
✓ 2  just migrate  (0013, additive)    ← owner
✓ 3  verify 0013                       ← agent, read-only
✓    phases 1–4 built against the new schema
✓    0014 (cancelled_month) written and rehearsed
✓    phase 5's withdrawal code is merged
  4  just backup                       ← owner, a fresh dump
  5  confirm no dated funds            ← agent, read-only
  6  just migrate  (0014 + 0015)       ← owner
```

**Steps 4 to 6 are the only ones left.** Nothing in Phase 1 began until step 2 was checked off. Acceptance scenarios
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
