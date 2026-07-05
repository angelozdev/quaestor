# 0026. Local-only posture

- **Status:** accepted
- **Date:** 2026-07-05
- **Deciders:** Angelo
- **Supersedes:** [0010 — Deployment posture](./0010-deployment-posture.md), [0013 — Daily scheduler as a thin sidecar](./0013-daily-scheduler-as-a-thin-sidecar.md)
- **Superseded by:** —

## Context and problem statement

Quaestor was designed and built for self-hosted single-VPS production deployment (ADR-0010): a five-service Docker stack with Caddy for public HTTPS, a separate Postgres container, a scheduler sidecar (ADR-0013), and a Tailscale sidecar (later removed by ADR-0025). The user has changed direction. Quaestor is now a **local-only** project that runs on the user's Mac, and the only thing that should leave the host is the **database**, which the user manages and secures themselves. Everything else (api, frontend, MCP, scheduler) stays local.

One non-obvious constraint shapes every other choice in this ADR: the local SQLite file at `.dev-data/quaestor.db` holds the user's actual financial data today. It is not a sandbox. The local "real" store is the primary store until the user migrates to remote Postgres, so the new posture must preserve that file across the change.

## Decision drivers

- **Local-only, single-user.** No public deployment, no multi-tenant surface, no TLS termination in scope.
- **Database is the only remote concern.** The app stack runs on the user's Mac; only the database leaves the host, by URL.
- **Preserve existing SQLite data.** `.dev-data/quaestor.db` is the user's actual financial data. The new posture must not wipe, replace, or repath it. A future migration to remote Postgres is documented but out of scope.
- **Auto-bootstrap with zero manual steps.** `docker compose up` must build, wait for the database, run migrations, and start serving. No "remember to run alembic first" instructions.
- **Two database profiles, explicit choice.** Sandbox (local SQLite) versus real (remote Postgres), selected by env file at the `docker compose` boundary, not by branch or by code path inside the app.

## Considered options

1. **Local-only with two env-file profiles (chosen).** A single `docker-compose.yml` with two services (`api`, `frontend`); a Python `__main__.py` entrypoint in the api container that waits for the database, runs `alembic upgrade head`, and starts uvicorn; an asyncio scheduler task spawned from the api's FastAPI lifespan. Two gitignored env files (`.env.local.sqlite`, `.env.local.remote`) pick the database; `just` recipes (`dev-local`, `dev-real`) pass the chosen file to `docker compose --env-file`.
2. **Full self-hosted prod (rejected).** Keep the existing five-service VPS topology: Caddy + Tailscale + Postgres container + scheduler sidecar + api + frontend, with Litestream-style continuous backup. Rejected because the user explicitly pivoted away from public deployment.
3. **Hybrid local app with managed Postgres (deferred).** Keep the app local, but pay for a managed Postgres (RDS or Neon) so backups, point-in-time recovery, and HA come for free. Deferred as too early for a paid managed service; the user already has a remote Postgres (Render.com, Oregon) they manage themselves.

## Decision outcome

Chosen option: **local-only with two env-file profiles**, because it satisfies all five drivers at once. No public surface. The database stays the only remote concern. The existing SQLite data carries over because the new compose reuses the named Docker volume, with no `docker compose down -v` anywhere in the recipes. The Python `__main__.py` makes bootstrap one command. The two env files turn sandbox-vs-real into a one-flag switch at the CLI.

Concrete shape:

- **Compose.** Single `docker-compose.yml` with two services (`api`, `frontend`). No `db`, no `caddy`, no `scheduler`, no override file, no Tailscale sidecar. The named volume `quaestor-dev-data` is reused so `.dev-data/quaestor.db` carries over without a reset.
- **Entrypoint.** `backend/src/quaestor/__main__.py`, run as `CMD ["python", "-m", "quaestor"]` from the api container. Probes the database URL (SQLite or Postgres), retries up to N times with backoff, runs `alembic upgrade head`, then starts uvicorn. Same language as the codebase, testable with pytest, no escaping of URLs or secrets.
- **Scheduler.** `backend/src/quaestor/scheduler.py` exposes `run_forever()`, an asyncio task that runs the daily job (`quaestor.jobs.daily.run`) once on boot (`RUN_ON_BOOT=1`, default), then every 24 hours. A failure is logged but does not kill the loop. Cancelled cleanly on lifespan shutdown. Spawned by `backend/src/quaestor/api.py` via an `@asynccontextmanager async def lifespan(app)` passed to `FastAPI(lifespan=...)`.
- **Env files.** Two gitignored files (`backend/.env.local.sqlite`, `backend/.env.local.remote`); `backend/.env.local.example` as the committed template; the old `backend/.env.production` and `backend/.env.local` are deleted. `just` recipes (`dev-local`, `dev-real`) export `QUAESTOR_ENV_FILE` and pass the chosen file via `docker compose --env-file`.
- **Remote database target.** A remote Postgres already exists (Render.com, Oregon region, database `quaestor_production_db`); the user manages its security, backups, and rotation. The app connects by URL only. The migration recipe from SQLite to that Postgres is documented (pgloader + ENUM casts) but not built in this plan.

