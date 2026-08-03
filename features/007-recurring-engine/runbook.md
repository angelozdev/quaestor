---
slug: 007-recurring-engine
checkpoint: 4
created: 2026-08-02
status: closed
steps:
  - id: backup-before-anything
    description: "Dump the local production Postgres to iCloud before touching schema or data"
    owner: human
    command: "just backup"
    evidence: "QuaestorBackups/quaestor-local-2026-08-02.dump — 53k, written 2 Aug 14:07. Verified genuinely pre-migration, not just date-gate-satisfying: `pg_restore --data-only --table=alembic_version -f -` on the dump yields `0007`, and its schema still declares `occurrencestatus AS ENUM ('posted','planned','skipped')` and `source AS ENUM ('manual','agent','import_')` — the pre-007 shape. A valid restore point for 0008/0009."
    completed: true
    blocking_acs:
      - AC-6
      - AC-12
      - AC-25

  - id: count-manual-recurring-incomes
    description: "Count and list the manual recurring incomes already in production (W8)"
    owner: human
    command: "QUAESTOR_ENV_FILE=backend/.env.local.postgres docker compose --env-file backend/.env.local.postgres --profile pg exec -T db psql -U \"${POSTGRES_USER:-quaestor}\" -d \"${POSTGRES_DB:-quaestor}\" -c \"select id, name, payee, amount, currency, active from recurring_item where type = 'income' and mode = 'manual' order by id;\""
    evidence: "Not captured before the migration ran, so recovered from the pre-migration dump instead (`pg_restore --data-only --table=recurring_item`), which is the same inventory: exactly 3 manual repeating incomes — id 8 Ubidots Salary / Ubidots / 622310100 COP / active; id 9 Ubidots Bonus / Ubidots / 284700 USD / active; id 10 Keystone Salary / Keystone / 380000 USD / active. So 0009 printed `repeating incomes switched to automatic: 3`. Running the command as written against the live DB now correctly returns 0 rows."
    completed: true
    blocking_acs:
      - AC-6

  - id: apply-migrations-0008-0009
    description: "Apply 0008 (the two enum values) and 0009 (manual repeating incomes become automatic) to the local production Postgres"
    owner: human
    command: "just migrate"
    evidence: "`select version_num from alembic_version;` -> `0009` (1 row), up from `0007` in the same-day pre-migration dump. 0009's effect confirmed on the live rows: `select type, mode, count(*) from recurring_item group by type, mode;` -> `expense|manual|11` and `income|auto|3`; zero rows match `type='income' AND mode='manual'`. Ids 8/9/10 are all `auto`."
    completed: true
    blocking_acs:
      - AC-6
      - AC-12
      - AC-25

  - id: resolve-orphaned-planned-incomes
    description: "Decide, per row, what to do with any planned income transactions the old manual incomes already produced"
    owner: human
    command: null
    evidence: "Sandbox showed 0; production does not. Two rows remain, found with the query in Fase B §5: tx 1634, 2026-07-30, Ubidots, 622310100, planned, from `Ubidots Salary`; tx 1635, 2026-07-31, Keystone, 380000, planned, from `Keystone Salary`. DECISION (user, 2026-08-02): leave both pending for now — neither is posted nor cancelled, and no screen resolves them. This is deliberate per ADR-0039, which says the choice is per row and belongs to the user, not to a migration. Step stays open; `blocking_acs: []`, so it does not gate the merge. TRIGGER (corrected 2026-08-02 by the user directly): both amounts DID land, in July — what is missing is not knowledge but the act of recording July at all, which the user has not uploaded yet. So the trigger is 'when July is recorded', not 'when the user finds out'. Resolve then by confirming each row with its real date and amount, or by deleting it and letting the import bring the real one. Worth doing before 2026-08-30, when the engine posts August's salaries by itself and a leftover July row starts looking like a duplicate. RESOLVED (user, 2026-08-02): the user superseded the defer — both rows confirmed as paid at their declared date and amount, to be corrected later if a figure turns out wrong. Executed through `services.planned.confirm_payment` (not raw SQL) so the balance, the transaction status and the occurrence moved together. Backups taken first: the verified pre-migration dump was preserved as `quaestor-local-2026-08-02-pre-migration.dump` because `just backup` writes a date-stamped name and would have overwritten it, then a fresh post-migration dump was taken. Result: tx 1634 and 1635 `planned` -> `posted`, their occurrences `planned` -> `posted` (so no later run re-charges 2026-07-30 or 2026-07-31); Nu Débito 407701901 -> 1030012001 COP (+622310100), DolarApp 694488 -> 1074488 USD (+380000). Both rows keep `source=manual`, which is historically accurate — they were created by the pre-0009 manual mode, not by the engine. FOLLOW-UP for whoever records July's bank statement: these two are now posted, so the imported salary lines are duplicates — skip or delete them at import time."
    completed: true
    blocking_acs: []

  - id: verify-enum-values-live
    description: "Confirm both new enum values exist in the production database"
    owner: human
    command: "QUAESTOR_ENV_FILE=backend/.env.local.postgres docker compose --env-file backend/.env.local.postgres --profile pg exec -T db psql -U \"${POSTGRES_USER:-quaestor}\" -d \"${POSTGRES_DB:-quaestor}\" -c \"select t.typname, e.enumlabel from pg_type t join pg_enum e on e.enumtypid = t.oid where t.typname in ('source', 'occurrencestatus') order by t.typname, e.enumsortorder;\""
    evidence: "8 rows, both new values present. occurrencestatus: posted, planned, skipped, offered. source: manual, agent, import_, recurring. Matches 0008's `_NEW_VALUES = ((\"occurrencestatus\", \"offered\"), (\"source\", \"recurring\"))` exactly, so the `autocommit_block` gotcha in Fase A §2 did not bite."
    completed: true
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

