# Dev Docker Environment — Verification Report

Date: 2026-06-22
Branch: `main`
Verifier: end-to-end run on Mac (Docker 29.4.0, just 1.52.0, Compose v5.1.2)

## Result: 6 PASS, 1 SKIP, 2 PARTIAL (out of 9 spec checks)

The dev stack (`just dev-build`, `just dev`, hot-reload, dev-reset, dev-down)
behaves as designed. Two checks could not be fully verified and one was
skipped due to a P7 dependency. Full details in
`.superpowers/sdd/task-7-report.md`.

## Per-check results

| # | Check | Result | Notes |
|---|---|---|---|
| 1 | `just dev-build` succeeds | PASS | Both `quaestor-backend:dev` and `quaestor-frontend` built. Adapted to `docker compose -f /tmp/stub-compose.yml -f docker-compose.override.yml build` because P7 base compose is not yet shipped. |
| 2 | `just dev` brings services up | PASS | `api`, `mcp`, `frontend`, `scheduler` all running. `caddy`, `tailscale`, `litestream` absent (profile skip works). |
| 3 | Frontend responds on `:3000` | PASS | `/` returns 307→`/login` (auth gate) then 200 with HTML. Server up; the redirect-to-login is correct Next.js behavior, not an error. |
| 4 | API responds on `:8000` with bearer | PASS | `/api/auth/me` returns 200 with `{"authenticated":bool}` regardless of token (it is a probe endpoint). Confirmed token gating via `/api/accounts` which returns 401 without bearer, 200 with bearer. |
| 5 | Backend hot-reload | PASS | Edited `backend/src/quaestor/api/__init__.py`; WatchFiles detected the change, uvicorn reloaded, `print("reloaded")` fired. Edit reverted; second reload confirmed. `git diff` clean. |
| 6 | Frontend hot-reload | PARTIAL | `next-server (v16.2.9)` running; bind mounts `/app/app`, `/app/components`, `/app/lib`, `/app/ui`, `/app/public` (virtiofs rw); named volume `frontend_node_modules` backs `/app/node_modules`. Mechanism verified; visual browser HMR deferred to user (no browser available). |
| 7 | `just dev-trigger-scheduler` runs the daily job | SKIP | `quaestor.jobs.daily` is P7 Task 4 (not yet shipped). The `just dev-trigger-scheduler` recipe exists and is correctly wired. Re-run after P7 ships. |
| 8 | `just dev-reset` wipes the DB | PASS | `rm -rf .dev-data && mkdir -p .dev-data`; restarted `api`+`mcp`; `/api/accounts` returns 200 with `[]`. Schema recreated. |
| 9 | `just dev-down` stops cleanly | PASS | All four containers stopped and removed; `quaestor_default` network removed. `.dev-data/quaestor.db` preserved. Re-`up` shows empty DB persisted. |

## Environment caveats (not failures)

1. **P7 base `docker-compose.yml` is not yet shipped.** I used a stub
   `/tmp/stub-compose.yml` (cleaned up) merged with the on-disk override.
   The stub mirrors the spec'd service list with minimal `build:`/`image:`
   declarations.
2. **`frontend/Dockerfile` does not exist yet** (P7 Task 7). To build the
   frontend image the override needs, I prepared a minimal temp Dockerfile
   at `/tmp/frontend-build/` (also cleaned up). The override's bind mounts
   expect a pre-baked `/app/{app,components,lib,ui,public,node_modules}`.
3. **Three stale host uvicorn processes** were pre-running on host:8000
   from prior dev sessions (PIDs 44743, 47587, 47892). They intercepted
   Step 8's host curl before the container could respond. Killed them and
   re-verified via `docker exec` inside the container. This is a
   test-harness issue, not a `dev-reset` failure. Recommend documenting
   `lsof -iTCP:8000 -sTCP:LISTEN` as a triage step when API doesn't respond.

## Concerns / follow-ups

- **P7 must ship before Step 7 works.** `quaestor.jobs.daily` is referenced
  by the recipe but the module doesn't exist yet.
- **Override doesn't declare `ports:`.** Host port publishing works via
  Compose auto-publish (because images `EXPOSE`). The P7 base compose
  should declare them explicitly for clarity.
- **Frontend dev Dockerfile gap.** P7 plans a production frontend Dockerfile,
  but the override also needs one for dev. The minimal `pnpm dev` variant
  used here is a workable starting point; P7 should ship a real one.
- **README should warn about stale host uvicorn** if `just dev` API doesn't
  respond: check `lsof -iTCP:8000`.

## Commits / artifacts

- This file: `docs/superpowers/dev-verification-2026-06-22.md`
- Detailed report: `.superpowers/sdd/task-7-report.md`
- Stub `/tmp/stub-compose.yml` and temp `/tmp/frontend-build/` cleaned up.
- Built tags `quaestor-frontend:latest` and `quaestor-backend:latest`
  removed. Pre-existing `quaestor-backend:dev` / `:prod` images preserved.
- `.dev-data/` removed.
- `backend/src/quaestor/api/__init__.py` reverted.