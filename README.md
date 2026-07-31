# Quaestor

Quaestor is a personal-finance backend + agent-native MCP layer (see `docs/adr/` for design). It runs entirely on your Mac: production data lives in a local Postgres 18 container (ADR-0030), and dated backups go to iCloud Drive. Nothing leaves the host.

This README covers the developer workflow.

## Quickstart

Quaestor ships three database profiles, picked by env file. Choose one and start:

```bash
# Profile A — PRODUCTION: local Postgres 18 container (your real data)
just dev-prod

# Profile B — local SQLite sandbox (default for development)
just dev-local

# Profile C — remote Postgres on Render (frozen standby since ADR-0030 — never write)
just dev-real
```

The first run builds Docker images (~1-2 min). Subsequent runs are instant. When the api container boots it waits for the database, runs `alembic upgrade head`, then starts uvicorn — zero manual steps.

Prerequisites: Docker (OrbStack or Docker Desktop — a hard runtime dependency for production, ADR-0030), `just` (`brew install just`), and the matching env file (see below).

## Env files

All env files are gitignored; copy them from the templates:

```bash
# For `just dev-prod` (production, local Postgres):
cp backend/.env.local.postgres.example backend/.env.local.postgres
# Edit POSTGRES_* and the secrets to your real values.

# For `just dev-local` (sandbox):
cp backend/.env.local.example backend/.env.local.sqlite
# Edit APP_TOKEN, APP_PASSWORD, SESSION_SECRET to your real values.

# For `just dev-real` (Render standby — read-only):
cp backend/.env.local.remote.example backend/.env.local.remote
# Edit QUAESTOR_DB to the Render Postgres URL, plus the secrets.
```

Your real financial data lives in the `quaestor_pg_data` named volume used by the `db` service. Never run `docker compose down -v` with the `pg` profile active — that would drop the volume. `docker compose down` (no `-v`) is always safe. `.dev-data/quaestor.db` is a disposable SQLite sandbox for development, bind-mounted into the `api` container at `/app/.dev-data/` — it holds no real data (ADR-0030).

## URLs (any profile)

- Frontend: <http://localhost:3000>
- REST API: <http://localhost:8000/api>

Edit any file under `backend/src/` and uvicorn restarts. Edit anything under `frontend/app/`, `frontend/components/`, etc. and Next.js hot-reloads.

## Common commands

```bash
just dev-prod       # PRODUCTION: stack against the local Postgres container
just dev-prod-down  # stop the production stack (volume preserved)
just backup         # pg_dump the production DB to iCloud Drive (dated file)
just dev-local      # start the stack against the local SQLite sandbox
just dev-real       # stack against Render (frozen standby — never write)
just dev-down       # stop the stack (preserves data)
just dev-logs       # follow logs from all services
just dev-test       # backend pytest on the host (in-memory SQLite)
just daily          # manually trigger the daily scheduler job
just db-which       # show which env file is currently active
```

## Architecture

Local Docker Compose:

- `api` — FastAPI + uvicorn. The `python -m quaestor` entrypoint waits for the DB, runs migrations, then starts the server. An asyncio task spawned from the FastAPI lifespan runs the daily scheduler (FX fetch + materialize + close-month) every 24h.
- `frontend` — Next.js dev server with hot reload.
- `db` — Postgres 18 (compose profile `pg`, only with `just dev-prod`). Data in the `quaestor_pg_data` named volume; port bound to `127.0.0.1:5432` for host tooling.

See `docs/adr/0026-local-only-posture.md` for the posture rationale and `docs/adr/0030-local-postgres-container-replaces-render-as-the-production-database.md` for why production data lives in the local container.

## Backups

Backup discipline is load-bearing (ADR-0030): between dumps, the Mac holds the only live copy of your data.

```bash
just backup   # dated pg_dump (custom format) → iCloud Drive/QuaestorBackups/
```

Verify a dump with `pg_restore --list <file>`. Render keeps the pre-cutover data as a frozen standby — never write to it (`just dev-real` is read-only by convention).
