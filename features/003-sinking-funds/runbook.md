---
slug: 003-sinking-funds
checkpoint: 4
created: 2026-08-04
status: open
steps:
  - id: backup-before-migration
    description: "Dump the local production Postgres to iCloud before revision 0011 drops three tables and one column"
    owner: human
    command: "just backup"
    evidence: ""
    completed: false
    blocking_acs:
      - AC-26
      - AC-27

  - id: count-goals-and-budgets-live
    description: "Confirm production still holds exactly one goal, zero contributions, three unconfirmed proposals and zero budgets — the shape revision 0011 expects to delete"
    owner: human
    command: "QUAESTOR_ENV_FILE=backend/.env.local.postgres docker compose --env-file backend/.env.local.postgres --profile pg exec -T db psql -U \"${POSTGRES_USER:-quaestor}\" -d \"${POSTGRES_DB:-quaestor}\" -c \"select 'goal' as t, count(*) from goal union all select 'goal_contribution', count(*) from goal_contribution union all select 'budget', count(*) from budget union all select 'goal_tx', count(*) from \\\"transaction\\\" where goal_id is not null;\""
    evidence: ""
    completed: false
    blocking_acs:
      - AC-27

  - id: confirm-no-confirmed-goal-transfer
    description: "Confirm no goal proposal was ever confirmed — a posted goal transfer moved real money and must NOT be deleted silently"
    owner: human
    command: "QUAESTOR_ENV_FILE=backend/.env.local.postgres docker compose --env-file backend/.env.local.postgres --profile pg exec -T db psql -U \"${POSTGRES_USER:-quaestor}\" -d \"${POSTGRES_DB:-quaestor}\" -c \"select id, date, payee, status, amount, transfer_group_id from \\\"transaction\\\" where goal_id is not null order by date;\""
    evidence: ""
    completed: false
    blocking_acs:
      - AC-27

  - id: apply-migration-0011
    description: "Apply revision 0011 (pre-flight guard, delete unconfirmed goal proposals, drop goal / goal_contribution / budget and transaction.goal_id) to the local production Postgres"
    owner: human
    command: "just migrate"
    evidence: ""
    completed: false
    blocking_acs:
      - AC-26
      - AC-27

  - id: verify-drop-live
    description: "Confirm the tables are gone, the proposals are gone, and every other movement survived with its category intact"
    owner: human
    command: "QUAESTOR_ENV_FILE=backend/.env.local.postgres docker compose --env-file backend/.env.local.postgres --profile pg exec -T db psql -U \"${POSTGRES_USER:-quaestor}\" -d \"${POSTGRES_DB:-quaestor}\" -c \"select to_regclass('goal') as goal, to_regclass('goal_contribution') as contrib, to_regclass('budget') as budget;\" -c \"select type, count(*) from \\\"transaction\\\" group by type order by type;\" -c \"select version_num from alembic_version;\""
    evidence: ""
    completed: false
    blocking_acs:
      - AC-26
      - AC-27
---

# Runbook — 003 sinking-funds

Pasos que no son código. Todos son `human` por una razón sola: el charter §7
exige humano para migraciones de esquema sobre datos reales, y el manifest
fuerza autonomía `low` en `migrations/**`. Producción es el contenedor Postgres
local (ADR-0030); Render es standby congelado y no se toca.

**Esta migración es destructiva de una forma que la `0010` no era.** La `0010`
agregaba constraints y su `downgrade()` los tiraba sin perder nada. La `0011`
**elimina tres tablas y una columna**. Revertirla recupera el esquema, no los
datos. El respaldo del paso 1 no es ceremonia: es la única vuelta atrás.

Se corre entero **al abrir F2**, después de que F0 y F1 hayan aterrizado — la
app tiene que saber calcular con fondos antes de que se le quiten las metas y
los sobres.

## 1. Respaldo

```
just backup
```

`just migrate` ya está gated por respaldo: aborta si no existe un dump con la
fecha de hoy. Este paso lo hace explícito en vez de dejar que el gate falle.

Verificá que el dump sea un punto de restauración real y no un archivo que
simplemente satisface el gate de fecha — lo mismo que se hizo en la 008:
`pg_restore` de su `alembic_version` tiene que dar `0010`, y su sección de
esquema tiene que **contener** todavía `goal` y `budget`.

**Evidencia:** ruta del dump en `QuaestorBackups/quaestor-local-<fecha>.dump`, y
las dos comprobaciones de arriba.

