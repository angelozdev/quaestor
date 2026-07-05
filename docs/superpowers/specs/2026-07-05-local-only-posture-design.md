# Local-Only Posture — Design

**Date:** 2026-07-05
**Status:** design (pending approval)
**ADR:** docs/adr/0026-local-only-posture.md (proposed, supersedes ADR-0010 and ADR-0013)
**Supersedes:** the production-deployment posture in docs/adr/0010-deployment-posture.md

---

## Spec / Design

(The following section IS the design spec. Task 1 of this plan is to copy it verbatim into `docs/superpowers/specs/2026-07-05-local-only-posture-design.md`.)

### Context

Quaestor was designed and built for self-hosted single-VPS production deployment:

- `docker-compose.yml` defines a 5-service stack (`api`, `db` Postgres, `frontend`, `caddy`, `scheduler`) plus a Tailscale sidecar (already removed by ADR-0025).
- `Caddyfile` publishes the public frontend + REST over HTTPS.
- A `scheduler` sidecar loops `quaestor.jobs.daily` every 24h (ADR-0013).
- `backend/.env.production` carries secrets for the VPS topology.
- The dev override (`docker-compose.override.yml`) builds a 4-service hot-reload variant.

The user has changed direction: Quaestor is now a **local-only** project that lives on their Mac. The only thing that should leave the host is the **database** — which the user manages and secures themselves. Everything else (frontend, API, MCP, scheduler) stays local. This is a deliberate, durable posture change, not a temporary experiment: the spec removes the production infrastructure that no longer applies and replaces it with a single-machine dev experience where `docker compose up` does everything (build, wait for DB, migrate, start) with zero manual steps.

**Important: the local SQLite at `.dev-data/quaestor.db` holds the user's actual financial data today — it is NOT a sandbox.** Preserving this file across the posture change is a hard requirement. The user will eventually pay for a remote Postgres and migrate the SQLite data into it; until then, the local SQLite is the primary data store.

The auto-migration pattern (Python `__main__.py` entrypoint) was chosen after research into how professional projects handle the same problem:

- **Django** chains `manage.py migrate && manage.py runserver` (Django 5.1 added `runserver --migrate`, but the canonical Python pattern is still a manual chain or a single-command wrapper).
- **Rails** ships an official `docker-entrypoint.sh` template that runs `bin/rails db:prepare` before `exec "${@}"`.
- **Alembic** maintainer Mike Bayer: *"add `alembic upgrade` to your deploy process"*; in-process lifespan migrations are explicitly discouraged with `workers ≥ 2` due to race conditions.
- **FastAPI community consensus**: prefer entrypoint script, init container, or Gunicorn `on_starting` master hook over lifespan migrations.

For Quaestor — single-process, single-worker, local-only — the Python `__main__.py` entrypoint is the cleanest fit: same language as the codebase, testable with pytest, no shell escaping of URLs/secrets, mirrors Django's `manage.py` philosophy.

### Decisions log (locked during brainstorming, 2026-07-05)

| Fork | Choice |
|---|---|
| **Posture** | Local-only on the user's Mac. No public deployment, no VPS, no Caddy, no Tailscale. |
| **Production DB** | Remote Postgres managed by the user (security, backups, rotation). App connects by URL. **Already provisioned**: Render.com Postgres (Oregon region), database `quaestor_production_db`. Credentials live in `backend/.env.local.remote` (gitignored). |
| **Test DB** | SQLite in-memory (host-side pytest, unchanged per ADR-0024). |
| **Local "real" DB** | SQLite file at `.dev-data/quaestor.db`. **This holds the user's actual financial data today** — not a sandbox. Preserved across this change. |
| **DB mode switching** | **Approach B** — two env files (`backend/.env.local.sqlite`, `backend/.env.local.remote`), passed to `docker compose` via `--env-file`. Recipes `dev-local` / `dev-real` pick which. |
| **Auto-bootstrap** | `docker compose up` builds images → waits for DB → runs `alembic upgrade head` → starts uvicorn. No manual steps. |
| **Bootstrap mechanism** | Python `backend/src/quaestor/__main__.py` (entrypoint module), not a bash script — same language, testable, no escaping issues. |
| **Scheduler** | In-process `asyncio` task inside the api's lifespan (run on boot + every 24h). Replaces the sidecar container. |
| **Compose structure** | Single `docker-compose.yml` (no override). Two services: `api` + `frontend`. No `db`, no `caddy`, no `scheduler`, no `tailscale`, no `mcp`. |
| **Dockerfile** | Single-stage (no `dev` / `prod` targets). CMD = `python -m quaestor`. |
| **MCP posture** | Unchanged from ADR-0025 (chat-only, in-process bridge; no HTTP `/mcp`). |
| **External MCP access** | Removed (ADR-0025). `.mcp.json` (referencing `localhost:9000/mcp`) deleted. |
| **Auth posture** | Unchanged. `APP_TOKEN` bearer + session cookie. `COOKIE_SECURE` defaults to `false` for local HTTP, set to `true` only if user fronts the app with TLS. |
| **Pytest** | Unchanged. In-memory SQLite on the host (ADR-0024). |
| **Branching / git** | One feature branch per plan. Conventional commits. Atomic per task. |
| **Docs affected** | New ADR-0026. ADR-0010 and ADR-0013 marked superseded. README rewritten. |

