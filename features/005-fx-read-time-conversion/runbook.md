---
slug: 005-fx-read-time-conversion
checkpoint: 4
created: 2026-07-30
status: done
steps:
  - id: backup-before-migration
    description: "Run `just backup` and confirm a fresh dated pg_dump exists in iCloud Drive"
    owner: human
    command: "just backup"
    evidence: "quaestor-local-2026-07-31.dump (53 KB, pg_restore --list OK) — taken POST-migration; no pre-migration local backup exists (recipe was broken, see outcome). Nearest prior state: quaestor-render-2026-07-28.dump."
    completed: true
    blocking_acs:
      - AC-12

  - id: run-migration-real-data
    description: "With the feature merged/checked out, restart the prod stack so alembic upgrade head applies revision 0005 to the real Postgres"
    owner: human
    command: "just dev-prod"
    evidence: "Applied automatically at api container boot 2026-07-31T03:34:52Z (bind-mounted src already contained 0005). Container log: 'Running upgrade 0004 -> 0005'. alembic_version = 0005; fx_rate table gone; settings.usd_cop present."
    completed: true
    blocking_acs:
      - AC-12

  - id: verify-trm-preloaded
    description: "Verify the TRM survived the migration pre-load (Settings page or GET /fx shows the last known rate, no MissingRate)"
    owner: human
    command: null
    evidence: "Pre-load worked: usd_cop = 3000.000000 (last fx_rate row), no MissingRate. Corrected to real TRM 3133 via POST /api/fx on 2026-07-31; GET /api/fx and DB both read 3133.000000."
    completed: true
    blocking_acs:
      - AC-12

  - id: post-migration-smoke
    description: "Smoke-check real data: transactions list shows COP equivalents, monthly report loads, balances intact"
    owner: agent
    command: null
    evidence: "634 transactions intact, amount/currency columns untouched. GET /api/transactions 200 with cop_equivalent (380000 x 3133 = 1190540000, exact). GET /api/reports?month=2026-07 200. auth/me 200."
    completed: true
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
contenedor; los dumps datados viven en iCloud Drive). Código pre-005:
commit `c2d59a0` (main pre-merge de PR #1).

## Resultado (2026-07-31) — cerrado

La migración se aplicó **sola**, antes del backup planeado: el boot del
contenedor api (2026-07-31T03:34:52Z) corrió `alembic upgrade head` con
el código de la feature ya presente vía bind mount. El gate "humano al
volante" nunca fue ejecutable — cualquier arranque del stack post-código
aplica migraciones sin confirmación.

Agravante: `just backup` estaba roto (escaping estilo make `$$` en el
justfile — `$$HOME` se expandía a PID+"HOME") y nunca había producido un
dump local. Corregido el 2026-07-31 (además: `exec -T`, y aborta si el
dump queda vacío).

Pérdida real: solo lo que 0005 droppea por diseño (historia `fx_rate` y
columnas congeladas) — prescindible per ADR-0031. Montos y monedas
originales intactos. TRM precargada verificada y luego corregida al
valor real (3133). Smoke completo verde.

**Lección para futuros runbooks con migraciones destructivas**: las
migraciones corren en cada boot del contenedor — un runbook que asuma
"el humano decide cuándo migrar" debe impedir el arranque del stack
hasta tener el backup (p. ej. levantar solo `db`:
`docker compose --profile pg up -d db` → `just backup` → stack completo).

AC-12: verde — pasos cerrados con evidencia.
