---
title: "Los movimientos se filtran por monto y por grupo, y cada vista lleva a los suyos"
slug: transaction-filters-and-drilldown
number: 017
status: done
autonomy_level: medium
branch: transaction-filters-and-drilldown
area: core
owner: angelo
assignee: local
tracker_ref: local
roadmap_ref: transaction-filters-and-drilldown
acceptance_stream: mixed
relevant_adrs: [0031]
created: 2026-08-19
intake: roadmap
validation_method: "Los tres flujos (pytest, aceptación generada, vitest), más una pasada en el navegador (CHARTER §6) confirmando el filtro de monto con conversión TRM contra un movimiento en USD y uno en COP, el filtro por grupo devolviendo las categorías correctas, y el enlace «Ver movimientos» desde categorías/grupos/etiquetas llegando ya filtrado."
---

# Los movimientos se filtran por monto y por grupo, y cada vista lleva a los suyos

## Outcome

El dueño puede pedir "qué gasté más de 100.000" o "todo lo de Transporte" y
la app responde — hoy ninguna de las dos preguntas tiene dónde hacerse. Un
filtro de monto (mayor que / menor que, comparado siempre en pesos vía la
TRM) se suma a los que ya existen, un filtro por grupo trae de una vez las
categorías de ese grupo, y las pantallas de grupos, categorías y etiquetas
ganan un botón que lleva directo a los movimientos ya filtrados. La barra
de filtros, hoy una fila plana de siete controles del mismo peso, se
reordena para que los que el dueño usa no se pierdan entre los que no usa.

## Por qué

Pedido por Angelo el 2026-08-09: "filtros de transacciones con mayor que /
menor que, filtrar por grupo además de por cuenta, y un botón o dropdown en
las vistas de grupos, categorías y etiquetas que lleve a los movimientos ya
filtrados — que sea mucho más user friendly".

**Medido contra el código, no asumido.** El pedido se parte en partes
desiguales:

- **Categoría y etiqueta ya se filtran hoy** — `transactions/page.tsx`
  renderiza sendos `EntitySelect`, cableados vía `TX_FILTER_SCHEMA` a
  `category_id`/`tag` en la API. Es la tercera vez que este patrón
  aparece (fondo vs. presupuesto, la nomenclatura del asistente, y ahora
  esto): la mitad de lo pedido ya está construido y el dueño no lo
  encontró, porque la barra no distingue lo que usa de lo que no.
- **El filtro de monto no existe en ninguna capa** — `rg
  amount_min|amount_max` no devuelve nada en todo el repo: ni en
  `list_transactions` (`services/transactions.py:449`, que hoy toma
  cuenta/categoría/etiqueta/tipo/estado/transfer_group/fecha y nada más),
  ni en el router, ni en `ListTransactionsInput` del MCP, ni en la UI. Es
  nuevo en las cuatro puertas a la vez, y el asistente debería poder
  responder "qué gastos pasan de 500.000" tanto como la pantalla.
- **El filtro por grupo no existe** — `Category.group_id` y la tabla
  `category_group` son reales y la pantalla de grupos los administra, pero
  ningún filtro los lee hoy. Producción tiene 10 grupos activos sobre 41
  categorías activas (8 en Transporte, 5 en Personal & Lifestyle, 5 en
  Servicios, 5 en Ingresos, 3 en Finanzas) — filtrar Transporte a mano hoy
  son ocho miradas separadas.

**Dos decisiones ya tomadas por el dueño**, la misma sesión:

1. El grupo es un filtro propio, no una multiselección de categorías — se
   elige "Finanzas" y llegan sus tres categorías juntas, sin poder sacar
   una del resultado.
2. La comparación de monto siempre se hace en pesos, convirtiendo a la TRM
   — un cargo de USD 37,20 entra en un filtro "mayor a 100.000" porque hoy
   vale ~150.000 COP, junto a los 250.000 cargados en pesos. Sigue de
   ADR-0031 (conversión a tiempo de lectura, sin cifra en COP guardada por
   movimiento): el mismo filtro puede devolver una lista distinta mañana
   si la TRM cambió, sin que el movimiento se haya tocado.

**El drill-down es la parte barata.** Los filtros ya viven en la URL —
`useUrlFilters` codifica cada uno como query param y `TX_FILTER_SCHEMA` los
nombra igual que la API, así que `/transactions?category_id=7` ya
funciona hoy escribiéndolo a mano; solo falta el link que lo produzca.
`DataTable` ya acepta `actions?: RowAction<T>[]` — el mismo array que
dibuja Editar/Archivar en categorías, grupos y etiquetas — así que "Ver
movimientos" es una entrada más ahí, apuntando a una forma de URL que ya
existe.