### Service topology (after)

```
┌────────────────────────────────────────────────────────────────────┐
│  User's Mac (localhost)                                            │
│                                                                    │
│  docker compose up                                                 │
│  ┌────────────────────┐         ┌─────────────────────────────────┐│
│  │  frontend          │ ──────► │  api  (FastAPI + Uvicorn)       ││
│  │  Next.js, :3000    │  /api/* │  :8000                           ││
│  └────────────────────┘         │                                 ││
│                                 │  ┌────────────────────────────┐ ││
│                                 │  │ __main__.py entrypoint     │ ││
│                                 │  │  wait_for_db → alembic up  │ ││
│                                 │  │  → uvicorn.run(...)        │ ││
│                                 │  └────────────────────────────┘ ││
│                                 │  ┌────────────────────────────┐ ││
│                                 │  │ lifespan: asyncio task     │ ││
│                                 │  │  daily job cada 24h +      │ ││
│                                 │  │  on boot                   │ ││
│                                 │  └────────────────────────────┘ ││
│                                 └──────────────┬──────────────────┘│
└────────────────────────────────────────────────┼──────────────────┘
                                                 │ QUAESTOR_DB
                          ┌──────────────────────┴────────────────────┐
                          │                                           │
                ┌─────────▼─────────┐                    ┌─────────────▼─────────────┐
                │ SQLite local      │                    │ Postgres remoto           │
                │ .dev-data/*.db    │                    │ (URL en .env.local.remote)│
                │ perfil "local"    │                    │ perfil "remote"           │
                │ `just dev-local`  │                    │ `just dev-real`           │
                └───────────────────┘                    └───────────────────────────┘

Pytest (host-side):  SQLite in-memory, sin cambios (ADR-0024).
```

### File changes

