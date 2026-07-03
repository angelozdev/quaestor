#!/usr/bin/env bash
# Daily scheduler loop (ADR-0013). Reuses the api image's Python + source.
#
# Env:
#   RUN_ON_BOOT       "1" (default) runs once immediately, then loops.
#                     "0" waits INTERVAL_SECONDS before the first run.
#   INTERVAL_SECONDS  seconds between runs (default 86400 = 24h).
#   LOG_PREFIX        log line prefix (default "scheduler").
set -euo pipefail

INTERVAL_SECONDS="${INTERVAL_SECONDS:-86400}"
RUN_ON_BOOT="${RUN_ON_BOOT:-1}"
LOG_PREFIX="${LOG_PREFIX:-scheduler}"

cd /app

log() { echo "$(date -u +%FT%TZ) ${LOG_PREFIX} $*"; }

trap 'log "received SIGTERM/SIGINT, exiting"; exit 0' SIGTERM SIGINT

run_once() {
  log "running daily job"
  if uv run python -m quaestor.jobs.daily; then
    log "daily job ok"
  else
    rc=$?
    log "daily job failed (rc=${rc}); will retry next interval"
  fi
  dump_postgres
}

# Daily Postgres backup (ADR-0024). Runs after the daily job so a
# job-side failure doesn't block the dump. FIFO-pruned to 7 days.
# pg_dump is non-blocking under MVCC, so it does NOT interfere with
# the running api/mcp. Missing pg_dump (e.g. un-rebuilt image) is a
# soft skip — the loop must keep ticking.
dump_postgres() {
  if ! command -v pg_dump > /dev/null 2>&1; then
    log "pg_dump skipped: not on PATH"
    return 0
  fi

  if [ -z "${PGPASSWORD:-}" ] && [ -n "${QUAESTOR_DB:-}" ]; then
    PGPASSWORD=$(printf '%s' "${QUAESTOR_DB}" | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')
    export PGPASSWORD
  fi

  local TS
  TS=$(date -u +%F)

  log "pg_dump -> /backups/quaestor-${TS}.dump"
  if pg_dump -U quaestor -h db -Fc quaestor > "/backups/quaestor-${TS}.dump"; then
    log "pg_dump ok"
  else
    rc=$?
    log "pg_dump failed (rc=${rc}); will retry next interval"
  fi

  ls -1tr /backups/quaestor-*.dump 2>/dev/null | head -n -7 | xargs -r rm -- 2>/dev/null || true
}

if [ "${RUN_ON_BOOT}" = "1" ]; then
  run_once
fi

while true; do
  log "sleeping ${INTERVAL_SECONDS}s"
  sleep "${INTERVAL_SECONDS}" &
  wait $!
  run_once
done
