"""
In-process daily scheduler (ADR-0026, supersedes ADR-0013).

Runs as an asyncio task inside the api's FastAPI lifespan.

Behavior:
- RUN_ON_BOOT=1 (default): run the daily job once at startup, then every INTERVAL_S.
- RUN_ON_BOOT=0: wait INTERVAL_S before the first run.
- A job failure is logged but does not kill the loop (self-healing).
- Lifespan shutdown cancels the task cleanly (SIGTERM from `docker stop`).
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Final

from quaestor.jobs import daily as daily_module

log = logging.getLogger(__name__)

INTERVAL_S: Final = 24 * 60 * 60  # 24 hours


async def _run_once() -> None:
    started = datetime.now(timezone.utc)
    log.info("scheduler: starting daily job at %s", started.isoformat())
    try:
        await asyncio.to_thread(daily_module.main)
        log.info("scheduler: daily job ok")
    except Exception:
        log.exception("scheduler: daily job failed; will retry next interval")


async def run_forever() -> None:
    run_on_boot = os.environ.get("RUN_ON_BOOT", "1") == "1"
    if run_on_boot:
        await _run_once()
    while True:
        log.info("scheduler: sleeping %ds until next run", INTERVAL_S)
        try:
            await asyncio.sleep(INTERVAL_S)
        except asyncio.CancelledError:
            log.info("scheduler: cancelled during sleep; exiting")
            raise
        await _run_once()
