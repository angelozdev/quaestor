# Remove External MCP HTTP Exposure — Single-User, Chat-Only

**Date:** 2026-07-03
**Status:** design (pending approval)
**ADR:** docs/adr/0025-remove-external-mcp-http.md (proposed, supersedes ADR-0011)
**Depends on:** ADR-0014 (chat endpoint with LiteLLM and in-memory MCP bridge)

---

## Context

Quaestor is a single-user personal-finance app. Today the MCP surface is reachable two ways:

1. **HTTP streamable-MCP** at `/mcp`, served by the `mcp` Docker service on `:9000`. The `tailscale` sidecar publishes it over the user's tailnet (ADR-0011), so Claude Code (or any other MCP client) on the user's machines can call tools directly.
2. **In-process bridge** inside the `api` service. The chat endpoint (`/api/chat`) uses `fastmcp.Client` with a `FastMCP` instance passed in memory — no TCP, no HTTP (ADR-0014). The frontend drives this; tools are resolved for the chat's agentic loop.

The user has now decided that path 1 is not needed:

- They do not use Claude Code or any other external MCP client against Quaestor.
- The chat feature (path 2) covers every interaction they actually have with the tools.
- The `tailscale` sidecar exists only to serve `/mcp` over the tailnet.
- External MCP surface = extra service + extra dependency + extra attack surface, for zero user value.

This spec removes path 1 entirely. Path 2 (in-process bridge for chat) is the only remaining MCP consumer. ADR-0011 is superseded.

### Decisions log (locked during brainstorming, 2026-07-03)

| Fork | Choice |
|---|---|
| Scope of cleanup | **B (Completo)** — close every loose end (dead tests, dev override, OWASP, README) but leave historical `docs/superpowers/{plans,specs}` untouched |
| Quality bar | Clean architecture, SOLID, no over-engineering — `build_mcp` extracted to its own module for SRP |
| `build_mcp()` location | New `backend/src/quaestor/mcp/builder.py` (Factory pattern, single responsibility) |
| Auth posture on chat | Unchanged — chat still requires `Authorization: Bearer $APP_TOKEN` (defense in depth, not network exposure) |
| HTTP server code | **Deleted** entirely (no commented-out branches, no "remote path" scaffolding) |
| External `/mcp` HTTP | Removed from `docker-compose.yml` and `docker-compose.override.yml` |
| `tailscale` sidecar | Removed from `docker-compose.yml` |
| `TS_AUTHKEY` / `TS_HOSTNAME` | Removed from `.env.example` |
| Commit strategy | Four atomic commits (refactor → code delete → compose drop → ADR+docs) |

---

## Architecture (after)

### Code: `backend/src/quaestor/mcp/`

```
backend/src/quaestor/mcp/
├── __init__.py
├── builder.py        # NEW: build_mcp() factory (≈25 LOC)
├── registry.py       # register_*_tools() — tool declarations
├── format.py         # markdown formatting helpers
└── tools/            # individual tool implementations
    ├── __init__.py
    ├── core.py
    ├── temporal.py
    ├── planning.py
    ├── ...
```

**Deleted**: `server.py`, `__main__.py`, `auth.py` (HTTP transport + bearer middleware + uvicorn entrypoint).

### Code: chat side (one import change)

- `backend/src/quaestor/api/chat.py` line 31: `from ..mcp.server import build_mcp` → `from ..mcp.builder import build_mcp`.
- `chat/service.py` and `chat/mcp/client.py` already use `fastmcp.Client` directly with an in-memory `FastMCP` — no changes needed.

### Docker: prod + dev

