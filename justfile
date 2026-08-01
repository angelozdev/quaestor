# Quaestor — local-only dev recipes (ADR-0026).
#
# ADR-0033: only the sqlite sandbox layers in docker-compose.dev.yml, which is
# what bind-mounts backend/src. The postgres and remote profiles run from the
# built image, so writing a file can never autoreload the app into an
# unattended `alembic upgrade head` against real data.

pg_env := "backend/.env.local.postgres"
pg := "QUAESTOR_ENV_FILE=" + pg_env + " docker compose --env-file " + pg_env + " --profile pg"

sqlite_env := "backend/.env.local.sqlite"
sqlite := "docker compose -f docker-compose.yml -f docker-compose.dev.yml --env-file " + sqlite_env

backup_dir := "$HOME/Library/Mobile Documents/com~apple~CloudDocs/QuaestorBackups"

_default:
	@just --list

# --- DB profiles (pick one) ----------------------------------------

# PRODUCTION: full stack against the local Postgres container (ADR-0030).
# Aborts when revisions are pending (ADR-0033) — back up and migrate first.
dev-prod: prod-check-migrations
	{{pg}} up --build

dev-prod-down:
	{{pg}} down

# Refuse to start production while the schema is behind (ADR-0033).
prod-check-migrations:
	{{pg}} up -d --wait db
	{{pg}} build api
	{{pg}} run --rm --no-deps api python scripts/check_pending_migrations.py

# Apply pending revisions to the local production Postgres. Backup-gated.
migrate:
	@test -s "{{backup_dir}}/quaestor-local-$(date +%F).dump" || { echo "no backup dated today — run just backup first"; exit 1; }
	{{pg}} up -d --wait db
	{{pg}} build api
	{{pg}} run --rm --no-deps api python -m alembic upgrade head

# Run against the local SQLite file in .dev-data/ (sandbox). Hot-reload lives here.
dev-local:
	QUAESTOR_ENV_FILE={{sqlite_env}} {{sqlite}} up --build

# Run against the Render Postgres (frozen standby since ADR-0030 — avoid writes).
dev-real:
	QUAESTOR_ENV_FILE=backend/.env.local.remote docker compose --env-file backend/.env.local.remote up --build

# --- Backups (ADR-0030) --------------------------------------------

# Dump the local production Postgres to iCloud Drive (dated file).
backup:
	{{pg}} up -d --wait db
	{{pg}} exec -T db \
		sh -c 'pg_dump -U "${POSTGRES_USER:-quaestor}" --format=custom --no-owner "${POSTGRES_DB:-quaestor}"' \
		> "{{backup_dir}}/quaestor-local-$(date +%F).dump"
	@test -s "{{backup_dir}}/quaestor-local-$(date +%F).dump" || { echo "backup dump is empty — removing"; rm "{{backup_dir}}/quaestor-local-$(date +%F).dump"; exit 1; }
	@echo "backup written to iCloud QuaestorBackups/quaestor-local-$(date +%F).dump"

# --- Common ops ----------------------------------------------------

# Stop the stack. PRESERVES the local SQLite DB (the quaestor-dev-data
# volume is not dropped). To wipe it manually, see "Manual reset" below.
dev-down:
	{{sqlite}} down

dev-logs:
	{{sqlite}} logs -f

dev-logs-one service:
	{{sqlite}} logs -f {{service}}

dev-shell-api:
	{{sqlite}} exec api sh

# Run pytest on the host (in-memory SQLite; no DB needed).
dev-test:
	cd backend && uv run pytest -q

# Manually trigger the daily job (FX + materialize + close-month).
daily:
	{{sqlite}} exec api \
		uv run python -m quaestor.jobs.daily

# Show which env file is currently active.
db-which:
	@echo "default recipes target {{sqlite_env}}"
	@echo "QUAESTOR_DB=" $(grep '^QUAESTOR_DB=' {{sqlite_env}} 2>/dev/null || echo "(no .env.local.sqlite yet)")
