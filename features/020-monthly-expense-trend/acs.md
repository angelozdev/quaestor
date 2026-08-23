---
ac_count: 12
high_priority_count: 6
discovered: 2026-08-22
reviewed: null
---

# Acceptance criteria — 020 monthly-expense-trend

Descubiertos el 2026-08-22 con el dueño, arrancando de un `/superpowers:brainstorming`
que exploró el pedido a fondo (tipo de vista, rango, ubicación, alcance,
nivel de detalle del gráfico, forma de la tabla) antes de que el dueño
decidiera, a mitad de camino, encausar el resultado por el pipeline propio
del proyecto (`discuss` → `feature-init`) en vez de `docs/superpowers/specs/`.
No hay código existente de esta pantalla para hacer reverse-engineer — modo
greenfield completo.

**Decisión de diseño tomada en esta sesión.** El asistente (chat/MCP) **no**
expone la evolución de 12 meses por ahora — vive solo en la pantalla. Se deja
escrito para que nadie la "arregle" después sin saber que fue elegido así;
revisar si el dueño empieza a pedir por chat cosas como "cómo vengo gastando
este año".

**Heredado, no decidido de nuevo aquí.** El TRM es una tasa única y global
(ADR-0031): el gasto en dólares de cualquier mes de la ventana se convierte
siempre con la tasa de **hoy**, así que si el TRM cambia, las cifras de meses
pasados con gasto en dólares cambian con él — igual que ya pasa hoy en la
pestaña "Mes". No es un AC nuevo, es el mismo comportamiento alcanzando un
lugar más (por eso AC-11 lo pin ya como prueba, siguiendo CHARTER §6).

---

## AC-1: La pestaña "Evolución" muestra los últimos 12 meses, siempre hasta hoy

**Priority:** high · **Type:** feature

El dueño abre la pestaña "Evolución" dentro de Reportes. Ve un gráfico de
barras apiladas con una barra por cada uno de los últimos 12 meses,
terminando siempre en el mes actual — sin importar qué mes tenga elegido en
la pestaña "Mes" de al lado.

## AC-2: Cada barra se apila por grupo de categoría, no por categoría suelta

**Priority:** high · **Type:** feature

Cada barra mensual se divide en colores, uno por grupo de categoría (ej.
Comida, Transporte, Utilidades) — nunca uno por categoría individual. Con
~10 grupos activos y ~40 categorías, apilar por categoría haría el gráfico
ilegible.

## AC-3: El mes en curso se ve parcial y va creciendo

**Priority:** high · **Type:** feature

Si hoy es 22 de agosto, la barra de agosto muestra lo gastado hasta hoy — no
se deja afuera ni se espera a que el mes cierre. Mañana, con un movimiento
más confirmado, esa misma barra crece.

## AC-4: Cada barra muestra su total en pesos, arriba

**Priority:** medium · **Type:** feature

Encima de cada barra aparece la cifra total gastada ese mes (ej.
"$2.450.000"), sumando todos los grupos — sin tener que sumar los colores a
ojo ni bajar a la tabla.

## AC-5: Debajo del gráfico, una tabla categoría x mes, ordenada por lo que más pesa

**Priority:** high · **Type:** feature

Debajo del gráfico hay una tabla: una fila por categoría, una columna por
cada uno de los 12 meses, con la cifra exacta en pesos. Las filas van de
mayor a menor gasto acumulado en la ventana — la categoría en la que más
gastaste sumando los 12 meses (ej. Restaurantes con $4.200.000) va primero.

## AC-6: Una categoría sin gasto en toda la ventana no aparece en la tabla

**Priority:** medium · **Type:** edge

Una categoría que no tuvo ni un peso de gasto en ninguno de los 12 meses
(nunca se usó, o hace mucho que no) se omite de la tabla — no sale una fila
de puros ceros.

## AC-7: Una categoría archivada conserva su historia real

**Priority:** medium · **Type:** edge

Una categoría archivada hace 2 meses, que sí gastó plata en los primeros 5
de los últimos 12, aparece igual en la tabla con esos montos — archivar hoy
no borra un gasto que de verdad ocurrió.

## AC-8: Una categoría sin grupo cae en "Sin grupo"

**Priority:** low · **Type:** edge

Una categoría que no tiene grupo asignado se agrupa bajo "Sin grupo", tanto
en el color del gráfico como en la tabla — mismo criterio que ya usa "por
grupo" en la pestaña "Mes" hoy.

## AC-9: Los meses anteriores al primer movimiento de la app muestran $0

**Priority:** medium · **Type:** edge

Si la app solo tiene 3 meses de historia real, los 9 meses más viejos de la
ventana de 12 se ven en $0 en el gráfico y en la tabla — sin marcarlos como
error ni excluirlos de la ventana.

## AC-10: Sin ningún gasto en los 12 meses, se ve el mismo estado vacío que "Mes"

**Priority:** low · **Type:** edge

Una instalación nueva, sin un solo movimiento registrado todavía, ve en
"Evolución" el mismo mensaje de "sin gastos" que ya muestra hoy la pestaña
"Mes" cuando un mes no tiene gasto — no una pantalla en blanco ni un error.

## AC-11: El gasto en dólares de la ventana se prueba también en dólares

**Priority:** high · **Type:** cross-cutting

Por CHARTER §6 ("una figura que la app convierte se prueba en otra moneda
también"): al menos un escenario de aceptación siembra gasto en una cuenta
en dólares dentro de la ventana de 12 meses y confirma que la barra y la
celda de la tabla de ese mes muestran la conversión a pesos con la TRM del
momento en que se lee — el mismo tipo de cobertura que faltó una vez y dejó
pasar una meta en dólares reportada 4.000 veces más chica.

## AC-12: Sin TRM configurada, "Evolución" rehúsa cargar igual que el resto de Reportes

**Priority:** high · **Type:** error

Si no hay una tasa TRM guardada, la pestaña "Evolución" no es una puerta
nueva para este error — falla exactamente igual que ya falla hoy toda la
pantalla Reportes (ADR-0031), porque vive en la misma respuesta que ya exige
la tasa para renderizar.
