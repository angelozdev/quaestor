---
slug: planned-payments-to-pay
checkpoint: 4
plan_status: approved
created: 2026-08-01
---

# Plan — 006 planned-payments-to-pay

Arquitectura confirmada por Angelo en sesión 2026-08-01. Cierra los 6
escenarios rojos de aceptación: AC-8 (deshacer una omisión, 3 rojos), AC-15
(ingresos fuera de la cola, 2 rojos) y AC-24 (total combinado en el chat, 1
rojo). Los otros 54 escenarios ya pasan contra el código actual — son el
candado de regresión de esta feature.

Sin cambio de esquema y sin migración: los tres cambios viven en servicios y
adaptadores.

## Architecture

### Deshacer una omisión (AC-8) — ADR-0034

`services/planned.py` gana `restore_payment(session, tx_id)`, el inverso
exacto de `skip_payment`: `skipped -> planned`, y si la fila venía de una
obligación mensual, su `RecurringOccurrence` vuelve a `planned`. Rechaza con
`IllegalTransition` lo que no esté en `skipped` y con `NotFound` lo que no
exista. No mueve saldo.

Restaurar la ocurrencia junto con la transacción no es un detalle: la
ocurrencia `skipped` es la marca que impide a `materialize_due` recrear esa
fecha. Dejarlas desincronizadas produciría un pago restaurado que la máquina
de recurrentes no reconoce.

`confirm_payment` sigue siendo la única puerta a `posted` — este cambio no
abre una segunda.

Superficies, por paridad (ADR-0006/0009): `POST /planned/{tx_id}/restore` en
`api/routers/planned.py` y herramienta `restore_payment` en `mcp/`,
clasificada **write-destructive** igual que `skip_payment` — o sea, fuera de
`LLM_ALLOWED_TOOLS`: el asistente no restaura por su cuenta.

Frontend: la acción vive en la **lista de transacciones**, no en "Por pagar"
(decisión de Angelo 2026-08-01). Esa pantalla ya muestra las filas omitidas
con su `StatusBadge` y ya filtra por estado, así que sólo se añade el botón
Restaurar en las filas cuyo estado sea omitido. "Por pagar" no gana una
tercera lista: lo omitido ya no es deuda y mezclarlo enturbiaría el total.

### La cola lleva sólo obligaciones (AC-15)

`services.planned.to_pay` filtra a gastos y transferencias; los ingresos
planeados quedan fuera de ambos grupos y, por tanto, del total.

El filtro se aplica en Python sobre las dos consultas que ya existen, no en
SQL. Las consultas ya vienen acotadas por estado y por fecha, así que el
conjunto sobre el que se filtra es de decenas de filas; meter un `IN` en el
`where` obligaría a ensanchar `list_transactions` — una función compartida por
todo el read path — para ganar nada medible. **Disparador para revisitarlo:**
si una ventana llega a cientos de filas planeadas, empujar el filtro a SQL
aprovechando el índice `ix_transaction_type_status_date`.

Radio de impacto — tres consumidores de `to_pay`:

| Consumidor | Efecto |
|---|---|
| `api/routers/planned.py` → pantalla y widget | Deja de mostrar ingresos planeados |
| `mcp/tools/temporal.py` → chat | Igual |
| `services/reports.py` línea de "pendientes" | Deja de contar ingresos planeados — coherente: pendiente es lo que se debe |

**No toca `safe_to_spend`.** Verificado: `services/budgets.py` calcula
`committed` desde `agg.month_planned_expense`, un camino distinto que ya era
sólo de gastos. Cero riesgo ahí.

### Total combinado en la respuesta del chat (AC-24)

`mcp/format.to_pay_table` conserva el subtotal por sección y añade una línea
de cierre con el total combinado **sólo cuando hay ambas secciones**. Una
respuesta de una sola sección se lee exactamente igual que hoy, así que el
cambio no altera el caso común. El número resultante es el mismo que el
titular de la pantalla, que es lo que AC-24 exige.

### Dónde vive el código

