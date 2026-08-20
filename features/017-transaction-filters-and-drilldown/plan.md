---
slug: transaction-filters-and-drilldown
checkpoint: 4
plan_status: proposed
created: 2026-08-19
---

# Plan — 017 transaction-filters-and-drilldown

## Architecture

### La decisión de fondo

**El monto se filtra en Python, después de leer; el grupo se filtra en
SQL, antes de leer.** No son la misma clase de filtro. `Category.group_id`
es una FK real — un join más, igual que ya hacen `category_id`/`account_id`
en `list_transactions`. El monto en cambio compara cifras en monedas
distintas, y este proyecto ya tiene un patrón fijo para eso (ADR-0031):
`services/reports.py` y `month_aggregate.py` traen las filas y, por cada
una, `to_cop_cents(tx.amount, tx.currency, trm)`. El filtro de monto copia
ese patrón exacto — trae lo que las otras columnas ya filtran, y en Python
se queda solo con las filas cuyo equivalente en pesos cae en el rango.

`list_transactions` llama `fx.get_trm(session)` ella misma, pero solo
cuando viene `amount_min` o `amount_max` — un listado sin filtro de monto
no exige TRM a nivel de servicio.

### AC-14 (sin TRM, el filtro de monto se bloquea) no pide código nuevo

El router REST ya llama `fx.get_trm(session)` de forma incondicional en
**cada** listado, para calcular `cop_equivalent` de salida
(`api/routers/transactions.py:47`). El AC no necesita un candado nuevo —
necesita quedar probado, y `spec.md` ya lo prueba.

### Las cuatro puertas

- **`services/transactions.py::list_transactions`** — gana `amount_min:
  int | None`, `amount_max: int | None`, `group_id: int | None`, misma
  forma que los kwargs que ya existen.
- **`api/routers/transactions.py`** — tres query params nuevos,
  passthrough directo, sin lógica propia.
- **`mcp/tools/core.py::ListTransactionsInput`** — gana `amount_min`,
  `amount_max`, `group: str | None` (por **nombre**, como ya hace
  `category`/`account` en el mismo modelo). El resolutor de nombre→id **ya
  existe y no se usaba todavía**: `_resolve_category_group_by_name`
  (`core.py:162`).
- **Frontend** — `TX_FILTER_SCHEMA` (`filter-schemas.ts`) gana los tres
  campos; la barra de filtros se reordena (Cuándo/Qué/Cuánto/Estado,
  contador de activos + Limpiar, decidido en CP2); `RowAction` "Ver
  movimientos" se suma en `DataTable` de categorías, grupos y etiquetas,
  armando la URL con el mismo `TX_FILTER_SCHEMA` que `useUrlFilters` ya
  lee (`frontend/app/(app)/transactions/page.tsx:284` es el precedente
  directo: la URL ya es la fuente de verdad, ADR-0027).

### Validación del rango y del monto negativo

Cliente, reutilizando el patrón `positiveCents`/Zod que ya usan
transacciones/recurrentes/fondos/metas — no una puerta nueva en el
backend. El mensaje del monto negativo reusa el texto exacto que 016 ya
fijó ("El monto debe ser mayor que cero"), en vez de inventar uno nuevo
para el mismo error.

### Alternativa considerada y descartada

**Pasar `trm` desde el router hacia el servicio**, en vez de que
`list_transactions` lo pida ella misma. Se descartó: acoplaría el filtro
de monto a un valor que hoy el router solo calcula para *formatear* la
salida (`TransactionOut.from_txs`), y `month_aggregate.py` ya establece el
precedente de que un servicio resuelve su propia dependencia de lectura
(`_fx.get_trm(session)` interno). Mantiene `list_transactions` autosuficiente
y probable en aislamiento.

## Charter Check

