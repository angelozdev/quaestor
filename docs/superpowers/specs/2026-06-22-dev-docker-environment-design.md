# Quaestor — Development Docker Environment (sub-project)

**Date:** 2026-06-22
**Depends on:** P7 deployment (same images, different runtime)
**Part of:** `2026-06-16-quaestor-general-design.md` (developer workflow, not user-facing)

---

## Objective

Give the developer a local command (`just dev`) that brings up `api`, `mcp`, `frontend`, and `scheduler` in Docker, with the source code bind-mounted so edits hot-reload. No Caddy, no Tailscale, no Litestream, no TLS — direct ports on `localhost`. The scheduler runs in a long-lived idle container that the developer triggers manually with `just dev-trigger-scheduler`. The shared SQLite DB lives in `./.dev-data/quaestor.db` on the developer's Mac and persists across restarts.

## Scope

- `docker-compose.override.yml` at the repo root. Auto-merged by Docker Compose with `docker-compose.yml` (P7 production) so `docker compose up` runs the dev stack by default. The override replaces the runtime concerns (commands, env, volumes) for the four services P7 ships; it does NOT redefine services or change the production compose.
- A `dev` target in `backend/Dockerfile` that installs dev dependencies (`pytest`, `watchfiles`) and exposes `/app/src` as a writable bind-mount point. The production image keeps the existing default target.
- A `MCP_RELOAD=1` env var honored by `quaestor.mcp.server.main()` that turns on `uvicorn.run(..., reload=True, reload_dirs=["/app/src"])`.
- A `justfile` at the repo root with recipes: `dev`, `dev-build`, `dev-logs`, `dev-down`, `dev-reset`, `dev-trigger-scheduler`, `dev-shell-api`, `dev-test`.
- Env loading: per-service `env_file:` pointing at `./backend/.env.local` and `./frontend/.env.local` (already maintained by the developer). The override overrides `QUAESTOR_DB` and `COOKIE_SECURE` only; everything else comes from the existing `.env.local` files.
- A `.gitignore` addition: `.dev-data/`.
- A `README.md` section "Development" with the four commands a new developer needs.

**Out of scope:** CI/CD, integration tests against the dev stack, seeding fixtures, multiple-dev-user scenarios (Litestream is single-writer), running dev compose on anything other than the developer's Mac.

## Contribution to the data model

**None.** Dev uses the same schema, the same `quaestor.db` file layout, and the same `db.init_db` migrations as production. The DB is just located at `./.dev-data/quaestor.db` instead of the production volume path.

## Components

| Component | What it is | Notes |
|---|---|---|
| `docker-compose.override.yml` | Docker Compose override file | Auto-merged with `docker-compose.yml` by Compose |
| `backend/Dockerfile` (modify) | Add a `dev` build stage | Installs dev deps; production default target unchanged |
| `backend/src/quaestor/mcp/server.py` (modify) | Honor `MCP_RELOAD=1` env var | Two-line change inside `main()` |
| `justfile` (create) | Dev command runner | Replaces Makefile |
| `.gitignore` (modify) | Exclude `.dev-data/` | One line |
| `README.md` (modify) | "Development" section | ~20 lines |

The override file defines overrides only for the four services P7 already declares. It does NOT add new services.

### Override file shape (illustrative)

