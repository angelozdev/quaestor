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