| # | Regla del charter | Estado | Evidencia |
|---|---|---|---|
| §1 | DAE con ATDD completo; ADRs para lo arquitectónico | ✅ | `feature.md`, `acs.md`, `spec.md` + IR existen, pipeline generado y en rojo (CP3). Sin ADR nueva — ver Amendments. |
| §2 | Posture local-only; capas `api/ → services/ → domain/ → db`; migraciones en `migrations/` | ✅ | Nada remoto. El filtro de monto vive en `services/`, usa `domain/money.py` ya existente — no cruza capas. Sin migración: `Category.group_id` ya existe, `amount_min`/`amount_max` son parámetros de lectura, no columnas. |
| §2 | URL como fuente de verdad para filtros de lista (ADR-0027) | ✅ | El feature entero se apoya en `useUrlFilters`/`TX_FILTER_SCHEMA` ya existentes — los reafirma, no los rodea. |
| §2 | Superficie MCP con paridad REST + política de tiers (ADR-0020) | ✅ | `list_transactions` ya está en `CORE_TOOL_NAMES` (tier de lectura) — sumar campos de filtro no cambia su tier, sigue siendo lectura pura. |
| §3 | Inglés en el código; Python ≥3.12 + uv + pytest; pnpm; Biome; Conventional Commits | ✅ | `amount_min`/`amount_max`/`group_id` son identificadores en inglés; las etiquetas ("Monto mínimo", "Grupo") son las únicas en español, como siempre. |
| §4 | Un solo usuario, local | ✅ | No agrega superficie fuera del alcance declarado. |
| §5 | Roles architect / implementer / acceptance-tester / reviewer | ✅ | CP4 architect (este plan), CP5 implementer, `spec.md` ya lo escribió el bridge de `atdd:atdd` + `pipeline-builder`, CP6–CP8 reviewer independiente. |
| §6 | Nada mergea sin backend **y** frontend verdes en la superficie tocada | ✅ | Stream `mixed`: 12 escenarios `@backend` (pytest) + 9 de pantalla (vitest). |
| §6 | Una pantalla que escribe plata se prueba contra una cuenta en otra moneda | N/A | Esta feature no escribe dinero — filtra y navega. Ningún movimiento se crea ni se corrige aquí. |
| §6 | Una cifra que la app convierte se prueba en otra moneda también | ✅ | AC-13 y AC-15 son exactamente esto: el filtro de monto compara un movimiento en USD, y el mismo filtro cambia de respuesta cuando cambia la TRM — ambos ya en `spec.md`, `@backend`. |
| §6 | Verde no es verificado: se maneja en navegador antes de darla por hecha | ✅ | Programado al cierre de la Rebanada 4 / CP7: los tres casos que `validation_method` nombra (monto con cuenta en dólares, filtro de grupo, "Ver movimientos"). |
| §7 | Autonomía media con puertas de datos | ✅ | Ninguna rebanada toca `migrations/**` — el tope `low` del manifiesto no se activa. |
| §7 | Humano obligatorio para merges a `main` | ✅ | El merge es del dueño. |
| — | Postura de autonomía declarada | ✅ | `medium`, sin excepción. |
| — | Independencia de la verificación | ✅ | `spec.md` quedó en rojo (10 fallan, 2 pasan por una razón documentada y aceptada) **antes** de este plan (CP3, 2026-08-19) — el pipeline se generó por un agente distinto de quien va a implementar. |
| — | Política de mutación | ✅ | Opt-in para esta feature (default del manifiesto). Blanco natural en CP8: los límites del rango de monto (`>=`/`<=`/`entre`, el caso de un solo extremo) y el join de grupo — exactamente los operadores que mutation testing invierte. Recordatorio heredado: la suite de backend no es hermética (`test_scheduler` toca `backend/quaestor.db` en disco) — correr el sweep sobre un worktree limpio. |

### Amendments

**Ninguna enmienda al charter.** La única fila N/A no es una desviación —
la regla existe para pantallas que escriben dinero, y esta feature nunca
escribe. No hay ⚠️ que arrastrar; ninguna decisión de esta feature
contradice una ADR aceptada (ADR-0027, ADR-0031, ADR-0020 se reafirman, no
se tocan).

## Phasing

Cuatro rebanadas — cada una atraviesa lo que hace falta de dominio, API y
pantalla, y cada una termina con sus escenarios en verde.

### Rebanada 1 — El monto se filtra, en las tres puertas de lectura

*AC-1, AC-7 (mitad monto), AC-8, AC-13, AC-14, AC-15 · 8 escenarios `@backend`*

`list_transactions` gana `amount_min`/`amount_max` y el post-filtro vía
`to_cop_cents`. El router pasa los query params. `ListTransactionsInput`
gana los mismos dos campos. Sin UI todavía — se prueba por servicio, REST
y MCP directamente.

Termina cuando los 8 escenarios `@backend` de monto pasan, y el resto de
la suite de transacciones (002, 012, 013, 015, 016) sigue exactamente
igual.

### Rebanada 2 — El grupo se filtra, en las tres puertas de lectura

*AC-2, AC-7 (mitad grupo), AC-10, AC-12 · 4 escenarios `@backend`*

`list_transactions` gana `group_id` (join vía `Category.group_id`). El
router lo pasa. `ListTransactionsInput` gana `group: str | None`, resuelto
con `_resolve_category_group_by_name` (ya existe, sin usar hasta ahora).