### Pros and cons of the options

**Local-only with two env-file profiles**
- Good, because the local SQLite holds the user's real data, and this option preserves it with no `down -v` and no schema rewrite.
- Good, because bootstrap is one command: build, wait, migrate, serve. No manual alembic step.
- Good, because the database stays the only remote concern, exactly the shape the user asked for.
- Good, because the asyncio scheduler inside lifespan kills the scheduler sidecar and `scripts/cron.sh` without losing functionality.
- Bad, because the local-only posture owns no backups. A host failure loses the SQLite file. That risk is acceptable for a personal-finance app where the user controls backup policy off-host.
- Bad, because `RUN_ON_BOOT=1` re-runs the daily job on every uvicorn hot reload. Idempotent, but noisy in logs; the user can flip to `RUN_ON_BOOT=0` if it bothers them.

**Full self-hosted prod (rejected)**
- Good, because it's already built and works.
- Bad, because the user pivoted away from public deployment. The production stack solves a problem the user no longer has.
- Bad, because Caddy, Tailscale, and Litestream-style backups each add operational surface and secret-rotation the user no longer wants.

**Hybrid local app with managed Postgres (deferred)**
- Good, because managed Postgres gives backups, point-in-time recovery, and HA for free, the natural next step if the app ever scales past a single machine.
- Bad (right now), because it adds a billing surface and a vendor dependency before there is a reason to pay for one.
- Bad (right now), because the user already has a remote Postgres they manage; a second managed instance would split data across two providers.

## Consequences

- Good: the local SQLite at `.dev-data/quaestor.db` is preserved across the posture change. The named Docker volume outlives `docker compose down`, image rebuilds, and compose rewrites.
- Good: `docker compose up` does everything. No separate migration script, no separate cron entry.
- Good: the daily job moves into the api process, retiring one container, one `scripts/cron.sh`, and one host cron entry.
- Bad / cost: ADR-0010 (deployment posture) and ADR-0013 (daily scheduler as a thin sidecar) are both superseded. Their bodies stay for historical reference; their frontmatter flips to `Superseded by: 0026` in Task 3.
- Bad / cost: Postgres in the prod stack goes away; remote Postgres is the only database the app talks to outside the sandbox. The migration recipe (pgloader + ENUM casts) is documented but not implemented yet.
- Bad / cost: there is no `dev-reset-local` recipe. Resetting the sandbox SQLite is a four-command manual sequence. The friction is intentional; it prevents accidental data loss.
- Unchanged: ADR-0024 (Postgres replaces SQLite) still applies. Only the topology changed; the engine, migrations, schema, and concurrency story are the same. Pytest stays on host-side SQLite in-memory. ADR-0025 (remove external MCP HTTP) still applies; chat stays in-process via the in-memory bridge, with no external `.mcp.json`.

## Confirmation

- ADR-0010 and ADR-0013 are marked `superseded by 0026` in `docs/adr/README.md` and in their own frontmatter (Task 3).
- `docs/adr/README.md` carries a row for 0026 with status `proposed`; the row flips to `accepted` after the implementation plan merges (Task 17).
- The implementation plan's downstream tasks (compose rewrite, `__main__.py`, `scheduler.py`, `api.py` lifespan, simplified `Dockerfile`, rewritten `justfile`) reference this ADR as the source of truth for the new topology.
- A grep across the committed tree for `Caddyfile`, `tailscale`, `litestream`, `quaestor-db-data`, `MCP_HOST`, `LETSENCRYPT_EMAIL` returns no hits in source code once the implementation tasks merge (Task 16).
- The smoke-test in Task 15 confirms `just dev-local` builds images, waits for the database, runs alembic, starts uvicorn, and logs the scheduler boot run end-to-end.

## Supersedes

- [0010 — Deployment posture](./0010-deployment-posture.md)
- [0013 — Daily scheduler as a thin sidecar](./0013-daily-scheduler-as-a-thin-sidecar.md)

## Related

- [0014 — Chat endpoint with LiteLLM and an in-memory MCP bridge](./0014-chat-endpoint-with-litellm-and-mcp-bridge.md). The chat endpoint stays as-is; only the posture around it changes.
- [0024 — Postgres replaces SQLite](./0024-postgres-replaces-sqlite.md). Still applies. Postgres is just remote now; the schema, migrations, and concurrency story are unchanged.
- [0025 — Remove external MCP HTTP exposure](./0025-remove-external-mcp-http.md). Still applies. Chat remains in-process only; the local-only posture adds no new MCP surface.
- Spec: `docs/superpowers/specs/2026-07-05-local-only-posture-design.md`.
- Future plan (deferred, not in scope here): a SQLite to Postgres data-migration recipe that ships a `just migrate-to-postgres` wrapper around pgloader with ENUM-cast handling.
