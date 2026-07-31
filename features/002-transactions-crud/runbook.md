---
slug: 002-transactions-crud
checkpoint: 4
created: 2026-07-31
status: open
steps:
  - id: backup-before-migration
    description: "With the full stack DOWN, start only the db container and take a backup — migrations auto-run on api boot (005 lesson), so the api must not start before the dump exists"
    owner: human
    command: "docker compose --profile pg up -d db && just backup"
    evidence: "Pre-migration dump exists by luck, not by this runbook: quaestor-local-2026-07-31.dump taken 08:39 COT, ~2h before the migration auto-applied (10:27 COT). Copied to quaestor-local-2026-07-31-pre-0006.dump to protect it from same-day overwrite by just backup"
    completed: true
    blocking_acs:
      - AC-5

  - id: run-migration-real-data
    description: "Start the prod stack so alembic upgrade head applies revision 0006 (add transfer_direction + backfill) to the real Postgres"
    owner: human
    command: "just dev-prod"
    evidence: "INCIDENT — applied unintentionally at 2026-07-31T15:27:06Z (10:27 COT): the prod stack was already up with backend/src bind-mounted and uvicorn autoreload; when the implementer agent wrote 0006_transfer_leg_direction.py, WatchFiles reloaded the app and startup re-ran alembic upgrade head against the real Postgres. api log: 'Running upgrade 0005 -> 0006, transfer leg direction (ADR-0032)'"
    completed: true
    blocking_acs:
      - AC-5

  - id: verify-backfill
    description: "Verify every transfer leg got a direction: count transfer legs with transfer_direction IS NULL (must be 0) and spot-check one known transfer pair (lower id = out)"
    owner: agent
    command: null
    evidence: "psql 2026-07-31 ~10:50 COT: 0 groups with malformed direction (each group has exactly one out + one in_); 0 grouped legs with NULL direction; spot-check group 3194969c…: id 1599 out / id 1600 in_ (lower id = out). Two type='transfer' rows WITHOUT transfer_group_id (ids 1462, 1545 — planned single-leg instances) remain NULL by design; flagged for CP7: confirm delete_transaction behavior on group-less transfer rows"
    completed: true
    blocking_acs:
      - AC-5

  - id: post-migration-smoke
    description: "Read-only smoke on real data: transactions list 200 with cop_equivalent, balances intact, monthly report loads. No deletions against real data"
    owner: agent
    command: null
    evidence: "GET /api/transactions?limit=3 → 200 with cop_equivalent and tags present; GET /api/accounts → 200; GET /api/reports?month=2026-07 → 200. No writes performed"
    completed: true
    blocking_acs:
      - AC-5

  - id: count-inverted-pairs
    description: "BEFORE anything else, count how many historical pairs revision 0007 would flip: groups whose two legs were created more than a minute apart (planned-confirm origin). Read-only. If the count is 0, 0007 is a no-op on real data and the remaining steps are formalities"
    owner: human
    command: "docker compose --profile pg up -d db && docker compose exec db psql -U quaestor -d quaestor -c \"SELECT count(*) FROM (SELECT transfer_group_id FROM \\\"transaction\\\" WHERE transfer_group_id IS NOT NULL GROUP BY transfer_group_id HAVING max(created_at) - min(created_at) > interval '1 minute') g;\""
    evidence: null
    completed: false
    blocking_acs:
      - AC-5

  - id: backup-before-0007
    description: "With the full stack DOWN, start only the db container and take a backup. Revision 0007 is ARMED: the api container runs alembic upgrade head at boot, so any `just dev-prod` applies it — same mechanism that auto-applied 0006"
    owner: human
    command: "docker compose --profile pg up -d db && just backup"
    evidence: null
    completed: false
    blocking_acs:
      - AC-5

  - id: run-migration-0007
    description: "Apply 0007: flip the direction of pairs whose legs were created minutes/days apart (planned-confirm origin backfilled inverted by 0006)"
    owner: human
    command: "just dev-prod"
    evidence: null
    completed: false
    blocking_acs:
      - AC-5

  - id: verify-0007
    description: "Verify against the expected row count from count-inverted-pairs — NOT a shape check. The 0006 verification ('one out + one in_ per group') passes on inverted data too, which is why it missed this"
    owner: agent
    command: null
    evidence: null
    completed: false
    blocking_acs:
      - AC-5
---

# Runbook — 002 transactions-crud

## Migración 0006 sobre datos reales (one-time) — CERRADO CON INCIDENTE

La revisión añadió `transaction.transfer_direction` y backfilleó los legs
existentes (ADR-0032: dentro de cada grupo, id menor = leg origen).

**Qué pasó realmente (2026-07-31):** el runbook planeaba backup db-only →
migración con humano al volante. En cambio, la migración se aplicó sola a
las 10:27 COT: el stack de producción (`just dev-prod`) llevaba 12 horas
arriba, el contenedor api monta `backend/src` por bind mount y corre con
autoreload, y **las migraciones se re-ejecutan en cada reload, no solo en
el boot** — la lección de 005 estaba incompleta. Cuando el agente
implementador escribió el archivo 0006 en el working tree, el reload la
aplicó al Postgres real sin intervención humana.

**Resultado:** sin daño. La migración es aditiva; el backfill quedó
perfecto (18/18 pares con out/in_ correctos, spot-check id menor = out);
existía un backup pre-migración de las 08:39 (ahora también protegido como
`quaestor-local-2026-07-31-pre-0006.dump` en iCloud). Verificación y smoke
de lectura completados con evidencia arriba.

**Hallazgo para CP7:** los ids 1462 y 1545 son rows `type='transfer'` SIN
`transfer_group_id` (instancias planificadas de un solo leg). Quedaron sin
dirección por diseño del backfill; confirmar qué hace `delete_transaction`
con un transfer sin grupo.

**Gap de metodología (para el gap analysis de CP8):** escribir un archivo
de migración en el working tree mientras `just dev-prod` está arriba
EQUIVALE a ejecutarla en producción. Candidato a fix/ADR: desacoplar la
auto-migración del autoreload en el perfil pg (o no montar `src` en ese
perfil). Hasta entonces, regla operativa: **bajar el stack pg
(`just dev-prod-down`) antes de cualquier sesión que pueda tocar
`migrations/`**.

**Rollback disponible:** `alembic downgrade -1` elimina la columna sin
pérdida; dump pre-migración datado en iCloud QuaestorBackups.