Termina cuando los 4 escenarios `@backend` de grupo pasan, sin tocar el
comportamiento de la Rebanada 1.

### Rebanada 3 — La barra se reordena, y avisa el rango que no tiene sentido

*AC-3, AC-9 · 4 escenarios vitest*

`TX_FILTER_SCHEMA` gana los tres campos nuevos (monto mín/máx, grupo). La
barra de `/transactions` se reagrupa en Cuándo/Qué/Cuánto/Estado, con
contador de filtros activos y el link Limpiar. Un rango invertido se avisa
en el momento, en español. **AC-15 original (monto negativo) se retiró en
CP5**: el input de monto reusa `MoneyInput`, que ya usa cada formulario de
dinero de la app y no deja escribir el signo menos — no hay un negativo
real que rechazar, y construir un input aparte solo para este filtro habría
sido inconsistente con el resto de la app.

Termina cuando los 5 escenarios vitest de esta rebanada pasan y la barra
sigue mostrando Categoría/Etiqueta/Cuenta/Tipo/Fecha exactamente como hoy.

### Rebanada 4 — Ver movimientos, y el paso por navegador

*AC-4, AC-5, AC-6, AC-11 · 4 escenarios vitest*

`RowAction` "Ver movimientos" en las tablas de Categorías, Grupos y
Etiquetas — arma la URL con el campo correspondiente de `TX_FILTER_SCHEMA`
y navega. Funciona igual desde una fila archivada (el soft-delete de
ADR-0005 no oculta el historial).

**Cierra con el paso por navegador de CHARTER §6**, contra el sandbox: el
filtro de monto con una cuenta en dólares, el filtro de grupo trayendo sus
categorías, y "Ver movimientos" aterrizando ya filtrado — los tres casos
que `validation_method` nombra.

## Performance budgets

Sin consulta nueva por el lado del grupo (un join); el monto es un
recorrido `O(n)` en Python sobre lo que las demás columnas ya filtraron —
mismo costo que ya paga `month_aggregate.py` hoy por cada mes que agrega.

| presupuesto | hoy | techo | por qué |
|---|---|---|---|
| filas convertidas por listado con filtro de monto | 0 | tamaño de la tabla `transaction` tras los demás filtros (~700 en producción hoy) | un `to_cop_cents` por fila, ya el patrón de `reports.py` |
| consultas nuevas a la base por el filtro de monto | — | **cero** | se resuelve sobre las filas ya traídas, no una consulta aparte |
| consultas nuevas a la base por el filtro de grupo | — | **uno** (join) | mismo costo que ya tiene filtrar por `category_id` |

Si la tabla `transaction` crece a un orden de magnitud más (~10.000 filas),
revisar si el filtro de monto conviene expresarlo contra la tabla TRM en
SQL en vez de en Python — no antes, medir primero.

## Collaboration schedule

| momento | quién | qué |
|---|---|---|
| antes de la rebanada 1 | dueño | aprueba este plan |
| fin de cada rebanada | agente | reporta escenarios verdes y qué queda rojo |
| fin de la rebanada 4 | **dueño + agente** | paso por navegador contra el sandbox (CHARTER §6) — sin este paso la feature no se da por hecha |
| merge a `main` | **dueño** | CHARTER §7 |

## Execution modes

- **Las cuatro rebanadas:** autonomía `medium` — ninguna toca
  `migrations/**`, así que el tope `low` del manifiesto no se activa en
  ningún punto.
- **Sin dispatch remoto:** `remote.ready: false` en el manifiesto.
- **Una rebanada, un commit**, Conventional Commits, escenarios de esa
  rebanada verdes antes de la siguiente.

## Test strategy

`feature.md` declara su propio `validation_method`:

> «Los tres flujos (pytest, aceptación generada, vitest), más una pasada
> en el navegador (CHARTER §6) confirmando el filtro de monto con
> conversión TRM contra un movimiento en USD y uno en COP, el filtro por
> grupo devolviendo las categorías correctas, y el enlace «Ver
> movimientos» desde categorías/grupos/etiquetas llegando ya filtrado.»

Los tres flujos estándar corren en cada rebanada (`./run-acceptance-tests.sh
features/017-transaction-filters-and-drilldown`, más `uv run pytest -q` y
`pnpm vitest run` completos antes de cerrar cada una). El paso por
navegador es exclusivo de la Rebanada 4, contra el sandbox, y es la
condición de cierre de la feature — no una verificación aparte.

**Mutación (CP8):** opt-in, sweep chico sobre los límites del rango de
monto y el join de grupo (ver Charter Check).
