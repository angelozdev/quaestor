# Remove External MCP HTTP Exposure — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the HTTP `/mcp` server and Tailscale sidecar from Quaestor. Keep the in-process MCP bridge used by the chat endpoint. Record the decision in ADR-0025 (supersedes 0011).

**Architecture:** Single coherent change in 4 atomic commits:
1. Refactor — extract `build_mcp()` to `quaestor.mcp.builder` (SOLID, SRP).
2. Delete — drop the HTTP server module + its auth middleware + their tests.
3. Infrastructure — drop the `mcp` and `tailscale` Docker services + `ts-serve.json` + Tailscale env vars.
4. Documentation — write ADR-0025 + update ADR index, deploy runbook, README, OWASP review.

Each commit is independently revertible. After all four, `docker compose` runs the prod stack with `api`, `frontend`, `db`, `caddy`, `scheduler` only.

**Tech Stack:** Python 3.12, `uv`, `pytest`, FastMCP, Docker Compose v2, Postgres 17 (ADR-0024).

**Spec:** `docs/superpowers/specs/2026-07-03-mcp-http-removal-design.md`

## Global Constraints

- Python 3.12 + `uv` (project standard).
- Postgres 17 in Docker (ADR-0024). SQLite branch retained for tests.
- `uv run pytest` is the gate for any Python change.
- `docker compose config` is the gate for any compose change.
- No commented-out code, no dead branches. If external MCP is reintroduced later, it's a new ADR + a new module — do not regress this file.
- Chat endpoint auth posture unchanged: `Authorization: Bearer $APP_TOKEN` required.
- Commit messages follow the project's conventional style: `type(scope): subject`. Examples in this codebase: `feat(mcp): …`, `chore(env): …`, `infra(compose): …`, `docs(adr-NNNN): …`.
- The `adr` skill (project skill) is used to author ADR-0025 — never hand-write ADRs.
- DRY, YAGNI, TDD where applicable, frequent small commits.

## File Structure

### New files
- `backend/src/quaestor/mcp/builder.py` — `build_mcp()` factory function (~25 LOC).
- `backend/tests/mcp/test_builder.py` — sanity test: `build_mcp()` returns a FastMCP with all expected tool names.
- `docs/adr/0025-remove-external-mcp-http.md` — the ADR (via `adr` skill).

### Modified files (per commit)
- Commit 1: `backend/src/quaestor/mcp/server.py` (remove `build_mcp`), `backend/src/quaestor/api/chat.py` (import path), `backend/tests/chat/test_mcp_client.py` (import path).
- Commit 2: deletions only.
- Commit 3: `docker-compose.yml`, `docker-compose.override.yml`, `.env.example`, `.envrc`.
- Commit 4: `docs/adr/README.md`, `docs/runbooks/deploy.md`, `README.md`, `docs/security/owasp-review-2026-06-28.md` (if applicable).

### Deleted files
- `backend/src/quaestor/mcp/server.py` (in commit 2)
- `backend/src/quaestor/mcp/__main__.py` (in commit 2)
- `backend/src/quaestor/mcp/auth.py` (in commit 2)
- `backend/tests/mcp/test_server.py` (in commit 2)
- `backend/tests/mcp/test_auth.py` (in commit 2)
- `backend/tests/mcp/test_reload_env.py` (in commit 2)
- `ts-serve.json` (in commit 3)

### NOT touched
- `backend/src/quaestor/mcp/registry.py` — already declarative; correct shape.
- `backend/src/quaestor/mcp/format.py` — pure helpers.
- `backend/src/quaestor/mcp/tools/*` — tool implementations unchanged.
- `docs/superpowers/specs/*` and `docs/superpowers/plans/*` (historical artifacts).

---

## Task 1: Extract `build_mcp()` to `builder.py` (commit 1 of 4)

**Files:**
- Create: `backend/src/quaestor/mcp/builder.py`
- Create: `backend/tests/mcp/test_builder.py`
- Modify: `backend/src/quaestor/mcp/server.py` (remove `build_mcp` function)
- Modify: `backend/src/quaestor/api/chat.py:31` (import path)
- Modify: `backend/tests/chat/test_mcp_client.py:7,26` (import paths)

**Interfaces:**
- Consumes: `from mcp.server.fastmcp import FastMCP`; `from .registry import register_*_tools` (all of them).
- Produces: `build_mcp() -> FastMCP` (a `FastMCP` named `"Quaestor"` with `json_response=True` and every tool registered).

