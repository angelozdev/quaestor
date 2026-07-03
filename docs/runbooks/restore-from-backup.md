# Quaestor — Restore From Backup (ADR-0024)

The DB is dumped daily by the `scheduler` service into the
`quaestor-backups` Docker volume (ADR-0013 + ADR-0024). A backup is not a
backup until restore is tested.

## Where the dumps live

The `quaestor-backups` volume is a Docker named volume. Its host
mountpoint is:

```bash
docker volume inspect quaestor-backups --format '{{ .Mountpoint }}'
# → /var/lib/docker/volumes/quaestor_backups/_data
```

Files inside the volume are named `quaestor-YYYY-MM-DD.dump` (one per
day, FIFO retention at 7). Older dumps are pruned automatically by the
`pg_dump` block in `backend/scripts/cron.sh`.

## Inspect a backup without restoring

```bash
docker run --rm -v quaestor_backups:/backups postgres:17-alpine \
  pg_restore -l /backups/quaestor-YYYY-MM-DD.dump
```

This lists every table, index, type, and constraint in the dump. Use it
to verify a backup before relying on it.

## Restore from a daily `pg_dump`

```bash
# 1. Stop the stack so the DB isn't being written:
docker compose down

# 2. Drop the db-data volume so Postgres starts empty:
docker compose down -v quaestor-db-data

# 3. Start ONLY the db service so we can restore into it:
docker compose up -d db
#    Wait for the healthcheck: docker compose ps shows db (healthy).

# 4. Run pg_restore into the running db:
docker compose exec -T db pg_restore \
  -U quaestor -d quaestor --clean --if-exists \
  /backups/quaestor-YYYY-MM-DD.dump
#    NOTE: --clean and --if-exists are idempotent. If the target DB is
#    empty (which it is post `down -v`), they are no-ops.

# 5. Bring the rest of the stack up:
docker compose up -d
```

Verify by opening the frontend and confirming accounts/transactions are
present.

## Things that do NOT count as a backup

- Copying Postgres' data directory directly from `/var/lib/postgresql/`
  while the DB is running: race with WAL writes; partial or corrupt
  data.
- Saving raw SQL emitted by `psql -c "SELECT ..."` and assuming it is a
  backup — it is a snapshot of one query, not the database.
- WAL segments without a base backup: useless on their own.
- An untested `pg_dump` is no backup. The "done" criterion (spec
  §Verification) requires a real `pg_restore -l` walk-through at least
  once after each deploy.

## Related ADRs

- ADR-0024 (Postgres replaces SQLite) — supersedes ADR-0012.
- ADR-0013 (daily scheduler is a thin sidecar) — owns the cron that
  produces the dumps.
