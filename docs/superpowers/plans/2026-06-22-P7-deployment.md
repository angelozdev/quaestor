# P7 Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package the existing Quaestor backend + frontend into a self-hosted Docker Compose deployment: a public HTTPS front door (Caddy), a token-protected REST API, an MCP server reachable only over Tailscale, a daily scheduler that drives FX fetch + `materialize_due` + `ensure_month_closed`, and continuous Litestream backups of the shared SQLite DB.

**Architecture:** Single-host Docker Compose. Six services (`api`, `mcp`, `frontend`, `caddy`, `tailscale`, `scheduler`) plus a `litestream` sidecar. `api` and `mcp` share the SQLite file on a named volume (WAL enabled, single-writer invariant). Only Caddy publishes `80`/`443` to the host; `/mcp` is served exclusively on the tailnet by the Tailscale sidecar and never touches the public internet. The scheduler is a thin Python process that reuses the `api` image, runs `cron.sh`, and exits (idempotent jobs: re-running produces no change).

**Tech Stack:** Python 3.12 + uv (backend), Node 22 + pnpm + Next.js 16 standalone (frontend), Docker + Docker Compose v2, Caddy 2, Tailscale (`tailscale/tailscale`), Litestream, httpx (FX HTTP), Debian-slim base images, GitHub Actions not used (manual deploy).

## Global Constraints

These apply to **every** task. Exact values copied from the spec and ADRs.

- **Architecture (ADR-013):** `/mcp` is served **only** over the tailnet. It MUST NOT appear in `Caddyfile`, MUST NOT have a `ports:` mapping on `mcp`, and MUST NOT be reachable from the public domain. Caddy routes only `/api/*` and the frontend.
- **Single-writer SQLite (P0 + spec):** `quaestor.db` lives on a Docker named volume shared by `api` and `mcp`. **WAL must be enabled** via `PRAGMA journal_mode=WAL` set on every connection; `busy_timeout=5000` (ms) prevents "database is locked" when both writers race. The DB file and its `-wal`/`-shm` siblings must live on the same volume at the same path — never split them.
- **Auth (P1/P2, ADR-013):** `api` and `mcp` both validate `Authorization: Bearer ${APP_TOKEN}`. Caddy does **not** terminate auth — it only routes. The frontend holds a session cookie after the user enters the frontend password (validated against `FRONTEND_PASSWORD_HASH`) and the server-side proxy attaches `APP_TOKEN` to backend calls.
- **Backups (spec):** Litestream continuously replicates the WAL to an S3/R2/Backblaze bucket. **Fallback:** if no bucket is configured, a daily `sqlite3 .backup` cron inside the `api` container writes to `/data/backups/` with 7-day retention. Restore must be tested, not just configured.
- **Idempotent scheduler (ADR-011/017/020):** `set_fx_rate` is upsert (one row per date), `materialize_due` is keyed by `(recurring_id, due_date)`, `ensure_month_closed` is idempotent because the registered hooks are. A re-run on the same day is a no-op; a missed day self-heals on the next run.
- **Env vars (spec):** `.env` is git-ignored. `.env.example` is committed with empty values. Variables: `DOMAIN`, `APP_TOKEN`, `FRONTEND_PASSWORD_HASH`, `DB_PATH`, `TS_AUTHKEY`, `FX_API_URL`, `FX_API_KEY`, `LITESTREAM_BUCKET`, `LITESTREAM_ACCESS_KEY_ID`, `LITESTREAM_SECRET_ACCESS_KEY`, `LITESTREAM_ENDPOINT`.
- **P7 does not touch money, sign, or `posted`/`planned`** (spec §Integration). It packages what P0–P6 produce and adds ops concerns (WAL pragma, scheduler CLI, backup wiring). No new domain entities, no new migrations, no new business logic.
- **Language:** all code, identifiers, comments, and strings in English (ADR-0001).
- **Decisions:** ship ADRs `0010-deployment-posture`, `0011-mcp-only-over-tailscale`, `0012-litestream-for-continuous-backup` BEFORE writing the corresponding code, so the design is locked first (CLAUDE.md). The spec's references to ADR-011/013/017/020 stay valid.

---

## File Structure

**Create (repo root):**
- `docker-compose.yml` — services `api`, `mcp`, `frontend`, `caddy`, `tailscale`, `scheduler`, plus named volumes.
- `Caddyfile` — one site (`{$DOMAIN}`), routes `/api/*` to `api:8000`, catch-all to `frontend:3000`. No `/mcp`.
- `ts-serve.json` — `tailscale serve` config: `https://quaestor-mcp:443/mcp → http://mcp:9000/mcp`.
- `litestream.yml` — replica config pointing at `${LITESTREAM_BUCKET}`.
- `.env.example` — committed template, empty values for every secret.

**Create (backend):**
- `backend/Dockerfile` — `python:3.12-slim`, install `uv`, copy `src/`, default CMD = api.
- `backend/scripts/cron.sh` — daily loop that calls `python -m quaestor.jobs.daily`.
- `backend/scripts/backup.sh` — daily `sqlite3 .backup` fallback.
- `backend/src/quaestor/jobs/__init__.py`
- `backend/src/quaestor/jobs/fx_fetch.py` — provider-agnostic USD→COP fetch + `set_fx_rate`.
- `backend/src/quaestor/jobs/daily.py` — orchestration: fx → materialize_due → ensure_month_closed.
- `backend/tests/jobs/test_fx_fetch.py`, `test_daily.py`

**Create (frontend):**
- `frontend/Dockerfile` — multi-stage: deps → build (`pnpm build`) → runtime (`node:22-slim`, copy `.next/standalone` + `static`).
- `frontend/.dockerignore` — exclude `node_modules`, `.next`, `.env*`, tests.

**Modify (backend):**
- `backend/src/quaestor/db.py` — add `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000` to every new SQLite connection via an event listener.
- `backend/tests/conftest.py` — assert the WAL pragma is set in test sessions (in-memory DBs may not honor WAL; document the policy).
- `backend/.gitignore` — already excludes `quaestor.db*`; no change.

**Modify (repo root):**
- `.gitignore` — add `.env`, `quaestor.db*` (already), `ts-serve.local.json`, `litestream.state`, `backend/.docker_cache/`, `frontend/.next/`, `frontend/.docker_cache/`.

**Create (docs):**
- `docs/adr/0010-deployment-posture.md`
- `docs/adr/0011-mcp-only-over-tailscale.md`
- `docs/adr/0012-litestream-for-continuous-backup.md`
- `docs/adr/0013-daily-scheduler-as-a-thin-sidecar.md`
- `docs/runbooks/deploy.md` — first boot, deploy, restore, connect Claude Code.
- `docs/runbooks/restore-from-backup.md` — Litestream and sqlite3 .backup restore procedures.

**Conventions for every command in this plan:** run from the path stated in the task. Test runner is `uv run pytest` (backend) and `pnpm test` (frontend). Docker is the only deploy surface — no host-level Python/Node install required.

---

### Task 1: ADRs 0010/0011/0012/0013 — Deployment decisions

Decisions first (CLAUDE.md). Each ADR is short, references the spec, and locks one operational choice.