- [x] **Step 1: Write the failing test**

Create `backend/tests/mcp/test_builder.py`:

```python
from mcp.server.fastmcp import FastMCP

from quaestor.mcp.builder import build_mcp


def test_build_mcp_returns_fastmcp_instance():
    mcp = build_mcp()
    assert isinstance(mcp, FastMCP)


def test_build_mcp_registers_all_expected_tools():
    mcp = build_mcp()
    expected_names = {
        # core reads
        "get_fx_rate",
        "list_transactions",
        # core writes
        "create_transaction",
        "update_transaction",
        # temporal
        "create_recurring",
        "update_recurring",
        "delete_recurring",
        "archive_recurring",
        "restore_recurring",
        "materialize_due",
        # planning
        "create_goal",
        "update_goal",
        "delete_goal",
        "contribute_goal",
        "create_budget",
        "update_budget",
        "delete_budget",
        "assign_budget",
        # masters
        "create_account",
        "update_account",
        "archive_account",
        "create_category",
        "update_category",
        "archive_category",
        "create_category_group",
        "update_category_group",
        "archive_category_group",
        "create_tag",
        "update_tag",
        "archive_tag",
        # settings
        "get_settings",
        "update_settings",
        # reports
        "monthly_report",
    }
    registered = {t.name for t in mcp._tool_manager._tools.values()}
    missing = expected_names - registered
    assert not missing, f"missing tools after build_mcp(): {sorted(missing)}"
```

