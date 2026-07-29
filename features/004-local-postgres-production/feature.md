---
title: "Local Postgres container replaces Render as the production database"
slug: local-postgres-production
number: 004
status: done
autonomy_level: medium
branch: main
area: platform
owner: angelo
assignee: local
tracker_ref: local
roadmap_ref: local-postgres-production
relevant_adrs: [0024, 0026, 0028, 0030]
created: 2026-07-28
intake: discuss
---

# Local Postgres container replaces Render as the production database

## Outcome

The user's production data lives in a local Postgres 18 container (named
volume `quaestor_pg_data`), seeded from the verified 2026-07-28 Render dump;
`just dev-prod` runs the full stack against it and `just backup` writes dated
dumps to iCloud Drive. Render stays untouched as a frozen standby.

## Scope

- ADR-0030 (accepted; supersedes ADR-0026's database-location clause).
- `docker-compose.yml`: `db` service (postgres:18, compose profile `pg`,
  volume mounted at `/var/lib/postgresql` per the 18-image layout).
- `backend/.env.local.postgres` (gitignored) + committed `.example`.
- `justfile`: `dev-prod`, `dev-prod-down`, `backup`.
- One-time `pg_restore` seed + verification (row counts match Render exactly;
  API serves restored data; safe-to-spend in ~11 ms vs seconds on Render).

Out: backup automation (roadmap `backup-automation`), Render retirement
(user's later call), charter/README doc alignment (cleanup C6).

## Source links

- `docs/adr/0030-local-postgres-container-replaces-render-as-the-production-database.md`.
- Decision emerged from the 2026-07-28 portfolio-review discuss session
  (backup-restore drop → "no local copy" finding → user chose option A).

## Code co-locations

- `docker-compose.yml`, `justfile`, `backend/.env.local.postgres.example`.
- Runtime (unchanged, per ADR-0026): `backend/src/quaestor/__main__.py`
  wait-migrate-serve entrypoint.

## Notes

Implemented interactively with the user 2026-07-28 (data operations are
human-gated by charter §7; the user directed the cutover). Changes are
uncommitted on `main` pending the user's commit decision. Post-cutover rule:
`dev-real` (Render) is read-only standby — writes there are lost to local.