## 2. Confirmar la forma que se va a borrar

Medido el 2026-08-02:

```
goal                 1 fila     ← "Korea", $10.000.000, deadline 2026-08-31
goal_contribution    0 filas
budget               0 filas    ← nunca se creó un sobre en la historia de la app
transaction con goal_id   3 filas ← 1 skipped 2026-06-30, 2 planned
```

Comando en el frontmatter (`count-goals-and-budgets-live`).

**Lo que tiene que salir:** exactamente esos cuatro números, o números que
puedas explicar. Pasó tiempo desde la medición y el dueño siguió usando la app.

**Si `budget` trae filas:** parar. Significa que alguien creó un sobre entre la
medición y hoy, y ese sobre tiene un significado que este plan asumió que no
existía. Se decide a mano antes de seguir.

**Evidencia:** la salida del `psql`.

## 3. Confirmar que ninguna propuesta se confirmó

Comando en el frontmatter (`confirm-no-confirmed-goal-transfer`).

Esto es el paso que más importa de todo el runbook.

AC-27 borra las propuestas **porque nunca movieron plata**: eran sugerencias de
una rutina de fin de mes que ya no existe. Una propuesta *confirmada* es otra
cosa — es una transferencia real, posteada, que cambió el saldo de dos cuentas.
Borrarla desharía un hecho.

**Lo que tiene que salir:** tres filas, todas con `status` en `planned` o
`skipped`. **Ninguna en `posted`.**

**Si aparece alguna `posted`:** parar. La revisión `0011` tiene que dejarla viva
y sólo soltarle el `goal_id` — sigue siendo una transferencia legítima entre dos
cuentas del dueño. Eso es un cambio al plan, no una decisión de la corrida.

**Evidencia:** la salida del `psql`, con las tres filas y sus estados.

## 4. Aplicar la revisión 0011

```
just migrate
```

Hace cuatro cosas, en este orden:

1. **Guarda previa** — cuenta transferencias `posted` con `goal_id`. Si hay
   alguna, se niega nombrando cuántas y no toca el esquema. Es la red por si el
   paso 3 se saltó, y es el equivalente exacto de la guarda que la `0010` puso
   sobre las filas sin categoría.
2. **Borra las propuestas sin confirmar** — las transferencias con `goal_id` en
   `planned` o `skipped`. AC-27.
3. **`DROP TABLE`** `goal_contribution`, `goal`, `budget`, en ese orden (la
   llave foránea manda).
4. **`DROP COLUMN`** `transaction.goal_id`.

**Gotcha:** el paso 4 usa `op.batch_alter_table` porque SQLite no sabe
`DROP COLUMN` sobre una tabla con constraints — reconstruye la tabla. En
Postgres emite un `ALTER` normal. Si algo falla aquí y no en la suite, mirar ahí
primero. Es el mismo mecanismo que la `0010`, por el mismo motivo.

**`downgrade()` recrea las tablas vacías y la columna nula.** No recupera la
meta ni las propuestas. Está escrito así a propósito y dicho en voz alta acá: la
vuelta atrás real es el dump del paso 1.

**Evidencia:** `select version_num from alembic_version;` → `0011`.

## 5. Verificar en vivo

Comando en el frontmatter (`verify-drop-live`). Tres cosas:

- `to_regclass` devuelve `NULL` para las tres tablas.
- **Los conteos de `transaction` por tipo son idénticos a antes menos tres**
  transferencias. AC-27 exige que todo lo demás sobreviva: cada gasto e ingreso
  con su categoría, cada transferencia sin ninguna. El CHECK de la 008 sigue
  vigente y lo respalda.
- `alembic_version` en `0011`.

**Evidencia:** salida del `psql`, con los conteos antes y después lado a lado.

## Qué NO está en este runbook

No hay provisioning, secretos, DNS ni consola de nube: la postura es local-only
(ADR-0026/0030) y esta feature no añade infraestructura. El despacho remoto de
agentes sigue apagado (`remote.ready: false`).

**No hay migración de la meta Korea a un fondo**, y no es un olvido. El dueño lo
decidió durante CP2 (`acs.md` decisión 9): los $10.000.000 existen pero nunca se
registraron, y el momento en que se siente a registrarlos es el momento en que
cree el fondo. La app arranca vacía (AC-20).

**No hay migración de sobres** porque nunca existió ninguno: cero filas en
`budget` en toda la historia de la app.
