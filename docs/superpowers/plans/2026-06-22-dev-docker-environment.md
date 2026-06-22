# Dev Docker Environment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `just dev` command on the developer's Mac that brings up `api`, `mcp`, `frontend`, and `scheduler` in Docker with hot-reload, a persistent local SQLite, and no production-only services (Caddy/Tailscale/Litestream) running.

**Architecture:** A `docker-compose.override.yml` at the repo root auto-merges with the P7 production `docker-compose.yml` (Compose auto-uses an override file when present). The override only redefines `api`/`mcp`/`frontend`/`scheduler` runtime concerns (build target, env, volumes, command); it tags `caddy`/`tailscale`/`litestream` with `profiles: ["never"]` so `docker compose up` skips them. The backend Dockerfile becomes a two-stage build with a `dev` target that includes pytest/watchfiles and exposes a writable `/app/src` for hot-reload. `quaestor.mcp.server.main()` reads `MCP_RELOAD=1` and turns on uvicorn's reload. A `justfile` at the repo root holds the recipes (`dev`, `dev-build`, `dev-logs`, `dev-down`, `dev-reset`, `dev-trigger-scheduler`, `dev-shell-api`, `dev-test`).

**Tech Stack:** Docker Compose v2 (auto-merge override), `just` (recipe runner), Python 3.12 + uv + uvicorn (`--reload` / `--reload-dir`), Node 22 + pnpm + `next dev`, Next.js 16.

## Global Constraints

These apply to **every** task. Exact values copied from the spec.

- **Auto-merge only:** `docker-compose.override.yml` must live in the **same directory** as `docker-compose.yml` (repo root) for Compose to auto-merge. Do NOT move it elsewhere.
- **Override file is dev-only:** It must NOT touch `docker-compose.yml`. Any change to the production stack goes through the P7 plan, not this one.
- **Profiles `["never"]` for prod-only services:** `caddy`, `tailscale`, `litestream` must be re-declared in the override with `profiles: ["never"]` so `docker compose up` (no `--profile` flag) skips them. They remain defined in `docker-compose.yml` for production.
- **Env precedence:** Compose `environment:` overrides `env_file:`. The override file loads `./backend/.env.local` (and `./frontend/.env.local`) via `env_file:`, then uses `environment:` only to override `QUAESTOR_DB` (to the bind-mount path) and `COOKIE_SECURE` (`"false"`). All other env vars flow from `.env.local` untouched.
- **Frontend bind mounts are selective:** Mount each subdirectory (`app`, `components`, `lib`, `ui`, `public`) plus root files (`package.json`, `next.config.ts`, `biome.json`). Use a named volume `frontend_node_modules` for `/app/node_modules` so it survives container restarts but stays invisible on the host.
- **`backend/.env.local` and `frontend/.env.local` already exist** (the developer maintains them). This plan does NOT create or modify either file. The override loads them as-is.
- **No new domain logic, schema, or business code.** The only code change to the backend Python is the `MCP_RELOAD` knob in `quaestor.mcp.server.main()`.
- **WAL + `busy_timeout=5000` from P7 Task 2** apply here too: `./.dev-data/quaestor.db` uses the same pragma path as production.
- **Language:** all code, identifiers, comments, strings in English (ADR-0001).
- **Mac-first:** the spec's "done" criterion assumes Docker Desktop on macOS with `brew install just`. Linux also works; Windows requires WSL2.

---

## File Structure

**Create (repo root):**
- `docker-compose.override.yml` — auto-merged with P7 `docker-compose.yml`. Overrides `api`/`mcp`/`frontend`/`scheduler`; tags `caddy`/`tailscale`/`litestream` as `profiles: ["never"]`.
- `justfile` — eight recipes for the dev workflow.

**Modify (backend):**
- `backend/Dockerfile` — split into `dev` and `prod` stages. The `dev` stage installs dev deps; the `prod` stage is the existing single-stage image renamed.
- `backend/src/quaestor/mcp/server.py` — read `MCP_RELOAD=1` and pass `reload=True` to `uvicorn.run(...)`.

**Modify (repo root):**
- `.gitignore` — add `.dev-data/`.
- `README.md` — add a "Development" section.