Respeta el layering del charter §2 — `api/` → `services/` → `domain/`:

- `domain/planned.py` (`OutstandingQueue`) **intacto**: sigue siendo un
  contenedor de dos listas. Qué entra en esas listas es política del sitio de
  construcción, que es donde ya vivía la exclusión mutua de los grupos
  (ADR-0023).
- `services/planned.py`: la transición nueva y el filtro.
- `api/routers/planned.py`, `mcp/registry.py`, `mcp/tools/temporal.py`,
  `mcp/format.py`: adaptadores delgados, sin lógica.
- Frontend: `lib/api/planned.ts` (o `transactions.ts`, según dónde caiga la
  acción) + la fila de la lista de transacciones.

Sin migración Alembic. Sin dependencias nuevas.

## Charter Check

| Regla del charter | Estado | Nota |
|---|---|---|
| §1 DAE + ATDD: la feature avanza por el pipeline de aceptación | ✅ | spec de 59 escenarios aprobado; baseline 54/6 rojo deliberado |
| §1 Decisiones arquitectónicas como ADR | ✅ | ADR-0034 escrita en este checkpoint (`proposed`), supersede en la práctica la cláusula "skipped = cancelado" del diseño P3 |
| §1 ADRs respetadas, nunca contradichas en silencio | ✅ | AC-20 mantiene la AC-9 de la 005 (lectura falla ruidosa, nunca asume tasa); la reversibilidad de la omisión se documenta en 0034 en vez de colarse |
| §2 Postura local-only (ADR-0026/0030) | ✅ | Sin infraestructura, sin migración, sin tocar Render |
| §2 Layering api → services → domain → db | ✅ | `domain/` intacto; lógica en `services/`; routers y tools delgados |
| §2 Paridad MCP + tiers (ADR-0020) | ✅ | `restore_payment` en REST y MCP; tier write-destructive como `skip_payment` |
| §3 Código/identificadores en inglés (ADR-0001); UI copy español | ✅ | `restore_payment`; copy "Restaurar" en español |
| §3 pnpm only / Biome / vitest colocado | ✅ | Sin dependencias nuevas |
| §3 Soft-delete uniforme (ADR-0005) | n/a | Aplica a masters; ADR-0034 explica por qué las transacciones no adoptan ese ciclo |
| §4 Alcance: finanzas personales, un usuario, local | ✅ | Sin superficie nueva fuera de eso |
| §6 Strict gate: tests backend Y frontend de la superficie tocada | ✅ | Test strategy abajo |
| §7 Autonomía medium + gates de datos | ✅ | Sin migraciones ni operaciones sobre `.dev-data/`; el merge a `main` sigue siendo humano |
| Auto: stance de autonomía | ✅ | medium; los overrides a low (`migrations/**`, `.dev-data/**`) no se activan — esta feature no toca esas rutas |
| Auto: independencia de verificación (Principio 7) | ✅ | CP7 verify con `agent_id` distinto al de CP5 implement |
| Auto: política de mutación | ✅ | `opt_in` en el manifest; se corre en CP8 sobre `services/planned.py` y `mcp/format.py` |
| Auto: presupuestos de performance | ✅ | Sección abajo (medium: informativos, no gate) |

**Amendments:** ninguno — sin desviaciones ⚠️.

## Phasing

- **F1 — Restaurar, backend (AC-8)**: `restore_payment` + sincronización de la
  ocurrencia + `POST /planned/{id}/restore` + herramienta MCP con tier
  destructivo + unit tests (rechazo de no-omitido, ocurrencia devuelta a
  pendiente, `materialize_due` no duplica después). Cierra 3 rojos.
- **F2 — La cola sólo obligaciones (AC-15)**: filtro en `to_pay` + unit tests
  (ingreso puntual planeado fuera, ingreso mensual manual fuera, total sin
  ingresos) + revisar la línea de "pendientes" del reporte mensual. Cierra 2
  rojos.
- **F3 — Total en el chat (AC-24)**: línea de cierre en `to_pay_table` + unit
  test MCP (dos secciones → total combinado; una sección → salida idéntica a
  hoy). Cierra 1 rojo.
