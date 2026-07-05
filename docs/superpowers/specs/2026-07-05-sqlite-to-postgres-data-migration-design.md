# SQLite → Postgres Data Migration (Quaestor local-only posture)

**Date:** 2026-07-05
**Status:** design (pending approval)
**Implements:** the deferred "Future migration: SQLite → Postgres" section of
`docs/adr/0026-local-only-posture.md` (accepted 2026-07-05)
**Related:** ADR-0024 (Postgres replaces SQLite, accepted 2026-07-03),
ADR-0026 (Local-only posture, accepted 2026-07-05)

---

## Context

Quaestor's local-only posture (ADR-0026) leaves the **database** as the only
thing that leaves the user's Mac. The local SQLite at `.dev-data/quaestor.db`
holds the user's actual financial data today (it is not a sandbox). The remote
Postgres (Render.com Oregon, database `quaestor_production_db`) is already
provisioned and the connection URL is in `backend/.env.local.remote`
(gitignored). The schema in the remote Postgres is created automatically by
`alembic upgrade head` on first boot of `just dev-real` (via
`backend/src/quaestor/__main__.py`).

ADR-0026 explicitly deferred the data-migration recipe as out of scope:

> **Scope note:** this migration recipe is **out of scope for this plan**. We
> document the path here so the user has it when ready. A separate plan will own
> the migration recipe implementation.

This spec IS that separate plan. It is operational, not architectural — the
strategy was settled by ADR-0026 and ADR-0024. No new ADR is needed.

## Decisions log (locked during brainstorming, 2026-07-05)

| Fork | Choice |
|---|---|
| **Local SQLite after migration** | Archive indefinitely to `~/quaestor-sqlite-archive/quaestor.db`. User deletes manually. |
| **Migration tool** | Custom Python script (~120 LOC). pgloader is overkill at sub-10K rows. |
| **Verification tool** | Custom Python script (~80 LOC). Row counts + FK integrity + sample rows + ENUM validity. |
| **Scripts location** | `/tmp/quaestor-migration/`. Ephemeral; deleted on reboot. Reproducible from runbook §3. |
| **Justfile changes** | NONE. No new recipes. |
| **Repo code changes** | Only env cleanup + runbook. No new tracked code. |
| **Verification depth** | Row counts + FK integrity + 5 sample rows per table + ENUM validity. Not full per-table hash (overkill at this scale). |
| **Schema management** | Alembic (already automated via `__main__.py`). Scripts only copy rows; never alter schema. |
| **FK handling during copy** | `SET session_replication_role = 'replica'` (disables triggers/FK checks for the session), restored after copy. |
| **Sequence reset** | `SELECT setval(pg_get_serial_sequence(t, 'id'), (SELECT MAX(id) FROM t))` for every table with a serial PK. |
| **Pre-migration safety net** | `pg_dump` of remote Postgres to `/tmp/quaestor-migration/pre-migration.dump` before any copy. |
| **Idempotency** | Migration uses `INSERT ... ON CONFLICT (id) DO NOTHING` so a re-run after a partial failure is safe. |
| **Delivery shape** | One PR ships the runbook + env cleanup. Scripts themselves live outside the repo. |
| **New ADR** | NONE. Operational task, not architectural. ADR-0026 covers the strategy. |
| **Files in repo that DON'T change** | `justfile`, `docker-compose.yml`, `__main__.py`, `db.py`, models, migrations, `README.md`, `.gitignore`, all `.env.local.sqlite` / `.env.local.remote` / `.env.local.example` / `.env.local.remote.example` files, root `.envrc`, `frontend/.env.local` (used by `frontend/lib/server-auth.ts` and `frontend/lib/proxy/build-target-url.ts`). |

## Service topology (during migration)