**Create (tests):**
- `backend/tests/mcp/test_reload_env.py` — test the env-var → uvicorn-kwargs mapping.

**No P7 production artifacts are touched.** `docker-compose.yml`, `Caddyfile`, `ts-serve.json`, `litestream.yml`, `backend/scripts/cron.sh`, `quaestor.jobs.fx_fetch`, `quaestor.jobs.daily` (from the P7 plan) are dependencies but are not modified by this plan.

**Conventions for every command in this plan:** run from the path stated in the task. The plan assumes the user has already installed `just` (`brew install just`) and Docker Desktop.

---

### Task 1: Backend Dockerfile — split into `dev` and `prod` stages

The override file references `target: dev`. Production keeps the existing image as the default target (renamed from the implicit one to an explicit `prod` stage).

**Files:**
- Modify: `backend/Dockerfile`

**Interfaces:**
- Produces: a multi-stage Dockerfile with named stages `dev` and `prod`. `dev` runs `uv sync --frozen` (with dev deps); `prod` runs `uv sync --frozen --no-dev` on top of `dev`. Default target remains `prod`. The `CMD` line lives on the `prod` stage so production users who build without `--target` get the same command as today.

- [ ] **Step 1: Replace the single-stage Dockerfile with a two-stage build**

Open `backend/Dockerfile` and replace its entire contents with:

```dockerfile
# Quaestor backend image — multi-stage (ADR-0013).
# `prod` (default) is what production (P7) uses.
# `dev` is what the local dev override (docker-compose.override.yml) builds.

# --- dev stage: includes dev deps so uvicorn --reload works.
FROM python:3.12-slim AS dev

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

RUN pip install --no-cache-dir uv==0.5.11

COPY pyproject.toml uv.lock ./
# Sync WITH dev deps (pytest, watchfiles).
RUN uv sync --frozen

COPY src/ ./src/
COPY scripts/ ./scripts/
RUN chmod +x ./scripts/cron.sh

ENV PATH="/app/.venv/bin:${PATH}"

# --- prod stage: drops dev deps. Default target for production builds.
FROM dev AS prod

RUN uv sync --frozen --no-dev

CMD ["uv", "run", "uvicorn", "quaestor.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

Pin `uv==0.5.11` to match whatever version the dev machine uses today
(`uv --version`). If the dev machine has a different version, bump the pin.

- [ ] **Step 2: Smoke-build both targets**

Run:
```bash
cd backend
docker build --target dev -t quaestor-backend:dev .
docker build --target prod -t quaestor-backend:prod .
```
Expected: both succeed. The `dev` image should be ~50 MB larger than `prod` (the dev-deps diff).

- [ ] **Step 3: Verify the `prod` image still runs the API**

Run:
```bash
docker run --rm -e QUAESTOR_DB=sqlite:///:memory: -e APP_TOKEN=t -p 8000:8000 quaestor-backend:prod &
sleep 3
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer t" http://localhost:8000/api/auth/me
kill %1
```
Expected: `200` or `401` (any real response). The kill command cleans up the background container.

- [ ] **Step 4: Commit**

```bash
git add backend/Dockerfile
git commit -m "build(backend): split Dockerfile into dev and prod stages"
```

---

### Task 2: `MCP_RELOAD` knob in `quaestor.mcp.server.main()`

The dev override sets `MCP_RELOAD=1`. `main()` reads it and passes `reload=True` to `uvicorn.run(...)`. Production callers (no env var) keep current behavior.

**Files:**
- Modify: `backend/src/quaestor/mcp/server.py:65-70`
- Test: `backend/tests/mcp/test_reload_env.py`

**Interfaces:**
- Produces: `def _uvicorn_kwargs_from_env(env: Mapping[str, str]) -> dict` — returns the kwargs that should be passed to `uvicorn.run(...)`. Keys: `factory`, `host`, `port`, `reload`, `reload_dirs`. `reload` is `True` iff `env["MCP_RELOAD"]` is in `{"1", "true", "yes"}` (case-insensitive); `reload_dirs` is `["/app/src"]` when reload is on, else `None`.
- Produces: `main()` calls `uvicorn.run("quaestor.mcp.server:build_app", **_uvicorn_kwargs_from_env(os.environ))`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/mcp/test_reload_env.py`:

