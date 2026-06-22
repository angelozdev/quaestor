# Quaestor — dev recipes.
#
# Quick start:
#   just dev-build   # one-time image build (~1-2 min)
#   just dev         # bring up the stack (foreground, Ctrl-C stops)
#   just dev-logs    # follow logs from all services
#
# When you're done:
#   just dev-down    # stop, keep .dev-data/
#   just dev-reset   # wipe .dev-data/ and restart api+mcp

_default:
	@just --list

# Start the dev stack (foreground; Ctrl-C stops).
dev:
	docker compose up

# Build images first (cold start or after pulling new source).
dev-build:
	docker compose build

# Follow logs from all services.
dev-logs:
	docker compose logs -f

# Follow logs from a single service, e.g. `just dev-logs-one api`.
dev-logs-one service:
	docker compose logs -f {{service}}

# Stop the stack. Keeps ./.dev-data/quaestor.db intact.
dev-down:
	docker compose down

# Wipe ./.dev-data/ and restart api+mcp so the schema is recreated fresh.
dev-reset:
	rm -rf .dev-data
	mkdir -p .dev-data
	docker compose up api mcp

# Manually run the daily job once (FX + materialize_due + ensure_month_closed).
# Requires P7's quaestor.jobs.daily module to be shipped.
dev-trigger-scheduler:
	docker compose exec scheduler uv run python -m quaestor.jobs.daily

# Open a shell in the api container.
dev-shell-api:
	docker compose exec api sh

# Run the backend test suite on the host (in-memory DB; does not touch .dev-data/).
dev-test:
	cd backend && uv run pytest -q
