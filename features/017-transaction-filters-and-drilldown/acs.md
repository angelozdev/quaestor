---
ac_count: 15
high_priority_count: 8
discovered: 2026-08-19
reviewed: null
---

# Acceptance criteria — 017 transaction-filters-and-drilldown

Descubiertos el 2026-08-19 con el dueño, a partir del roadmap
`id:transaction-filters-and-drilldown` (pedido el 2026-08-09) y de leer el
código real de `services/transactions.py`, `filter-schemas.ts`,
`use-url-filters.ts` y `data-table.tsx` antes de preguntar. Categoría y
etiqueta ya se filtraban hoy — el hueco real es monto, grupo, y que la barra
de filtros no distinguía lo que el dueño usa de lo que no.

**Riesgo aceptado, no un AC de corrección.** Dos movimientos siguen en
negativo hoy — un retiro de Tyba (29.084.436,55 COP) y uno de a2censo
(1.500.000 COP), ambos pendientes de modelarse como transferencia entre
cuentas propias (`id:amount-must-be-positive`, roadmap aparte). El dueño
decidió construir el filtro de monto igual, sin esperar a que eso se
resuelva. Ninguna escena de aceptación de esta feature elige esas dos filas
ni afirma qué hace "menor que" con ellas — quedan fuera de lo que se prueba,
no dentro de lo que se garantiza.

**Decisión de diseño tomada en esta sesión.** La barra de filtros se agrupa
por tema — Cuándo (Desde, Hasta), Qué (Cuenta, Categoría, Grupo, Etiqueta,
Tipo), Cuánto (Monto mínimo, Monto máximo), Estado — con un contador de
filtros activos y un link para limpiarlos, todo siempre visible (nada detrás
de un toggle).

**AC-15 (monto negativo en el filtro se avisa) se retiró en CP5.** El input
de monto reutiliza `MoneyInput`, el mismo que ya usa cada formulario de
dinero de la app — y ese componente ni deja escribir el signo menos, lo
descarta en silencio, igual hoy en el formulario de gastos. No hay un
negativo real que rechazar: el AC asumía una caja que permitía escribirlo, y
la que existe no lo permite. Retirado con el dueño en vez de construir un
input aparte solo para este filtro.

---

## AC-1: Filtrar movimientos por un monto mínimo y/o máximo

**Priority:** high · **Type:** feature

El dueño pone "Monto mínimo: 100.000" en Transacciones. La lista muestra
solo movimientos cuyo valor, convertido a pesos, es igual o mayor a esa
cifra — sin importar en qué moneda quedó guardado el movimiento. Un cargo de
USD 37,20 entra en ese filtro el día que la TRM lo hace valer más de
100.000 COP, junto a un cargo de 250.000 hecho en pesos.

## AC-2: Filtrar movimientos por grupo trae todas sus categorías juntas

**Priority:** high · **Type:** feature

El dueño elige el grupo "Finanzas" (que hoy agrupa tres categorías). La
lista muestra los movimientos de esas tres categorías juntas, sin poder
sacar una del resultado — el grupo es su propio filtro, no una selección
múltiple de categorías.

## AC-3: La barra de filtros se agrupa por tema y dice cuántos están activos

**Priority:** high · **Type:** feature

El dueño abre Transacciones. Los nueve controles del filtro (antes siete)
aparecen agrupados bajo Cuándo / Qué / Cuánto / Estado. En cuanto pone al
menos un filtro, aparece "N filtros activos" con un link "Limpiar" que los
saca todos de una vez.

## AC-4: "Ver movimientos" desde una categoría abre Transacciones ya filtrada

**Priority:** high · **Type:** feature

El dueño está en Categorías, en la fila de "Restaurantes", y elige "Ver
movimientos". Cae en Transacciones con el filtro Categoría ya puesto en
"Restaurantes" y la lista mostrando solo esos movimientos.

## AC-5: "Ver movimientos" desde un grupo abre Transacciones ya filtrada

**Priority:** medium · **Type:** feature