```python
"""MCP_RELOAD env var drives uvicorn reload mode."""
from __future__ import annotations

from collections import OrderedDict

import pytest

from quaestor.mcp.server import _uvicorn_kwargs_from_env


def _env(**kwargs) -> "OrderedDict[str, str]":
    return OrderedDict(kwargs)


def test_defaults_match_production_behavior():
    """No MCP_RELOAD -> reload off, host/port from MCP_HOST/MCP_PORT or defaults."""
    env = _env(MCP_HOST="0.0.0.0", MCP_PORT="9000")
    kw = _uvicorn_kwargs_from_env(env)
    assert kw["factory"] is True
    assert kw["host"] == "0.0.0.0"
    assert kw["port"] == 9000
    assert kw["reload"] is False
    assert kw["reload_dirs"] is None


def test_mcp_reload_1_enables_reload():
    env = _env(MCP_RELOAD="1", MCP_HOST="0.0.0.0", MCP_PORT="9000")
    kw = _uvicorn_kwargs_from_env(env)
    assert kw["reload"] is True
    assert kw["reload_dirs"] == ["/app/src"]


def test_mcp_reload_true_enables_reload():
    env = _env(MCP_RELOAD="true")
    kw = _uvicorn_kwargs_from_env(env)
    assert kw["reload"] is True


def test_mcp_reload_yes_enables_reload():
    env = _env(MCP_RELOAD="yes")
    kw = _uvicorn_kwargs_from_env(env)
    assert kw["reload"] is True


def test_mcp_reload_zero_disables_reload():
    env = _env(MCP_RELOAD="0")
    kw = _uvicorn_kwargs_from_env(env)
    assert kw["reload"] is False


def test_mcp_reload_empty_string_disables_reload():
    env = _env(MCP_RELOAD="")
    kw = _uvicorn_kwargs_from_env(env)
    assert kw["reload"] is False


def test_mcp_reload_garbage_disables_reload():
    env = _env(MCP_RELOAD="maybe")
    kw = _uvicorn_kwargs_from_env(env)
    assert kw["reload"] is False


def test_port_default_is_9000():
    env = _env()
    kw = _uvicorn_kwargs_from_env(env)
    assert kw["port"] == 9000
    assert kw["host"] == "0.0.0.0"


def test_port_invalid_raises_value_error():
    env = _env(MCP_PORT="not-a-number")
    with pytest.raises(ValueError):
        _uvicorn_kwargs_from_env(env)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && uv run pytest tests/mcp/test_reload_env.py -v`
Expected: ImportError — `_uvicorn_kwargs_from_env` does not exist yet.

- [ ] **Step 3: Implement the helper and rewire `main()`**

Modify `backend/src/quaestor/mcp/server.py`. Replace the body of `main()` and add the helper above it. Final state:

```python
"""MCP server assembly + entry point (`python -m quaestor.mcp`).

Builds a FastMCP instance, registers the core tools, exposes the streamable-HTTP
transport at `/mcp`, and wraps it with the bearer-auth middleware. We do NOT use
`mcp.run()` because we apply our own auth layer; we run uvicorn over the
auth-wrapped app instead.
"""
from __future__ import annotations

import os
from collections.abc import Mapping

# ... (existing imports and build_mcp/build_app stay unchanged) ...


_TRUTHY = {"1", "true", "yes"}


def _uvicorn_kwargs_from_env(env: Mapping[str, str]) -> dict:
    """Translate env vars into kwargs for uvicorn.run().

    `MCP_RELOAD` in {"1", "true", "yes"} (case-insensitive) enables uvicorn's
    autoreload, watching `/app/src` so edits to backend source trigger a
    restart. In production this env var is unset and reload is off.
    """
    reload_raw = env.get("MCP_RELOAD", "")
    reload = reload_raw.strip().lower() in _TRUTHY
    return {
        "factory": True,
        "host": env.get("MCP_HOST", "0.0.0.0"),
        "port": int(env.get("MCP_PORT", "9000")),
        "reload": reload,
        "reload_dirs": ["/app/src"] if reload else None,
    }


def main() -> None:
    import uvicorn

    uvicorn.run("quaestor.mcp.server:build_app", **_uvicorn_kwargs_from_env(os.environ))
```