**Note:** `mcp._tool_manager._tools` is the internal registry FastMCP uses. If the SDK changes internals in a future version, this test will break — that's the regression coverage we want.

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/mcp/test_builder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'quaestor.mcp.builder'`.

- [x] **Step 3: Create `builder.py`**

Create `backend/src/quaestor/mcp/builder.py`:

```python
"""Build the in-process FastMCP instance used by the chat agentic loop.

Single factory function. Tools are declared in `quaestor.mcp.registry` and
registered here. No HTTP, no auth — the chat endpoint (`quaestor.api.chat`)
imports `build_mcp` and passes the result to `MCPClient`, which talks to it
in-memory via `fastmcp.Client`.

If external MCP access is ever reintroduced, a new module (e.g. `http.py`)
should wrap this `FastMCP` with `streamable_http_app()` + auth middleware —
do NOT regress this file.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .registry import (
    register_accounts_tools,
    register_budgets_reads_tools,
    register_category_groups_tools,
    register_categories_tools,
    register_core_tools,
    register_goals_reads_tools,
    register_planning_tools,
    register_recurring_restore_tools,
    register_reports_tools,
    register_settings_tools,
    register_tags_tools,
    register_temporal_tools,
    register_transactions_writes_tools,
)


def build_mcp() -> FastMCP:
    """A FastMCP instance with every Quaestor tool registered.

    The result is consumed in-process by `quaestor.chat.mcp.MCPClient`.
    """
    mcp = FastMCP("Quaestor", json_response=True)
    register_core_tools(mcp)
    register_temporal_tools(mcp)
    register_planning_tools(mcp)
    register_accounts_tools(mcp)
    register_categories_tools(mcp)
    register_category_groups_tools(mcp)
    register_tags_tools(mcp)
    register_transactions_writes_tools(mcp)
    register_settings_tools(mcp)
    register_budgets_reads_tools(mcp)
    register_goals_reads_tools(mcp)
    register_reports_tools(mcp)
    register_recurring_restore_tools(mcp)
    return mcp
```

- [x] **Step 4: Run the new test to verify it passes**

Run: `uv run pytest backend/tests/mcp/test_builder.py -v`
Expected: PASS for both tests. The `expected_names` set matches every `register_*_tools` call above.

- [x] **Step 5: Update `api/chat.py` import**

Edit `backend/src/quaestor/api/chat.py` line 31:

Find:
```python
from ..mcp.server import build_mcp
```

Replace with:
```python
from ..mcp.builder import build_mcp
```

- [x] **Step 6: Update `tests/chat/test_mcp_client.py` imports**

Edit `backend/tests/chat/test_mcp_client.py` line 7 and line 26 (both occurrences):

Find: `from quaestor.mcp.server import build_mcp`
Replace with: `from quaestor.mcp.builder import build_mcp`

(Use `replace_all=true` if there are more than 2; verify by re-reading the file after.)

- [x] **Step 7: Remove `build_mcp` from `server.py`**

Edit `backend/src/quaestor/mcp/server.py`. Delete the `build_mcp` function (the 17-line block from `def build_mcp() -> FastMCP:` through `return mcp`). Leave `build_app`, `_uvicorn_kwargs_from_env`, and `main` intact for now — they are deleted in Task 2.

Also remove the now-unused imports from `server.py`:

- Remove `register_accounts_tools`
- Remove `register_budgets_reads_tools`
- Remove `register_category_groups_tools`
- Remove `register_categories_tools`
- Remove `register_core_tools`
- Remove `register_goals_reads_tools`
- Remove `register_planning_tools`
- Remove `register_recurring_restore_tools`
- Remove `register_reports_tools`
- Remove `register_settings_tools`
- Remove `register_tags_tools`
- Remove `register_temporal_tools`
- Remove `register_transactions_writes_tools`

Keep imports: `import os`, `from collections.abc import Mapping`, `from mcp.server.fastmcp import FastMCP`, `from .. import db`, `from .auth import BearerAuthMiddleware` (still used by `build_app`).

The final file should look like:

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

from mcp.server.fastmcp import FastMCP

from .. import db
from .auth import BearerAuthMiddleware


def build_app():
    """The auth-wrapped streamable-HTTP ASGI app served at `/mcp`.

    `streamable_http_app()` returns a Starlette app whose lifespan runs the MCP
    session manager, so adding our middleware keeps that lifespan intact.
    """
    db.init_db(db.engine)
    mcp = FastMCP("Quaestor", json_response=True)
    app = mcp.streamable_http_app()
    app.add_middleware(BearerAuthMiddleware)
    return app


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

Note: this file is deleted entirely in Task 2. The point of this task is just to extract `build_mcp` without breaking anything.

- [x] **Step 8: Run the full test suite**

Run: `uv run pytest`
Expected: PASS. All existing tests still pass; new `test_builder.py` passes; chat tests pass via the new import path; server tests still pass because `server.py` still has `main`/`build_app`.

- [x] **Step 9: Commit**

```bash
git add backend/src/quaestor/mcp/builder.py \
        backend/tests/mcp/test_builder.py \
        backend/src/quaestor/mcp/server.py \
        backend/src/quaestor/api/chat.py \
        backend/tests/chat/test_mcp_client.py
git commit -m "feat(mcp): extract build_mcp() to builder.py"
```

---

## Task 2: Delete HTTP server module + dead tests (commit 2 of 4)

**Files:**
- Delete: `backend/src/quaestor/mcp/server.py`
- Delete: `backend/src/quaestor/mcp/__main__.py`
- Delete: `backend/src/quaestor/mcp/auth.py`
- Delete: `backend/tests/mcp/test_server.py`
- Delete: `backend/tests/mcp/test_auth.py`
- Delete: `backend/tests/mcp/test_reload_env.py`

**Interfaces:**
- Consumes: nothing (pure deletion).
- Produces: a `backend/src/quaestor/mcp/` tree with only `__init__.py`, `builder.py`, `registry.py`, `format.py`, `tools/`.

- [ ] **Step 1: Verify nothing imports the soon-to-be-deleted modules**

Run:
```bash
git grep -nE "from quaestor\.mcp\.(server|auth|__main__)|from \.\.mcp\.(server|auth)|from \.mcp\.(server|auth)"
```

Expected: no matches. (The previous task already migrated `chat.py` and `test_mcp_client.py`.)

- [ ] **Step 2: Delete the HTTP server module**

```bash
git rm backend/src/quaestor/mcp/server.py
git rm backend/src/quaestor/mcp/__main__.py
git rm backend/src/quaestor/mcp/auth.py
```

- [ ] **Step 3: Delete the dead tests**

```bash
git rm backend/tests/mcp/test_server.py
git rm backend/tests/mcp/test_auth.py
git rm backend/tests/mcp/test_reload_env.py
```

- [ ] **Step 4: Run the full test suite**

Run: `uv run pytest`
Expected: PASS. No test should reference the deleted files (verified in Step 1). The chat tests use the new `builder.build_mcp` import.

- [ ] **Step 5: Verify the final `mcp/` tree**

Run: `find backend/src/quaestor/mcp -type f -name '*.py' | sort`
Expected:
```
backend/src/quaestor/mcp/__init__.py
backend/src/quaestor/mcp/builder.py
backend/src/quaestor/mcp/format.py
backend/src/quaestor/mcp/registry.py
backend/src/quaestor/mcp/tools/__init__.py
backend/src/quaestor/mcp/tools/budgets_reads.py
backend/src/quaestor/mcp/tools/core.py
backend/src/quaestor/mcp/tools/goals_reads.py
backend/src/quaestor/mcp/tools/masters.py
backend/src/quaestor/mcp/tools/planning.py
backend/src/quaestor/mcp/tools/recurring_restore.py
backend/src/quaestor/mcp/tools/reports.py
backend/src/quaestor/mcp/tools/settings.py
backend/src/quaestor/mcp/tools/temporal.py
backend/src/quaestor/mcp/tools/transactions.py
```

- [ ] **Step 6: Commit**

```bash
git commit -m "chore(mcp): remove HTTP server module + dead tests"
```

---

## Task 3: Drop `mcp` and `tailscale` from compose + env (commit 3 of 4)

**Files:**
- Modify: `docker-compose.yml` (remove services + volume)
- Modify: `docker-compose.override.yml` (remove dev mcp + tailscale profile)
- Delete: `ts-serve.json`
- Modify: `.env.example` (remove TS_AUTHKEY + TS_HOSTNAME)
- Modify: `.envrc` (remove TS_AUTHKEY line)

**Interfaces:**
- Consumes: nothing.
- Produces: a compose stack with only `api`, `frontend`, `db`, `caddy`, `scheduler`. No Tailscale. No `/mcp` listener anywhere.

- [ ] **Step 1: Edit `docker-compose.yml`**

Remove the `mcp:` service block (currently lines 37–50, the entire `mcp:` key including its `build`, `command`, `environment`, `expose`, `healthcheck`, `restart`).

Remove the `tailscale:` service block (currently lines 86–101, the entire `tailscale:` key).

Remove the `tailscale-state:` line from the `volumes:` section (currently the last line of `volumes:`).

Verify the resulting `services:` block has exactly: `api`, `db`, `frontend`, `caddy`, `scheduler`. Verify the `volumes:` block has: `quaestor-db-data`, `quaestor-backups`, `caddy-data`, `caddy-config`. (No `tailscale-state`.)

- [ ] **Step 2: Edit `docker-compose.override.yml`**

Remove the dev `mcp:` service block (currently lines 33–51, the entire `mcp:` key).

Remove the `tailscale:` lines under the `caddy:`/`tailscale:` profiles block (currently lines 116–117):
```yaml
  tailscale:
    profiles: ["never"]
```

Leave the `caddy: profiles: ["never"]` line intact.

Verify the resulting override's top-level `services:` block has: `api`, `frontend`, `scheduler`, `db`, `caddy` (with `profiles: ["never"]`).

- [ ] **Step 3: Delete `ts-serve.json`**

```bash
git rm ts-serve.json
```

- [ ] **Step 4: Edit `.env.example`**

Remove the Tailscale block (currently lines 21–25):

```
# --- Tailscale (serves /mcp on the tailnet, ADR-0011) ---
# Reusable auth key from https://login.tailscale.com/admin/settings/keys
TS_AUTHKEY=
# Optional tailnet hostname for the sidecar (default: quaestor-mcp)
TS_HOSTNAME=quaestor-mcp
```

Verify the file no longer mentions `TS_AUTHKEY`, `TS_HOSTNAME`, or Tailscale.

- [ ] **Step 5: Edit `.envrc`**

Remove the line `export TS_AUTHKEY=dev-placeholder-not-used` and its preceding comment line `# Override sets tailscale profiles:["never"] in dev, so this is unused.`

Resulting file:

```bash
# Quaestor dev env (direnv). Run `direnv allow` once.
# Pulls backend secrets from backend/.env.local (single source of truth).
dotenv backend/.env.local
# Compose-only vars not in backend/.env.local:
export DOMAIN=quaestor.local
# Bcrypt prefix needs single quotes (otherwise Compose interpolates $2b).
export FRONTEND_PASSWORD_HASH='$2b$12$dummyhashplaceholderdontuseinprod000000000000000000'
```

- [ ] **Step 6: Validate prod compose**

Run: `docker compose config`
Expected: exit 0. The output mentions only `api`, `db`, `frontend`, `caddy`, `scheduler`. No warnings about undefined services or volumes.

- [ ] **Step 7: Validate dev compose (override merges)**

Run: `docker compose -f docker-compose.yml -f docker-compose.override.yml config`
Expected: exit 0. The `mcp` service should NOT appear (it was removed from both files). The `caddy` service should appear with `profiles: ["never"]`.

- [ ] **Step 8: Verify no stragglers**

Run:
```bash
git grep -nE "TS_AUTHKEY|TS_HOSTNAME|ts-serve|tailscale|tailscale-state" \
    docker-compose.yml docker-compose.override.yml .env.example .envrc
```

Expected: no matches.

- [ ] **Step 9: Commit**

```bash
git add docker-compose.yml docker-compose.override.yml .env.example .envrc
git commit -m "infra(compose): drop mcp and tailscale services; drop ts-serve.json"
```

---

## Task 4: Write ADR-0025 + update runbook/README/OWASP (commit 4 of 4)

**Files:**
- Create: `docs/adr/0025-remove-external-mcp-http.md` (via `adr` skill)
- Modify: `docs/adr/README.md` (index)
- Modify: `docs/runbooks/deploy.md`
- Modify: `README.md` (line 8)
- Modify: `docs/security/owasp-review-2026-06-28.md` (only if it references `/mcp` or Tailscale as attack surface)

**Interfaces:**
- Consumes: nothing.
- Produces: an ADR in `docs/adr/`, an updated index, a deploy runbook without Tailscale/MCP sections, a README without Tailscale, and (if applicable) an updated OWASP review.

- [ ] **Step 1: Author ADR-0025 using the `adr` skill**

Run (in the project root):

```bash
uv run .claude/skills/adr/scripts/new_adr.py "Remove external MCP HTTP exposure"
```

The skill creates a new ADR file (numbered `0025-`) with a template. Open the file and fill it in with this content (matching the spec):

```markdown
# 0025 — Remove External MCP HTTP Exposure (chat-only MCP)

- **Status:** accepted
- **Date:** 2026-07-03
- **Supersedes:** 0011

## Context

Quaestor is single-user. The MCP surface had two consumers: an HTTP streamable-MCP server (`mcp` service on `:9000`, published over Tailscale by the `tailscale` sidecar) for external clients like Claude Code, and an in-process bridge inside the `api` service used by the chat endpoint. The user does not use any external MCP client; the chat covers every interaction they actually have with the tools. The HTTP server + Tailscale sidecar = extra service, extra dependency, extra attack surface, zero user value.

## Decision

Remove the HTTP MCP server and the `tailscale` sidecar. The in-process MCP bridge used by the chat endpoint is the only remaining MCP consumer. Code structure:

- `backend/src/quaestor/mcp/builder.py` (NEW) — `build_mcp()` factory function, single responsibility (Factory pattern, SRP).
- `backend/src/quaestor/mcp/{server,__main__,auth}.py` — DELETED. No commented-out branches, no "remote path" scaffolding. If external MCP access is ever reintroduced, it's a new module + a new ADR.
- `backend/src/quaestor/mcp/{registry,format,tools/*}.py` — unchanged. Tools continue to be invoked in-process by the chat.
- `docker-compose.yml`, `docker-compose.override.yml` — drop `mcp` and `tailscale` services + `tailscale-state` volume.
- `ts-serve.json` — DELETED.
- `.env.example`, `.envrc` — drop `TS_AUTHKEY` and `TS_HOSTNAME`.

## Consequences

- External MCP clients (Claude Code over Tailscale) lose access. If the user wants this back, it's a new ADR.
- One fewer service in the prod stack. One fewer dependency (Tailscale).
- Smaller attack surface: no externally reachable MCP listener, no bearer auth middleware.
- Chat endpoint auth posture unchanged: still requires `Authorization: Bearer $APP_TOKEN`. Defense in depth remains.
- `build_mcp()` lives in a clean module (Factory pattern) — chat depends on an abstraction, not on concrete tool implementations.

## Related

- Spec: `docs/superpowers/specs/2026-07-03-mcp-http-removal-design.md`.
- ADR-0014 — chat endpoint with LiteLLM and in-memory MCP bridge (kept; this ADR confirms it as the only MCP path).
- ADR-0011 (superseded) — original MCP-only-over-Tailscale decision.
```

- [ ] **Step 2: Update the ADR index**

Edit `docs/adr/README.md`. In the index table:

- Add a row for `0025` with title "Remove external MCP HTTP exposure" and status "accepted" date "2026-07-03".
- Flip the row for `0011` to read: status `superseded by 0025`.

- [ ] **Step 3: Update the deploy runbook**

Edit `docs/runbooks/deploy.md`. Remove or rewrite every Tailscale/MCP reference:

- In **First boot**, remove any line referencing `TS_AUTHKEY` from the env-fill list (step 3).
- Remove **step 7** ("Smoke-test `/api/chat` from a tailnet client (ADR-0014)...").
- Remove **step 8** entirely ("Verify the tailnet surface...").
- Remove the entire **Connect Claude Code (ADR-0011)** section.
- Remove the trailing note about `ts-serve.json` and `TS_HOSTNAME`.

Keep all other sections (Caddy, DB, scheduler, backup link) intact.

- [ ] **Step 4: Update `README.md`**

Edit `README.md` line 8. Find:

```
Local dev runs four services (`api`, `mcp`, `frontend`, `scheduler`) in Docker
```

Replace `four` with `three` and remove `mcp` from the list:

```
Local dev runs three services (`api`, `frontend`, `scheduler`) in Docker
```

Also edit the same paragraph's "No TLS, no Caddy, no Tailscale, no Litestream." to remove Tailscale:

```
Local dev runs three services (`api`, `frontend`, `scheduler`) in Docker
with hot reload. No TLS, no Caddy, no Litestream.
```

Also remove any other MCP-specific dev URL (the README's "URLs" section references `:9000/mcp` — remove that bullet).

- [ ] **Step 5: Update OWASP review if applicable**

Open `docs/security/owasp-review-2026-06-28.md`. Run:

```bash
git grep -nE "tailscale|TS_AUTH|/mcp|MCP HTTP" docs/security/owasp-review-2026-06-28.md
```

If there are matches: edit the file to remove `/mcp` as an attack surface and remove Tailscale as a mitigation. Replace with a one-liner noting that MCP tools are reachable only through the chat endpoint (in-process, requires `APP_TOKEN`).

If there are no matches: skip this step.

- [ ] **Step 6: Final grep across non-historical docs**

Run:
```bash
git grep -nE "TS_AUTHKEY|TS_HOSTNAME|ts-serve\.json|tailscale" \
    docs/runbooks/ README.md docs/adr/ docs/security/
```

Expected: only matches inside ADR-0025 itself (which records the removal) and the flipped row in the ADR index. No live references in `deploy.md`, `README.md`, or OWASP.

- [ ] **Step 7: Final verification across the whole tree**

Run:
```bash
git grep -nE "python -m quaestor\.mcp|quaestor\.mcp\.server|quaestor\.mcp\.auth|quaestor\.mcp\.__main__" \
    -- ':!docs/superpowers/specs/*' ':!docs/superpowers/plans/*'
```

Expected: no matches outside historical specs/plans (which are intentionally untouched) and the ADR-0025 record.

- [ ] **Step 8: Commit**

```bash
git add docs/adr/0025-remove-external-mcp-http.md \
        docs/adr/README.md \
        docs/runbooks/deploy.md \
        README.md
git commit -m "docs(adr-0025): remove external MCP HTTP exposure (supersedes 0011)"
```

---

## Self-Review

**1. Spec coverage:**
- "MCP tools remain accessible only via in-process bridge used by chat" → covered (Tasks 1, 2).
- "Remove HTTP server code, no commented-out branches" → covered (Task 2 deletes wholesale).
- "Move `build_mcp()` to `builder.py` for SRP" → covered (Task 1).
- "Drop mcp + tailscale from compose" → covered (Task 3).
- "Drop ts-serve.json" → covered (Task 3).
- "Drop TS_AUTHKEY/TS_HOSTNAME from .env.example + .envrc" → covered (Task 3).
- "Delete dead tests" → covered (Task 2).
- "Update runbook, README, OWASP" → covered (Task 4).
- "Write ADR-0025 superseding 0011" → covered (Task 4).
- "Update ADR index" → covered (Task 4).
- "Four atomic commits" → covered (one commit per task).
- All "no-objetivos" respected (no OAuth on chat, no multi-tenant, no subprocess, no registry refactor, no historical-doc rewriting).

**2. Placeholder scan:** No "TBD", no "implement later", no "similar to Task N", no vague "add appropriate handling". All code blocks are complete. All commands have expected output.

**3. Type consistency:** `build_mcp()` signature is `() -> FastMCP` consistently across Tasks 1 (definition) and the spec. No naming drift. No consumer references a deleted function by mistake.

**4. Risk:** Task 1's `expected_names` set in `test_builder.py` is hand-curated. If the actual list of registered tools differs (e.g. an extra tool I missed), the test will fail. This is intentional regression coverage — adjust the set to match the real FastMCP tool registry if needed. The Step 4 "expected: PASS" assumes the set is accurate; if it isn't, that's caught immediately, not at the end.