- **F4 — Frontend**: acción Restaurar en las filas omitidas de la lista de
  transacciones + vitest colocado. Sin cambios en "Por pagar".
- **F5 — Cierre**: run de aceptación 60/60 verde en 006 y 124/124 global (002 y
  005 como candado de regresión), spec-check, suites backend y frontend
  completas, ADR-0034 a `accepted`.

F1, F2 y F3 son independientes entre sí — tocan funciones distintas del mismo
módulo y ningún rojo depende de otro. F4 depende de F1.

## Performance budgets

(Autonomía medium — informativos, no gate.)

- `restore_payment`: mismo perfil que `skip_payment` — una lectura de la
  transacción, una de la ocurrencia, un commit. Sin consultas nuevas.
- Filtro de la cola: cero consultas extra; descarta filas ya traídas. El coste
  es una comparación de enum por fila.
- `to_pay_table`: el total combinado reutiliza
  `OutstandingQueue.total_cop_cents`, el mismo método que usa el router REST.
  Eso implica una segunda pasada de conversión sobre las filas que cada sección
  ya convirtió — coste despreciable a esta escala (decenas de filas, y
  `to_cop_cents` corta en COP sin tocar Decimal) y es justamente lo que
  garantiza que el chat y la pantalla reporten la misma cifra
  (AC-24, paridad ADR-0006/0009).

## Collaboration schedule

- **Hecho**: ACs aprobadas (CP2), spec aprobado (CP3), arquitectura confirmada
  y ADR-0034 escrita (este plan).
- **Humano re-entra en**: (1) handoff de CP5 — revisión del diff; (2) aceptar
  o rechazar ADR-0034 antes del merge; (3) CP7 verify; (4) merge a `main`
  (§7 del charter).
- Umbral de bucle atascado: 3 (manifest).

## Execution modes

- CP5 en la rama `planned-payments-to-pay`, autonomía medium.
- Ningún override a `low` se activa: la feature no toca
  `backend/src/quaestor/migrations/**` ni `.dev-data/**`.
- Despacho a subagente implementador: **no automático en esta sesión** — la
  instrucción vigente de Angelo es que los subagentes sólo se lanzan cuando él
  lo pide. El handoff lo deja explícito en vez de asumirlo.
- Run de aceptación completo por ciclo (124 ejecuciones, ~7 s: barato — no hace
  falta modo de impacto).

## Test strategy

`feature.md` no declara `validation_method`, así que aplica el stack DAE por
defecto, explícito:

- **Aceptación**: `./run-acceptance-tests.sh features/006-planned-payments-to-pay`
  — baseline 54/6 rojo (60 ejecuciones); meta 60/60, y el run global 124/124
  con 002 y 005 intactas como candado de regresión.
- **Unit backend** (pytest host-side, SQLite en memoria): `restore_payment`
  (rechazo de no-omitido, ocurrencia sincronizada, sin movimiento de saldo,
  `materialize_due` idempotente después de restaurar); filtro de la cola
  (ingreso puntual y mensual excluidos, gasto y transferencia dentro, total sin
  ingresos); `to_pay_table` (total combinado con dos secciones, salida
  inalterada con una sola).
- **Paridad de superficies**: `tests/api/test_planned.py` (restore devuelve la
  fila a pendiente; restaurar algo no omitido se rechaza) y
  `tests/mcp/test_temporal.py` (`restore_payment` existe y está clasificada
  write-destructive, ausente de `LLM_ALLOWED_TOOLS`).
- **Frontend**: vitest colocado sobre la fila de la lista de transacciones — el
  botón Restaurar aparece sólo en filas omitidas y no en pendientes ni
  confirmadas.
- **Mutación** (CP8, `opt_in` en el manifest, alcance `changed_files`):
  `atdd:mutate` sobre `services/planned.py` y `mcp/format.py`.
- **Sin capa e2e** (charter §6): la superficie de navegador se cubre con vitest
  colocado, no con un runner de navegador.