Keep the existing `import os` (line 9) and the existing `def main():` block replaced.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && uv run pytest tests/mcp/test_reload_env.py -v`
Expected: 9 passes.

- [ ] **Step 5: Run the full suite**

Run: `cd backend && uv run pytest -q`
Expected: all tests pass; no regressions.

- [ ] **Step 6: Commit**

```bash
git add backend/src/quaestor/mcp/server.py backend/tests/mcp/test_reload_env.py
git commit -m "feat(mcp): MCP_RELOAD=1 enables uvicorn autoreload (dev only)"
```

---

### Task 3: `.gitignore` — exclude `.dev-data/`

One line. The dev DB and its WAL siblings live there.

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add the line**

Append to `/Users/angelozdev/me/quaestor/.gitignore` (the file currently has lines
1-37; append at the end):

```
# Local dev DB and WAL siblings (bind-mounted into api/mcp/scheduler in dev)
.dev-data/
```

- [ ] **Step 2: Verify `.dev-data/` is ignored**

Run:
```bash
mkdir -p /Users/angelozdev/me/quaestor/.dev-data
cd /Users/angelozdev/me/quaestor && git check-ignore -v .dev-data
rmdir /Users/angelozdev/me/quaestor/.dev-data
```
Expected: prints the matching rule (`.dev-data/`) on the first line of output.

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore .dev-data/"
```

---

### Task 4: `docker-compose.override.yml`

The single biggest file in this plan. Auto-merged with P7 `docker-compose.yml`. Defines the four dev services with overrides and tags the three prod-only services as `profiles: ["never"]`.

**Files:**
- Create: `docker-compose.override.yml`

**Interfaces:** Resolved by Docker Compose's auto-merge. Each service override replaces the matching fields in the base compose (commands, env, volumes, build target); unmatched fields are inherited from the base.

- [ ] **Step 1: Create the override file**

Create `/Users/angelozdev/me/quaestor/docker-compose.override.yml`:

```yaml
# Auto-merged with docker-compose.yml by Compose.
# `docker compose up` runs this dev stack by default.
#
# To run the production stack explicitly (skipping this override):
#   docker compose -f docker-compose.yml up -d
#
# To run the dev stack PLUS the prod-only services (rare):
#   docker compose --profile never up

services:
  api:
    build:
      context: ./backend
      target: dev
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
      - ./backend/scripts:/app/scripts:ro
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
    command: ["uv", "run", "python", "-m", "quaestor.mcp"]
    volumes:
      - ./backend/src:/app/src:rw
      - ./backend/pyproject.toml:/app/pyproject.toml:ro
      - ./backend/uv.lock:/app/uv.lock:ro
      - ./.dev-data:/.dev-data

  frontend:
    env_file:
      - ./frontend/.env.local
    environment:
      API_INTERNAL_URL: http://api:8000
    command: ["pnpm", "dev"]
    volumes:
      - ./frontend/app:/app/app
      - ./frontend/components:/app/components
      - ./frontend/lib:/app/lib
      - ./frontend/ui:/app/ui
      - ./frontend/public:/app/public
      - ./frontend/package.json:/app/package.json:ro
      - ./frontend/pnpm-lock.yaml:/app/pnpm-lock.yaml:ro
      - ./frontend/next.config.ts:/app/next.config.ts:ro
      - ./frontend/biome.json:/app/biome.json:ro
      - ./frontend/tsconfig.json:/app/tsconfig.json:ro
      - frontend_node_modules:/app/node_modules

  scheduler:
    build:
      context: ./backend
      target: dev
    env_file:
      - ./backend/.env.local
    environment:
      QUAESTOR_DB: sqlite:////.dev-data/quaestor.db
    command:
      - sh
      - -c
      - |
        trap 'exit 0' TERM INT
        echo 'scheduler ready (manual trigger only)'
        while true; do
          sleep 86400 &
          wait $$!
        done
    volumes:
      - ./.dev-data:/.dev-data

  # Inherited from docker-compose.yml but skipped in dev:
  caddy:
    profiles: ["never"]
  tailscale:
    profiles: ["never"]
  litestream:
    profiles: ["never"]

volumes:
  frontend_node_modules:
```

