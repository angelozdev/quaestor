---
slug: transactions-crud
checkpoint: 4
plan_status: approved
created: 2026-07-31
---

# Plan — 002 transactions-crud

Arquitectura confirmada por Angelo en sesión 2026-07-31. Cierra los 5
escenarios rojos de aceptación (AC-5 borrado de transferencias, AC-6/AC-15
quitar tags) más el toque frontend de AC-10.

## Architecture

### Dirección almacenada por leg (AC-5) — ADR-0032

Columna nueva `transfer_direction` en `Transaction` (`out` | `in`, nullable —
solo legs de transferencia la llevan). `transfer()` la asigna al crear cada
leg.

`delete_transaction` pierde el rechazo de transfers y gana la rama de par:
si el tx es un leg, carga ambos legs por `transfer_group_id`, revierte cada
saldo según su dirección (`out` → devuelve `amount` a su cuenta; `in` → lo
resta), borra ambos rows + sus tag links — commit atómico, rollback ante
cualquier fallo (mismo patrón try/except del `transfer()` actual).

**Migración Alembic 0006** (add column + backfill): dentro de cada
`transfer_group_id`, el `id` menor siempre fue el leg origen — invariante
verificada en todas las versiones de `transfer()` (P0 y post-005: el leg
origen entra primero en `session.add_all`). El backfill materializa eso una
vez; en adelante la dirección es dato, no inferencia. SQLite dev vía
`batch_alter_table`; Postgres real con humano al volante (runbook.md, con
la lección de 005: backup con solo el contenedor `db` arriba, porque las
migraciones corren solas en el boot del api).

**Alternativas descartadas** (detalle en ADR-0032): montos con signo (rompe
la invariante P0 "amount siempre positivo"), entidad TransferGroup (peso sin
requisito que lo pida), inferencia por id en runtime (invariante oculta
load-bearing para siempre).

### Tags en todas las superficies (AC-6 / AC-15)

- **Servicio** (`services/tags.py`): nueva `untag_transaction(session,
  tx_id, tags)` — quita links, idempotente (tag ausente = no-op); y
  `set_transaction_tags(session, tx_id, tags)` — replace-set compuesto de
  add + remove, para la superficie REST.