| Component | What changes |
|---|---|
| `docker-compose.yml` | Rewrite. Two services (`api`, `frontend`). No `db`, no `caddy`, no `scheduler`. No override. `env_file` references `${QUAESTOR_ENV_FILE}` which `just` recipes export before calling compose. Volumes `quaestor-dev-data` (sqlite) + `frontend_node_modules`. |
| `docker-compose.override.yml` | DELETED. |
| `backend/Dockerfile` | Simplify to single stage. Drop `dev` / `prod` targets. Drop `postgresql-client`. `CMD = ["python", "-m", "quaestor"]`. |
| `backend/src/quaestor/__main__.py` | NEW. Entry point: `wait_for_db(url)` → `run_migrations()` → `asyncio.run(_run_async())` which calls `uvicorn.Server(config).serve()`. |
| `backend/src/quaestor/scheduler.py` | NEW. `run_forever()` asyncio task: `_run_once()` on boot (if `RUN_ON_BOOT=1`), then loop with `asyncio.sleep(86400)`. Errors logged, loop survives. |
| `backend/src/quaestor/api.py` | Add `@asynccontextmanager async def lifespan(app)` that creates an `asyncio.create_task(run_forever(), name="daily-scheduler")` before yield and `task.cancel()` + `await task` after. Pass `lifespan=lifespan` to `FastAPI(lifespan=...)`. |
| `backend/tests/test_main.py` | NEW. Unit tests for `wait_for_db` (sqlite success, postgres success, max attempts exit, immediate success), `run_migrations` (success and non-zero exit), `_probe_sqlite`, `_probe_postgres`. |
| `backend/tests/test_scheduler.py` | NEW. Unit tests for `_run_once` (success and failure), `run_forever` (`RUN_ON_BOOT=1` runs immediately, `RUN_ON_BOOT=0` skips, cancellation exits). |
| `justfile` | Rewrite. New recipes: `dev-local`, `dev-real`, `dev-down`, `dev-logs`, `dev-logs-one`, `dev-shell-api`, `dev-test`, `daily`, `db-which`. Drop `db-upgrade`, `db-downgrade`, `db-revision`, `db-shell`, `db-backup-now` (DB is remote; user manages). **NO `dev-reset-local` recipe** — preserving the SQLite data is intentional; manual reset is documented in the plan but never automated. |
| `backend/.env.local` | Renamed to `backend/.env.local.sqlite`. New file `backend/.env.local.remote`. Both gitignored. Old `backend/.env.local` removed. |
| `backend/.env.example` | Rewrite. Drop `DOMAIN`/`LETSENCRYPT_EMAIL` (none in compose). Drop `POSTGRES_PASSWORD` (DB is remote). Drop `MCP_HOST`/`MCP_PORT`. Add `SCHEDULER_ENABLED`, `RUN_ON_BOOT` (scheduler is in-process). |
| `backend/.env.production` | DELETED. |
| `backend/scripts/cron.sh` | DELETED. (Replaced by in-process scheduler.) |
| `Caddyfile` (root) | DELETED. |
| `backend/Caddyfile/` | DELETED (empty directory). |
| `.mcp.json` | DELETED. (Stale reference to `localhost:9000/mcp`; service removed by ADR-0025.) |
| `.envrc` | Drop `DOMAIN` and `FRONTEND_PASSWORD_HASH` exports (no longer needed). |
| `.gitignore` | Drop references to `quaestor-db-data`, `quaestor-backups`, `litestream.state`, `ts-serve.local.json`. Keep `quaestor_dev_data/`, `frontend_node_modules/`. Keep all SQLite patterns (still used by `.dev-data/`). |
| `README.md` | Rewrite for local-only posture. Quickstart: `just dev-local` and `just dev-real`. Drop the VPS / Caddy / Tailscale / Litestream sections. Add a "Future migration to remote Postgres" section linking to the migration notes in this plan. |
| `docs/adr/0026-local-only-posture.md` | NEW. Status `proposed` during impl → `accepted` post-merge. Supersedes 0010 + 0013. |
| `docs/adr/0010-deployment-posture.md` | Update frontmatter: add `Superseded by: 0026`. Body stays for historical reference. |
| `docs/adr/0013-daily-scheduler-as-a-thin-sidecar.md` | Update frontmatter: add `Superseded by: 0026`. Body stays. |
| `docs/adr/README.md` | Insert row 0026; flip 0010 and 0013 to `superseded by 0026`. |

### Auto-bootstrap — Python `__main__.py`

**Why Python, not bash:** Same language as the codebase (a Python dev reads it instantly). No escaping of URLs (`postgresql://user:p@ss@host:5432/db`) or secrets. Testable with pytest (mock `psycopg.connect` + `subprocess.run`). Cross-platform if you ever run outside Docker. Mirrors Django's `manage.py` philosophy. Industry reference: Django `manage.py runserver --migrate` (5.1+); Rails official `docker-entrypoint.sh` (we prefer Python for the reasons above).