## Scope

**Dentro:**

- `amount_min`/`amount_max` (enteros en centavos COP) sumados a
  `list_transactions`, al router REST, a `ListTransactionsInput` del MCP,
  y a la barra de filtros — comparando siempre en pesos vía la tabla TRM.
- `group_id` sumado en las mismas cuatro puertas — un parámetro propio que
  hace join contra `category`, sin volverse multiselección de
  `category_id`.
- Botón/acción "Ver movimientos" en las filas de las pantallas de grupos,
  categorías y etiquetas — reutiliza `RowAction` de `DataTable` y arma la
  URL con `useUrlFilters`/`TX_FILTER_SCHEMA`.
- La barra de filtros se reordena para sostener nueve controles sin que
  los usados se pierdan entre los que no — agrupación visual y/o conteo de
  filtros activos, a decidir en discover-acs mirando la pantalla.
- **Riesgo aceptado, documentado, no bloqueante** (decisión del dueño
  2026-08-19): dos movimientos siguen en negativo hoy — un retiro de Tyba
  (29.084.436,55 COP) y uno de a2censo (1.500.000 COP), ambos pendientes
  de modelarse como transferencia entre cuentas propias
  (`id:amount-must-be-positive`, roadmap). Mientras eso no se resuelva,
  esas dos filas pueden comportarse raro bajo "menor que" (aparecer como
  el gasto "más chico" siendo en realidad un retiro grande). El filtro se
  construye igual; el comportamiento sobre esas dos filas queda anotado
  como limitación conocida, no como AC a cumplir.

**Fuera:**

- **Resolver Tyba/a2censo de fondo** — es `id:amount-must-be-positive`,
  ítem propio del roadmap, con su propia migración (`amount > 0` en 7
  columnas), su propia ADR y su propio tope de autonomía `low` en
  `migrations/**`.
- **El rediseño visual completo de la barra** (Impeccable) — esta feature
  reordena y agrupa los controles existentes más los dos nuevos; no
  rehace el sistema de diseño. `id:impeccable-ui-overhaul` ya nombra esta
  pantalla como candidata a un pase posterior con esa herramienta.
- **`daily-trm-fetch`** — si la TRM del día falta, ADR-0031/038 ya hacen
  de eso un hard stop en toda lectura; esta feature hereda ese
  comportamiento, no lo cambia.

## Charter signals

- **Una pantalla que muestra dinero se prueba en el navegador** (CHARTER
  §6): el filtro de monto convierte a pesos vía TRM en vivo — el mismo
  tipo de cifra que ya salió mal una vez en el aviso de un fondo.
- Sin migración de esquema — ningún campo nuevo en la base, así que el
  tope `low` de `migrations/**` no aplica a esta feature.

## Related code / design pointers

- `backend/src/quaestor/services/transactions.py:449` — `list_transactions`,
  hoy sin `amount_min`/`amount_max`/`group_id`
- `backend/src/quaestor/domain/models.py:96` — `Category.group_id`, ya
  existe; `category_group`, la tabla que lo respalda
- `backend/src/quaestor/mcp/tools/core.py` — `ListTransactionsInput`, la
  cuarta puerta
- `frontend/lib/filter-schemas.ts` — `TX_FILTER_SCHEMA`, donde nombrar los
  dos parámetros nuevos
- `frontend/lib/use-url-filters.ts` — ya codifica cada filtro como query
  param; el drill-down se apoya en esto sin cambios
- `frontend/components/data-table.tsx:22` — `RowAction<T>`, ya usado por
  Editar/Archivar en categorías, grupos y etiquetas
- `frontend/app/(app)/transactions/page.tsx` — la barra de filtros actual,
  siete controles sin agrupar
- ADR-0031 — conversión FX a tiempo de lectura; por qué la comparación de
  monto no puede ser un `WHERE amount > X` directo contra la columna

## Riesgos

**Que "menor que" sin resolver el signo de Tyba/a2censo confunda al dueño
antes de que `amount-must-be-positive` cierre.** Aceptado explícitamente
como riesgo conocido — ver Scope. Si en el uso real resulta más molesto de
lo previsto, la salida es adelantar ese ítem del roadmap, no parchear este
filtro con una regla de signo ad hoc.

**Que la conversión a pesos en el filtro sea lenta o pesada sobre 669+
movimientos.** ADR-0031 ya resolvió esto para las pantallas que leen; el
filtro de monto es la primera vez que esa conversión decide qué filas
*entran* a una lista, no solo cómo se muestran — a resolver en plan si hace
falta un SQL contra la tabla TRM o un filtro aplicado después de leer.
