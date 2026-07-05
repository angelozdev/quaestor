# Orphan Docker Resource Cleanup (2026-07-05)

## What was removed

From the previous (`<2026-07-04`) compose project that pre-dated the
local-only posture (ADR-0026):

| Resource | Type | Source service |
|---|---|---|
| `quaestor-db-1` | container (postgres:17-alpine, 41h old) | old `db` service |
| `quaestor-mcp-1` | container (image `b141d46ae0e9`, 41h old) | old `mcp` service (already removed per ADR-0025) |
| `quaestor-scheduler-1` | container (image `b141d46ae0e9`, 41h old) | old `scheduler` sidecar |
| `quaestor_default` | bridge network (no containers attached) | old compose project network |

## What was intentionally NOT removed

- `quaestor_frontend_node_modules` — still used by the current stack.
- `.dev-data/quaestor.db` — user's live financial data.
- Volumes from the old compose (`quaestor_quaestor-backups`,
  `quaestor_quaestor-data`, `quaestor_quaestor-db-data`) — left in place;
  no current references but not strictly orphans either. Clean up in a
  separate change if/when you confirm they hold nothing valuable.

## Verification after cleanup

- `docker ps -a --filter "name=quaestor-"` → empty.
- `docker network ls --filter "name=quaestor"` → empty.
- `sqlite3 .dev-data/quaestor.db "SELECT COUNT(*) FROM account;"` → `6`
  (data preserved end-to-end).

## When to use this runbook

Whenever the Docker Desktop shows a separate "quaestor" project with
`db`, `mcp`, or `scheduler` containers older than the current stack
(those services no longer exist in the local-only compose).

## Re-running the cleanup

```bash
docker rm -f quaestor-db-1 quaestor-mcp-1 quaestor-scheduler-1
docker network rm quaestor_default
```