- **REST**: `tags: list[str] | None` en `TransactionCreate` y
  `TransactionUpdate` — replace-set cuando viene, `None` = no tocar.
  `TransactionOut` gana `tags: list[str]` (los escenarios "viewing the
  expense shows the tags" leen esta superficie).
- **MCP**: `update_transaction` gana `add_tags: list[str]` y
  `remove_tags: list[str]` (ergonomía conversacional); `record_*` ya
  acepta `tags`. Tier write-safe, sin cambios de política (ADR-0020).
- **UI**: campo de tags (chips con autocompletado de `GET /tags`) en
  `transaction-create-dialog` y `transaction-edit-dialog`; el filtro por
  tag ya existe.
- **Handlers rojos**: los 2 tests apuntan a nombres intencionales
  (`tags.untag_transaction`, `mcp.tools.transactions.remove_transaction_tag`);
  al implementar, el binding se ata a la API real — ajuste legítimo, la
  aserción de comportamiento no cambia.

### Par visible al editar (AC-10, frontend)

`TransactionOut` ya expone `transfer_group_id`. El edit dialog de un leg
muestra badge "parte de una transferencia" + datos de la contraparte
(cuenta y monto, vía la lista filtrada por grupo que ya sirve el API). Los
campos de monto quedan visualmente fuera (ya son inmutables en backend).

### Data flow (resumen)

```
crear:    dialog/MCP → transactions.transfer (setea direction) → DB
borrar:   dialog/MCP → transactions.delete_transaction
            ├─ expense/income: reversa single (hoy)
            └─ transfer leg: carga par por grupo → reversa por direction
               → borra ambos (atómico)
tags:     REST PATCH (replace-set) ─┐
          MCP add/remove_tags ──────┴→ tags.tag/untag_transaction → links
```

Capas intactas (`api → services → domain → db`); cero rutas de lectura
nuevas (ADR-0028 no se toca); reports/budgets filtran por tipo y nunca leen
`transfer_direction`.

## Charter Check

| Regla del charter | Estado | Nota |
|---|---|---|
| §1 DAE + ATDD: la feature avanza por el pipeline de aceptación | ✅ | spec 33 escenarios aprobado; baseline 59/5 rojo deliberado |
| §1 Decisiones arquitectónicas como ADR | ✅ | ADR-0032 (schema) escrito y aceptado en este checkpoint |
| §2 Postura local-only (ADR-0026/0030) | ✅ | Migración 0006 solo en el Postgres local; Render intocado |
| §2 Layering api → services → domain → db | ✅ | Dirección en domain/model, lógica de par en services, routers thin |
| §2 Paridad MCP + tiers (ADR-0006/0009/0020) | ✅ | add/remove_tags y delete de par en ambas superficies; tier write-safe sin cambios |
| §3 Código/identificadores en inglés (ADR-0001); UI copy español | ✅ | `transfer_direction`, `untag_transaction`; copy del badge en español |
| §3 pnpm only / Biome / vitest colocado | ✅ | Sin dependencias nuevas |
| §3 Soft-delete uniforme (ADR-0005) | n/a | Aplica a masters; el borrado permanente de transacciones quedó decidido en AC-4 |
| §6 Strict gate: tests backend Y frontend de la superficie tocada | ✅ | Test strategy abajo |
| §7 Autonomía medium + gates de datos | ✅ | `migrations/**` → low per manifest; runbook con humano |
| Auto: stance de autonomía | ✅ | medium; override low en `backend/src/quaestor/migrations/**` y `.dev-data/**` |
| Auto: independencia de verificación (Principio 7) | ✅ | CP7 verify con `agent_id` distinto al implementador |
| Auto: política de mutación | ✅ | `atdd:mutate` sobre `transactions.py`/`tags.py` en CP8 |
| Auto: presupuestos de performance | ✅ | Sección abajo (medium: informativos) |

**Amendments:** ninguno — sin desviaciones ⚠️.

## Phasing

- **F1 — Dirección + borrado de par (backend)**: modelo
  `transfer_direction` + migración 0006 (backfill) + `transfer()` setea +
  `delete_transaction` rama de par + unit tests (par mismo-currency,
  cross-currency, backfill, atomicidad). Cierra los 3 rojos de AC-5.
- **F2 — Tags backend**: `untag_transaction`/`set_transaction_tags` +
  REST (`tags` en create/patch/out) + MCP (`add_tags`/`remove_tags`) +
  re-binding de los 2 handlers rojos a la API real + unit tests. Cierra
  AC-6/AC-15.
- **F3 — Frontend**: chips de tags en create/edit dialogs + badge/contraparte
  de transferencia en el edit dialog + habilitar borrar transferencia en la
  lista + vitest colocado.
- **F4 — Cierre**: run completo de aceptación 64/64 verde (59+5), spec-check,
  suites backend/frontend completas.

## Performance budgets

(Autonomía medium — informativos, no gate.)

- Borrado de par: máximo 2 queries extra sobre el borrado actual (par por
  grupo + cuentas ya en sesión).
- Tags replace-set: O(tags del tx) queries, sin N+1 sobre la lista.
- Migración 0006: segundos sobre los datos reales (una pasada de UPDATE por
  grupos).

## Collaboration schedule

- **Hecho**: arquitectura confirmada + ADR-0032 aceptado (este plan).
- **Auto**: CP5 implement se despacha solo (autonomía medium).
- **Humano re-entra en**: (1) handoff CP5 — revisión del diff; (2) CP7
  verify; (3) runbook — migración 0006 sobre datos reales (backup db-only
  primero); (4) merge a main (§7).
- Stuck-loop threshold 3 (manifest).

## Execution modes

- CP5 vía subagente implementador, branch `transactions-crud`, autonomía
  medium.
- Paths a low (manifest): `backend/src/quaestor/migrations/**` y
  `.dev-data/**` — el implementador escribe 0006 pero NO la ejecuta contra
  datos reales; eso es del runbook.
- Run de aceptación completo por ciclo (64 ejecuciones, ~2 s: barato).

## Test strategy

`feature.md` sin `validation_method` → stack DAE por defecto, explícito:

- **Aceptación**: `./run-acceptance-tests.sh features/002-transactions-crud`
  — baseline 33/5 rojo (38 ejecuciones); meta 38/38, y el run global
  64/64 (005 intacto como candado de regresión).
- **Unit backend**: pytest host-side; nuevos: dirección en `transfer()`,
  reversa de par (mismo y distinto currency), backfill 0006 (seed
  rev-0005 → upgrade head), `untag_transaction` idempotente, replace-set,
  MCP add/remove_tags.
- **Unit frontend**: vitest colocado — chips de tags (create/edit), badge de
  par en el edit dialog, acción de borrar transferencia.
- **Mutación**: `atdd:mutate` sobre `services/transactions.py`,
  `services/tags.py` en CP8.
- **Gate estricto (§6)**: backend + frontend verdes para la superficie
  tocada antes de merge; run de aceptación completo antes de push.
- **Datos reales**: la migración 0006 se valida vía runbook (humano);
  AC-5 no se declara cerrado en CP7 sin los pasos del runbook completados
  sobre el Postgres real.