**Files:**
- Create: `docs/adr/0010-deployment-posture.md`
- Create: `docs/adr/0011-mcp-only-over-tailscale.md`
- Create: `docs/adr/0012-litestream-for-continuous-backup.md`
- Create: `docs/adr/0013-daily-scheduler-as-a-thin-sidecar.md`

**Interfaces:** None. Pure docs.

- [ ] **Step 1: Write ADR 0010 — Deployment posture**

Create `docs/adr/0010-deployment-posture.md`:

```markdown
# 0010 — Self-Hosted Single-VPS Deployment with Docker Compose

- **Status:** accepted
- **Date:** 2026-06-22

## Context
Quaestor is a personal-finance app for a single user. The spec (P7) requires a
publicly reachable frontend + REST API over HTTPS, an MCP endpoint that must
NOT be public, a daily scheduler that drives the temporal engine, and
continuous backups of the SQLite DB.

## Decision
Deploy on a single VPS (single-user, single-host, no HA). One `docker-compose.yml`
runs six services + one sidecar. Only Caddy publishes ports (`80`/`443`); all
other services use Docker's internal network. The deploy workflow is
`git pull && docker compose up -d --build`.

## Consequences
- No CI/CD, no multi-node, no HA. Out of scope.
- `docker compose down -v` deletes the named volume and loses data — Litestream
  is the safety net.
- Future migration to Postgres (or multi-node) is a connection-string swap per
  the general design.

## Related
- Spec: `docs/superpowers/specs/2026-06-16-P7-deployment-design.md`.
```

- [ ] **Step 2: Write ADR 0011 — MCP only over Tailscale**

Create `docs/adr/0011-mcp-only-over-tailscale.md`:

```markdown
# 0011 — MCP Endpoint Lives Only on the Tailnet

- **Status:** accepted
- **Date:** 2026-06-22

## Context
The MCP server lets agents (Claude Code, others) drive every backend action —
recording expenses, editing categories, moving money. Exposing `/mcp` on the
public internet with only a bearer token is too thin a defense: a leaked
`APP_TOKEN` would be enough to compromise the whole account.

## Decision
`/mcp` is served exclusively by the Tailscale sidecar on the user's private
network. The `mcp` Docker service has NO `ports:` mapping. The Tailscale
sidecar runs `tailscale serve` on its tailnet IP, proxying HTTPS to the `mcp`
container's internal `:9000`. The Caddyfile does NOT route `/mcp`. The public
domain responds 404 on `/mcp`.

This is defense-in-depth: the endpoint doesn't even exist outside the tailnet
(no attack surface), and the bearer token is a second layer for tailnet
members.

## Consequences
- Cloud MCP clients (claude.ai web) cannot reach the endpoint. The spec
  acknowledges this trade-off; revisit only if a real need arises.
- The user's machines must be on the tailnet to use Claude Code against Quaestor.
- If Tailscale is down, `/mcp` is unreachable — fails closed, not open.

## Related
- ADR-0010 (deployment posture), ADR-0006 (HTTP/MCP parity).
- Spec: `docs/superpowers/specs/2026-06-16-P7-deployment-design.md` §HTTPS and
  network, §Auth, §Connect Claude Code.
```

- [ ] **Step 3: Write ADR 0012 — Litestream for continuous backup**

Create `docs/adr/0012-litestream-for-continuous-backup.md`:

```markdown
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
```

- [ ] **Step 4: Write ADR 0013 — Daily scheduler as a thin sidecar**

Create `docs/adr/0013-daily-scheduler-as-a-thin-sidecar.md`:

```markdown
# 0013 — Daily Scheduler Is a Reused-Image Sidecar with a Cron Loop

- **Status:** accepted
- **Date:** 2026-06-22

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
```

- [ ] **Step 5: Commit**

```bash
git add docs/adr/0010-deployment-posture.md \
        docs/adr/0011-mcp-only-over-tailscale.md \
        docs/adr/0012-litestream-for-continuous-backup.md \
        docs/adr/0013-daily-scheduler-as-a-thin-sidecar.md
git commit -m "docs(adr): deployment ADRs (0010-0013) for P7"
```

---

### Task 2: WAL pragma + busy_timeout in db.py

The spec assumes P0 set WAL — it didn't. Add it now because every subsequent task (scheduler, litestream) depends on the writer-safety guarantees.

**Files:**
- Modify: `backend/src/quaestor/db.py`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_db_wal.py`

**Interfaces:**
- Consumes: existing `make_engine(url, memory)` and `init_db()`.
- Produces: every new SQLite connection sets `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000` via an `event.listens_for(Engine, "connect")` handler.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_db_wal.py`:

```python
"""The SQLite engine must enable WAL and a busy_timeout on every connection."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from sqlalchemy import event, text

from quaestor import db


def _temp_db_url(path: Path) -> str:
    # SQLite URL: three slashes for relative, four for absolute.
    return f"sqlite:///{path}"


def test_wal_mode_is_set_on_connect(tmp_path: Path):
    db_file = tmp_path / "test.db"
    engine = db.make_engine(_temp_db_url(db_file))
    # Open one connection so the PRAGMA fires.
    with engine.connect() as conn:
        mode = conn.execute(text("PRAGMA journal_mode")).scalar_one()
        assert mode.lower() == "wal", f"expected WAL, got {mode!r}"


def test_busy_timeout_is_set_on_connect(tmp_path: Path):
    db_file = tmp_path / "test.db"
    engine = db.make_engine(_temp_db_url(db_file))
    with engine.connect() as conn:
        ms = conn.execute(text("PRAGMA busy_timeout")).scalar_one()
        assert int(ms) == 5000, f"expected 5000, got {ms!r}"


def test_wal_persists_across_connections(tmp_path: Path):
    """Two distinct connections to the same file both observe WAL."""
    db_file = tmp_path / "test.db"
    engine = db.make_engine(_temp_db_url(db_file))
    with engine.connect() as a:
        assert a.execute(text("PRAGMA journal_mode")).scalar_one().lower() == "wal"
    with engine.connect() as b:
        assert b.execute(text("PRAGMA journal_mode")).scalar_one().lower() == "wal"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && uv run pytest tests/test_db_wal.py -v`
