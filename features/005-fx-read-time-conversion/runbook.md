---
slug: 005-fx-read-time-conversion
checkpoint: 4
created: 2026-07-30
status: open
steps:
  - id: backup-before-migration
    description: "Run `just backup` and confirm a fresh dated pg_dump exists in iCloud Drive"
    owner: human
    command: "just backup"
    evidence: null
    completed: false
    blocking_acs:
      - AC-12

  - id: run-migration-real-data
    description: "With the feature merged/checked out, restart the prod stack so alembic upgrade head applies revision 0005 to the real Postgres"
    owner: human
    command: "just dev-prod"
    evidence: null
    completed: false
    blocking_acs:
      - AC-12

  - id: verify-trm-preloaded
    description: "Verify the TRM survived the migration pre-load (Settings page or GET /fx shows the last known rate, no MissingRate)"
    owner: human
    command: null
    evidence: null
    completed: false
    blocking_acs:
      - AC-12

  - id: post-migration-smoke
    description: "Smoke-check real data: transactions list shows COP equivalents, monthly report loads, balances intact"
    owner: agent
    command: null
    evidence: null
    completed: false
    blocking_acs:
      - AC-12
---

# Runbook — 005 fx-read-time-conversion

## Migración sobre datos reales (one-time)

La revisión Alembic 0005 es destructiva sobre datos reales (drop de
`transaction.fx_rate`/`to_base` y de la tabla `fx_rate`) — gate de
autonomía low per manifest: **humano al volante**.

Orden: backup → migrar → verificar TRM precargada → smoke. La migración
copia el rate más reciente de `fx_rate` a `Settings.usd_cop` antes del
drop, así que no debe aparecer ningún `MissingRate` tras el upgrade; si
aparece, la precarga falló — fija la TRM a mano en Settings y repórtalo.

**Rollback**: restaurar el dump de `just backup` (pg_restore sobre el
contenedor; los dumps datados viven en iCloud Drive). El código pre-005
sigue en `main` hasta el merge.

AC-12 no puede declararse verde en CP7 mientras estos pasos sigan
abiertos.
