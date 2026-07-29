# 0030. Local Postgres container replaces Render as the production database

- **Status:** accepted
- **Date:** 2026-07-28
- **Deciders:** Angelo
- **Supersedes:** [0026 — Local-only posture](./0026-local-only-posture.md) (database-location clause only; see scope note below)
- **Superseded by:** —

## Context and problem statement

ADR-0026 made Quaestor local-only with one exception: the database lived on
remote Render Postgres ("the database is the only remote concern"). That
exception has hurt twice. Every SELECT is a network round-trip to Oregon, which
forced the bounded-query redesign of ADR-0028 and still leaves the app
noticeably slower than local. And the user's real financial data sits with a
third party they must trust and manage, while having no local copy at all —
the 2026-07-28 portfolio review found zero local backups. The user decided:
production data comes home. Which topology serves a single-user local app whose
owner wants speed and an off-host backup?

**Scope note.** This ADR supersedes only 0026's database-location decision
(remote Render as the production DB and the "database is the only remote
concern" driver). Everything else in 0026 remains in force as decided there:
local-only posture, no public deployment, the two-service compose, the
`__main__.py` wait-migrate-serve entrypoint, the in-process asyncio scheduler,
and env-file profile selection.

## Decision drivers

- **Latency.** Remote Postgres made every SELECT a network round-trip (the
  driver behind ADR-0028's multi-second hangs). A local DB removes the class of
  problem instead of managing it.
- **Data ownership.** The user wants their financial data on their own machine,
  with a copy they control.
- **Backup at last.** The local-only posture "owns no backups" (0026, accepted
  cost). Moving the data home must come with a backup story, not remove Render's.
- **Live database must not sync-corrupt.** iCloud Drive syncs and evicts files;
  a live DB (SQLite or Postgres data dir) inside it risks corruption. Backups
  go to iCloud; the live store must not.
- **Keep the bootstrap contract.** `docker compose up` still waits, migrates,
  serves (0026's entrypoint), regardless of where the DB lives.

## Considered options

1. **Postgres 18 container in the compose stack, named volume, pg_dump backups
   to iCloud Drive.**
2. **Keep Render as production** (status quo), add scheduled pg_dump to iCloud.
3. **Promote the local SQLite profile to production** and migrate the Render
   data into it.
4. **Live database file inside iCloud Drive** (what "use the iCloud copy as
   production" would literally mean).

## Decision outcome

Chosen option: **Postgres 18 container + named volume + pg_dump backups to
iCloud**, because it satisfies every driver: queries become local (latency
class eliminated, ADR-0028's bounded read path stays as defense in depth), the
data lives on the user's machine, the dump-to-iCloud recipe gives an off-host
copy, and the engine stays Postgres so ADR-0024 (schema, migrations,
concurrency) is untouched.

Concrete shape:

- **Compose.** A `db` service (`postgres:18`, matching the 18.4 dump origin) in
  `docker-compose.yml` under compose profile `pg`, data in named volume
  `quaestor-pg-data`, port bound to `127.0.0.1:5432` for host tooling,
  `pg_isready` healthcheck. The api's existing wait-retry entrypoint handles
  startup ordering — no `depends_on` needed.
- **Env profile.** `backend/.env.local.postgres` (gitignored) +
  `backend/.env.local.postgres.example` (committed): `QUAESTOR_DB`
  pointing at `db:5432`, `POSTGRES_*` for the container.
- **Recipes.** `just dev-prod` runs the stack against the local Postgres
  (production posture); `just backup` dumps the local DB to
  `~/Library/Mobile Documents/com~apple~CloudDocs/QuaestorBackups/` with a
  dated filename. `dev-local` (SQLite sandbox) and `dev-real` (Render) remain.
- **Seed.** One-time `pg_restore` of the 2026-07-28 Render dump into the fresh
  volume, before first app boot (the dump carries `alembic_version`, so the
  entrypoint's `alembic upgrade head` is a no-op).
- **Render.** Untouched, kept as a warm standby with the pre-cutover data.
  Retiring it is the user's later call, made only after local production has
  proven itself and backups have accumulated.

### Pros and cons of the options

**Postgres container + named volume + iCloud dumps (chosen)**
- Good, because queries are local: the ADR-0028 latency driver disappears.
- Good, because ADR-0024 stands unchanged — same engine, migrations, ENUMs,
  concurrency story; pytest stays host-side in-memory SQLite.
- Good, because the named volume follows 0026's proven no-`down -v` safety
  pattern for precious data.
- Bad, because the Mac is now the single live copy between dumps — a dead disk
  loses the delta since the last backup (mitigated by frequent `just backup`;
  automation tracked on the roadmap).
- Bad, because Postgres in Docker must be running for the app to work; OrbStack
  becomes a hard runtime dependency of production.

**Keep Render + scheduled backups**
- Good, because a managed-ish remote survives local disk failure.
- Bad, because the latency tax on every query stays forever.
- Bad, because it keeps the trust/ownership concern the user wants gone.

**Promote SQLite to production**
- Good, because it is the simplest possible topology (one file, no container).
- Bad, because it reverses ADR-0024 (Postgres was chosen for real concurrency
  and migration semantics) and needs a Postgres→SQLite data conversion with
  ENUM/type loss — migration effort with a capability downgrade.

**Live DB file inside iCloud Drive**
- Good, because it is what the user first pictured — zero extra moving parts.
- Bad, because iCloud sync + eviction against a live database file is a known
  corruption pattern; rejected outright. Snapshots in iCloud, never the live store.

## Consequences

- Good: every read path gets faster for free; ADR-0028's bounded queries stay
  as a correctness/robustness property rather than a survival requirement.
- Good: the user finally has backups (first verified dump 2026-07-28) and owns
  the live store.
- Bad / cost: backup discipline is now load-bearing. `just backup` must be run
  (or automated) regularly; the roadmap tracks automation.
- Bad / cost: two "real data" locations exist during the transition (local =
  production, Render = frozen standby). Anything written to Render after the
  cutover is lost to local — the user must stop using `dev-real` for writes.
- Bad / cost: doc drift to clean: CHARTER.md §2, `.engineer/manifest.yml`
  (`validation.prod`), README, and the stale claim in 0026 that
  `.dev-data/quaestor.db` holds real data (the user confirmed real data had
  already moved to Render before this ADR).
- Unchanged: ADR-0024 (Postgres engine), ADR-0025 (no external MCP), 0026's
  non-database clauses, ADR-0028 (bounded read path).

## Confirmation

- `just dev-prod` boots the stack against the local container; the app serves
  real data at `http://localhost:3000` with row counts matching the Render dump.
- `just backup` produces a dated dump in the iCloud folder; `pg_restore --list`
  reads it back.
- `docs/adr/README.md`: 0030 accepted; 0026 marked "superseded by 0030
  (database clause)".
- Code review checklist: no recipe or doc reintroduces Render as the default
  write target; `.env.local.remote` survives only as the standby profile.