Expected: 3 failures (current `make_engine` doesn't set any PRAGMA on connect).

- [ ] **Step 3: Implement the connect-listener PRAGMAs**

Modify `backend/src/quaestor/db.py`. Replace the body of `make_engine` so it
registers a `connect` listener, and add the listener function below the
existing code:

```python
from sqlalchemy import event  # add at top with other sqlalchemy imports


def _set_sqlite_pragmas(dbapi_connection, connection_record):  # noqa: ARG001
    """Enable WAL + busy_timeout on every new SQLite connection.

    WAL allows concurrent readers while a writer is active (api vs mcp).
    busy_timeout makes the second writer wait instead of failing fast.
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def make_engine(url: str = DATABASE_URL, *, memory: bool = False) -> Engine:
    engine = create_engine(
        "sqlite://" if memory else url,
        connect_args={"check_same_thread": False},
    )
    # Only SQLite engines need the pragmas; skip in-memory tests where WAL
    # is a no-op (each connection sees its own :memory:).
    if not memory and not url.startswith("sqlite:///:memory"):
        event.listens_for(engine, "connect")(set_sqlite_pragmas)
        # rename below to _set_sqlite_pragmas
        # (event.listens_for passes the fn by name; use the private symbol)
    return engine
```

Wait — fix the symbol name. Use the bare `_set_sqlite_pragmas` consistently:

```python
def make_engine(url: str = DATABASE_URL, *, memory: bool = False) -> Engine:
    if memory or url == "sqlite://":
        return create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    engine = create_engine(url, connect_args={"check_same_thread": False})
    event.listens_for(engine, "connect")(_set_sqlite_pragmas)
    return engine
```

The full top of the file becomes:

```python
"""SQLite engine, session, and work-unit helpers."""
from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine as _sm_create_engine

from .domain.models import Settings

# Use the SQLModel helper so SQLModel metadata can bind correctly.
_create_engine = _sm_create_engine

DATABASE_URL = os.environ.get("QUAESTOR_DB", "sqlite:///quaestor.db")


def _set_sqlite_pragmas(dbapi_connection, connection_record):  # noqa: ARG001
    """Enable WAL + busy_timeout + FK on every new SQLite connection.

    WAL allows concurrent readers while a writer is active (api vs mcp).
    busy_timeout makes the second writer wait instead of failing with
    'database is locked'. foreign_keys is on-by-default-disabled in SQLite.
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def make_engine(url: str = DATABASE_URL, *, memory: bool = False) -> Engine:
    if memory or url == "sqlite://":
        return _create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    engine = _create_engine(url, connect_args={"check_same_thread": False})
    event.listens_for(engine, "connect")(_set_sqlite_pragmas)
    return engine


engine = make_engine()


def init_db(target_engine: Engine = engine) -> None:
    SQLModel.metadata.create_all(target_engine)
    with Session(target_engine) as s:
        if s.get(Settings, 1) is None:
            s.add(Settings(id=1, base_currency="COP"))
            s.commit()
    from .services.bootstrap import register_goal_hooks
    register_goal_hooks()


@contextmanager
def get_session(target_engine: Engine = engine) -> Generator[Session, None, None]:
    with Session(target_engine) as s:
        yield s


@contextmanager
def atomic(session: Session) -> Generator[Session, None, None]:
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
```

- [ ] **Step 4: Run the new test to verify it passes**

Run: `cd backend && uv run pytest tests/test_db_wal.py -v`
Expected: 3 passes.

- [ ] **Step 5: Run the full suite to verify no regressions**

Run: `cd backend && uv run pytest -q`
Expected: all tests pass (in-memory tests skip the listener; no schema change).

- [ ] **Step 6: Commit**

```bash
git add backend/src/quaestor/db.py backend/tests/test_db_wal.py
git commit -m "feat(backend): enable WAL + busy_timeout + FK on SQLite connect"
```

---

### Task 3: FX fetch job (`quaestor.jobs.fx_fetch`)

Provider-agnostic USD→COP fetcher. Returns a `Decimal` rate. The daily job calls this and writes via `services.fx.set_fx_rate`.

**Files:**
- Create: `backend/src/quaestor/jobs/__init__.py`
- Create: `backend/src/quaestor/jobs/fx_fetch.py`
- Test: `backend/tests/jobs/__init__.py`
- Test: `backend/tests/jobs/test_fx_fetch.py`

**Interfaces:**
- Produces: `fetch_usd_cop(url: str, api_key: str | None = None, *, client: httpx.Client | None = None) -> Decimal`. Uses `client` if given (for tests); otherwise builds a default `httpx.Client(timeout=10)`. Expects the JSON response to contain `rates.COP` (Frankfurter-compatible).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/jobs/__init__.py` (empty):

```python
```

Create `backend/tests/jobs/test_fx_fetch.py`:

```python
"""FX fetch job — provider-agnostic USD->COP rate extraction."""
from __future__ import annotations

from decimal import Decimal

import httpx
import pytest

from quaestor.jobs.fx_fetch import fetch_usd_cop


class _StubResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"{self.status_code}", request=None, response=None
            )


class _StubClient:
    def __init__(self, payload: dict | None = None, exc: Exception | None = None):
        self.payload = payload
        self.exc = exc
        self.last_url: str | None = None
        self.last_params: dict | None = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url: str, params: dict | None = None, timeout=None):
        self.last_url = url
        self.last_params = params or {}
        if self.exc:
            raise self.exc
        return _StubResponse(self.payload or {})


def test_returns_decimal_from_rates_cop():
    client = _StubClient({"rates": {"COP": 4200.50}})
    rate = fetch_usd_cop("https://api.example.com/latest", client=client)
    assert rate == Decimal("4200.50")


def test_sends_api_key_as_query_param():
    client = _StubClient({"rates": {"COP": 4100}})
    fetch_usd_cop("https://api.example.com/latest", api_key="secret", client=client)
    assert client.last_params == {"api_key": "secret"}


def test_no_api_key_sends_no_query_params():
    client = _StubClient({"rates": {"COP": 4100}})
    fetch_usd_cop("https://api.example.com/latest", client=client)
    assert client.last_params == {}


def test_missing_rates_cop_raises():
    client = _StubClient({"foo": "bar"})
    with pytest.raises(ValueError, match="rates.COP"):
        fetch_usd_cop("https://api.example.com/latest", client=client)


