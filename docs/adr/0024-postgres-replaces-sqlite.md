# 0024. Postgres replaces SQLite

- **Status:** proposed
- **Date:** 2026-07-03
- **Deciders:** Angelo
- **Supersedes:** [0012 — Litestream Replicates the SQLite WAL Continuously](./0012-litestream-for-continuous-backup.md)
- **Superseded by:** —

## Context and problem statement

Quaestor's storage is currently a single SQLite file with Litestream shipping
the WAL to S3 (ADR-0012). The app has not shipped yet, so this is the cheapest
window to revisit the storage substrate before any real data accumulates.

Three things have changed since ADR-0012 was accepted. The chat endpoint
(ADR-0014) now wants to write transactions and FX rates concurrently with the
REST API and the scheduler, and SQLite's single-writer model serializes those
writes. The schema is also growing — soft-delete columns, audit fields, recurring
projection tables, FX-rate snapshots — and the project would benefit from a real
migration tool, typed columns, and foreign-key enforcement instead of ad-hoc
`ALTER TABLE` plus Python-level invariants. Finally, because the app is still
greenfield, the cost of switching now is roughly the cost of switching later,
minus the data-migration gymnastics that come with a live database.

On the backup side, two simplifications apply: there is no S3 bucket yet (and
we don't want to introduce one just for backups), and a worst-case loss window
of up to 24 hours is acceptable for a personal-finance app that is still in
pre-launch.

## Decision drivers

- **Concurrency:** the chat endpoint, REST API, and scheduler need to write
  in parallel without serializing on a single SQLite writer lock.
- **Schema discipline:** we want Alembic migrations, real foreign keys, typed
  columns, and partial indexes instead of growing the SQLite schema ad hoc.
- **Greenfield window:** no production data yet, so switching storage is cheap
  now and expensive later.
- **Simplicity:** no S3 dependency; backups stay local for now.
- **Acceptable loss:** up to 24 hours of writes is tolerable in the worst case.

## Considered options

1. **Postgres 17 in Docker Compose (chosen).** Run Postgres 17 as another
   container alongside `api`, `mcp`, `frontend`, and `scheduler`. Same
   single-host topology as today, no new infra service.
2. **S3 + WAL-G base backup + WAL archive.** Keep Postgres but ship WAL
   continuously to S3 the way Litestream ships the SQLite WAL. Closer to the
   existing posture but reintroduces the S3 dependency we want to avoid.
3. **Keep SQLite.** Stay on the current stack. No migration, no schema
   rewrite, no concurrency gain.
4. **Managed Postgres (RDS / Neon).** Outsource the database to a managed
   service with built-in backups, point-in-time recovery, and HA. Strong
   long-term posture, but premature for a single-user app on a single VPS.

## Decision outcome

Chosen option: **Postgres 17 in Docker Compose**, because it satisfies all
three primary drivers (concurrency, schema discipline, greenfield) while
honoring the two simplifications (no S3, ≤24h loss window acceptable). Managed
Postgres is the natural next step if the app ever outgrows a single VPS, but
introducing it now would add a network dependency and a billing surface
without paying for itself at current scale.

Concrete shape:

- **Engine:** Postgres 17, run as a service in `docker-compose.yml` on the
  same host as the rest of the stack.
- **Migrations:** Alembic (already in the Python ecosystem and idiomatic for
  SQLAlchemy), replacing the current SQLite `ALTER TABLE` sequence.
- **Backups:** a daily `pg_dump -Fc` cron inside the `api` container writes
  `/data/backups/quaestor-YYYY-MM-DD.dump` with 7-day retention. No S3, no
  off-host replication. A missed day means up to 24h of unbacked writes,
  which is acceptable for this app.
- **Restore:** `pg_restore -d quaestor <dump>` against the running container.

### Pros and cons of the options

**Postgres 17 in Docker Compose**
- Good, because real concurrency, real FKs, real migrations, real types.
- Good, because no new infra surface — it's just another container.
- Good, because Alembic gives us reversible, reviewable schema changes.
- Bad, because we now operate a Postgres instance (vacuum, logs, tuning).
- Bad, because daily `pg_dump` means up to 24h loss in the worst case.

**S3 + WAL-G**
- Good, because continuous WAL shipping keeps the loss window near zero.
- Bad, because it requires an S3 bucket and its credentials as secrets.
- Bad, because it contradicts the "no S3" simplification.

**Keep SQLite**
- Good, because no migration work and the existing tooling already works.
- Bad, because concurrency, schema discipline, and the greenfield opportunity
  are all unresolved.

**Managed Postgres (RDS / Neon)**
- Good, because point-in-time recovery, HA, and managed backups come for free.
- Good, because it scales past a single VPS without re-architecting.
- Bad, because it adds a network hop, a billing surface, and a vendor
  dependency that is overkill for a single-user app.

## Consequences

- Good: chat, REST, and scheduler writes no longer serialize on one writer.
- Good: Alembic replaces ad-hoc `ALTER TABLE` with reversible migrations.
- Good: real foreign keys and partial indexes catch schema bugs at write
  time instead of in application code.
- Good: daily `pg_dump` keeps backups local and simple — no S3, no extra
  secrets.
- Bad / cost: ADR-0012 (Litestream) is fully superseded; the Litestream
  sidecar and its config go away.
- Bad / cost: we now own Postgres operations (vacuum, logs, restart on
  crash) instead of a single-file SQLite.
- Bad / cost: a missed daily backup means up to 24h of writes lost.

## Confirmation

- ADR-0012 is marked `superseded by 0024` in `docs/adr/README.md` and in
  its own frontmatter.
- The migration plan's downstream tasks (compose update, Alembic setup,
  `pg_dump` cron, restore drill) reference this ADR as the source of truth.
- The test suite continues to run against SQLite in-memory on the host for
  speed; only the running stack talks to Postgres.

## Supersedes

- `0012-litestream-for-continuous-backup.md`

## Related

- ADR-0010 — Deployment posture (defines the single-host topology this ADR
  fits inside).
- ADR-0011 — MCP only over Tailscale (network surface around the database).
- ADR-0013 — Daily scheduler as a thin sidecar (shares the `docker-compose`
  topology this ADR extends).