```
┌──────────────────────────────────────────────────┐
│ docker-compose.yml + docker-compose.override.yml │
├──────────────────────────────────────────────────┤
│                                                  │
│  ┌──────────┐    ┌──────────┐    ┌────────────┐  │
│  │   api    │    │ frontend │    │   caddy    │  │
│  │ (FastAPI │    │ (Next.js │    │ (TLS+proxy)│  │
│  │  + MCP   │    │  :3000)  │    │  80/443    │  │
│  │  bridge  │    └──────────┘    └─────┬──────┘  │
│  │  in-proc)│                          │         │
│  └────┬─────┘                          │         │
│       │            ┌──────────┐        │         │
│       └───────────►│ scheduler│        │         │
│       │            │ (daily)  │        │         │
│       │            └────┬─────┘        │         │
│       │                 │              │         │
│       ▼                 ▼              │         │
│     ┌─────────┐                          │       │
│     │   db    │                          │       │
│     │ pg 17   │                          │       │
│     └─────────┘                          │       │
│                                           │       │
│  REMOVED: mcp service, tailscale service, │       │
│            tailscale-state volume        │       │
└──────────────────────────────────────────────────┘
```

Only `caddy` publishes host ports. `api` and `frontend` use `expose:` (internal Docker network only). `db`, `scheduler` are on the internal network. No external MCP listener exists anywhere.

---

## File changes

| File | Action | Notes |
|---|---|---|
| `backend/src/quaestor/mcp/builder.py` | **NEW** | `build_mcp()` extracted from old `server.py`. ~25 LOC. One factory function, no HTTP, no auth. |
| `backend/src/quaestor/mcp/server.py` | DELETE | Was 90 LOC (HTTP server + bearer middleware + uvicorn entrypoint). |
| `backend/src/quaestor/mcp/__main__.py` | DELETE | Was 5 LOC (`python -m quaestor.mcp` entrypoint). |
| `backend/src/quaestor/mcp/auth.py` | DELETE | Was HTTP `BearerAuthMiddleware` + `token_ok()`. |
| `backend/src/quaestor/api/chat.py` | EDIT | Change one import: `..mcp.server.build_mcp` → `..mcp.builder.build_mcp`. |
| `backend/tests/chat/test_mcp_client.py` | EDIT | Change two imports to `quaestor.mcp.builder`. |
| `backend/tests/mcp/test_server.py` | DELETE | Tested HTTP transport (no longer exists). |
| `backend/tests/mcp/test_auth.py` | DELETE | Tested bearer middleware (no longer exists). |
| `backend/tests/mcp/test_reload_env.py` | DELETE | Tested uvicorn reload knobs (no longer exists). |
| `docker-compose.yml` | EDIT | Remove `mcp` service (lines 37–50), `tailscale` service (lines 86–101), `tailscale-state` volume (line 122). |
| `docker-compose.override.yml` | EDIT | Remove the dev `mcp` service override; remove `tailscale: profiles: ["never"]` line. |
| `ts-serve.json` | DELETE | Tailscale `serve` config; nothing to serve now. |
| `.env.example` | EDIT | Remove `TS_AUTHKEY` and `TS_HOSTNAME` (lines 21–25). |
| `.envrc` | EDIT | Remove `export TS_AUTHKEY=dev-placeholder-not-used` and its preceding comment about Tailscale dev override. |
| `docs/adr/0025-remove-external-mcp-http.md` | **NEW** | `accepted`, **supersedes 0011**. |
| `docs/adr/README.md` | EDIT | Add 0025 row; flip 0011 status to "superseded by 0025". |
| `docs/runbooks/deploy.md` | EDIT | Remove "Connect Claude Code" section; remove Tailscale steps from `.env` fill list; drop steps 8 (tailnet surface). |
| `README.md` | EDIT | Line 8 dev-mode preamble: `"No TLS, no Caddy, no Tailscale, no Litestream."` → `"No TLS, no Caddy, no Litestream."` (Tailscale no longer in the stack at all.) |
| `docs/security/owasp-review-2026-06-28.md` | EDIT | If it enumerates `/mcp` as an attack surface or Tailscale as a mitigation, update accordingly. |

**NOT changed**:
- `backend/src/quaestor/mcp/registry.py` — already the right shape (declarative tool registration).
- `backend/src/quaestor/mcp/format.py` — pure helpers.
- `backend/src/quaestor/mcp/tools/*` — all tool implementations stay.
- `docs/superpowers/specs/*` and `docs/superpowers/plans/*` — historical artifacts of each phase. The ADR is the source of truth for "what we do now"; historical docs are the record of "what we decided in that phase". A future reader who needs "current posture" reads the ADR; one who needs "what we did in P7" reads the historical P7 spec. Mixing them loses both.