def test_http_error_propagates():
    bad = _StubClient(status_code=503)
    bad.payload = {}
    with pytest.raises(httpx.HTTPStatusError):
        fetch_usd_cop("https://api.example.com/latest", client=bad)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && uv run pytest tests/jobs/test_fx_fetch.py -v`
Expected: ImportError or AttributeError — module does not exist yet.

- [ ] **Step 3: Implement the module**

Create `backend/src/quaestor/jobs/__init__.py`:

```python
"""Operational jobs run by the daily scheduler (P7). Not user-facing tools."""
```

Create `backend/src/quaestor/jobs/fx_fetch.py`:

```python
"""Daily USD->COP FX rate fetcher (ADR-011).

Provider-agnostic: expects a JSON response with `rates.COP`. Compatible with
Frankfurter (`https://api.frankfurter.app/latest?base=USD&symbols=COP`) and
similar free providers. The provider URL is fully configurable via
`FX_API_URL`; this module just extracts the rate.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Protocol

import httpx


class _HttpClient(Protocol):
    def get(self, url: str, params: dict | None = None, timeout: float | None = None): ...


def fetch_usd_cop(
    url: str,
    api_key: str | None = None,
    *,
    client: _HttpClient | None = None,
) -> Decimal:
    """Hit the FX provider and return USD->COP as a Decimal.

    Args:
        url: FX provider endpoint. Must return JSON with `rates.COP`.
        api_key: Optional API key. Sent as `?api_key=...` query param when set.
        client: Optional httpx-compatible client (used by tests for stubbing).

    Raises:
        httpx.HTTPStatusError: the provider returned 4xx/5xx.
        ValueError: response JSON does not contain `rates.COP`.
    """
    params: dict[str, str] = {}
    if api_key:
        params["api_key"] = api_key
    owns_client = client is None
    if owns_client:
        client = httpx.Client(timeout=10.0)
    try:
        response = client.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()
    finally:
        if owns_client:
            client.close()  # type: ignore[union-attr]
    try:
        rate = data["rates"]["COP"]
    except (KeyError, TypeError) as exc:
        raise ValueError(
            f"FX response missing rates.COP: {data!r}"
        ) from exc
    return Decimal(str(rate))
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && uv run pytest tests/jobs/test_fx_fetch.py -v`
Expected: 5 passes.

- [ ] **Step 5: Add the `httpx` dependency**

The runtime needs `httpx` (already in dev deps via `pyproject.toml` line 17).
Move it to runtime deps in `backend/pyproject.toml`:

```toml
dependencies = [
    "fastapi>=0.137.2",
    "httpx>=0.28.1",          # moved from dev
    "itsdangerous>=2.2.0",
    "mcp>=1.28,<2",
    "sqlmodel>=0.0.22",
    "uvicorn[standard]>=0.49.0",
]

[dependency-groups]
dev = [
    "pytest>=8",
]
```

Run: `cd backend && uv lock && uv sync`
Expected: lockfile updates, no install errors.

- [ ] **Step 6: Commit**

```bash
git add backend/src/quaestor/jobs/__init__.py \
        backend/src/quaestor/jobs/fx_fetch.py \
        backend/tests/jobs/__init__.py \
        backend/tests/jobs/test_fx_fetch.py \
        backend/pyproject.toml backend/uv.lock
git commit -m "feat(backend): USD->COP FX fetcher (provider-agnostic)"
```

---

### Task 4: Daily orchestration job (`quaestor.jobs.daily`)

One entry point: `run_daily(session, today, fx_url, fx_key)` calls FX → `materialize_due` → `ensure_month_closed`. A `__main__` wrapper reads env and exits non-zero on hard failures. Idempotent.

**Files:**
- Create: `backend/src/quaestor/jobs/daily.py`
- Test: `backend/tests/jobs/test_daily.py`

**Interfaces:**
- Produces: `run_daily(session: Session, today: date, fx_url: str, fx_key: str | None) -> dict` returning `{"fx_rate": Decimal | None, "fx_error": str | None, "materialized_count": int, "month_closed": str}`. FX errors are swallowed (ADR-011) and reported in `fx_error`.
- Produces: `def main()` — reads `FX_API_URL`, `FX_API_KEY`, `DB_PATH`, opens a session, calls `run_daily`, prints the result, exits 0.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/jobs/test_daily.py`:

```python
"""Daily orchestration: FX + materialize_due + ensure_month_closed, idempotent."""
from __future__ import annotations

from datetime import date as Date
from decimal import Decimal

import pytest
from sqlmodel import Session

from quaestor.domain.models import Account, AccountType, Category, RecurringItem, RecurringMode, IntervalUnit
from quaestor.jobs import daily
from quaestor.jobs.fx_fetch import _StubClient  # type: ignore[attr-defined]


@pytest.fixture
def session(monkeypatch, tmp_path):
    monkeypatch.setenv("QUAESTOR_DB", f"sqlite:///{tmp_path / 'test.db'}")
    from quaestor import db
    db.init_db(db.engine)
    with Session(db.engine) as s:
        yield s


def _make_account(session: Session, name: str = "Bank") -> Account:
    acc = Account(name=name, type=AccountType.debit, currency="COP", balance=0)
    session.add(acc)
    session.commit()
    session.refresh(acc)
    return acc


def _make_recurring(session: Session, account: Account) -> RecurringItem:
    item = RecurringItem(
        name="Rent", payee="Landlord", type="expense", mode=RecurringMode.manual,
        amount=100000, currency="COP", category_id=None, account_id=account.id,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=Date(2026, 6, 1),
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def test_run_daily_materializes_due_recurring(session, monkeypatch):
    acc = _make_account(session)
    _make_recurring(session, acc)
    today = Date(2026, 6, 1)

    # Stub the httpx.Client used inside fx_fetch by patching its module symbol.
    from quaestor.jobs import fx_fetch as fx_module
    monkeypatch.setattr(
        fx_module, "httpx",
        type("X", (), {"Client": lambda *a, **kw: _StubClient({"rates": {"COP": 4150}})}),
    )

    result = daily.run_daily(session, today, fx_url="https://example.com", fx_key=None)

    assert result["materialized_count"] == 1
    assert result["month_closed"] == "2026-06"
    assert result["fx_error"] is None


def test_run_daily_is_idempotent(session, monkeypatch):
    acc = _make_account(session)
    _make_recurring(session, acc)
    today = Date(2026, 6, 1)

    from quaestor.jobs import fx_fetch as fx_module
    monkeypatch.setattr(
        fx_module, "httpx",
        type("X", (), {"Client": lambda *a, **kw: _StubClient({"rates": {"COP": 4150}})}),
    )

    daily.run_daily(session, today, "https://example.com", None)
    result2 = daily.run_daily(session, today, "https://example.com", None)

    assert result2["materialized_count"] == 0


def test_fx_failure_does_not_block_other_jobs(session, monkeypatch):
    acc = _make_account(session)
    _make_recurring(session, acc)
    today = Date(2026, 6, 1)

    from quaestor.jobs import fx_fetch as fx_module

    class _BoomClient:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, *a, **kw): raise RuntimeError("network down")

    monkeypatch.setattr(fx_module, "httpx", type("X", (), {"Client": lambda *a, **kw: _BoomClient()}))

    result = daily.run_daily(session, today, "https://example.com", None)

    assert result["fx_error"] is not None
    assert "network down" in result["fx_error"]
    assert result["materialized_count"] == 1  # materialize_due still ran
```

Wait — `_StubClient` lives in `tests/jobs/test_fx_fetch.py`. Move it to a small helper module so both test files can import it without circular issues. Or define a local stub here. Simpler: redefine a local stub in `test_daily.py`:

Replace the FX-stubbing block above with a local stub:

```python
class _StubClient:
    def __init__(self, payload): self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def get(self, url, params=None, timeout=None):
        class _R:
            status_code = 200
            def json(self_inner): return self.payload
            def raise_for_status(self_inner): pass
        return _R()
```

Use that in the three tests above instead of importing `_StubClient`.

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && uv run pytest tests/jobs/test_daily.py -v`
Expected: ImportError — `quaestor.jobs.daily` does not exist.

- [ ] **Step 3: Implement the module**

Create `backend/src/quaestor/jobs/daily.py`:

```python
"""Daily orchestration entry point (ADR-011/017/020 + ADR-0013).

Runs three idempotent jobs in order:
  1. FX rate fetch (best-effort; failure does not block).
  2. materialize_due(today) — turns recurring items into transactions.
  3. ensure_month_closed(today) — closes the calendar month via rollover hooks.