```python
"""
Quaestor container entrypoint: wait for DB → migrate → start uvicorn.
Runs as `python -m quaestor` from the container CMD (ADR-0026).
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from typing import Final

import psycopg
import uvicorn
from sqlalchemy import create_engine

LOG_PREFIX: Final = "[entrypoint]"
DB_WAIT_MAX_ATTEMPTS: Final = 30
DB_WAIT_INTERVAL_S: Final = 2.0


def log(msg: str) -> None:
    print(f"{LOG_PREFIX} {msg}", flush=True)


def _probe_sqlite(url: str) -> None:
    create_engine(url).connect().close()


def _probe_postgres(url: str) -> None:
    psycopg.connect(url, connect_timeout=3).close()


def wait_for_db(url: str) -> None:
    last_exc: Exception | None = None
    for attempt in range(1, DB_WAIT_MAX_ATTEMPTS + 1):
        try:
            if url.startswith("sqlite"):
                _probe_sqlite(url)
            else:
                _probe_postgres(url)
            log(f"DB reachable (attempt {attempt}/{DB_WAIT_MAX_ATTEMPTS})")
            return
        except Exception as exc:
            last_exc = exc
            if attempt >= DB_WAIT_MAX_ATTEMPTS:
                break
            time.sleep(DB_WAIT_INTERVAL_S)
    log(f"DB unreachable after {DB_WAIT_MAX_ATTEMPTS} attempts: {last_exc}")
    sys.exit(1)


def run_migrations() -> None:
    log("running alembic upgrade head")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=False, cwd="/app",
    )
    if result.returncode != 0:
        log(f"alembic upgrade failed (rc={result.returncode}); aborting")
        sys.exit(result.returncode)


async def _run_async() -> None:
    config = uvicorn.Config(
        "quaestor.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["/app/src"],
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


def main() -> None:
    url = os.environ.get("QUAESTOR_DB", "sqlite+aiosqlite:///:memory:")
    wait_for_db(url)
    run_migrations()
    log("starting uvicorn")
    asyncio.run(_run_async())


if __name__ == "__main__":
    main()
```

### In-process scheduler

`backend/src/quaestor/scheduler.py`:

```python
"""
In-process daily scheduler (ADR-0026, supersedes ADR-0013).

Replaces the `scheduler` Docker sidecar + `scripts/cron.sh`.
Runs as an asyncio task inside the api's FastAPI lifespan.

Behavior:
- RUN_ON_BOOT=1 (default): run the daily job once at startup, then every INTERVAL_S.
- RUN_ON_BOOT=0: wait INTERVAL_S before the first run.
- A job failure is logged but does not kill the loop (self-healing).
- Lifespan shutdown cancels the task cleanly (SIGTERM from `docker stop`).
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Final

from quaestor.jobs import daily as daily_module

log = logging.getLogger(__name__)

INTERVAL_S: Final = 24 * 60 * 60  # 24 hours


async def _run_once() -> None:
    started = datetime.now(timezone.utc)
    log.info("scheduler: starting daily job at %s", started.isoformat())
    try:
        await asyncio.to_thread(daily_module.run)
        log.info("scheduler: daily job ok")
    except Exception:
        log.exception("scheduler: daily job failed; will retry next interval")


async def run_forever() -> None:
    run_on_boot = os.environ.get("RUN_ON_BOOT", "1") == "1"
    if run_on_boot:
        await _run_once()
    while True:
        log.info("scheduler: sleeping %ds until next run", INTERVAL_S)
        try:
            await asyncio.sleep(INTERVAL_S)
        except asyncio.CancelledError:
            log.info("scheduler: cancelled during sleep; exiting")
            raise
        await _run_once()
```

`backend/src/quaestor/api.py` — add:

```python
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from quaestor.scheduler import run_forever

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("api: lifespan startup")
    task = asyncio.create_task(run_forever(), name="daily-scheduler")
    try:
        yield
    finally:
        log.info("api: lifespan shutdown; cancelling scheduler")
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(lifespan=lifespan, ...)  # existing constructor call augmented with lifespan=
```

**Why this is safe:** Single worker (`--reload` implies `workers=1`). No race condition. The job (`daily_module.run`) is idempotent (FX upserts by date, `materialize_due`/`ensure_month_closed` are self-healing per ADR-0013). A job failure logs and continues.

**Interaction with `--reload`:** uvicorn reloads cancel the lifespan and start a new one, so `RUN_ON_BOOT=1` re-runs the job on every file save. Idempotent. Mitigation: set `RUN_ON_BOOT=0` in env to silence.

### Env file strategy (Approach B)

| File | Purpose |
|---|---|
| `backend/.env.local.sqlite` (gitignored) | Active for `just dev-local`. `QUAESTOR_DB=sqlite+aiosqlite:////app/.dev-data/quaestor.db`. |
| `backend/.env.local.remote` (gitignored) | Active for `just dev-real`. `QUAESTOR_DB=postgresql://quaestor:PASSWORD@HOST:5432/quaestor`. |
| `backend/.env.example` (committed) | Template — no secrets, with comments. |

Both files are passed via `docker compose --env-file <path>`. Compose uses `env_file: ${QUAESTOR_ENV_FILE}` (the env var is exported by `just` before invoking compose). No compose override needed.

### Future migration: SQLite → Postgres (documented, NOT implemented now)

