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