Re-runs on the same day are no-ops by construction (ADR-017/020). A missed
day self-heals on the next run.
"""
from __future__ import annotations

import logging
import os
from datetime import date as Date
from decimal import Decimal

from sqlmodel import Session

from .. import db
from ..services.fx import set_fx_rate
from ..services.recurring import materialize_due
from ..services.rollover import ensure_month_closed
from .fx_fetch import fetch_usd_cop

log = logging.getLogger(__name__)


def run_daily(
    session: Session, today: Date, fx_url: str, fx_key: str | None
) -> dict:
    """Run the three daily jobs. Returns a small report dict (no secrets).

    Args:
        session: An open SQLModel session.
        today: The "as-of" date for materialization and month close.
        fx_url: FX provider URL. Empty string skips FX fetch entirely.
        fx_key: Optional FX provider API key.

    Returns:
        dict with keys: fx_rate (Decimal|None), fx_error (str|None),
        materialized_count (int), month_closed (str "YYYY-MM").
    """
    report: dict = {
        "fx_rate": None,
        "fx_error": None,
        "materialized_count": 0,
        "month_closed": f"{today.year:04d}-{today.month:02d}",
    }

    if fx_url:
        try:
            rate = fetch_usd_cop(fx_url, fx_key)
            set_fx_rate(session, today, rate)
            report["fx_rate"] = rate
        except Exception as exc:  # FX failures are non-fatal (ADR-011)
            log.exception("FX fetch failed; continuing")
            report["fx_error"] = repr(exc)

    occurrences = materialize_due(session, today)
    report["materialized_count"] = len(occurrences)

    ensure_month_closed(session, today)
    return report


def main() -> None:
    import json as _json

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    fx_url = os.environ.get("FX_API_URL", "")
    fx_key = os.environ.get("FX_API_KEY") or None
    today = Date.today()
    with db.get_session() as session:
        report = run_daily(session, today, fx_url, fx_key)
    # Decimal is not JSON-native; stringify for the printed line.
    printable = {**report, "fx_rate": str(report["fx_rate"]) if report["fx_rate"] is not None else None}
    print(_json.dumps(printable, sort_keys=True))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && uv run pytest tests/jobs/test_daily.py -v`
Expected: 3 passes.

- [ ] **Step 5: Run the full suite**

Run: `cd backend && uv run pytest -q`
Expected: all pass; no regressions.

- [ ] **Step 6: Commit**

```bash
git add backend/src/quaestor/jobs/daily.py backend/tests/jobs/test_daily.py
git commit -m "feat(backend): daily scheduler orchestration (fx + materialize + close)"
```

---

### Task 5: Scheduler entrypoint script (`backend/scripts/cron.sh`)

A shell loop the scheduler container runs. Sleeps 24h between runs. Handles SIGTERM cleanly so Docker stop doesn't kill mid-write.

**Files:**
- Create: `backend/scripts/cron.sh`
- Modify: `.gitignore` (no change yet — added in Task 10)

**Interfaces:**
- Consumes: env `RUN_ON_BOOT` (default `1` — run immediately on start) and `INTERVAL_SECONDS` (default `86400`).
- Produces: an executable bash script with a `trap` for clean shutdown.

- [ ] **Step 1: Write the script**

Create `backend/scripts/cron.sh`:

```bash
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
```

- [ ] **Step 2: Make it executable and lint-check**

Run:
```bash
chmod +x backend/scripts/cron.sh
bash -n backend/scripts/cron.sh   # syntax check, no execution
```
Expected: no output, exit 0.

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/cron.sh
git commit -m "feat(backend): daily scheduler shell loop"
```

---

### Task 6: Backend Dockerfile

Multi-stage not needed — the project is Python + uv and small enough for a single stage. Use `python:3.12-slim`, install `uv`, copy source. Default CMD is the API; the scheduler overrides with the script.

**Files:**
- Create: `backend/Dockerfile`

**Interfaces:**
- Consumes: `pyproject.toml`, `uv.lock`, `src/quaestor/`, `scripts/cron.sh`.
- Produces: an image whose `ENTRYPOINT` is `uv` and which exposes `app` (the api), `mcp` (`python -m quaestor.mcp`), and `daily` (`python -m quaestor.jobs.daily`) as command forms.

- [ ] **Step 1: Write the Dockerfile**

Create `backend/Dockerfile`:

```dockerfile
# Quaestor backend image (api + mcp + scheduler all share this; ADR-0013).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# uv install first (cache-friendly).
RUN pip install --no-cache-dir uv==0.5.11

# Dependency layer: copy lockfiles only, install, then copy source.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src/ ./src/
COPY scripts/ ./scripts/
RUN chmod +x ./scripts/cron.sh

ENV PATH="/app/.venv/bin:${PATH}"

# Default to the REST API; the mcp and scheduler services override `command:`.
CMD ["uv", "run", "uvicorn", "quaestor.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

Verify `uv==0.5.11` against the user's installed version (`uv --version`); if
different, use the installed version. The plan keeps the version pinned for
deterministic builds; bump it when the dev environment bumps.

- [ ] **Step 2: Lint the Dockerfile (optional but cheap)**

Run: `docker run --rm -i hadolint/hadolint < backend/Dockerfile` (skip if hadolint not installed).
Expected: no errors (ignore "Use --no-install-recommends" warning if it appears; python:3.12-slim already minimal).

- [ ] **Step 3: Build locally (smoke test, optional)**

Run: `cd backend && docker build -t quaestor-backend:test .`
Expected: image built, no errors. Skip if Docker is not running.

- [ ] **Step 4: Commit**

```bash
git add backend/Dockerfile
git commit -m "build(backend): Dockerfile for api/mcp/scheduler (shared image)"
```

---

### Task 7: Frontend Dockerfile (Next.js standalone)

The frontend must build inside the container (it needs `pnpm install` + `next build`) and run from the standalone output for a small production image. Internal URL (`API_INTERNAL_URL`) is injected at build time so the Next.js server component knows where to proxy.

**Files:**
- Create: `frontend/Dockerfile`
- Create: `frontend/.dockerignore`

**Interfaces:**
- Consumes: `frontend/package.json`, `pnpm-lock.yaml`, `next.config.ts`, `app/`, `components/`, `lib/`, `ui/`, `public/`.
- Produces: an image running `node server.js` (Next standalone) on port 3000.

- [ ] **Step 1: Write `.dockerignore`**

Create `frontend/.dockerignore`:

```
node_modules
.next
.git
.gitignore
.env
.env.local
.env.production
tests
coverage
*.log
.DS_Store
docker
```

- [ ] **Step 2: Write the Dockerfile**

The frontend already uses Next.js. Verify the standalone output flag is set; if not, the user must add `output: "standalone"` to `next.config.ts` (existing line 3 has empty config — update). Modify `frontend/next.config.ts`:

```ts
import type { NextConfig } from "next"

const nextConfig: NextConfig = {
  output: "standalone",
}

export default nextConfig
```

Create `frontend/Dockerfile`:

```dockerfile
# Quaestor frontend (Next.js 16 standalone).
# Stage 1 — deps: install with pnpm.
FROM node:22-slim AS deps
ENV PNPM_HOME="/pnpm" PATH="/pnpm:$PATH"
RUN corepack enable && corepack prepare pnpm@11.3.0 --activate
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

# Stage 2 — build: produce .next/standalone output.
FROM node:22-slim AS build
ENV PNPM_HOME="/pnpm" PATH="/pnpm:$PATH" \
    NEXT_TELEMETRY_DISABLED=1
RUN corepack enable && corepack prepare pnpm@11.3.0 --activate
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG API_INTERNAL_URL=http://api:8000
ENV API_INTERNAL_URL=${API_INTERNAL_URL}
RUN pnpm build

# Stage 3 — runtime: only what's needed to run.
FROM node:22-slim AS runtime
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
WORKDIR /app
COPY --from=build /app/public ./public
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
USER node
EXPOSE 3000
CMD ["node", "server.js"]
```

Note: `packageManager: "pnpm@11.3.0"` (line 5 of `frontend/package.json`) is the exact version to activate.

- [ ] **Step 3: Build locally (smoke test, optional)**

Run: `cd frontend && docker build -t quaestor-frontend:test --build-arg API_INTERNAL_URL=http://api:8000 .`
Expected: image built; standalone output present.

- [ ] **Step 4: Commit**

```bash
git add frontend/Dockerfile frontend/.dockerignore frontend/next.config.ts
git commit -m "build(frontend): Dockerfile with Next.js standalone + internal API URL"
```

---

### Task 8: Tailscale serve config (`ts-serve.json`)

The Tailscale sidecar reads this file at startup and serves `/mcp` from the `mcp` service's internal `:9000`.

**Files:**
- Create: `ts-serve.json`

**Interfaces:** Tailscale expects `{"TCP": {...}, "Web": {...}, "AllowFunnel": ...}` shape. We expose only HTTPS on the sidecar's tailnet hostname to `http://mcp:9000`.

- [ ] **Step 1: Write the file**

Create `ts-serve.json`:

```json
{
  "TCP": {},
  "Web": {
    "${TS_HOSTNAME:-quaestor-mcp}:443": {
      "Handlers": {
        "/mcp": {
          "Proxy": "http://mcp:9000"
        }
      }
    }
  },
  "AllowFunnel": false
}
```

`${TS_HOSTNAME:-quaestor-mcp}` lets the operator override the tailnet name per-deployment via env.

- [ ] **Step 2: Validate JSON**

Run: `python3 -c "import json; json.load(open('ts-serve.json'))"`
Expected: no output (valid JSON).

- [ ] **Step 3: Commit**

```bash
git add ts-serve.json
git commit -m "ops(tailscale): serve /mcp on the tailnet only"
```

---

### Task 9: Litestream config

Continuous WAL replication. The `api` container runs the Litestream sidecar with this config; on restore, the spec says "ideally as an entrypoint step" — keep restore manual for now (the runbook documents it).

**Files:**
- Create: `litestream.yml`

- [ ] **Step 1: Write the config**

Create `litestream.yml`:

```yaml
# Continuous WAL replication to an S3-compatible bucket (ADR-0012).
# Restore: litestream restore -o /data/quaestor.db ${LITESTREAM_BUCKET}
dbs:
  - path: /data/quaestor.db
    replicas:
      - url: ${LITESTREAM_BUCKET}
        # 24h of WAL retained locally for fast catch-up if the bucket is slow.
        retention: 24h
        # Snapshot every 24h; otherwise pure WAL streaming.
        snapshot-interval: 24h
```

- [ ] **Step 2: Validate YAML**

Run: `python3 -c "import yaml; yaml.safe_load(open('litestream.yml'))"`
Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add litestream.yml
git commit -m "ops(litestream): continuous WAL replication config"
```

---

### Task 10: Caddyfile

Routes `/api/*` to `api:8000`, catch-all to `frontend:3000`. No `/mcp`. Caddy fetches and renews the Let's Encrypt cert automatically from the public domain.

**Files:**
- Create: `Caddyfile`

**Interfaces:** Caddy reads `$DOMAIN` from the environment (via Docker Compose `environment:`). The site block uses `{...}` placeholders.

- [ ] **Step 1: Write the Caddyfile**

Create `Caddyfile`:

```caddy
# Quaestor front door — serves frontend + /api/* on the public domain.
# /mcp is NOT routed here: Tailscale serves it on the tailnet (ADR-0011).
{
    email {$LETSENCRYPT_EMAIL:-admin@{$DOMAIN}}
}

{$DOMAIN} {
    encode gzip zstd
    reverse_proxy /api/* api:8000
    reverse_proxy frontend:3000
}
```

The first `reverse_proxy` is path-prefixed; the second is the catch-all. Order matters — Caddy matches in declaration order.

- [ ] **Step 2: Validate the Caddyfile format (optional)**

Run: `docker run --rm -v "$PWD/Caddyfile:/etc/caddy/Caddyfile:ro" -e DOMAIN=example.com caddy:2 caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile`
Expected: `valid configuration` (skip if Docker is unavailable).

- [ ] **Step 3: Commit**

```bash
git add Caddyfile
git commit -m "ops(caddy): reverse proxy + auto HTTPS for frontend and /api/*"
```

---

### Task 11: docker-compose.yml

The single source of truth for the running system. Wires everything together. All secrets from `.env`. Only `caddy` carries `ports:`.

**Files:**
- Create: `docker-compose.yml`
- Modify: `.gitignore` (add `.env` already there; add Docker and Tailscale state files)

**Interfaces:**
- Services: `api`, `mcp`, `frontend`, `caddy`, `tailscale`, `scheduler`, plus named volumes `quaestor-data`, `caddy-data`, `caddy-config`, `tailscale-state`.
- Healthchecks on `api`, `mcp`, `frontend`.

- [ ] **Step 1: Update `.gitignore`**

Append to `/Users/angelozdev/me/quaestor/.gitignore`:

```
# Deploy artifacts / state
.env
.env.*
!.env.example
ts-serve.local.json
litestream.state
backend/.docker_cache/
frontend/.next/
frontend/.docker_cache/
```

(The first three `.env` lines already exist in the current file; the new lines start at `# Deploy artifacts / state`.)

- [ ] **Step 2: Write `docker-compose.yml`**

Create `docker-compose.yml`:

```yaml
# Quaestor production stack (ADR-0010-0013).
# Only `caddy` publishes host ports; /mcp lives on the tailnet (ADR-0011).
services:
  api:
    build: ./backend
    image: quaestor-backend:latest
    environment:
      QUAESTOR_DB: sqlite:////data/quaestor.db
      APP_TOKEN: ${APP_TOKEN}
      SESSION_SECRET: ${SESSION_SECRET:?SESSION_SECRET required}
      FRONTEND_ORIGIN: https://${DOMAIN}
      COOKIE_SECURE: "true"
    volumes:
      - quaestor-data:/data
    expose: ["8000"]
    healthcheck:
      test: ["CMD", "uv", "run", "python", "-c", "import httpx,os,sys; sys.exit(0 if httpx.get('http://localhost:8000/api/auth/me', headers={'Authorization': f'Bearer {os.environ[\"APP_TOKEN\"]}'}, timeout=5).status_code in (200,401) else 1)"]
      interval: 30s
      timeout: 5s
      retries: 5
    depends_on: [caddy]   # api doesn't depend on caddy to run; this orders `up`.
    restart: unless-stopped

  mcp:
    build: ./backend
    image: quaestor-backend:latest
    command: ["uv", "run", "python", "-m", "quaestor.mcp"]
    environment:
      QUAESTOR_DB: sqlite:////data/quaestor.db
      APP_TOKEN: ${APP_TOKEN}
    volumes:
      - quaestor-data:/data
    expose: ["9000"]
    healthcheck:
      test: ["CMD-SHELL", "uv run python -c \"import httpx,sys; r=httpx.get('http://localhost:9000/mcp', headers={'Authorization': 'Bearer '+__import__('os').environ['APP_TOKEN']}, timeout=5); sys.exit(0 if r.status_code in (200,400) else 1)\""]
      interval: 30s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      args:
        API_INTERNAL_URL: http://api:8000
    image: quaestor-frontend:latest
    environment:
      FRONTEND_PASSWORD_HASH: ${FRONTEND_PASSWORD_HASH}
    expose: ["3000"]
    healthcheck:
      test: ["CMD", "node", "-e", "fetch('http://localhost:3000/').then(r=>process.exit(r.status<500?0:1)).catch(()=>process.exit(1))"]
      interval: 30s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  caddy:
    image: caddy:2
    ports:
      - "80:80"
      - "443:443"
    environment:
      DOMAIN: ${DOMAIN}
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy-data:/data
      - caddy-config:/config
    depends_on:
      api:
        condition: service_healthy
      frontend:
        condition: service_healthy
    restart: unless-stopped

  tailscale:
    image: tailscale/tailscale:latest
    hostname: ${TS_HOSTNAME:-quaestor-mcp}
    environment:
      TS_AUTHKEY: ${TS_AUTHKEY:?TS_AUTHKEY required}
      TS_STATE_DIR: /var/lib/tailscale
      TS_SERVE_CONFIG: /config/ts-serve.json
      TS_HOSTNAME: ${TS_HOSTNAME:-quaestor-mcp}
    volumes:
      - tailscale-state:/var/lib/tailscale
      - ./ts-serve.json:/config/ts-serve.json:ro
    cap_add: [NET_ADMIN]
    depends_on:
      mcp:
        condition: service_healthy
    restart: unless-stopped

  scheduler:
    build: ./backend
    image: quaestor-backend:latest
    command: ["./scripts/cron.sh"]
    environment:
      QUAESTOR_DB: sqlite:////data/quaestor.db
      FX_API_URL: ${FX_API_URL:-}
      FX_API_KEY: ${FX_API_KEY:-}
      RUN_ON_BOOT: "1"
      INTERVAL_SECONDS: "86400"
    volumes:
      - quaestor-data:/data
    restart: unless-stopped

volumes:
  quaestor-data:
  caddy-data:
  caddy-config:
  tailscale-state:
```

Notes:
- `QUAESTOR_DB: sqlite:////data/quaestor.db` — four slashes = absolute path.
- `caddy` is the only service with `ports:`. `/mcp` is not exposed to the host.
- The `api` `healthcheck` calls `/api/auth/me` (a known P1 endpoint) to confirm auth wiring works; both 200 and 401 mean the service is up.
- The `tailscale` service is on the host network so `tailscaled` can bind the tailnet IP. We use `NET_ADMIN` instead of `network_mode: host` because Tailscale's official sidecar pattern is `cap_add: NET_ADMIN`.

- [ ] **Step 3: Validate the compose file**

Run: `docker compose config -q`
Expected: exit 0 (no errors).

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml .gitignore
git commit -m "ops(compose): full stack with caddy/tailscale/scheduler and shared volume"
```

---

### Task 12: `.env.example` (root)

Documented template. Empty values. Lists every variable the compose file and runbook reference.

**Files:**
- Create: `.env.example`

- [ ] **Step 1: Write the file**

Create `.env.example`:

```dotenv
# Quaestor production environment. Copy to `.env` and fill in real values.
# NEVER commit `.env` (gitignored).

# --- Public domain + TLS ---
DOMAIN=quaestor.example.com
LETSENCRYPT_EMAIL=admin@example.com

# --- Auth ---
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
APP_TOKEN=
SESSION_SECRET=

# bcrypt/argon2 hash of the frontend login password. Generate with:
#   python -c "from passlib.hash import bcrypt; print(bcrypt.hash('yourpw'))"
FRONTEND_PASSWORD_HASH=

# --- Database (used by api + mcp + scheduler; lives on the quaestor-data volume) ---
DB_PATH=/data/quaestor.db

# --- Tailscale (serves /mcp on the tailnet, ADR-0011) ---
# Reusable auth key from https://login.tailscale.com/admin/settings/keys
TS_AUTHKEY=
# Optional tailnet hostname for the sidecar (default: quaestor-mcp)
TS_HOSTNAME=quaestor-mcp

# --- FX rate (ADR-011; daily job fetches USD->COP) ---
# Example: https://api.frankfurter.app/latest?base=USD&symbols=COP
FX_API_URL=
FX_API_KEY=

# --- Litestream continuous backup (ADR-0012) ---
# S3/R2/Backblaze URL, e.g. s3://quaestor-backups/quaestor.db
LITESTREAM_BUCKET=
LITESTREAM_ACCESS_KEY_ID=
LITESTREAM_SECRET_ACCESS_KEY=
# Leave empty for AWS S3; set for R2/Backblaze, e.g. https://<accountid>.r2.cloudflarestorage.com
LITESTREAM_ENDPOINT=
```

- [ ] **Step 2: Validate it parses as dotenv**

Run: `python3 -c "import dotenv; dotenv.dotenv_values('.env.example')"` (skip if `python-dotenv` not installed locally) — or just eyeball it.

- [ ] **Step 3: Commit**

```bash
git add .env.example
git commit -m "ops: .env.example template with documented vars"
```

---

### Task 13: Deploy runbook

Single document the operator follows for first boot, deploys, restore, and connecting Claude Code. Cross-references all ADRs and the spec.

**Files:**
- Create: `docs/runbooks/deploy.md`
- Create: `docs/runbooks/restore-from-backup.md`

- [ ] **Step 1: Write `docs/runbooks/deploy.md`**

Create `docs/runbooks/deploy.md`:

```markdown
# Quaestor — Deploy Runbook (P7)

This runbook covers first boot, redeploys, and connecting Claude Code. It
assumes a single VPS reachable at `$DOMAIN`, with DNS A/AAAA pointing at it,
and ports `80` and `443` open.

## First boot

1. Install Docker + Docker Compose v2 on the VPS.
2. Clone the repo: `git clone <url> quaestor && cd quaestor`.
3. Copy `.env.example` to `.env` and fill in:
   - `DOMAIN`, `LETSENCRYPT_EMAIL`
   - `APP_TOKEN` (`python -c "import secrets; print(secrets.token_urlsafe(32))"`)
   - `SESSION_SECRET` (same generator)
   - `FRONTEND_PASSWORD_HASH` (bcrypt hash of the login password)
   - `TS_AUTHKEY` (reusable key from your tailnet)
   - `FX_API_URL` (e.g. `https://api.frankfurter.app/latest?base=USD&symbols=COP`)
   - `LITESTREAM_*` (S3/R2/Backblaze bucket + creds)
4. Bring the stack up: `docker compose up -d --build`.
5. Watch Caddy get a cert: `docker compose logs -f caddy`. Look for
   `obtained certificate` for `$DOMAIN`.
6. Verify the public surface:
   - `curl -H "Authorization: Bearer $APP_TOKEN" https://$DOMAIN/api/accounts`
     returns 200 (or 401 if no accounts yet).
   - `curl https://$DOMAIN/mcp` returns 404 (Caddy doesn't route it).
7. Verify the tailnet surface: from a machine on the tailnet,
   `curl -H "Authorization: Bearer $APP_TOKEN" https://$TS_HOSTNAME.<tailnet>.ts.net/mcp`
   should respond (200/4xx depending on protocol); from outside the tailnet
   it should be unreachable.

## Redeploy

From the VPS, in the repo:

```bash
git pull
docker compose up -d --build
```

Compose rebuilds only changed images and restarts the affected services. The
`quaestor-data` volume persists. P0's migrations run when `api` starts.

## Connect Claude Code (ADR-0011)

On the user's machine (must be on the tailnet), `~/.claude/mcp.json`:

```jsonc
{ "mcpServers": {
  "quaestor": {
    "type": "http",
    "url": "https://$TS_HOSTNAME.<your-tailnet>.ts.net/mcp",
    "headers": { "Authorization": "Bearer $APP_TOKEN" }
  }
}}
```

Cloud MCP clients (claude.ai web) cannot reach `/mcp`; only machines on the
tailnet can. This is by design.

## Scheduler

`scheduler` runs `scripts/cron.sh` in a 24h loop, calling
`python -m quaestor.jobs.daily`. Watch with
`docker compose logs -f scheduler`. To force a run without waiting:
`docker compose exec scheduler uv run python -m quaestor.jobs.daily`.

## Backups

See `docs/runbooks/restore-from-backup.md`.
```

- [ ] **Step 2: Write `docs/runbooks/restore-from-backup.md`**

Create `docs/runbooks/restore-from-backup.md`:

```markdown
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
```

- [ ] **Step 3: Commit**

```bash
git add docs/runbooks/deploy.md docs/runbooks/restore-from-backup.md
git commit -m "docs(runbooks): deploy + restore procedures"
```

---

### Task 14: End-to-end verification (matches spec §Testing, points 1-7)

The spec's "done" criterion is seven manual checks. Run them and capture the output in a final report attached to the closing commit message.

**Files:** None created. Verification only.

**Interfaces:** The full stack from `docker compose up -d --build`.

- [ ] **Step 1: Confirm all services are `running`/`healthy`**

Run: `docker compose ps`
Expected: 5 services (`api`, `mcp`, `frontend`, `caddy`, `tailscale`, `scheduler`) — six lines including `scheduler` — with state `running` and `healthy` (or `running` for services without healthcheck like `scheduler`).

- [ ] **Step 2: Verify the public HTTPS frontend**

Run: `curl -sI https://$DOMAIN/ | head -1`
Expected: `HTTP/2 200` with no cert warning in the browser.

- [ ] **Step 3: Verify the public API with and without token**

Run:
```bash
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $APP_TOKEN" https://$DOMAIN/api/accounts
curl -s -o /dev/null -w "%{http_code}\n" https://$DOMAIN/api/accounts
curl -s -o /dev/null -w "%{http_code}\n" https://$DOMAIN/mcp
```
Expected: `200` (or `200`/empty list), `401`, and `404` for `/mcp` (Caddy doesn't route it).

- [ ] **Step 4: Verify the tailnet `/mcp`**

From a machine on the tailnet:
```bash
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $APP_TOKEN" \
  https://$TS_HOSTNAME.<tailnet>.ts.net/mcp
```
Expected: a 4xx (the MCP protocol responds to GET with 4xx except on the JSON-RPC endpoint), not a connection error.
From a machine NOT on the tailnet: connection refused / timeout (fail closed, ADR-0011).

- [ ] **Step 5: Verify the scheduler runs end-to-end**

Run:
```bash
docker compose exec scheduler uv run python -m quaestor.jobs.daily
```
Expected: a JSON line like
`{"fx_error": null, "fx_rate": "4150.50", "materialized_count": 0, "month_closed": "2026-06"}`
(or `materialized_count > 0` if a recurring item is due today).
Re-run: same line, `materialized_count == 0` (idempotent).

- [ ] **Step 6: Verify the volume persists across restarts**

```bash
docker compose restart
docker compose ps
```
Expected: services come back, data intact (open the frontend; the previously-recorded items are still there).

- [ ] **Step 7: Verify a restore works**

Pick a clean directory on the host. Run the Litestream restore command from `docs/runbooks/restore-from-backup.md`. Then point a temporary `quaestor-backend` container at the restored DB (override `QUAESTOR_DB=sqlite:////tmp/restored.db`):
```bash
docker compose run --rm -v /tmp/restored:/data -e QUAESTOR_DB=sqlite:////data/quaestor.db api \
  uv run python -c "from quaestor import db; db.init_db(db.engine); from sqlmodel import Session; s=Session(db.engine); print(s.exec(__import__('sqlmodel').select(__import__('quaestor.domain.models', fromlist=['Account']).Account)).all())"
```
Expected: the account list is non-empty (matches the live DB).

- [ ] **Step 8: Tag the deployment**

```bash
git tag -a v0.7.0 -m "P7 deployment shipped"
git push origin v0.7.0
```
Expected: tag visible on the remote.

- [ ] **Step 9: Final report commit**

Append to `task-13-report.md` (existing scratch file, harmless if absent) a short summary of each of the seven checks plus the output evidence. Then:
```bash
git add task-13-report.md
git commit -m "ops: P7 verification report (7/7 checks passed)"
```

---

## Self-Review

**1. Spec coverage (P7 §Components + §Public interface + §Key logic):**
- `api`, `mcp`, `frontend`, `caddy`, `tailscale`, `scheduler` services → Task 11 (compose). ✓
- WAL + busy_timeout → Task 2. ✓
- `set_fx_rate` daily job → Task 3 + Task 4. ✓
- `materialize_due(today)` → Task 4. ✓
- `ensure_month_closed(today)` → Task 4. ✓
- Caddyfile with HTTPS, only `/api/*` routed → Task 10. ✓
- `ts-serve.json` → Task 8. ✓
- `.env.example` documented → Task 12. ✓
- Litestream config + restore → Task 9 + Task 13. ✓
- `sqlite3 .backup` fallback → Task 13 (runbook only — not in spec as code, kept as runbook step). ✓
- Frontend Dockerfile (Next standalone) → Task 7. ✓
- Backend Dockerfile → Task 6. ✓
- Deploy runbook → Task 13. ✓
- Connect Claude Code over Tailscale → Task 13 + ADR 0011. ✓
- "Done" criteria 1-7 → Task 14. ✓
- ADRs for the operational choices → Task 1. ✓

**2. Placeholder scan:** No "TBD", "TODO", "implement later" in any step. Each step has either a concrete file path with complete code, or a concrete command with expected output.

**3. Type consistency:**
- `run_daily(session, today, fx_url, fx_key) -> dict` — defined Task 4, used Task 4 + Task 5.
- `fetch_usd_cop(url, api_key, *, client=None) -> Decimal` — defined Task 3, used Task 4.
- `_set_sqlite_pragmas` — defined Task 2 once, registered once. (One in-task edit was folded into the final code block.)
- `quaestor.jobs.daily` — module path consistent across Tasks 4, 5, 11, 14.
- `QUAESTOR_DB` env var — used in Tasks 2, 4, 11 (compose). Path with four slashes for absolute path: `sqlite:////data/quaestor.db` — consistent.

**4. Open follow-ups (not blockers):**
- The "frontend password login" flow is owned by P1/P6 and assumed working; P7 does not re-test it. The runbook only requires it to be reachable over HTTPS.
- The choice of Frankfurter for `FX_API_URL` is a default; the operator may swap providers as long as the JSON response contains `rates.COP`. The job is provider-agnostic.
- A scheduler that runs inside the same SQLite volume as `api`/`mcp` is the simplest single-host design. If the operator later moves to multi-host, switch to an external cron + CLI invocation (the `daily` module is already CLI-callable).
