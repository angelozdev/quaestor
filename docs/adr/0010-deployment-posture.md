# 0010 — Self-Hosted Single-VPS Deployment with Docker Compose

- **Status:** accepted
- **Date:** 2026-06-22
- **Superseded by:** [0026 — Local-only posture](./0026-local-only-posture.md)

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
