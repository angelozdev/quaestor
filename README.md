# Quaestor

Quaestor is an owned personal-finance backend + agent-native MCP layer (see `docs/adr/` for design). This README covers the developer workflow.

## Development

Local dev runs three services (`api`, `frontend`, `scheduler`) in Docker
with hot reload. No TLS, no Caddy, no Litestream.

Prerequisites: Docker Desktop, `just` (`brew install just`), and the
`backend/.env.local` + `frontend/.env.local` files (already in the repo, edit
if you need different secrets).

```bash
just dev-build   # one-time image build
just dev         # bring up the stack
just dev-logs    # follow logs
just dev-down    # stop
just dev-reset   # wipe ./.dev-data/ and restart fresh
just dev-trigger-scheduler   # run the daily job once (FX + materialize + close)
just dev-shell-api           # shell into the api container
just dev-test    # backend pytest (host-side, in-memory DB)
```

URLs (once `just dev` is running):
- Frontend: <http://localhost:3000>
- REST API: <http://localhost:8000/api>


Edit any file under `backend/src/` and uvicorn restarts. Edit anything under
`frontend/app/`, `frontend/components/`, etc. and Next.js hot-reloads. The
SQLite DB lives at `./.dev-data/quaestor.db` (gitignored).