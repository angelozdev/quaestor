# 0012 — Litestream Replicates the SQLite WAL Continuously

- **Status:** accepted
- **Date:** 2026-06-22

## Context
The single SQLite file is the source of truth for all of Quaestor (accounts,
transactions, budgets, goals, FX rates, settings). Loss = total loss. A daily
snapshot is too coarse: a missed day means up to 24h of unbacked writes.

## Decision
Use Litestream in `replicate` mode as a sidecar, continuously shipping the
WAL to an S3-compatible bucket (AWS S3, Cloudflare R2, Backblaze B2). Restore
is a single command: `litestream restore -o quaestor.db <bucket>`.

Fallback (no bucket configured): a daily `sqlite3 .backup` cron inside the
`api` container writes `/data/backups/quaestor-YYYY-MM-DD.db` with 7-day
retention. `sqlite3 .backup` checkpoints and is safe to run while the DB is
hot.

## Consequences
- Raw `cp` of `quaestor.db` is FORBIDDEN (loses WAL data). The spec is
  explicit: only Litestream or `sqlite3 .backup` are acceptable.
- An untested backup is no backup. The "done" criterion (spec §Testing) requires
  a real restore to a clean directory.
- The bucket credentials are secrets; they live in `.env`, never in git.

## Related
- ADR-0010 (deployment posture), P0 (db.py).
- Spec: `docs/superpowers/specs/2026-06-16-P7-deployment-design.md` §Backups.
