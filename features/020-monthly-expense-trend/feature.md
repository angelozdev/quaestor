---
title: "La evolución del gasto se lee en la misma pantalla del mes, por grupo y mes a mes"
slug: monthly-expense-trend
number: 020
status: done
autonomy_level: medium
branch: monthly-expense-trend
area: reports
owner: angelo
assignee: local
tracker_ref: local
acceptance_stream: mixed
relevant_adrs: [0002, 0004, 0006, 0009, 0028, 0031, 0044, 0045, 0050, 0057, 0061]
created: 2026-08-22
intake: discuss
validation_method: "Los tres flujos (pytest, aceptación generada, vitest), más una pasada en el navegador (CHARTER §6): sembrar gasto en al menos 3 meses distintos repartido en al menos 2 grupos, abrir la pestaña Evolución y confirmar que las barras apiladas y la tabla categoría x mes coinciden con lo sembrado, mes por mes y categoría por categoría."
---

# La evolución del gasto se lee en la misma pantalla del mes, por grupo y mes a mes

## Outcome

El dueño abre la pestaña "Evolución" dentro de Reportes, junto a la pestaña
"Mes" que ya existe, y ve de un vistazo los últimos 12 meses de gasto —
siempre terminando en el mes actual — para saber qué tanto gastó y en qué
grupos de categorías viene subiendo o bajando mes a mes. Un gráfico de barras
apiladas (una por mes, un color por grupo) contesta "¿en qué se me fue la
plata este último año?"; una tabla debajo, categoría por mes, contesta "¿y en
esta categoría puntual?".

## Por qué

El dueño ya lee cada mes suelto en la pestaña "Mes", pero no puede ver si
"Restaurantes" viene subiendo tres meses seguidos, o si "Transporte" se disparó
en agosto contra julio, sin abrir un mes a la vez y hacer la cuenta a mano.
Ejemplo concreto que motivó el pedido: si en junio el grupo Comida costó
$500.000, en julio $650.000 y en agosto $480.000, hoy esa historia no se
puede leer en ningún lado junta — hay que entrar mes por mes y anotar.

## Decisiones ya tomadas con el dueño

1. Evolución continua por categoría/grupo a lo largo del tiempo — no una
   comparación puntual de dos meses elegidos a mano.
2. Rango fijo: últimos 12 meses, siempre terminando en el mes actual —
   independiente del selector de mes que ya existe en la pestaña "Mes".
3. Vive como pestaña nueva dentro de Reportes, no como pantalla nueva en el
   menú.
4. Solo gasto — no ingreso, igual que `by_category`/`by_group` hoy.
5. El gráfico apila por grupo de categoría (~10 grupos activos en
   producción), no por categoría (~40) — 40 barras/líneas por mes no se leen.
6. Debajo del gráfico, una tabla matriz completa — una fila por categoría, una
   columna por cada uno de los 12 meses — sin necesitar click ni filtro.
7. Librería de gráficos: Recharts, verificada contra industria antes de
   elegirla — es la que usa shadcn/ui internamente para su propio componente
   de gráficos, ~2.4M descargas semanales, resuelve barras apiladas de
   fábrica, se colorea con variables CSS (compatible con el sistema
   dark-first ya existente, ADR-0004/0050) y corre como client component en
   Next.js 16 + React 19 sin fricción. Es dependencia nueva del frontend →
   necesita su propio ADR.

## Scope

- **Pestaña nueva "Evolución"** en `frontend/app/(app)/reports/page.tsx`,
  junto a la vista de un mes que ya existe (features/011-monthly-report).
- **Gráfico de barras apiladas** (Recharts): eje X = últimos 12 meses, cada
  barra apilada por grupo de categoría. Solo expresa gasto.
- **Tabla matriz** debajo del gráfico: fila = categoría, columna = cada uno de
  los 12 meses, cifra exacta en pesos. Categoría sin grupo cae en un bucket
  "Sin grupo" (mismo criterio que `by_group` ya usa hoy con `"Ungrouped"`,
  escrito en español al ser código nuevo).
- **Backend**: extender la respuesta de `GET /api/reports` (servicio
  `services/reports.py` + `domain/report_types.py`) con una sección nueva de
  tendencia, en vez de abrir un endpoint separado.
  `MonthAggregate._spent_by_cat_month` (`services/month_aggregate.py`) ya
  carga, en una sola consulta `GROUP BY (category_id, year, month)`, el gasto
  de TODA la historia — no acotado al mes del reporte que se pidió
  (ADR-0028). Los últimos 12 meses se arman en memoria sobre ese dato ya
  cargado, sin ninguna consulta nueva — mismo precedente que ADR-0044 (el
  fold vive en el aggregate).
- **ADR nueva**: elección de Recharts como librería de gráficos del frontend.
- **Fuera de alcance**: comparar dos meses puntuales entre sí (evaluado y
  descartado a favor de la evolución continua); tendencia de ingresos (el
  pedido fue sobre gasto); selector de rango de meses configurable (queda
  fijo en 12); **paridad con el chat/MCP** — resuelto en discover-acs
  (2026-08-22): el asistente no expone la evolución de 12 meses por ahora,
  queda exclusiva de la pantalla (AC-1 a AC-10 de `acs.md`), rompiendo a
  propósito la paridad ADR-0006/0009 mantiene para el resto de reports.

## Qué ya es cierto, medido al momento de abrir esta feature

- La pantalla Reportes (features/011-monthly-report) ya tiene una pestaña de
  un solo mes: neto, ingresos, gastos, fondos, metas, por categoría, por
  grupo, balances de cuentas, drift mes a mes (solo ingreso/gasto/neto
  totales — no por categoría), disponible de cierre.
- `by_category`/`by_group` en `report_types.py` ya calculan porcentaje sobre
  el total de gasto del mes — mismo patrón a reusar para la tendencia.
- El frontend no tiene ninguna librería de gráficos instalada hoy (confirmado
  por búsqueda en `package.json`, `frontend/components` y `frontend/ui`).
- Producción tiene ~2-3 meses de datos reales (arranque limpio, sin backfill,
  decisión de producto ya registrada) — los meses más viejos de la ventana de
  12 van a leer $0. Mismo criterio ya aceptado para "reportes flacos al
  principio"; no hace falta un estado vacío especial para esto.

## Señales del charter

- **No hay migración ni tabla nueva** — es una sección calculada, sin estado
  persistido nuevo.
- **Nueva dependencia de frontend (Recharts)** — arquitectónicamente
  significativa, necesita ADR antes o durante el plan.
- No toca `migrations/**`, `.dev-data/**` ni ninguna ruta de pago — autonomía
  medium sin excepción del charter.
