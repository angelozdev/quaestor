---
slug: 008-mandatory-categories
checkpoint: 4
created: 2026-08-03
status: open
steps:
  - id: backup-before-migration
    description: "Dump the local production Postgres to iCloud before revision 0010 touches the schema"
    owner: human
    command: "just backup"
    evidence: null
    completed: false
    blocking_acs:
      - AC-17
      - AC-18
      - AC-19

  - id: count-uncategorised-live
    description: "Confirm production still holds zero uncategorised expenses and incomes — the precondition revision 0010 refuses without"
    owner: human
    command: "QUAESTOR_ENV_FILE=backend/.env.local.postgres docker compose --env-file backend/.env.local.postgres --profile pg exec -T db psql -U \"${POSTGRES_USER:-quaestor}\" -d \"${POSTGRES_DB:-quaestor}\" -c \"select type, count(*) filter (where category_id is null) as uncategorised, count(*) as total from \\\"transaction\\\" group by type order by type;\""
    evidence: "Run 2026-08-03 by the agent, read-only, at Angelo's request. expense 549 total / 0 uncategorised; income 50 / 0; transfer 39 / 39 uncategorised, which is AC-3 working. Identical to the AC-19 figures of 2026-08-02, so nothing was recorded uncategorised in between. Also checked in the same pass: alembic_version is 0009 (the pre-feature head 0010 expects) and 0 direction contradictions (no movement filed under a category of the opposite direction), so the AC-15 rule lands on clean data too."
    completed: true
    blocking_acs:
      - AC-18
      - AC-19

  - id: count-uncategorised-recurring-live
    description: "Confirm every recurring item carries a category — the precondition for the NOT NULL half of revision 0010"
    owner: human
    command: "QUAESTOR_ENV_FILE=backend/.env.local.postgres docker compose --env-file backend/.env.local.postgres --profile pg exec -T db psql -U \"${POSTGRES_USER:-quaestor}\" -d \"${POSTGRES_DB:-quaestor}\" -c \"select id, name, type, active from recurring_item where category_id is null order by id;\""
    evidence: "Run 2026-08-03 by the agent, read-only, at Angelo's request. 0 rows — every recurring item carries a category, so the NOT NULL half of 0010 applies without touching data."
    completed: true
    blocking_acs:
      - AC-6

  - id: apply-migration-0010
    description: "Apply revision 0010 (pre-flight guard, type-discriminated CHECK on transaction, NOT NULL on recurring_item.category_id) to the local production Postgres"
    owner: human
    command: "just migrate"
    evidence: null
    completed: false
    blocking_acs:
      - AC-17
      - AC-18
      - AC-19

  - id: verify-constraint-live
    description: "Confirm the CHECK exists in production and that the 39 transfers survived it"
    owner: human
    command: "QUAESTOR_ENV_FILE=backend/.env.local.postgres docker compose --env-file backend/.env.local.postgres --profile pg exec -T db psql -U \"${POSTGRES_USER:-quaestor}\" -d \"${POSTGRES_DB:-quaestor}\" -c \"select conname, pg_get_constraintdef(oid) from pg_constraint where conrelid = 'transaction'::regclass and contype = 'c';\" -c \"select count(*) from \\\"transaction\\\" where type = 'transfer' and category_id is null;\""
    evidence: null
    completed: false
    blocking_acs:
      - AC-17
---

# Runbook — 008 mandatory-categories

Pasos que no son código. Todos son `human` por una razón sola: el charter §7
exige humano para migraciones de esquema sobre datos reales, y el manifest
fuerza autonomía `low` en `migrations/**`. Producción es el contenedor Postgres
local (ADR-0030); Render es standby congelado y no se toca.

Se corre entero **al abrir F2**, no antes: la revisión `0010` instala una
barrera que rechaza filas sin categoría, y hasta que F0 no haya aterrizado
todavía hay rutas de escritura que pueden crearlas.

## 1. Respaldo

```
just backup
```

`just migrate` ya está gated por respaldo: aborta si no existe un dump con la
fecha de hoy. Este paso lo hace explícito en vez de dejar que el gate falle.

**Evidencia:** ruta del dump en `QuaestorBackups/quaestor-local-<fecha>.dump`.

## 2. Confirmar que los datos siguen limpios

El backfill se hizo el 2026-08-02 y dejó esto:

```
expense      549 movements   0 uncategorised
income        50 movements   0 uncategorised
transfer      39 movements  39 uncategorised   ← correcto, esto es AC-3
recurring     14 items       0 uncategorised
```

Entre esa fecha y hoy pasó tiempo, y el dueño siguió registrando plata con la
regla todavía apagada. Correr el conteo de nuevo no es ceremonia: es la
diferencia entre una migración que aterriza y una que se niega.

Comandos en el frontmatter (`count-uncategorised-live` y
`count-uncategorised-recurring-live`).

**Lo que tiene que salir:**

- `expense` y `income` → `uncategorised = 0`.
- `transfer` → `uncategorised = total`. Si alguna transferencia tiene
  categoría, la migración también se cae, por la otra mitad del CHECK.
- `recurring_item` sin categoría → **0 filas**.

**Si sale distinto:** no fuerces nada. Categoriza las filas desde la app (una
por una es correcto — clasificar plata es una decisión por movimiento, no una
que una migración pueda tomar) y vuelve a contar. Las 24 filas de
`🔄 Payment / Transfer` **sí** tienen categoría, así que pasan: están fuera de
alcance a propósito.

**Evidencia:** la salida del `psql`, aunque sea toda ceros.

## 3. Aplicar la revisión 0010

```
just migrate
```

Hace tres cosas, en este orden:

1. **Guarda previa** — cuenta gastos e ingresos sin categoría. Si hay, se niega
   nombrando cantidad y tipo (*"1 expense is still uncategorised"*) y no toca
   el esquema. Esto es AC-18, y es la red por si el paso 2 se saltó.
2. **CHECK sobre `transaction`** — `expense`/`income` exigen categoría,
   `transfer` exige no tenerla.
3. **`NOT NULL` sobre `recurring_item.category_id`.**

**Gotcha:** la revisión usa `op.batch_alter_table` porque SQLite no sabe
`ALTER TABLE ADD CONSTRAINT`. En Postgres eso emite un `ALTER` normal, así que
aquí no debería notarse — pero si algo falla en este paso y no en la suite,
mirar ahí primero.

**Evidencia:** `select version_num from alembic_version;` → `0010`.

## 4. Verificar en vivo

Comando en el frontmatter (`verify-constraint-live`). Dos cosas:

- El CHECK aparece en `pg_constraint` con la definición discriminada por tipo.
- **Las 39 transferencias siguen ahí y siguen sin categoría.** Es la
  verificación que importa: un `NOT NULL` a secas habría pasado los pasos 1–3 y
  roto exactamente esto.

**Evidencia:** salida del `psql`, con el conteo de transferencias.

## Qué NO está en este runbook

No hay provisioning, secretos, DNS ni consola de nube: la postura es local-only
(ADR-0026/0030) y esta feature no añade infraestructura. El despacho remoto de
agentes sigue apagado (`remote.ready: false`).

El backfill histórico **no** está aquí porque ya se hizo: 131 filas resueltas el
2026-08-02 tras un respaldo fresco (`quaestor-local-2026-08-02.dump`), 101 de
ellas fijando los 10 recurrentes que no tenían categoría. Queda como el registro
de por qué existe la feature, en `acs.md` AC-19.
