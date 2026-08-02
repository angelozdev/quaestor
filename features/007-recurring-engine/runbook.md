---
slug: 007-recurring-engine
checkpoint: 4
created: 2026-08-02
status: open
steps:
  - id: backup-before-anything
    description: "Dump the local production Postgres to iCloud before touching schema or data"
    owner: human
    command: "just backup"
    evidence: null
    completed: false
    blocking_acs:
      - AC-6
      - AC-12
      - AC-25

  - id: count-manual-recurring-incomes
    description: "Count and list the manual recurring incomes already in production (W8)"
    owner: human
    command: "QUAESTOR_ENV_FILE=backend/.env.local.postgres docker compose --env-file backend/.env.local.postgres --profile pg exec -T db psql -U \"${POSTGRES_USER:-quaestor}\" -d \"${POSTGRES_DB:-quaestor}\" -c \"select id, name, payee, amount, currency, active from recurring_item where type = 'income' and mode = 'manual' order by id;\""
    evidence: null
    completed: false
    blocking_acs:
      - AC-6

  - id: apply-migrations-0008-0009
    description: "Apply 0008 (the two enum values) and 0009 (manual repeating incomes become automatic) to the local production Postgres"
    owner: human
    command: "just migrate"
    evidence: null
    completed: false
    blocking_acs:
      - AC-6
      - AC-12
      - AC-25

  - id: resolve-orphaned-planned-incomes
    description: "Decide, per row, what to do with any planned income transactions the old manual incomes already produced"
    owner: human
    command: null
    evidence: null
    completed: false
    blocking_acs: []

  - id: verify-enum-values-live
    description: "Confirm both new enum values exist in the production database"
    owner: human
    command: "QUAESTOR_ENV_FILE=backend/.env.local.postgres docker compose --env-file backend/.env.local.postgres --profile pg exec -T db psql -U \"${POSTGRES_USER:-quaestor}\" -d \"${POSTGRES_DB:-quaestor}\" -c \"select t.typname, e.enumlabel from pg_type t join pg_enum e on e.enumtypid = t.oid where t.typname in ('source', 'occurrencestatus') order by t.typname, e.enumsortorder;\""
    evidence: null
    completed: false
    blocking_acs:
      - AC-12
      - AC-25
---

# Runbook — 007 recurring-engine

Pasos que no son código. Todos son `human` por una razón sola: el charter §7
exige humano para migraciones de esquema sobre datos reales, y el manifest
fuerza autonomía `low` en `migrations/**` y `.dev-data/**`. Producción es el
contenedor Postgres local (ADR-0030); Render es standby congelado y no se toca.

## Fase A — Antes de F0 (esquema)

### 1. Respaldo

```
just backup
```

`just migrate` ya está gated por respaldo: aborta si no existe un dump con la
fecha de hoy. Este paso lo hace explícito en vez de dejar que el gate falle.

**Evidencia:** ruta del dump en `QuaestorBackups/quaestor-local-<fecha>.dump`.

### 2. Aplicar las migraciones 0008 y 0009

```
just migrate
```

**0008** añade dos valores de enum: `offered` en `occurrencestatus` y el valor
de motor en `source`. Ambos van dentro de `op.get_context().autocommit_block()`
porque `ALTER TYPE … ADD VALUE` no corre dentro del bloque transaccional de
Alembic.

**0009** convierte a automático todo ingreso recurrente que esperaba
aprobación (ADR-0039). Imprime cuántas filas cambió:

```
[0009] repeating incomes switched to automatic: N
```

Anota ese número — es el conteo que W8 pedía, y dice si el paso 5 tiene
trabajo.

**Gotcha:** si la migración se escribe sin el `autocommit_block`, falla en
Postgres y **pasa** en la suite de aceptación (SQLite guarda los enums como
texto). El único lugar donde se detecta es aquí.

### 3. Verificar los valores en vivo

Ver el comando en el frontmatter (`verify-enum-values-live`). Debe listar
`posted, planned, skipped, offered` para `occurrencestatus` y el valor de motor
añadido a `source`.

**Evidencia:** salida del `psql`.

## Fase B — Después de migrar (limpieza de lo que quedó)

### 4. Contar lo que había antes de tocar nada

Ver el comando en el frontmatter (`count-manual-recurring-incomes`). Córrelo
**antes** del paso 2 si quieres el inventario con nombres; si no, el número que
imprime 0009 basta.

**Evidencia:** la tabla de salida, aunque tenga 0 filas.

### 5. Resolver los ingresos planeados que quedaron colgando

La migración 0009 convierte el ingreso a automático, pero **no toca los
movimientos que ese ingreso ya había creado**. Esos quedan como `planned`, sin
pantalla que los resuelva. Se dejan a propósito (ADR-0039): registrarlos movería
saldos que nunca confirmaste, y cancelarlos borraría la constancia de que
esperabas esa plata. Cuál de las dos corresponde cambia fila por fila, y es tu
decisión, no la de una migración.

Búscalos así:

```
QUAESTOR_ENV_FILE=backend/.env.local.postgres docker compose \
  --env-file backend/.env.local.postgres --profile pg exec -T db \
  psql -U "${POSTGRES_USER:-quaestor}" -d "${POSTGRES_DB:-quaestor}" -c \
  "select t.id, t.date, t.payee, t.amount, r.name from \"transaction\" t
     join recurring_item r on r.id = t.recurring_id
    where t.type = 'income' and t.status = 'planned' order by t.date;"
```

Por cada fila: si la plata sí entró, regístrala como movimiento normal; si no
entró, omítela. En el sandbox el conteo dio **0**, así que este paso puede
cerrarse sin trabajo si producción se ve igual.

**Evidencia:** la decisión escrita, fila por fila, o "0 filas".

## Qué NO está en este runbook

No hay provisioning, secretos, DNS ni consola de nube: la postura es local-only
(ADR-0026/0030) y esta feature no añade infraestructura. El despacho remoto de
agentes sigue apagado (`remote.ready: false`).