When the user is ready to migrate their SQLite data into the remote Postgres (Render.com Oregon), the migration path is:

1. **Set `backend/.env.local.remote`** with the URL: `QUAESTOR_DB=postgresql://quaestor_production_db_user:REDACTED@dpg-d9574ki8qa3s73dl491g-a.oregon-postgres.render.com:5432/quaestor_production_db`. (User fills in their actual password; gitignored.)
2. **Run `alembic upgrade head`** against the new DB to create the schema (already supported by `__main__.py` — `just dev-real` triggers it automatically on first boot).
3. **Migrate the data** from SQLite to Postgres. The recommended tool is `pgloader` (mature, OSS, handles type coercion from SQLite to Postgres):
   ```sh
   pgloader sqlite:///path/to/.dev-data/quaestor.db postgresql://user:REDACTED@host/quaestor_production_db
   ```
   For tables with Postgres-native ENUM types (ADR-0024), the migration script needs `--with "create table"` and explicit casts. A future PR can ship a `just migrate-to-postgres` recipe that wraps this and handles the ENUM casts.
4. **Smoke-test**: `just dev-real` points at the remote Postgres. CRUD in the browser. Verify accounts/transactions/recurring/goals match the SQLite snapshot.
5. **Archive the SQLite** (don't delete immediately — keep `.dev-data/quaestor.db` for 30 days as a rollback safety net).

**Scope note:** this migration recipe is **out of scope for this plan**. We document the path here so the user has it when ready. A separate plan will own the migration recipe implementation.

**Why not implement now:** the user explicitly chose "Solo documentar (futuro)". Implementing `pgloader` integration + ENUM-cast handling is non-trivial (need to verify each table's column types, handle the `interval_count` numeric→integer cast, etc.). Doing it before the user has tested the new posture with their existing SQLite data is wasted work — the new posture must work first.

### `justfile` (final form)

```just
# Quaestor — local-only dev recipes (ADR-0026).

_default:
    @just --list

# --- DB profiles (pick one) ----------------------------------------

# Run against the local SQLite file in .dev-data/.
dev-local:
    QUAESTOR_ENV_FILE=backend/.env.local.sqlite docker compose --env-file backend/.env.local.sqlite up --build

# Run against your remote Postgres.
dev-real:
    QUAESTOR_ENV_FILE=backend/.env.local.remote docker compose --env-file backend/.env.local.remote up --build

# --- Common ops ----------------------------------------------------

dev-down:
    docker compose --env-file backend/.env.local.sqlite down

dev-logs:
    docker compose --env-file backend/.env.local.sqlite logs -f

dev-logs-one service:
    docker compose --env-file backend/.env.local.sqlite logs -f {{service}}

dev-shell-api:
    docker compose --env-file backend/.env.local.sqlite exec api sh

# Run pytest on the host (in-memory SQLite; no DB needed).
dev-test:
    cd backend && uv run pytest -q

# Manually trigger the daily job (FX + materialize + close-month).
daily:
    docker compose --env-file backend/.env.local.sqlite exec api \
        uv run python -m quaestor.jobs.daily

# Show which env file is currently active.
db-which:
    @echo "default recipes target backend/.env.local.sqlite"
    @echo "QUAESTOR_DB=" $$(grep '^QUAESTOR_DB=' backend/.env.local.sqlite 2>/dev/null || echo "(no .env.local.sqlite yet)")
```

**Data preservation guarantee:** the local SQLite file lives inside the Docker named volume `quaestor-dev-data`, mounted at `/app/.dev-data/` inside the api container. Named volumes persist independently of `docker-compose.yml` — they survive `docker compose down`, image rebuilds, and compose changes, as long as you do NOT pass `-v`. The new compose reuses the same volume name, so your existing `.dev-data/quaestor.db` data carries over automatically. **No `down -v` anywhere in the recipes.** If you ever need to wipe the local SQLite (intentionally, manually):

```sh
docker compose --env-file backend/.env.local.sqlite down
docker compose --env-file backend/.env.local.sqlite exec api rm -f /app/.dev-data/quaestor.db
docker compose --env-file backend/.env.local.sqlite up --build
# entrypoint.sh runs `alembic upgrade head` which recreates the schema on next boot.
```

We deliberately do NOT ship this as a `just dev-reset-local` recipe. Copy-pasting four commands is a small friction that prevents accidental data loss.

### Tests

**Existing (unchanged):** host-side `uv run pytest` runs against SQLite in-memory (ADR-0024). No changes to fixtures, conftest, or test config.

**New tests:**

`backend/tests/test_main.py`:
- `test_probe_sqlite_success` — create_engine + connect succeeds.
- `test_probe_postgres_success` — mocked `psycopg.connect` succeeds.
- `test_probe_postgres_failure` — mocked connect raises; exception propagates.
- `test_wait_for_db_immediate_success_sqlite` — first attempt succeeds (SQLite path).
- `test_wait_for_db_eventual_success_postgres` — first N attempts fail, then succeeds.
- `test_wait_for_db_max_attempts_exits_1` — every attempt fails; `sys.exit(1)`.
- `test_run_migrations_success` — mocked subprocess returns 0; function returns.
- `test_run_migrations_failure_exits` — mocked subprocess returns non-zero; `sys.exit(rc)`.

`backend/tests/test_scheduler.py`:
- `test_run_once_success` — `daily_module.run` called via `asyncio.to_thread`; logs success.
- `test_run_once_failure_logged_not_raised` — `daily_module.run` raises; exception logged but not propagated.
- `test_run_forever_runs_immediately_when_run_on_boot` — `RUN_ON_BOOT=1` → first call before sleep.
- `test_run_forever_skips_initial_when_run_on_boot_0` — `RUN_ON_BOOT=0` → first action is sleep.
- `test_run_forever_cancellation_exits_cleanly` — `asyncio.CancelledError` during sleep → propagates; loop exits.

### Failure modes / rollback

| Failure | Detection | Recovery |
|---|---|---|
| `wait_for_db` times out | Container exits 1 with `[entrypoint] DB unreachable after 30 attempts: ...` | Check Postgres URL / network; restart `just dev-real`. |
| `alembic upgrade head` fails | Container exits 1 with `[entrypoint] alembic upgrade failed (rc=N)` | Inspect migration; rebuild image. |
| Scheduler task crashes inside lifespan | `log.exception` in scheduler; lifespan re-raises on cancellation but otherwise logs only | Check `docker compose logs api`; fix the job code, restart. |
| Worker hot-reload re-runs scheduler noisily | Visible in logs after every save | Set `RUN_ON_BOOT=0` in env. |
| Remote Postgres URL/password compromised in `.env.local.remote` | Out of scope for the app; security posture is host-level | User rotates password; rotates URL in env. |
| `docker compose down -v` wipes the SQLite file | User has no local data | Use `docker compose down` (no `-v`); documented. |

**Rollback:** `git revert` of the merge commit. ADR-0010 and ADR-0013 stay in git history with `superseded by 0026` frontmatter so prior decisions remain auditable.

### Verification (done criteria)

After all tasks complete, the user (or a smoke-test runner) verifies:

- [ ] `just dev-local` builds images, starts api + frontend, alembic upgrades, scheduler logs "running daily job" once on boot.
- [ ] `just dev-real` builds images, starts api + frontend, alembic upgrades against remote Postgres, scheduler logs "running daily job" once on boot.
- [ ] Open browser at `http://localhost:3000`, log in, perform CRUD → data lands in the expected DB.
- [ ] `just daily` runs the daily job on demand; logs visible.
- [ ] `docker compose restart api` (against the sqlite stack) → scheduler re-runs on boot.
- [ ] Switch `QUAESTOR_ENV_FILE` from sqlite to remote → api connects to remote Postgres.
- [ ] `just dev-test` (pytest on host) green against in-memory SQLite.
- [ ] Hot reload works: edit a Python file → uvicorn restarts → scheduler task re-spawns.
- [ ] `grep -r 'Caddyfile\|tailscale\|litestream\|quaestor-db-data\|MCP_HOST' .` (excluding `docs/superpowers/`) returns no production-infrastructure references.
- [ ] `git log --oneline | head -30` shows one commit per task, no fixup/squash commits.

### No-objetivos

- Public deployment / VPS provisioning.
- HTTPS via Caddy, Tailscale sidecar, off-host backups.
- CI/CD pipeline, multi-node HA.
- Multi-worker uvicorn (single-worker is correct for local-only single-user).
- Managed Postgres (RDS / Neon). The remote DB is whatever the user already has.
- Migration from SQLite-on-disk to SQLite-in-Postgres — out of scope.
