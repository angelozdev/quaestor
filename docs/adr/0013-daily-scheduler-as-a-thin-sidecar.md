# 0013 — Daily Scheduler Is a Reused-Image Sidecar with a Cron Loop

- **Status:** accepted
- **Date:** 2026-06-22
- **Superseded by:** [0026 — Local-only posture](./0026-local-only-posture.md)

## Context
Three jobs must run every day without human action: FX rate fetch (ADR-011),
`materialize_due(today)` (ADR-020), and `ensure_month_closed(today)` (ADR-017).
All three are idempotent and exist as plain Python functions today; nothing
calls them on a clock.

## Decision
Add a `scheduler` service to `docker-compose.yml` that uses the same image as
`api` (Python + uv + the project source) and runs `backend/scripts/cron.sh`.
The script loops every 24h, calling `python -m quaestor.jobs.daily`, which in
turn calls the three jobs in order. The container is `restart: unless-stopped`
so a host reboot restarts it.

The `materialize_due` and `ensure_month_closed` calls are already idempotent
by design (ADR-017/020); the FX fetch is idempotent because `set_fx_rate`
upserts on date. A missed day self-heals on the next run.

The scheduler shares the same SQLite volume (`quaestor-data`) as `api`/`mcp`
so it can write. WAL + `busy_timeout` (per ADR-0010 + spec) serialize writes
without conflict.

## Consequences
- Scheduler downtime of N days is self-healing — the next run materializes the
  missed occurrences and closes the missed months in one pass.
- FX API downtime does NOT block other jobs: `run_daily` swallows FX errors
  and logs them (ADR-011).
- No new third-party scheduler (Celery beat, APScheduler in-process) — a plain
  shell loop is enough for single-user daily cadence.

## Related
- ADR-0010, ADR-0011, ADR-0012.
- ADR-011, ADR-017, ADR-020 (existing decisions).
- Spec: `docs/superpowers/specs/2026-06-16-P7-deployment-design.md` §Scheduler.
