"""
Quaestor container entrypoint: wait for DB → migrate → start uvicorn.
Runs as `python -m quaestor` from the container CMD (ADR-0026).
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from typing import Final

import psycopg
import uvicorn
from sqlalchemy import create_engine

LOG_PREFIX: Final = "[entrypoint]"
DB_WAIT_MAX_ATTEMPTS: Final = 30
DB_WAIT_INTERVAL_S: Final = 2.0


def log(msg: str) -> None:
    print(f"{LOG_PREFIX} {msg}", flush=True)


def _probe_sqlite(url: str) -> None:
    create_engine(url).connect().close()


def _probe_postgres(url: str) -> None:
    psycopg.connect(url, connect_timeout=3).close()


def wait_for_db(url: str) -> None:
    last_exc: Exception | None = None
    for attempt in range(1, DB_WAIT_MAX_ATTEMPTS + 1):
        try:
            if url.startswith("sqlite"):
                _probe_sqlite(url)
            else:
                _probe_postgres(url)
            log(f"DB reachable (attempt {attempt}/{DB_WAIT_MAX_ATTEMPTS})")
            return
        except Exception as exc:
            last_exc = exc
            if attempt >= DB_WAIT_MAX_ATTEMPTS:
                break
            time.sleep(DB_WAIT_INTERVAL_S)
    log(f"DB unreachable after {DB_WAIT_MAX_ATTEMPTS} attempts: {last_exc}")
    sys.exit(1)


def run_migrations() -> None:
    log("running alembic upgrade head")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=False, cwd="/app",
    )
    if result.returncode != 0:
        log(f"alembic upgrade failed (rc={result.returncode}); aborting")
        sys.exit(result.returncode)


async def _run_async() -> None:
    config = uvicorn.Config(
        "quaestor.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["/app/src"],
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


def main() -> None:
    url = os.environ.get("QUAESTOR_DB", "sqlite:///:memory:")
    wait_for_db(url)
    run_migrations()
    log("starting uvicorn")
    asyncio.run(_run_async())


if __name__ == "__main__":
    main()
