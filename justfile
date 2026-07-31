# Quaestor — local-only dev recipes (ADR-0026).

_default:
	@just --list

# --- DB profiles (pick one) ----------------------------------------

# PRODUCTION: full stack against the local Postgres container (ADR-0030).
dev-prod:
	QUAESTOR_ENV_FILE=backend/.env.local.postgres docker compose --env-file backend/.env.local.postgres --profile pg up --build

dev-prod-down:
	QUAESTOR_ENV_FILE=backend/.env.local.postgres docker compose --env-file backend/.env.local.postgres --profile pg down

# Run against the local SQLite file in .dev-data/ (sandbox).
dev-local:
	QUAESTOR_ENV_FILE=backend/.env.local.sqlite docker compose --env-file backend/.env.local.sqlite up --build

# Run against the Render Postgres (frozen standby since ADR-0030 — avoid writes).
dev-real:
	QUAESTOR_ENV_FILE=backend/.env.local.remote docker compose --env-file backend/.env.local.remote up --build

# --- Backups (ADR-0030) --------------------------------------------

# Dump the local production Postgres to iCloud Drive (dated file).
backup:
	QUAESTOR_ENV_FILE=backend/.env.local.postgres docker compose --env-file backend/.env.local.postgres --profile pg exec -T db \
		sh -c 'pg_dump -U "${POSTGRES_USER:-quaestor}" --format=custom --no-owner "${POSTGRES_DB:-quaestor}"' \
		> "$HOME/Library/Mobile Documents/com~apple~CloudDocs/QuaestorBackups/quaestor-local-$(date +%F).dump"
	@test -s "$HOME/Library/Mobile Documents/com~apple~CloudDocs/QuaestorBackups/quaestor-local-$(date +%F).dump" || { echo "backup dump is empty — removing"; rm "$HOME/Library/Mobile Documents/com~apple~CloudDocs/QuaestorBackups/quaestor-local-$(date +%F).dump"; exit 1; }
	@echo "backup written to iCloud QuaestorBackups/quaestor-local-$(date +%F).dump"

# --- Common ops ----------------------------------------------------

# Stop the stack. PRESERVES the local SQLite DB (the quaestor-dev-data
# volume is not dropped). To wipe it manually, see "Manual reset" below.
dev-down:
	docker compose --env-file backend/.env.local.sqlite down

dev-logs:
	docker compose --env-file backend/.env.local.sqlite logs -f

dev-logs-one service:
	docker compose --env-file backend/.env.local.sqlite logs -f {{service}}

dev-shell-api:
	docker compose --env-file backend/.env.local.sqlite exec api sh

# Run pytest on the host (in-memory SQLite; no DB needed).
dev-test:
	cd backend && uv run pytest -q

# Manually trigger the daily job (FX + materialize + close-month).
daily:
	docker compose --env-file backend/.env.local.sqlite exec api \
		uv run python -m quaestor.jobs.daily

# Show which env file is currently active.
db-which:
	@echo "default recipes target backend/.env.local.sqlite"
	@echo "QUAESTOR_DB=" $(grep '^QUAESTOR_DB=' backend/.env.local.sqlite 2>/dev/null || echo "(no .env.local.sqlite yet)")