El dueño está en Grupos de categorías, en la fila de "Finanzas", y elige
"Ver movimientos". Cae en Transacciones con el filtro Grupo ya puesto en
"Finanzas".

## AC-6: "Ver movimientos" desde una etiqueta abre Transacciones ya filtrada

**Priority:** medium · **Type:** feature

El dueño está en Etiquetas, en la fila de una etiqueta cualquiera, y elige
"Ver movimientos". Cae en Transacciones con el filtro Etiqueta ya puesto.

## AC-7: El asistente contesta preguntas de monto y de grupo igual que la pantalla

**Priority:** medium · **Type:** feature

El dueño le pregunta al asistente "qué gastos pasan de 500.000" o "cuánto
gasté en Finanzas este mes". Hoy no puede contestar ninguna de las dos — el
MCP no tiene esos parámetros. Después responde con la misma cifra que
mostraría la pantalla con el mismo filtro puesto.

## AC-8: Un solo extremo del rango de monto alcanza

**Priority:** medium · **Type:** edge

El dueño pone solo "Monto mínimo" y deja "Monto máximo" vacío (o
viceversa). El filtro funciona como un rango abierto de un solo lado, no
exige los dos campos.

## AC-9: Un rango de monto invertido se avisa, no se ignora en silencio

**Priority:** high · **Type:** edge

El dueño pone "Monto mínimo: 500.000" y "Monto máximo: 100.000". La app
avisa que el rango no tiene sentido en vez de devolver una lista vacía sin
explicar por qué.

## AC-10: Un grupo sin categorías activas no rompe el filtro

**Priority:** low · **Type:** edge

El dueño filtra por un grupo cuyas categorías están todas archivadas. La
lista queda vacía con el mismo mensaje de "sin movimientos" que ya usa
cualquier otro filtro sin resultados — no un error.

## AC-11: El drill-down funciona también desde una categoría, grupo o etiqueta archivada

**Priority:** medium · **Type:** edge

El dueño está viendo una categoría archivada y elige "Ver movimientos".
Igual llega a Transacciones filtrada por esa categoría — archivar no borra
el historial, y el dueño puede querer revisarlo.

## AC-12: Grupo y categoría elegidos juntos se combinan como cualquier otro par de filtros

**Priority:** medium · **Type:** edge

El dueño pone Grupo "Finanzas" y además Categoría "Restaurantes" (que no
pertenece a ese grupo). Los dos filtros se combinan con Y, como ya pasa hoy
entre Cuenta y Categoría — si no hay movimientos que cumplan ambos a la
vez, la lista queda vacía, no es un error.

## AC-13: El filtro de monto puede traer una fila distinta mañana, sin que el movimiento cambie

**Priority:** high · **Type:** cross-cutting

El dueño corre el mismo filtro "mayor a 100.000" dos días distintos sobre
el mismo movimiento en dólares. Si la TRM cambió entre un día y el otro, el
movimiento puede entrar el primer día y salir el segundo (o al revés) — el
filtro se calcula con la TRM del momento en que se aplica, nunca con una
cifra guardada.

## AC-14: Sin la TRM del día, el filtro de monto se bloquea igual que cualquier lectura que convierte moneda

**Priority:** high · **Type:** error

Falta la tasa del día en la tabla TRM. El dueño intenta filtrar por monto y
ve el mismo aviso que ya ve hoy en cualquier pantalla que necesita
convertir una cifra — el filtro no es una puerta nueva para ese error, es
la misma regla ya vigente (ADR-0031) alcanzando un lugar más.

## AC-15: El filtro de monto se prueba con un movimiento en una cuenta de otra moneda

**Priority:** high · **Type:** cross-cutting

Por CHARTER §6 ("una figura que la app convierte se prueba en otra moneda
también"): al menos un caso de aceptación filtra por monto sobre un
movimiento guardado en una cuenta en dólares, no solo en pesos — el mismo
tipo de cifra convertida que una vez mostró 100.000.000 en vez de
1.000.000 en el aviso de un fondo.