```yaml
# Auto-merged with docker-compose.yml by Compose.
services:
  api:
    build:
      context: ./backend
      target: dev              # use the dev stage of the multi-stage Dockerfile
    env_file:
      - ./backend/.env.local
    environment:
      QUAESTOR_DB: sqlite:////.dev-data/quaestor.db
      COOKIE_SECURE: "false"
    command: >-
      uv run uvicorn quaestor.api:app
      --host 0.0.0.0 --port 8000
      --reload --reload-dir /app/src
    volumes:
      - ./backend/src:/app/src:rw
      - ./backend/pyproject.toml:/app/pyproject.toml:ro
      - ./backend/uv.lock:/app/uv.lock:ro
      - ./.dev-data:/.dev-data

  mcp:
    build:
      context: ./backend
      target: dev
    env_file:
      - ./backend/.env.local
    environment:
      QUAESTOR_DB: sqlite:////.dev-data/quaestor.db
      MCP_RELOAD: "1"
    volumes:
      - ./backend/src:/app/src:rw
      - ./backend/pyproject.toml:/app/pyproject.toml:ro
      - ./backend/uv.lock:/app/uv.lock:ro
      - ./.dev-data:/.dev-data

  frontend:
    build:
      context: ./frontend
    env_file:
      - ./frontend/.env.local
    command: ["pnpm", "dev"]
    volumes:
      - ./frontend/app:/app/app
      - ./frontend/components:/app/components
      - ./frontend/lib:/app/lib
      - ./frontend/ui:/app/ui
      - ./frontend/public:/app/public
      - ./frontend/package.json:/app/package.json:ro
      - ./frontend/next.config.ts:/app/next.config.ts:ro
      - ./frontend/biome.json:/app/biome.json:ro
      - frontend_node_modules:/app/node_modules

  scheduler:
    build:
      context: ./backend
      target: dev
    env_file:
      - ./backend/.env.local
    environment:
      QUAESTOR_DB: sqlite:////.dev-data/quaestor.db
    command: ["sh", "-c", "trap 'exit 0' TERM INT; echo 'scheduler ready (manual trigger only)'; while true; do sleep 86400 & wait $$!; done"]
    volumes:
      - ./.dev-data:/.dev-data

volumes:
  frontend_node_modules:
```

Notes on the override:
- `api`, `mcp`, `scheduler` use the `dev` target of the backend Dockerfile (a new multi-stage target). `frontend` uses the same single-stage frontend Dockerfile as production but overrides the command to `pnpm dev`.
- The override does NOT change Caddy, Tailscale, or Litestream: those services are unchanged from P7 production and would only run if the user explicitly invokes them (Compose auto-merge only applies to services declared in both files; Caddy/Tailscale are only in `docker-compose.yml`, so they stay live unless removed).
- This is intentional: the user's first `docker compose up` brings up the full stack including Caddy/Tailscale. The override removes only the things that conflict (commands, env, volumes). If the user wants to skip Caddy/Tailscale in dev, they can stop them with `docker compose stop caddy tailscale`.

### `justfile` shape

```just
# Quaestor — dev recipes.

_default:
    @just --list

# Start the dev stack (foreground; Ctrl-C stops).
dev:
    docker compose up

# Build images first (cold start).
dev-build:
    docker compose build

# Follow logs from all services.
dev-logs:
    docker compose logs -f

# Stop the stack (keeps data in ./.dev-data/quaestor.db).
dev-down:
    docker compose down

# Wipe ./.dev-data/ and restart api+mcp so the schema is recreated.
dev-reset:
    rm -rf .dev-data
    mkdir -p .dev-data
    docker compose up api mcp

# Manually run the daily job once (FX + materialize_due + ensure_month_closed).
dev-trigger-scheduler:
    docker compose exec scheduler uv run python -m quaestor.jobs.daily

# Open a shell in the api container.
dev-shell-api:
    docker compose exec api sh

# Run the backend test suite (on the host, not in a container).
dev-test:
    cd backend && uv run pytest -q
```

### Backend Dockerfile `dev` target

The existing backend Dockerfile is single-stage. Change it to a two-stage build:

```dockerfile
# Stage dev: includes pytest + watchfiles for hot reload.
FROM python:3.12-slim AS dev
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
RUN pip install --no-cache-dir uv==0.5.11
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen                # sync WITH dev deps
COPY scripts/ ./scripts/
RUN chmod +x ./scripts/cron.sh
ENV PATH="/app/.venv/bin:${PATH}"

# Stage prod: production-only deps, default target.
FROM dev AS prod
RUN uv sync --frozen --no-dev

# Default to prod (used by P7 production compose).
CMD ["uv", "run", "uvicorn", "quaestor.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

When the override specifies `target: dev`, only the first stage runs. The second stage (`prod`) is what production uses and remains the default target.

### MCP reload hook

In `backend/src/quaestor/mcp/server.py`, modify `main()`:

```python
def main() -> None:
    import uvicorn

    host = os.environ.get("MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_PORT", "9000"))
    reload = os.environ.get("MCP_RELOAD", "").lower() in ("1", "true", "yes")
    uvicorn.run(
        "quaestor.mcp.server:build_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
        reload_dirs=["/app/src"] if reload else None,
    )
```

The `factory=True` form is required because `build_app()` is a factory. Reload only watches `/app/src` (not `.venv`) to keep noise down. No-op in production (env var absent).

## Public interface

The developer's surface is six commands and two URLs.

```text
just dev                  # start (foreground)
just dev-build            # first-time image build
just dev-logs             # follow logs
just dev-down             # stop
just dev-reset            # wipe DB and restart
just dev-trigger-scheduler  # run daily job once
just dev-shell-api        # shell into api
just dev-test             # pytest (host-side)