```
┌──────────────────────────────────────────────────────────────────────────┐
│  User's Mac                                                              │
│                                                                          │
│   ┌─────────────────────┐     ┌──────────────────────────────────────┐   │
│   │ .dev-data/          │     │ /tmp/quaestor-migration/             │   │
│   │   quaestor.db       │     │   migrate.py                         │   │
│   │   (SQLite)          │     │   verify.py                          │   │
│   └────────┬────────────┘     │   README.txt                         │   │
│            │                  │   pre-migration.dump (after Step 1)  │   │
│            │ read             └──────────┬───────────────────────────┘   │
│            │                             │ write                         │
│            ▼                             ▼                               │
│   ┌─────────────────────────────────────────────────────────────────┐    │
│   │ Render.com Oregon                                               │    │
│   │   quaestor_production_db (Postgres 17)                          │    │
│   │   schema created by `alembic upgrade head` (already automated)  │    │
│   └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│   api container: STOPPED during migration (`just dev-down`)              │
│                                                                          │
│   After success:                                                         │
│     .dev-data/quaestor.db  →  ~/quaestor-sqlite-archive/quaestor.db      │
│     (mv, not rm; user deletes manually when ready)                       │
└──────────────────────────────────────────────────────────────────────────┘
```

## Ephemeral artifacts (in `/tmp/quaestor-migration/`)

### `migrate.py` (~120 LOC)

Outline:

1. **Pre-flight.** Read `QUAESTOR_DB` env (the remote URL). Open SQLite via
   `aiosqlite` at `.dev-data/quaestor.db`. Open Postgres via `psycopg`. Confirm
   api is not running (`subprocess.run(["pgrep", "-f", "uvicorn"], ...)` — if
   it returns 0, abort with a clear error).
2. **Schema bootstrap.** Connect to remote Postgres. Check `pg_class` for the
   `account` table; if missing, run `subprocess.run(["alembic", "upgrade",
   "head"], cwd="/path/to/backend")` (idempotent). Abort if alembic fails.
3. **Pre-migration safety dump.** Run `pg_dump` against the remote URL to
   `/tmp/quaestor-migration/pre-migration.dump`. For a first-time migration
   this will be near-empty; the dump is the rollback target if a future
   re-run ever needs it.
4. **Disable FK checks.** `cursor.execute("SET session_replication_role =
   'replica'")` on the Postgres connection.
5. **Copy each table** in dependency order:

   ```python
   TABLES_IN_DEPENDENCY_ORDER = [
       "account",
       "category_group",
       "fx_rate",
       "tag",
       "category",
       "goal",
       "settings",
       "budget",
       "recurring_item",
       "transaction",
       "goal_contribution",
       "recurring_occurrence",
       "transaction_tag",
   ]
   ```

   For each table:
   - `SELECT * FROM <table>` on SQLite (read all rows).
   - `INSERT INTO <table> (...) VALUES (...) ON CONFLICT (id) DO NOTHING` on
     Postgres in a single transaction (one `BEGIN; ... COMMIT;` per table).
   - Print `[migrate] account: 12 rows copied`.
6. **Reset Postgres sequences.** For every table with a serial PK:

   ```sql
   SELECT setval(
       pg_get_serial_sequence('account', 'id'),
       (SELECT COALESCE(MAX(id), 0) FROM account)
   );
   ```

   Repeat for all 13 tables.
7. **Re-enable FK checks.** `cursor.execute("SET session_replication_role =
   'origin'")`.
8. **Print summary.** Per-table row counts and total.

ENUMs are handled automatically: SQLite stores them as `TEXT`, the SQLAlchemy
`Enum(AccountType)` column emits the Python enum value on read, and Postgres
accepts the Python enum value into its native ENUM column. No manual casts.

### `verify.py` (~80 LOC)

Outline (each check prints PASS/FAIL; exit 1 on first FAIL):

1. **Row counts.** For every table in `TABLES_IN_DEPENDENCY_ORDER`:

   ```sql
   SELECT COUNT(*) FROM <table>  -- SQLite
   SELECT COUNT(*) FROM <table>  -- Postgres
   ```

   Numbers must match exactly.
2. **FK integrity.** For every FK column in every table, run:

   ```sql
   SELECT COUNT(*) FROM child c
   WHERE NOT EXISTS (SELECT 1 FROM parent p WHERE p.id = c.fk_column)
   ```

   Must return 0 for every FK.
3. **Sample rows (5 per table).** Pick 5 random rows from SQLite; for each,
   deep-compare every column to the Postgres row with the same `id`. Compare
   via SQLModel ORM (`session.get(Model, id)` on both sides, then `model
   == other_model` field-by-field after coercing `Decimal` to comparable
   types).