---

## `builder.py` shape

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
    # ... all register_*_tools calls
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

The exact list of `register_*` calls matches the current `server.py` line-for-line (verbatim copy). The shape is preserved exactly to keep `git blame` on individual tool additions readable.

---

## Tests

**Kept** (unchanged or with trivial import update):
- `backend/tests/mcp/test_registry.py` — registry behavior (now imports `builder.build_mcp`).
- `backend/tests/mcp/test_format.py` — markdown formatting.
- All `backend/tests/mcp/test_*tools*.py` — exercise individual tool logic, no transport.
- `backend/tests/chat/test_mcp_client.py` — chat integration (import update only).

**Deleted** (test the removed HTTP transport):
- `backend/tests/mcp/test_server.py`
- `backend/tests/mcp/test_auth.py`
- `backend/tests/mcp/test_reload_env.py`

**Optional new test** (recommended):
- `backend/tests/mcp/test_builder.py` — sanity check that `build_mcp()` returns a `FastMCP` with all expected tool names registered (uses `await mcp.list_tools()` via `fastmcp.Client`). Cheap regression coverage against accidental tool drops.

---

## Failure modes / rollback

| Failure | Detection | Recovery |
|---|---|---|
| `build_mcp()` import breaks chat | `pytest` red on `tests/chat/test_mcp_client.py` | Re-fix the import; refactor commit (#1) is the natural revert boundary. |
| Compose YAML invalid | `docker compose config` errors | Re-fix or revert commit #3. |
| `docker compose.override.yml` still references removed services | `docker compose up` warns about orphan overrides | Re-fix or revert commit #3. |
| VPS deploy after merge breaks | `docker compose ps` shows restart loop | `git revert <merge>` on VPS, `docker compose up -d --build` to rebuild. |
| User wants external MCP back | Discovered post-merge | New ADR (re-introduce `http.py` + bearer middleware + Tailscale). Do NOT regress `builder.py`. |

Each of the four commits is independently revertible. They can be merged in order or as one PR.

---

## Verification (done criteria)

- `uv run pytest` green (full suite, including `test_builder.py` if added).
- `docker compose config` exits 0; output mentions only `api`, `frontend`, `db`, `caddy`, `scheduler`.
- `docker compose -f docker-compose.yml -f docker-compose.override.yml config` exits 0 (dev override still merges cleanly).
- `grep -r "TS_AUTHKEY\|TS_HOSTNAME" --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.next --exclude-dir=__pycache__` returns nothing outside historical docs.
- `grep -rn "python -m quaestor.mcp" backend/ docs/runbooks/ docker-compose*.yml Caddyfile README.md .env.example` returns nothing.
- `git grep "from quaestor.mcp.server"` returns nothing (all imports migrated).
- Local `docker compose up -d --build` brings up `api`, `frontend`, `db`, `caddy`, `scheduler` healthy; chat endpoint resolves MCP tools end-to-end via a smoke test (e.g. one tool call through the chat UI).
- VPS redeploy with `git pull && docker compose up -d --build` succeeds; existing data and chat feature work; `https://$DOMAIN/mcp` continues to 404 (Caddy never routed it; nothing changes externally).

---

## No-objetivos

- Re-introducing OAuth / API-key auth on the chat endpoint (chat already requires `APP_TOKEN`).
- Multi-tenant MCP (Quaestor is single-user by ADR-0010).
- Subprocess-based MCP (current in-process bridge is correct per ADR-0014).
- Refactoring `registry.py` (already declarative).
- Adding observability (metrics/tracing) to the MCP bridge — defer until operational need.
- Updating historical `docs/superpowers/{plans,specs}` to match new state — they are historical record.

## Related

- ADR-0011 (superseded) — original MCP-only-over-Tailscale decision.
- ADR-0014 — chat endpoint with LiteLLM and in-memory MCP bridge (kept; this change confirms it as the only MCP path).
- ADR-0024 — recent Postgres migration (orthogonal; demonstrates the precedent of removing a service + writing an ADR).
- `docs/superpowers/specs/2026-06-16-P7-deployment-design.md` — historical P7 design; documents the previous Tailscale/MCP posture. Stays as-is.