# URLs:
http://localhost:3000     # frontend (Next.js dev server)
http://localhost:8000/api # REST API (uvicorn --reload)
http://localhost:9000/mcp # MCP (uvicorn --reload when MCP_RELOAD=1)
```

## Key logic and rules

**Bind mount over COPY.** The dev stack bind-mounts `./backend/src` and the frontend source directories into the containers. Edits on the host show up in the container immediately; uvicorn and `next dev` watch and restart. No rebuild required.

**Env precedence is `environment:` > `env_file:` > shell.** The override file uses `env_file:` to load `.env.local` and `environment:` to override the two values that must differ in dev (`QUAESTOR_DB` to the bind-mount path, `COOKIE_SECURE: "false"` because there is no TLS in dev). Everything else (`APP_TOKEN`, `SESSION_SECRET`, `APP_PASSWORD`, `MCP_HOST`, `MCP_PORT`, `FRONTEND_ORIGIN`) flows from `.env.local` untouched. The developer edits one file and the change applies on the next `docker compose up`.

**Frontend bind mounts are selective.** Mounting `./frontend` directly would overwrite the `node_modules` that the image installs. The override mounts each subdirectory (`app`, `components`, `lib`, `ui`, `public`) plus a few root files (`package.json`, `next.config.ts`, `biome.json`), and uses an anonymous-named volume `frontend_node_modules` for `node_modules` so it survives container restarts but is invisible on the host.

**Scheduler stays idle in dev.** The override replaces the production `cron.sh` command with a long-running sleep loop. The container stays up so the developer can `docker compose exec scheduler ...` into it without paying the container-start cost every time. Trigger the daily job with `just dev-trigger-scheduler`. To test the FX job alone, target it directly: `docker compose exec scheduler uv run python -m quaestor.jobs.fx_fetch` (the spec for `quaestor.jobs.fx_fetch` already exists from P7 Task 3; if not yet shipped, this command will not work and the developer runs the orchestration instead).

**Caddy/Tailscale/Litestream stay up but are not in the developer's critical path.** They are inherited from `docker-compose.yml` unchanged. The browser talks to the frontend at `localhost:3000` directly, bypassing Caddy. Claude Code on the same Mac talks to the MCP at `localhost:9000` directly, bypassing Tailscale. The developer can stop them with `docker compose stop caddy tailscale` to free ports `80`/`443` and reduce noise, but it is not required.

**Single-writer SQLite invariant is preserved.** The dev DB is one file, mounted into all three services that write. WAL + `busy_timeout` (from P7 Task 2) serialize writes. There is no second host. If the developer runs tests on the host with `cd backend && uv run pytest`, those tests use an in-memory SQLite (`tests/conftest.py`) and never touch the dev DB, so they do not race with the containers.

**`.dev-data/` is gitignored and disposable.** It holds the SQLite file plus its `-wal` and `-shm` siblings (because Compose mounts the directory, not just the file). The developer can wipe it with `just dev-reset` and start over.

## Errors/Risks

- **Port already in use.** If `3000`/`8000`/`9000` is bound by another process on the host, `docker compose up` fails. The developer checks with `lsof -i :3000`. Caddy on port `80`/`443` may conflict with a local reverse-proxy dev tool (e.g., `nginx`); stop Caddy with `docker compose stop caddy`.
- **Frontend `.next/` mismatch.** The first `pnpm dev` run after switching from production standalone may complain about `.next/` artifacts left over from the prior build. Fix: `rm -rf frontend/.next && just dev-build`. (Already gitignored.)
- **`.env.local` missing.** The first run fails because Compose cannot read the file. The developer creates it (a template is in `backend/.env.example`; copy and edit).
- **`uv sync --frozen` drift.** If `backend/uv.lock` changes after the dev image is built, `uv run` may complain. Fix: `just dev-build`.
- **Stale `node_modules` after package.json change.** The override mounts `package.json` as `:ro` but does not trigger `pnpm install` automatically. The developer runs `docker compose exec frontend pnpm install` after adding a dep, then restarts `frontend` (`docker compose restart frontend`).
- **Two MCP/HTTP processes** (host `python -m quaestor.mcp` AND container) racing for `:9000`. The developer should not run MCP on the host while containers are up. Use `just dev-shell-mcp` style exec into the container, or stop the container first.

## Testing and "done" criterion

The spec's "done" criterion is the developer can do this end-to-end without rebuilding:

1. `just dev-build` succeeds.
2. `just dev` brings up `api`, `mcp`, `frontend`, `scheduler`, and they reach `running` state within ~60 seconds.
3. `http://localhost:3000` returns 200 and serves the frontend.
4. `curl -H "Authorization: Bearer $(grep APP_TOKEN backend/.env.local | cut -d= -f2)"; http://localhost:8000/api/auth/me` returns 200 or 401 (a real response, not a connection error).
5. Edit `backend/src/quaestor/api/__init__.py` to add `print("reloaded")` somewhere visible. Within 2 seconds, `just dev-logs api` shows the reload line and a new request to `:8000` triggers the new code.
6. Edit `frontend/app/page.tsx` (or any client component) to change a string. The browser hot-reloads without manual refresh.
7. `just dev-trigger-scheduler` prints a JSON line with `materialized_count` and `month_closed`; rerun shows `materialized_count == 0`.
8. `just dev-reset` wipes `./.dev-data/`; the next request creates a fresh schema.
9. `just dev-down` stops everything cleanly.

"Done" = all nine points pass on a fresh Mac (Docker Desktop + `just` installed via `brew install just`).

## Integration with other sub-projects

- **P7 Deployment:** the production `docker-compose.yml` is the base; the override file auto-merges with it. P7 already sets up WAL + `busy_timeout` (Task 2 of P7), the FX + daily jobs (Tasks 3-4 of P7), and the `quaestor.jobs.daily` CLI entry point. This sub-project consumes those.
- **P3 Temporal Engine:** the dev `scheduler` container runs the same `quaestor.jobs.daily` module; no changes to P3.
- **P1 API + Auth:** `require_auth` reads `APP_TOKEN` from env. Dev passes the dev `APP_TOKEN` from `.env.local`.
- **P2 MCP:** the dev `mcp` service runs the same `quaestor.mcp.server.main()`; this sub-project adds the `MCP_RELOAD` knob.
- **P6 Frontend:** uses the same Next.js codebase. Dev runs `pnpm dev` instead of `next start`; everything else is identical.

**Cross-cutting conventions respected:** this sub-project does not touch money, sign, schema, or business logic. It only changes how the existing artifacts are packaged and run on the developer's machine. No new domain entities, no new migrations, no new business logic.
