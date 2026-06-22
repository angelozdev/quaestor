# Quaestor — Restore From Backup (P7, ADR-0012)

The DB is replicated continuously by Litestream. A backup is not a backup
until restore is tested.

## Litestream (preferred)

```bash
# On the VPS, stop the stack so the DB isn't being written:
docker compose down

# Restore the latest replica to the volume mount point:
docker run --rm -v quaestor_quaestor-data:/data litestream/litestream:latest \
  restore -o /data/quaestor.db "$LITESTREAM_BUCKET"

# Bring the stack back up:
docker compose up -d
```

Verify by opening the frontend and checking that accounts/transactions are
present.

## sqlite3 .backup (fallback)

If Litestream isn't configured, the `api` container writes a daily
`/data/backups/quaestor-YYYY-MM-DD.db`. To restore:

```bash
docker compose down
docker compose run --rm -v quaestor_quaestor-data:/data api \
  cp /data/backups/quaestor-YYYY-MM-DD.db /data/quaestor.db
docker compose up -d
```

## Things that do NOT count as a backup

- `cp quaestor.db somewhere` while the DB is hot: loses WAL data.
- `docker cp` of a running container's DB: same risk.

If you only have a raw `cp` of the file from before WAL was enabled
(pre-2026-06-22), the data is intact but inconsistent with the new WAL
configuration. Start fresh with WAL disabled (`PRAGMA journal_mode=DELETE`)
and re-enable after a clean checkpoint.