4. **ENUM validity.** For every Postgres-native ENUM column, fetch distinct
   values and confirm every value is in the enum's label list:

   ```sql
   SELECT DISTINCT type FROM account
   ```

   Each result must be in `('debit', 'credit', 'cash', 'savings')`. Repeat
   for all 9 ENUMs (`accounttype`, `goalstatus`, `txtype`, `recurringmode`,
   `intervalunit`, `txstatus`, `source`, `contributionsource`,
   `occurrencestatus`).
5. **Singleton settings row.** Confirm exactly 1 row in `settings`.
6. **Print summary.** `VERIFIED: 13 tables, N total rows, all checks PASS.`

### `README.txt` (~10 lines)

```
Quaestor SQLite → Postgres one-shot migration.
Scripts are ephemeral. Re-create from
docs/runbooks/sqlite-to-postgres-migration.md §3 if /tmp gets cleared.

Order:
  1. mkdir -p /tmp/quaestor-migration && cd /tmp/quaestor-migration
  2. (paste migrate.py and verify.py from runbook §3)
  3. export QUAESTOR_DB="postgresql://..."   (the remote URL)
  4. python3 migrate.py
  5. python3 verify.py    (must exit 0)
  6. (manual) just dev-real + browser smoke test
  7. (manual) archive SQLite  → runbook §4 step 8
  8. (manual) env cleanup    → runbook §4 steps 9-10
```

## File changes (in the repo)

