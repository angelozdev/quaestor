# Quaestor

Quaestor is a personal-finance backend + agent-native MCP layer (see `docs/adr/` for design). It runs locally on your Mac — the only thing that leaves the host is the database, which you manage and secure yourself.

This README covers the developer workflow.

## Quickstart

Quaestor ships two database profiles, picked by env file. Choose one and start:

```bash
# Profile A — local SQLite (sandbox; default for development)
just dev-local

# Profile B — your remote Postgres (Render.com Oregon; "production-like")
just dev-real
```

The first run builds Docker images (~1-2 min). Subsequent runs are instant. When the api container boots it waits for the database, runs `alembic upgrade head`, then starts uvicorn — zero manual steps.

Prerequisites: Docker Desktop, `just` (`brew install just`), and the matching env file (see below).

## Env files

Both env files are gitignored; copy them from the templates:

```bash
# For `just dev-local` (sandbox):
cp backend/.env.local.example backend/.env.local.sqlite
# Edit APP_TOKEN, APP_PASSWORD, SESSION_SECRET to your real values.

# For `just dev-real` (production-like):
cp backend/.env.local.remote.example backend/.env.local.remote
# Edit QUAESTOR_DB to your real Postgres URL, plus the secrets.
```

`.dev-data/quaestor.db` (your real financial data) lives in the repo-root `.dev-data/` directory, bind-mounted into the `api` container at `/app/.dev-data/`. The host file is the source of truth — it is gitignored. `docker compose down` (no `-v`) preserves it; the only remaining named volume (`frontend_node_modules`) is a disposable node_modules cache and is safe to drop with `-v`.

## URLs (after `just dev-local`)

- Frontend: <http://localhost:3000>
- REST API: <http://localhost:8000/api>

Edit any file under `backend/src/` and uvicorn restarts. Edit anything under `frontend/app/`, `frontend/components/`, etc. and Next.js hot-reloads.

## Common commands

```bash
just dev-local   # start the stack against local SQLite
just dev-real    # start the stack against your remote Postgres
just dev-down    # stop the stack (preserves data)
just dev-logs    # follow logs from all services
just dev-test    # backend pytest on the host (in-memory SQLite)
just daily       # manually trigger the daily scheduler job
just db-which    # show which env file is currently active
```

## Architecture

Local Docker Compose with two services:

- `api` — FastAPI + uvicorn. The `python -m quaestor` entrypoint waits for the DB, runs migrations, then starts the server. An asyncio task spawned from the FastAPI lifespan runs the daily scheduler (FX fetch + materialize + close-month) every 24h.
- `frontend` — Next.js dev server with hot reload.

See `docs/adr/0026-local-only-posture.md` (proposed) for the design rationale and `docs/superpowers/specs/2026-07-05-local-only-posture-design.md` for the full spec.

## Future migration: SQLite → Postgres

The local SQLite holds your actual financial data. When you want to move it to your remote Postgres:

1. Set `backend/.env.local.remote` with the new URL.
2. `alembic upgrade head` runs automatically on first boot.
3. `pgloader sqlite:///path/to/.dev-data/quaestor.db postgresql://user:REDACTED@host/quaestor_production_db` — copies the data.
4. Smoke-test with `just dev-real`.
5. Archive `.dev-data/quaestor.db` for 30 days as a rollback safety net.

ENUM casts may need explicit handling (ADR-0024 documents the Postgres ENUM types).
