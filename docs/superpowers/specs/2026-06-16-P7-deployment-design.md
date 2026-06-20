# Quaestor — P7 Deployment (sub-project)

**Date:** 2026-06-16
**Depends on:** all (P0, P1, P2, P3, P4, P5, P6) — packages what they produce
**Part of:** `2026-06-16-quaestor-general-design.md` (see §4 Deployment and auth, §3 Architecture)

---

## Objective

Bring Quaestor online: a **self-hosted VPS**, **single-user**, with a domain + HTTPS. The **frontend and `/api/*` are public** behind Caddy; **`/mcp` is not exposed to the internet** — it lives behind **Tailscale** (private network, ADR-013) and is reachable only from the user's own machines. The browser should serve the frontend over HTTPS, a token-authenticated `curl` to the API should respond, Claude Code should connect to `/mcp` **over Tailscale**, a **daily job** should keep the FX rate fresh (ADR-011), and the DB should be continuously backed up and restorable.

## Scope

- `docker-compose.yml`: services `api`, `mcp`, `frontend`, `caddy`, **`tailscale`** (sidecar that serves `/mcp` on the private network) and **`scheduler`** (daily FX job). The DB (`quaestor.db`) lives on a **persistent volume shared by `api` and `mcp`**.
- `Caddyfile`: one domain, routed by path. Automatic HTTPS (Let's Encrypt). **Only publishes the frontend + `/api/*`; `/mcp` does not leave the internet** (Tailscale serves it).
- **Daily scheduler (ADR-011/017/020):** the `scheduler` runs, **every day**, three idempotent jobs: (a) **FX** — hits a free API and updates `usd_cop` in `FxRate` (`python -m quaestor.jobs.fx_fetch` → `set_fx_rate`); (b) **`materialize_due(today)`** — materializes the occurrences of recurring items with `due_date ≤ today` (due-driven, supports any interval: weekly, biweekly, monthly…; auto items post on their date, manual ones fall into "to-pay"); (c) **`ensure_month_closed`** — ensures the current **calendar month** is closed (`close_month(current_month)`: envelope rollover + goal contribution proposals): on day 1 it materializes the close, on other days it is a no-op, and a missed day self-heals. The temporal engine runs **on its own**, not by hand.
- Environment variables (`.env`, not committed): `APP_TOKEN`, the frontend password hash, domain, DB path, Litestream config, **`TS_AUTHKEY`** (Tailscale), **`FX_API_URL`/`FX_API_KEY`** (rate provider).
- Backups with **Litestream** (continuous replication to a bucket) + restore; minimal fallback: a daily `sqlite3 .backup` cron.
- Deploy steps (`git pull && docker compose up -d --build`) and how to connect Claude Code to `/mcp` **over Tailscale**.
- Security posture: the public API only with a token; **`/mcp` off the internet (Tailscale)**; only Caddy publishes 80/443.

**Out of scope:** CI/CD, multi-node orchestration, high availability, Postgres (the general design leaves it as a future migration via connection string). Single-writer SQLite is enough for single-user.

## Contribution to the data model

**None.** P7 defines no entities, fields, or migrations. It only packages and deploys the artifacts of P0–P6. Its only relationship with the data is operational: **where** `quaestor.db` lives (the volume), **who writes to it** (api + mcp, in practice one process at a time), and **how it is backed up/restored**. The migrations are run by the backend at startup (P0's responsibility); P7 only guarantees that the file persists across restarts.

## Components

| Component | What it is | Image / base |
|---|---|---|
| `api` | FastAPI served by uvicorn (P1), listens on internal `:8000` | Python 3.12 + uv |
| `mcp` | MCP streamable-HTTP (P2), listens on internal `:9000` | Python 3.12 + uv |
| `frontend` | Next.js App Router (P6), internal `:3000` | node, standalone build |
| `caddy` | Reverse proxy + auto HTTPS, the only one that publishes `80/443` to the host (frontend + `/api/*`) | `caddy:2` |
| `tailscale` | Sidecar that joins the VPS to the tailnet and **serves `/mcp`** on the private network (`tailscale serve` → `mcp:9000`). Publishes no ports to the host | `tailscale/tailscale` |
| `scheduler` | Idempotent daily jobs: FX rate fetch → `FxRate` + `materialize_due(today)` (due-driven recurring items, ADR-020) + `ensure_month_closed` (calendar-month close, ADR-017) | Python 3.12 + uv (reuses the `api` image) |
| `litestream` | Sidecar (or process inside `api`) replicating the DB | `litestream/litestream` |
| volume `quaestor-data` | Persists `quaestor.db` (+ `-wal`, `-shm`) | Docker named volume |

`api` and `mcp` mount **the same volume** at the same path (`/data/quaestor.db`) → they share the SQLite file. `frontend` and `caddy` do not touch the DB.

## Public interface

The sub-project's versioned artifacts (at the repo root):

### `docker-compose.yml` (shape)
```yaml
services:
  api:
    build: ./backend
    command: uv run uvicorn quaestor.api:app --host 0.0.0.0 --port 8000
    environment: [APP_TOKEN, DB_PATH, FRONTEND_PASSWORD_HASH]
    volumes: ["quaestor-data:/data"]
    expose: ["8000"]            # internal network only, no "ports:"
    restart: unless-stopped
  mcp:
    build: ./backend
    command: uv run python -m quaestor.mcp   # streamable-HTTP on :9000
    environment: [APP_TOKEN, DB_PATH]
    volumes: ["quaestor-data:/data"]
    expose: ["9000"]
    restart: unless-stopped
  frontend:
    build: ./frontend
    environment: [API_INTERNAL_URL=http://api:8000, FRONTEND_PASSWORD_HASH, APP_TOKEN]
    expose: ["3000"]
    restart: unless-stopped
  caddy:
    image: caddy:2
    ports: ["80:80", "443:443"]   # the only one published to the host (frontend + /api/*)
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy-data:/data
      - caddy-config:/config
    depends_on: [api, frontend]
    restart: unless-stopped
  tailscale:                       # /mcp does NOT leave the internet: it is served over the tailnet
    image: tailscale/tailscale
    hostname: quaestor-mcp
    environment:
      - TS_AUTHKEY=${TS_AUTHKEY}
      - TS_SERVE_CONFIG=/config/ts-serve.json   # serve https /mcp -> http://mcp:9000
      - TS_STATE_DIR=/var/lib/tailscale
    volumes: ["tailscale-state:/var/lib/tailscale", "./ts-serve.json:/config/ts-serve.json:ro"]
    cap_add: ["NET_ADMIN"]
    depends_on: [mcp]
    restart: unless-stopped
  scheduler:                       # daily FX job (ADR-011)
    build: ./backend
    command: ["./scripts/cron.sh"]  # daily crond: fx_fetch + materialize_due + ensure_month_closed (idempotent)
    environment: [DB_PATH, FX_API_URL, FX_API_KEY]
    volumes: ["quaestor-data:/data"]
    restart: unless-stopped
volumes:
  quaestor-data:
  caddy-data:
  caddy-config:
  tailscale-state:
```

### `Caddyfile` (shape)
```caddy
{$DOMAIN} {
    encode gzip
    handle /api/* {
        reverse_proxy api:8000
    }
    # /mcp is NOT routed here: the Tailscale sidecar serves it on the private network (ADR-013).
    handle {
        reverse_proxy frontend:3000
    }
}
```
Automatic HTTPS: Caddy obtains and renews the Let's Encrypt cert for `$DOMAIN` only. Port 80 redirects to 443.

### `.env.example` (documented; the real `.env` **is not committed**)
```dotenv
DOMAIN=quaestor.yourdomain.com
APP_TOKEN=                 # static bearer for API + MCP (generate 32+ random bytes)
FRONTEND_PASSWORD_HASH=    # hash (bcrypt/argon2) of the frontend login password
DB_PATH=/data/quaestor.db
# Tailscale (serves /mcp on the private network, ADR-013)
TS_AUTHKEY=                # tailnet auth key (reusable, tagged)
# FX rate (daily job, ADR-011)
FX_API_URL=                # endpoint of the usd_cop rate provider
FX_API_KEY=                # if the provider requires it
# Litestream
LITESTREAM_BUCKET=s3://quaestor-backups/quaestor.db
LITESTREAM_ACCESS_KEY_ID=
LITESTREAM_SECRET_ACCESS_KEY=
LITESTREAM_ENDPOINT=       # for R2/Backblaze; empty for AWS S3
```
`.env` and `quaestor.db*` go in `.gitignore`. `.env.example` is committed, with empty values.

## Key logic and rules

**Single SQLite writer.** SQLite allows one writer at a time. `api` and `mcp` share the file; in single-user usage writes are sporadic and short, so SQLite's locking (with **WAL** enabled) serializes them without trouble. Rules:
- **WAL mode mandatory** on the connection (set by P0 in `db.py`): it allows concurrent reads while a writer is active and reduces contention between `api` and `mcp`.
- WAL implies **three files**: `quaestor.db`, `quaestor.db-wal`, `quaestor.db-shm`. They must all live on the **same volume** at the same path for both services; never mount the DB separately nor copy it hot without a checkpoint.
- A reasonable `busy_timeout` (e.g. 5s) so the second writer waits instead of failing with "database is locked".
- Do not run more than one replica of `api` or `mcp`. Single-writer is an invariant, not a limitation to work around.

**HTTPS and network.** Only `caddy` publishes ports to the host (`80`, `443`) → frontend + `/api/*`. `api`/`mcp`/`frontend` use `expose` (visible only on Docker's internal network, not on the host). **`/mcp` does not come in through Caddy:** the `tailscale` sidecar serves it (`tailscale serve` → `mcp:9000`) **only inside the tailnet** (ADR-013); no `mcp` port touches the internet. The user reaches `/mcp` via the tailnet's MagicDNS from their machines.

**Auth (summary of §4 of the general design, implemented by P1/P2).** API and MCP require `Authorization: Bearer $APP_TOKEN`; no token → 401. Caddy does **not** terminate auth, it only routes; the destination service validates the token. The frontend validates the password (against `FRONTEND_PASSWORD_HASH`) and keeps a session; server-side it attaches `APP_TOKEN` to its API calls. **Defense in depth for `/mcp` (ADR-013):** first Tailscale (the endpoint doesn't even exist outside the tailnet), then the bearer token. The static token is no longer the only thing protecting the sensitive endpoint.

**Backups — Litestream (recommended).** Continuously replicates `quaestor.db` (reading the WAL) to an S3/R2/Backblaze bucket. Config in `litestream.yml`:
```yaml
dbs:
  - path: /data/quaestor.db
    replicas:
      - url: ${LITESTREAM_BUCKET}
```
Clean restore: `litestream restore -o /data/quaestor.db ${LITESTREAM_BUCKET}` before starting `api`/`mcp` (ideally as an entrypoint step: if the DB doesn't exist, restore; then start). **Minimal fallback** if there is no bucket: a daily cron `sqlite3 /data/quaestor.db ".backup /data/backups/quaestor-$(date +%F).db"` (uses the backup API, safe while hot) with N-day retention.

**Deploy.** From the VPS, in the repo: `git pull && docker compose up -d --build`. Compose rebuilds the changed images and restarts with zero loss of the volume. P0's migrations run when `api` starts. First boot: create `.env`, point the domain's DNS at the VPS, `docker compose up -d`, and wait for Caddy to issue the cert.

**Connect Claude Code to the MCP over Tailscale (ADR-013).** The user's machine must be on the **same tailnet** (Tailscale installed and logged in). The MCP server is streamable-HTTP served by the Tailscale sidecar on the VPS's **MagicDNS** name (`https://quaestor-mcp.<tailnet>.ts.net/mcp`), not on the public domain. In Claude Code's MCP config:
```jsonc
{ "mcpServers": {
  "quaestor": {
    "type": "http",
    "url": "https://quaestor-mcp.<your-tailnet>.ts.net/mcp",
    "headers": { "Authorization": "Bearer <APP_TOKEN>" }
  }
}}
```
There is no local stdio shim: the client speaks HTTPS to the VPS **over the tailnet's private network**, with the auth header as a second layer. **Trade-off:** cloud MCP clients (claude.ai web) are not on the tailnet → they cannot reach `/mcp`; if they were needed, the posture would be revisited (ADR-013).

## Errors/Risks

- **"database is locked"** from two simultaneous writers (api + mcp) → mitigated with WAL + `busy_timeout`; if it persists, it indicates a long write (review P3 rollover transactions, which must be short and atomic).
- **WAL not included in a manual backup** → a raw `cp` of the `.db` without a checkpoint loses WAL data. That's why Litestream (follows the WAL) or `sqlite3 .backup` (does a checkpoint), never a hot `cp`.
- **`APP_TOKEN` or `.env` leaked** → with `/mcp` already off the internet (Tailscale), a leaked token only grants access to the public API; rotate anyway (change env + restart + update Claude Code's config). `.env` stays out of git.
- **Tailscale sidecar down** → `/mcp` unreachable (the agent can't operate), but **nothing is exposed to the internet**: it fails closed, not open. Restart `tailscale`; verify `TS_AUTHKEY` is valid.
- **FX API down or unresponsive** → the daily job doesn't update the rate; the backend uses the **last effective one** and `to_base` freezes likewise. Manual override with `set_fx_rate` if needed. It doesn't block records (ADR-011).
- **Cert won't issue** (DNS pointed wrong, port 80 closed in the VPS firewall) → Caddy retries; verify the domain's `A`/`AAAA` records and that `80/443` are open on the VPS.
- **Volume deleted** (`docker compose down -v`) → loss of the DB. Document that `-v` destroys data; the safety net is Litestream.
- **Service exposed by mistake** (`ports:` on api/mcp) → bypass of Caddy and TLS. Only `caddy` carries `ports:`.
- **Untested restore** = nonexistent backup. The "done" criterion requires an actual restore.

## Testing and "done" criterion

Manual verification (single-user, no CI):
1. `docker compose up -d --build` brings up the **services** (api, mcp, frontend, caddy, tailscale, scheduler) and they end up `healthy`/`running` (`docker compose ps`).
2. `https://$DOMAIN/` serves the **frontend over HTTPS** with a valid cert (no browser warning).
3. `curl -H "Authorization: Bearer $APP_TOKEN" https://$DOMAIN/api/accounts` responds 200; **without** the header it responds 401. **`https://$DOMAIN/mcp` does NOT respond** (not routed in Caddy → confirms `/mcp` is not public).
4. **Over Tailscale:** `curl https://quaestor-mcp.<tailnet>.ts.net/mcp ...` and, end-to-end, **Claude Code (on the tailnet) connects** to `/mcp`, lists the tools, and runs one (e.g. recording an expense). A machine **outside the tailnet** cannot reach the endpoint.
5. **Scheduler:** after a run there is a `usd_cop` rate for today in `FxRate`; `materialize_due(today)` leaves the due occurrences materialized (auto items posted, manual ones in "to-pay"); and `ensure_month_closed` leaves the calendar month closed (rollover + proposed contributions). All **no-op on the second run** (idempotent). Manual `set_fx_rate` still works as an override.
6. The volume **persists**: `docker compose restart` keeps the data.
7. **Restorable backup:** `litestream restore` (or the daily copy) rebuilds `quaestor.db` in a clean directory and `api` starts on that DB with the data intact. (It isn't a backup until the restore is tested.)

"Done" = all 7 points pass.

## Integration with other sub-projects

- **P0 Core:** provides `db.py` with **WAL** and `busy_timeout`, and runs migrations at startup. P7 only persists the file and shares the volume.
- **P1 API + Auth:** defines the `api` service and validates `APP_TOKEN`. P7 builds it, exposes it on the internal network only, and routes `/api/*` to it via Caddy.
- **P2 MCP:** defines the `mcp` service (streamable-HTTP) and its bearer auth. P7 does **not** route it through Caddy: the `tailscale` sidecar serves it on the tailnet (ADR-013) and P7 documents how Claude Code connects via MagicDNS.
- **P3 Temporal engine:** its writes (rollover, confirm payment) must be short/atomic so they don't collide with the single-writer; it requires no deploy artifact of its own.
- **P4 / P5:** no deploy artifacts of their own; they ride inside `api`/`mcp`. P5 (importer) can produce large writes (CSV bulk) → another reason for WAL + `busy_timeout`.
- **P6 Frontend:** defines the `frontend` service; P7 builds it, routes it as the catch-all in Caddy, and passes it `API_INTERNAL_URL=http://api:8000` (internal network) + the password hash.

**Cross-cutting conventions respected:** P7 does not touch money, sign, or `posted`/`planned` (it does not manipulate data); its responsibility is that the **single `quaestor.db`** — the source of truth for the whole system — persists, is protected by a token behind HTTPS, and is backed up and restorable.