| Path | Action | Why |
|---|---|---|
| `backend/.env.example` | **DELETE** | Superseded by `backend/.env.local.example` per ADR-0026. Not referenced by any recipe, code, or direnv. Has the same `QUAESTOR_DB=sqlite:////app/.dev-data/quaestor.db` line as `.env.local.sqlite`, which makes it a confusing duplicate. |
| `backend/.env.local` | **DELETE** | Old name from before ADR-0026. Contains stale `QUAESTOR_DB=sqlite:///quaestor.db` (relative path that would resolve wrong inside the api container). `backend/.envrc` still references this file; that reference must be updated in the same change. |
| `backend/.envrc` | **EDIT** | One-line change: `dotenv .env.local` → `dotenv .env.local.sqlite`. |
| `docs/runbooks/sqlite-to-postgres-migration.md` | **CREATE** | The persistent record of the migration recipe. Captures the full source of both scripts (so they're reproducible if `/tmp` is cleared), the run order, the env cleanup commands, and the failure modes. ~150 lines. |

## Files in the repo that do NOT change

- `justfile` — no new recipes.
- `docker-compose.yml` — untouched.
- `backend/.env.local.sqlite` — active config for `just dev-local`.
- `backend/.env.local.remote` — active config for `just dev-real`.
- `backend/.env.local.example` — committed template (cp source for `.env.local.sqlite`).
- `backend/.env.local.remote.example` — committed template (cp source for `.env.local.remote`).
- `frontend/.env.local` — used. `API_URL` is referenced in `frontend/lib/server-auth.ts` (line 3) and `frontend/lib/proxy/build-target-url.ts` (line 6). Deleting would break server-side auth and the SSR proxy.
- `.envrc` (root) — already points at `backend/.env.local.sqlite`. Active.
- `.gitignore` — no new patterns needed (no new files being added to the repo except the runbook, which is markdown and tracked).
- `README.md` — untouched. The runbook is the place for migration notes; the README stays focused on the current dev workflow.
- `backend/src/quaestor/__main__.py`, `db.py`, `domain/models.py`, `migrations/` — untouched. The migration script uses these via imports but does not modify them.
- `backend/scripts/cleanup_stale_planned.py` — untouched. It defaults to `.dev-data/quaestor.db` if `QUAESTOR_DB` is unset; after archiving, an unset `QUAESTOR_DB` would point at a missing file. The script's existing fallback (`if not os.environ.get("QUAESTOR_DB") and dev_db_path.exists()`) already handles this gracefully — it only sets the SQLite URL if the file exists.

## Postgres-native ENUMs handled

The Postgres schema (created by Alembic) defines 9 native ENUMs. The migration
script does not need to cast them explicitly — SQLAlchemy's `Enum(...)`
column on read returns the Python enum value, and Postgres accepts the
Python enum value into the ENUM column.

| ENUM name | Allowed values | Tables using it |
|---|---|---|
| `accounttype` | debit, credit, cash, savings | account |
| `goalstatus` | active, reached, paused | goal |
| `txtype` | expense, income, transfer | recurring_item, transaction |
| `recurringmode` | auto, manual | recurring_item |
| `intervalunit` | day, week, month, year | recurring_item |
| `txstatus` | planned, posted, skipped | transaction |
| `source` | manual, agent, import_ | transaction |
| `contributionsource` | confirmed, manual | goal_contribution |
| `occurrencestatus` | posted, planned, skipped | recurring_occurrence |

`verify.py` step 4 confirms every distinct value in every ENUM column is one
of the allowed labels — catches any silent coercion drift.

## Pre-flight checks (run before `migrate.py`)

The runbook lists these as §2; the script enforces them as step 1:

1. **api not running.** `pgrep -f uvicorn` returns non-zero. If it returns
   zero, `migrate.py` aborts with: "Stop the api first: `just dev-down`."
2. **Remote Postgres reachable.** `psycopg.connect(QUAESTOR_DB,
   connect_timeout=3).close()` succeeds.
3. **SQLite file exists and has data.** `sqlite3 .dev-data/quaestor.db
   "SELECT COUNT(*) FROM transaction"` returns > 0.
4. **Schema in remote Postgres.** `migrate.py` checks for the `account` table
   in `pg_class`; if missing, runs `alembic upgrade head` automatically.

## Verification (done criteria)

- [ ] `python3 /tmp/quaestor-migration/verify.py` exits 0.
- [ ] `just dev-real` starts the api against remote Postgres.
- [ ] Browser at <http://localhost:3000> shows accounts/transactions/recurring/goals matching the SQLite snapshot.
- [ ] Create a new transaction via the UI; it appears in `quaestor_production_db`.
- [ ] `mv .dev-data/quaestor.db ~/quaestor-sqlite-archive/` succeeded; `ls -la ~/quaestor-sqlite-archive/` shows the file.
- [ ] `ls backend/.env.example backend/.env.local 2>&1` reports "No such file or directory" for both.
- [ ] `cat backend/.envrc` shows `dotenv .env.local.sqlite`.
- [ ] One final `just dev-real` + browser session: app still works.
- [ ] `git status` shows only `docs/runbooks/sqlite-to-postgres-migration.md` added; no other tracked files modified.

## Failure modes / rollback

| Failure | Detection | Recovery |
|---|---|---|
| `api` still running during migration | `pgrep -f uvicorn` returns 0 | `just dev-down`, then re-run `migrate.py`. |
| Alembic schema missing in remote | `pg_class` query for `account` returns no rows | `migrate.py` auto-runs `alembic upgrade head` (idempotent). |
| `pg_dump` pre-migration fails | non-zero exit from `subprocess.run` | Check Postgres URL, network access. |
| Migration script crashes mid-table | unhandled exception | Re-run `migrate.py`; the `INSERT ... ON CONFLICT (id) DO NOTHING` makes a second pass safe. |
| `verify.py` reports mismatch | exit code 1 | Inspect the failed check; if remote Postgres had pre-existing data, restore from `pre-migration.dump`. |
| Browser smoke test reveals missing data | manual | Restore remote Postgres from `pre-migration.dump` (only useful for re-runs; first migration has no remote data to lose); SQLite is still in `.dev-data/` until step 8. |
| Archive SQLite step forgotten | SQLite still in `.dev-data/` | Re-run `mv .dev-data/quaestor.db ~/quaestor-sqlite-archive/`. |
| Env cleanup step forgotten | `.env.example` / `.env.local` still exist | Re-run `rm backend/.env.example backend/.env.local` and `sed -i '' 's|dotenv .env.local|dotenv .env.local.sqlite|' backend/.envrc`. |

## No-objetivos (out of scope, explicitly)

- Online cutover / dual-write from SQLite to Postgres. Single-user app;
  api-downtime during migration is acceptable.
- Continuous `pg_dump` to S3 / off-host backup. Render.com handles remote
  Postgres backups as part of its managed service.
- Reverse migration (Postgres → SQLite). Not requested.
- A permanent migration tool in the repo. The user explicitly asked for
  "no trace" of the migration in the codebase. The runbook captures the
  recipe; the scripts are ephemeral and reproducible from the runbook.
- New ADR. This is operational work that implements a deferred plan from
  ADR-0026. No new architecture decision is being made.