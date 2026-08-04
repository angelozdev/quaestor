# Quaestor — Engineering Charter

Signed off by Angelo on 2026-07-28 (DAE onboarding, Checkpoint 0).
§2 amended 2026-07-29 — ADR-0030 alignment (cleanup C6), signed off by Angelo.
§4 amended 2026-08-04 — feature 003 collapses envelopes and goals into the fund
(product ADR-037, technical ADR-0043/0044), signed off by Angelo.

## 1. Methodology

- **DAE (Disciplined Agentic Engineering)** with full ATDD coverage as the goal:
  every feature — existing and new — ends up with `feature.md`, `acs.md`,
  `spec.md` (+ IR) and passing generated acceptance tests.
- Single-repo monorepo. `methodology_root` = repo root. Feature folders live in
  `features/`; project state in `.engineer/`.
- Architecturally-significant decisions are recorded as ADRs in `docs/adr/`
  (the `adr` skill); product decisions in `docs/decisions/product-decisions.md`.
  ADRs are respected — supersede, never silently contradict (see `CLAUDE.md`).

## 2. Architecture

- **Posture: local-only** (ADR-0026; DB-location clause superseded by
  ADR-0030). Docker Compose — `api` (FastAPI + uvicorn; `python -m quaestor`
  waits for the DB, runs `alembic upgrade head`, serves; an asyncio scheduler
  task in the FastAPI lifespan runs the daily job), `frontend` (Next.js dev
  server) and `db` (Postgres 18, compose profile `pg`, named volume
  `quaestor_pg_data`, only under `just dev-prod`). Nothing remote: production
  data lives in the local Postgres container; backups via `just backup` →
  dated pg_dump to iCloud Drive. Render Postgres is a frozen standby (never
  write); `.dev-data/quaestor.db` SQLite is a dev sandbox with no real data.
- **Backend layering:** `api/` (routers, auth, CSRF) → `services/` (use-cases)
  → `domain/` (SQLModel models, value objects, pure logic) → `db.py`.
  Jobs in `jobs/`, migrations in `migrations/` (Alembic).
- **MCP surface:** in-process FastMCP tools (`mcp/`) with REST parity
  (ADR-0006/0009) and a read/write-safe/write-destructive tier policy
  (ADR-0020). No external MCP exposure (ADR-0025).
- **Chat:** LiteLLM provider + in-memory MCP bridge, SSE streaming
  (ADR-0014/0016/0017/0018/0022); tool output sanitized before LLM/UI.
- **Frontend:** Next.js App Router; app-agnostic design system in `ui/`
  (ADR-0002); TanStack Query + TanStack Form + Zod v4 (ADR-0008);
  `QueryBoundary` as the uniform async-state contract (ADR-0029); URL query
  params as the single source of truth for list filters (ADR-0027); BFF proxy
  route handler for `/api/*`.

## 3. Conventions

- English for all code and identifiers (ADR-0001). UI copy is Spanish.
- Backend: Python ≥3.12, `uv`, pytest (host-side, in-memory SQLite).
- Frontend: pnpm only — never npm/yarn (ADR-0003); Biome + Lefthook
  (ADR-0007); vitest with colocated `*.test.ts(x)`.
- Conventional Commits.
- Dark-first theming with elevation tokens (ADR-0004).
- Soft-delete + restore as the uniform lifecycle for masters (ADR-0005).
- Dev workflow via `just` recipes (`dev-local`, `dev-real`, `dev-test`, …).

## 4. Scope

- **In:** personal finance for a single user, local-only. Differentiators:
  the **fund** — one noun replacing envelopes and goals, where a funding rule
  *is* the monthly number and no monthly ritual exists (product ADR-037,
  amending ADR-002/016 and superseding ADR-003/006) — and an agent-native MCP
  layer over an owned schema (product ADR-001).
- **Out:** multi-tenant, public deployment, TLS termination, mobile apps.

## 5. Agent team

Default roles for the DAE pipeline:

- **architect** — plans the implementation, owns ADR proposals.
- **implementer** — writes the code, test-first.
- **acceptance-tester** — writes/maintains GWT specs and the generated
  acceptance tests (ATDD pipeline).
- **reviewer** — reviews before merge (standards + spec fidelity).

## 6. Quality stance

- **Strict gate, effective now:** nothing merges without passing backend AND
  frontend tests for the touched surface. New features are born through the
  ATDD pipeline (acceptance tests before implementation).
- Current baseline: backend 91 `test_*.py` files; frontend 33 colocated vitest
  files; **no e2e layer** — acceptance-test coverage is built retroactively per
  feature via the consolidation backlog.
- Existing-feature ATDD coverage is tracked in `.engineer/consolidation.md`
  and paid down feature by feature.

## 7. Autonomy stance

- **Medium, with data gates.** Validation surface: local stack (`just
  dev-local`, tcp :8000/:3000 health) + host-side pytest + vitest. No staging,
  no monitoring, no feature flags (local-only posture) — the ceiling is the
  local test surface.
- The agent may autonomously: implement, write/run tests, refactor, update
  docs and DAE artifacts on feature branches.
- **Human required for:** schema migrations touching real data, any
  destructive operation on `.dev-data/`, merges to `main`, and anything
  touching `dev-real` / the remote Postgres (Render).
- Remote/cloud agent dispatch: not yet enabled (`remote.ready: false`) — see
  `.engineer/manifest.yml` for the pending one-time setup checklist.
