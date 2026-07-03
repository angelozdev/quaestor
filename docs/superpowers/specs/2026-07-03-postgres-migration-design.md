# Postgres Migration — Replace SQLite with Postgres 17 (greenfield, pre-prod)

**Date:** 2026-07-03
**Status:** design (pending approval)
**ADR:** docs/adr/0024-postgres-replaces-sqlite.md (proposed, supersedes ADR-0012)
**Depends on:** nothing (greenfield before production launch)

### Context

Quaestor's backend has run on SQLite since the project's inception (P0), with Litestream as the continuous-WAL backup (ADR-0012). The user has now decided to migrate to Postgres BEFORE the first production deploy. Three drivers:

1. **Concurrency.** The four services (`api`, `mcp`, `scheduler`, plus the frontend's SSR fetches inside `api`) all share one SQLite file today. WAL + `busy_timeout=5000` serializes writers. With future multi-writer workloads (e.g. chat writing while an FX job runs) this is the first thing that will bite.
2. **Schema discipline.** The schema today is created by `SQLModel.metadata.create_all` inside `init_db`. There is no migration history — every change to `models.py` is "edit and pray". Alembic gives each change a versioned, reviewable, reversible migration.
3. **Greenfield window.** The user has not yet deployed. There is no prod data to migrate and no cutover window to schedule. This is the cheapest possible moment to do the switch: one PR, one deploy, no rollback choreography required.

Two adjacent simplifications that fell out of clarifying questions:

- **No S3.** The `${LITESTREAM_BUCKET}` env var in `litestream.yml` is a placeholder that has never been wired to a real bucket. The user does NOT use S3 for anything. All S3/Litestream references are placeholders and will be deleted in the same change.
- **Acceptable data-loss window: up to 24h.** A daily `pg_dump` on the VPS is acceptable. Off-host continuous WAL archive (wal-g, pgBackRest) was considered and rejected — over-engineered for a single-user app where the user is the operator of the only VPS.

### Decisions log (locked during brainstorming, 2026-07-03)

| Fork               | Choice                                                       |
| ------------------ | ------------------------------------------------------------ |
| Why migrate        | Schema discipline (Alembic) + concurrency headroom           |
| Scope              | Local dev + future prod                                      |
| Postgres version   | 17 (`postgres:17-alpine`)                                    |
| Migration tool     | Alembic                                                      |
| Backup strategy    | Daily `pg_dump -Fc` to a local Docker volume, 7-day rotation |
| Off-host backup    | None (no S3, no off-host)                                    |
| Tests DB           | Stay on SQLite in-memory (`sqlite://`) for test runs         |
| Existing prod data | None (not yet deployed)                                      |
| Litestream         | Removed entirely; ADR-0012 superseded                        |

### Service topology (after)

```
┌────────────────────────────────────────────────────────┐
│ docker compose (production) + docker-compose.override  │
│ (dev) — merged by Compose                              │
├────────────────────────────────────────────────────────┤
│                                                        │
│  ┌──────────┐    ┌──────────┐    ┌────────────┐        │
│  │   api    │    │   mcp    │    │  frontend  │        │
│  └────┬─────┘    └────┬─────┘    └────────────┘        │
│       │               │                                │
│       └───────┬───────┘                                │
│               │  postgresql://quaestor:***@db:5432/quaestor │
│               ▼                                        │
│         ┌─────────┐    ┌───────────────────────┐       │
│         │   db    │◄───┤  scheduler (daily)    │       │
│         │ pg 17   │    │  ├─ FX fetch          │       │
│         └────┬────┘    │  ├─ materialize       │       │
│              │         │  ├─ ensure_month_closed       │
│              │         │  └─ pg_dump → /backups│       │
│              ▼         └───────────────────────┘       │
│       ┌────────────┐                                   │
│       │ db-data    │ quaestor-db-data (volume)         │
│       └────────────┘                                   │
│                                                        │
│  Removed: litestream service + litestream.yml          │
│  Added:  db service, quaestor-backups volume           │
└────────────────────────────────────────────────────────┘
```

### File changes

| Component                                                  | What changes                                                                                                                                                                                                                                         |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | -------------------------------------------------------- |
| `docker-compose.yml`                                       | Add `db: postgres:17-alpine`. Add `quaestor-db-data` + `quaestor-backups` volumes. Switch `QUAESTOR_DB` on `api`/`mcp`/`scheduler` to the Postgres URL. Remove `litestream` service. Add `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` env vars. |
| `docker-compose.override.yml`                              | Same `db` override (port `5432` exposed on host for `just db-shell`). Drop `.dev-data/` usage; `dev-reset` drops the Postgres volume instead of `rm -rf .dev-data/`.                                                                                 |
| `backend/pyproject.toml`                                   | Add `alembic>=1.13` and `psycopg[binary]>=3.2`.                                                                                                                                                                                                      |
| `backend/src/quaestor/db.py`                               | Drop `_set_sqlite_pragmas`. Use `create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=10)`. Keep the SQLite branch for tests (`memory=True` path). `init_db()` becomes a thin call to `alembic upgrade head`.                   |
| `backend/alembic.ini` + `backend/src/quaestor/migrations/` | Standard Alembic scaffold. `env.py` binds `target_metadata = SQLModel.metadata` and imports `DATABASE_URL` from `quaestor.db`.                                                                                                                       |
| `backend/src/quaestor/migrations/versions/0001_initial.py` | Auto-generated initial migration capturing the current schema. Includes Postgres-native ENUM types for `AccountType`, `TxType`, `IntervalUnit`, `RecurringMode`, `OccurrenceStatus`, `TxStatus`, `Source`.                                           |
| `backend/scripts/cron.sh`                                  | Add a daily `pg_dump -Fc quaestor > /backups/quaestor-${TS}.dump; ls -1tr /backups/quaestor-\*.dump                                                                                                                                                  | head -n -7 | xargs -r rm`block before`python -m quaestor.jobs.daily`. |
| `justfile`                                                 | Add `db-upgrade`, `db-downgrade -1`, `db-revision "msg"`, `db-shell`, `db-backup-now`. Replace `dev-reset`'s `rm -rf .dev-data` with `docker compose down -v` for `db`.                                                                              |
| `litestream.yml`                                           | DELETED.                                                                                                                                                                                                                                             |
| `backend/.env.example`, `backend/.env.production`          | Replace `QUAESTOR_DB=sqlite://...` with `QUAESTOR_DB=postgresql://...`. Add `POSTGRES_PASSWORD`. Remove `DB_PATH`.                                                                                                                                   |
| `.env.example` (root)                                      | Remove `DB_PATH`, `LITESTREAM_*` env vars.                                                                                                                                                                                                           |
| `.gitignore`                                               | Remove `backend/quaestor.db*`, `.dev-data/`. Add `quaestor_backups/`.                                                                                                                                                                                |
| `docs/runbooks/restore-from-backup.md`                     | Rewrite for `pg_restore` from a `quaestor-YYYY-MM-DD.dump` file.                                                                                                                                                                                     |
| `docs/adr/0024-postgres-replaces-sqlite.md`                | NEW. Status `proposed` during impl → `accepted` post-merge. Supersedes 0012.                                                                                                                                                                         |
| `docs/adr/README.md` index                                 | Insert row for 0024; flip 0012 to "superseded by 0024".                                                                                                                                                                                              |

### Postgres-native ENUM handling

`domain/models.py` declares `class AccountType(str, Enum):` etc. SQLAlchemy's `Enum(AccountType)` infers a Postgres native ENUM type when running on Postgres (`native_enum=True` is the default). Each becomes a real `CREATE TYPE account_type AS ENUM (...)` in the migration.

Adding a new enum value later requires `ALTER TYPE ... ADD VALUE` (a manual SQL step inside a future migration). Documented in the migration template.

Tests on SQLite still pass because SQLAlchemy falls back to `VARCHAR + CHECK` when `native_enum=True` is forced off (SQLite path) — automatic, no test changes needed.

### Backups

A single backup job runs daily from the existing `scheduler` service (ADR-0013 "thin sidecar"). After `quaestor.jobs.daily` finishes successfully:

```sh
TS=$(date -u +%F)
pg_dump -U quaestor -h db -Fc quaestor > /backups/quaestor-${TS}.dump
ls -1tr /backups/quaestor-*.dump | head -n -7 | xargs -r rm
```

Mounts: `scheduler` gains `volumes: [quaestor-backups:/backups]`. The volume is on the host filesystem. It is **not** bind-mounted, so backups cannot be tarballed/scp'd without explicit operator action — intentional (the user said local-only is fine, no off-host).

The dump format `-Fc` is verified-restore-friendly: `pg_restore -l quaestor-2026-07-03.dump` lists every object.

### Tests

**Decision:** tests stay on SQLite in-memory. `db.make_engine(url="sqlite://", memory=True)` is exercised for every pytest run.

- Features exercised (FKs, transactions, CRUD, eager relationships) are dialect-equivalent.
- SQLite-in-memory tests are ~10× faster than spinning a Postgres container per test session.
- Postgres-specific surface (ENUM type, range types, JSONB, advisory locks) is not used in code paths tests cover.

Implication: `db.py` keeps its SQLite branch in `make_engine()`. Known small cost (asymmetric branch) in exchange for no testcontainers.

### Failure modes / rollback

Because this is greenfield and pre-prod, rollback is `git revert`. There is no live data to lose.

| Failure                         | Detection                     | Recovery                                                                                    |
| ------------------------------- | ----------------------------- | ------------------------------------------------------------------------------------------- |
| Initial migration fails partway | `api` healthcheck 503         | `docker compose down -v`, restore compose from previous commit, `docker compose up`.        |
| `psycopg` wheel unavailable     | Image build fails             | `psycopg[binary]` ships pure-Python wheels; if needed, fall back to `psycopg2-binary>=2.9`. |
| `pg_dump` contention            | Visible in `pg_stat_activity` | `pg_dump` does NOT acquire an `ACCESS EXCLUSIVE` lock — it is non-blocking.                 |
| `quaestor-backups` fills disk   | Docker warns at ~85%          | Add a `df -h` check to the runbook. Defer until data warrants.                              |

### Verification (done criteria)

- `docker compose -f docker-compose.yml -f docker-compose.override.yml up` on a fresh host with `--profile never` (i.e., production stack + dev override): `api` reports 200 within 30s; initial Alembic migration runs as part of the `db` entrypoint.
- `just db-shell` opens `psql`; `\d transaction` shows the full table with FKs.
- `just dev-test` runs the full pytest suite green against SQLite in-memory.
- `just db-backup-now` writes `/backups/quaestor-YYYY-MM-DD.dump`; `pg_restore -l <file>` lists ~20 objects.
- `docker compose down -v && docker compose up` after seeding a few rows via the API: rows persist across restarts, are wiped when the volume is dropped with `-v`.

### No-objetivos

- Multi-host replication / read replicas.
- Connection pooling with PgBouncer (SQLAlchemy's built-in pool is enough).
- TLS to the database (services are on the same Docker network).
- Postgres extensions (`pgvector`, `pg_trgm`, etc.).
- Off-host continuous backup (WAL-G, pgBackRest).
- Online cutover / dual-write from SQLite (greenfield exempts).

## Decisions log

| Fork               | Choice                                                       |
| ------------------ | ------------------------------------------------------------ |
| Why migrate        | Schema discipline (Alembic) + concurrency headroom           |
| Scope              | Local dev + future prod                                      |
| Postgres version   | 17 (`postgres:17-alpine`)                                    |
| Migration tool     | Alembic                                                      |
| Backup strategy    | Daily `pg_dump -Fc` to a local Docker volume, 7-day rotation |
| Off-host backup    | None (no S3, no off-host)                                    |
| Tests DB           | Stay on SQLite in-memory (`sqlite://`) for test runs         |
| Existing prod data | None (not yet deployed)                                      |
| Litestream         | Removed entirely; ADR-0012 superseded                        |