**Resultado en producción (2026-08-02):** no se ve igual — el conteo dio **2**.

```
  id  |    date    |  payee   |  amount   | status  |      name
------+------------+----------+-----------+---------+-----------------
 1634 | 2026-07-30 | Ubidots  | 622310100 | planned | Ubidots Salary
 1635 | 2026-07-31 | Keystone |    380000 | planned | Keystone Salary
```

Decisión del usuario: **dejarlas pendientes por ahora**. No se registran ni se
cancelan. Es el único paso del runbook que sigue abierto, y no bloquea ninguna
AC (`blocking_acs: []`).

**Cerrado el 2026-08-02.** El usuario reemplazó el aplazamiento: ambos montos sí
entraron en julio, y como los ingresos ya son automáticos pidió marcarlos como
pagados y corregir después si alguna cifra sale mal.

Se ejecutó por `services.planned.confirm_payment`, no por SQL directo, para que
el saldo, el estado del movimiento y la ocurrencia se movieran juntos. Antes se
preservó el dump pre-migración como `quaestor-local-2026-08-02-pre-migration.dump`
(`just backup` usa la fecha como nombre y lo habría sobrescrito) y se tomó un
respaldo fresco.

```
                        antes         ->  después
🏦 Nu Débito     407.701.901 COP  ->  1.030.012.001 COP   (+622.310.100)
💵 DolarApp          694.488 USD  ->      1.074.488 USD   (+380.000)
tx 1634 / 1635        planned     ->  posted
ocurrencias           planned     ->  posted
```

Las ocurrencias quedaron en `posted`, así que ninguna corrida futura vuelve a
cobrar el 30 ni el 31 de julio. Ambas filas conservan `source=manual`, que es
históricamente correcto: las creó el modo manual anterior a 0009, no el motor.

**Pendiente para quien registre el extracto de julio:** estas dos ya están
posteadas, así que las líneas de sueldo del banco son duplicados — omitirlas o
borrarlas al importar.

**Evidencia:** la decisión escrita, fila por fila, o "0 filas".

## Qué NO está en este runbook

No hay provisioning, secretos, DNS ni consola de nube: la postura es local-only
(ADR-0026/0030) y esta feature no añade infraestructura. El despacho remoto de
agentes sigue apagado (`remote.ready: false`).