Notes:
- The `api` `command` uses YAML folded scalars (`>-`) for readability.
- The `scheduler` `command` is a small bash one-liner that traps SIGTERM/SIGINT and waits. The `$$!` expands to the PID of the most recent background process; in this context it expands to the `sleep` PID, but since `wait` is in a loop with `sleep 86400`, a SIGTERM exits via the trap cleanly.
- `frontend` overrides do NOT include a `build:` block — the override inherits the `build: { context: ./frontend }` from the base compose (P7 Task 7), avoiding duplication.
- `frontend` does override the CMD (`pnpm dev` vs. `node server.js`) and the env. Both compose correctly via the merge.

- [ ] **Step 2: Validate the file**

Run:
```bash
cd /Users/angelozdev/me/quaestor && docker compose config -q
```
Expected: exit 0, no errors. (If `docker-compose.yml` from P7 hasn't shipped yet, this will fail with "no such file"; in that case, temporarily create a minimal stub — see Step 3.)

- [ ] **Step 3: (Conditional) validate against a minimal base compose**

If P7 has not yet shipped `docker-compose.yml`, create a temporary stub to
validate the override file's syntax. Create `/tmp/stub-compose.yml`:

```yaml
services:
  api:
    build: ./backend
    image: quaestor-backend:latest
  mcp:
    build: ./backend
    image: quaestor-backend:latest
  frontend:
    build: ./frontend
    image: quaestor-frontend:latest
  scheduler:
    build: ./backend
    image: quaestor-backend:latest
  caddy:
    image: caddy:2
  tailscale:
    image: tailscale/tailscale
  litestream:
    image: litestream/litestream
```

Then:
```bash
cd /Users/angelozdev/me/quaestor
docker compose -f /tmp/stub-compose.yml -f docker-compose.override.yml config -q
rm /tmp/stub-compose.yml
```
Expected: exit 0. Skip this step entirely if P7 has shipped; `docker compose config -q` works against the real `docker-compose.yml`.

- [ ] **Step 4: Commit**

```bash
git add docker-compose.override.yml
git commit -m "ops(dev): docker-compose.override.yml with hot reload + never-profiled prod services"
```

---

### Task 5: `justfile`

Eight recipes. Replace Make with `just` (one binary, no `.PHONY`, no tabs).

**Files:**
- Create: `justfile`

- [ ] **Step 1: Create the file**

Create `/Users/angelozdev/me/quaestor/justfile`:

```just
# Quaestor — dev recipes.
#
# Quick start:
#   just dev-build   # one-time image build (~1-2 min)
#   just dev         # bring up the stack (foreground, Ctrl-C stops)
#   just dev-logs    # follow logs from all services
#
# When you're done:
#   just dev-down    # stop, keep .dev-data/
#   just dev-reset   # wipe .dev-data/ and restart api+mcp

_default:
    @just --list

# Start the dev stack (foreground; Ctrl-C stops).
dev:
    docker compose up

# Build images first (cold start or after pulling new source).
dev-build:
    docker compose build

# Follow logs from all services.
dev-logs:
    docker compose logs -f

# Follow logs from a single service, e.g. `just dev-logs-one api`.
dev-logs-one service:
    docker compose logs -f {{service}}

# Stop the stack. Keeps ./.dev-data/quaestor.db intact.
dev-down:
    docker compose down

# Wipe ./.dev-data/ and restart api+mcp so the schema is recreated fresh.
dev-reset:
    rm -rf .dev-data
    mkdir -p .dev-data
    docker compose up api mcp

# Manually run the daily job once (FX + materialize_due + ensure_month_closed).
# Requires P7's quaestor.jobs.daily module to be shipped.
dev-trigger-scheduler:
    docker compose exec scheduler uv run python -m quaestor.jobs.daily

# Open a shell in the api container.
dev-shell-api:
    docker compose exec api sh

# Run the backend test suite on the host (in-memory DB; does not touch .dev-data/).
dev-test:
    cd backend && uv run pytest -q
```

Notes:
- `just` requires recipes to be indented with **one tab**, not spaces.
- `_default` lists recipes when you run `just` with no args.
- `dev-logs-one service` shows the `just` parameter syntax (`{{service}}`).

- [ ] **Step 2: Verify the recipes parse**

Run:
```bash
cd /Users/angelozdev/me/quaestor && just --list
```
Expected: prints the 9 recipe names (8 + `_default`). If `just` is not installed: `brew install just`.

- [ ] **Step 3: Dry-run the `dev-down` recipe**

Run: `cd /Users/angelozdev/me/quaestor && just --evaluate dev-down`
Expected: prints `docker compose down` (the body of the recipe).

- [ ] **Step 4: Commit**

```bash
git add justfile
git commit -m "ops(dev): justfile with dev/build/logs/down/reset/trigger-scheduler/shell/test"
```

---

### Task 6: README — "Development" section

A short block at the top of the README pointing developers to the four commands they need. The existing `README.md` is at `/Users/angelozdev/me/quaestor/README.md` — check its current content first.

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Read the current README**

Run: `Read /Users/angelozdev/me/quaestor/README.md`

- [ ] **Step 2: Add a "Development" section**

Insert the following block as the second section (right after the existing `# Quaestor` heading + first paragraph, before any other top-level section):

````markdown
## Development

Local dev runs four services (`api`, `mcp`, `frontend`, `scheduler`) in Docker
with hot reload. No TLS, no Caddy, no Tailscale, no Litestream.

Prerequisites: Docker Desktop, `just` (`brew install just`), and the
`backend/.env.local` + `frontend/.env.local` files (already in the repo, edit
if you need different secrets).

```bash
just dev-build   # one-time image build
just dev         # bring up the stack
just dev-logs    # follow logs
just dev-down    # stop
just dev-reset   # wipe ./.dev-data/ and restart fresh
just dev-trigger-scheduler   # run the daily job once (FX + materialize + close)
just dev-shell-api           # shell into the api container
just dev-test    # backend pytest (host-side, in-memory DB)
```

URLs (once `just dev` is running):
- Frontend: <http://localhost:3000>
- REST API: <http://localhost:8000/api>
- MCP: <http://localhost:9000/mcp>

Edit any file under `backend/src/` and uvicorn restarts. Edit anything under
`frontend/app/`, `frontend/components/`, etc. and Next.js hot-reloads. The
SQLite DB lives at `./.dev-data/quaestor.db` (gitignored).
````

If the existing README has a different structure, add a `## Development`
heading at the same level as the existing `##` headings; preserve any other
formatting choices (e.g., emoji-free, no trailing whitespace).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: Development section with just dev* workflow"
```

---

### Task 7: End-to-end verification (matches spec §Testing, points 1-9)

The spec's "done" criterion is nine checks. Run them on the developer's Mac.

**Files:** None created. Verification only.

**Interfaces:** The full dev stack via `just dev`.

- [ ] **Step 1: `just dev-build` succeeds**

Run: `cd /Users/angelozdev/me/quaestor && just dev-build`
Expected: exit 0; both `quaestor-backend:dev` and `quaestor-frontend` images build.

- [ ] **Step 2: `just dev` brings services up**

In one terminal: `cd /Users/angelozdev/me/quaestor && just dev`
In another terminal: `docker compose ps`
Expected: `api`, `mcp`, `frontend`, `scheduler` all `running`. `caddy`, `tailscale`, `litestream` are absent from the listing (skipped via `profiles: ["never"]`).

- [ ] **Step 3: Frontend responds on `:3000`**

Run: `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/`
Expected: `200`.

- [ ] **Step 4: API responds on `:8000`**

Run:
```bash
TOKEN=$(grep APP_TOKEN /Users/angelozdev/me/quaestor/backend/.env.local | cut -d= -f2)
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/auth/me
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/auth/me
```
Expected: `200` or `401` on the first line, `401` on the second (proves token gating works).

- [ ] **Step 5: Backend hot-reload**

Edit `backend/src/quaestor/api/__init__.py` and add a `print("reloaded", flush=True)` line at the top of the `create_app()` function (right before `app = FastAPI(...)`).
Run: `just dev-logs-one api` in another terminal.
Expected: within ~2 seconds, a line like `reloaded` appears, then uvicorn logs `Application startup complete.` again.
Revert the edit (delete the `print` line) and confirm uvicorn reloads a second time.
Commit nothing — the edit is reverted in Step 5's body.

- [ ] **Step 6: Frontend hot-reload**

Open `http://localhost:3000/` in the browser. Note the current text on the home page.
Edit `frontend/app/page.tsx` and change a visible string (e.g., a heading).
Expected: the browser updates within ~1 second without manual refresh (Next.js HMR).
Revert the edit.

- [ ] **Step 7: `just dev-trigger-scheduler` runs the daily job**

Run: `just dev-trigger-scheduler`
Expected output (one line of JSON):
```json
{"fx_error": null, "fx_rate": "...", "materialized_count": 0, "month_closed": "2026-06"}
```
Run again: `just dev-trigger-scheduler`
Expected: `materialized_count: 0` (idempotent).

If `quaestor.jobs.daily` is not yet shipped (P7 Task 4 not done), this step
will fail with `No module named quaestor.jobs.daily`. Skip with a note and
re-run after P7 ships.

- [ ] **Step 8: `just dev-reset` wipes the DB**

Run: `just dev-reset` (in a separate terminal; this keeps the stack up but wipes the file).
After it finishes, hit `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/accounts` (with the bearer token).
Expected: `200` (empty list) — proves the schema was recreated.

- [ ] **Step 9: `just dev-down` stops cleanly**

Run: `just dev-down`
Expected: `docker compose ps` shows nothing running (or only stopped containers).
Re-run: `just dev`. The DB persists; accounts/transactions from before the down are still there.

- [ ] **Step 10: Final summary**

Append a short note to `docs/superpowers/dev-verification-2026-06-22.md` (create if
absent) capturing the output of each of the nine checks. Then:

```bash
git add docs/superpowers/dev-verification-2026-06-22.md
git commit -m "ops(dev): verification report (9/9 checks passed)"
```

---

## Self-Review

**1. Spec coverage:**
- `docker-compose.override.yml` auto-merged → Task 4. ✓
- Backend Dockerfile `dev` target → Task 1. ✓
- `MCP_RELOAD=1` knob → Task 2. ✓
- `justfile` with 8 recipes → Task 5. ✓
- Per-service `env_file:` from existing `.env.local` → Task 4. ✓
- Frontend selective bind mounts + `frontend_node_modules` volume → Task 4. ✓
- `profiles: ["never"]` for Caddy/Tailscale/Litestream → Task 4. ✓
- `.gitignore` `.dev-data/` → Task 3. ✓
- README Development section → Task 6. ✓
- End-to-end 9-check verification → Task 7. ✓

**2. Placeholder scan:** No "TBD" / "TODO" / "implement later". Every code block is complete. Every command has an expected output. The conditional Step 3 of Task 4 (stub `docker-compose.yml`) is explicit, not a placeholder.

**3. Type consistency:**
- `_uvicorn_kwargs_from_env(env: Mapping[str, str]) -> dict` — used in Task 2 only, no drift.
- `dev-logs-one service` recipe — `{{service}}` template is consistent with `just` syntax throughout the file.
- `quaestor.jobs.daily` referenced as a dependency in Tasks 5 (recipe) and 7 (verification step). If P7 hasn't shipped, the recipe exists but the verification check is conditional. This is acknowledged, not hidden.
- `MCP_RELOAD` flag check matches `quaestor.mcp.server.main()` change in Task 2 and the `environment:` block in Task 4.
- Path `/.dev-data/quaestor.db` (single leading slash, absolute path inside container) is consistent in Tasks 4 and 7.

**4. Open follow-ups (not blockers):**
- The P7 production stack must ship before Task 7's Step 7 (`dev-trigger-scheduler`) works. If P7 is not yet merged, the recipe still exists in `justfile`; the engineer runs P7 first or documents the gap.
- The `api` container's `command:` in the override uses `uv run uvicorn ...`. If the user prefers bare `uvicorn` (PATH is set), the recipe still works because the `dev` Dockerfile's `ENV PATH` includes `/app/.venv/bin`. No code change needed; the long form is explicit.
- Linux users: `just`, Docker, and `docker compose` are all available. The Mac-specific parts (`brew install just`) live only in the README and Task 7's expected output — they do not affect the override or Dockerfile.
