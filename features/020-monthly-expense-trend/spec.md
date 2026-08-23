# Acceptance specs — 020 monthly-expense-trend

Formalizes `acs.md` (12 ACs, approved 2026-08-22) as standard Gherkin.

## Dos flujos, porque `feature.md` declara `acceptance_stream: mixed`

`@backend` fija los datos: qué 12 meses entran en la ventana, cómo se reparte
cada mes por grupo (no por categoría), cómo se ordena y filtra la tabla,
y la conversión de dólares con la TRM del momento en que se lee. Todo esto
vive en `MonthAggregate`/`reports.monthly_report` (ADR-0028/0044) y es
exactamente lo que `pytest` puede fijar sin tocar el navegador.

AC-4 y AC-10 son puramente de pantalla — dónde cae la cifra sobre la barra, y
qué mensaje se ve cuando no hay nada que graficar — y quedan como escenario
sin etiqueta, atado a `vitest` por título literal (ADR-0045): no necesitan
pasos automatizables, solo que el `Scenario:` coincida con el título de un
test de `vitest`.

## Sobre AC-11 y AC-12

El TRM es una tasa única y global (ADR-0031, ya heredado — ver la nota en
`acs.md`): no hay una tasa "de marzo" distinta de la de hoy. AC-11 no prueba
que exista una tasa histórica — prueba que un gasto en dólares fechado en
cualquier mes de la ventana se convierte igual, con la tasa vigente al momento
de leer la pantalla, cumpliendo el mandato de CHARTER §6.

AC-12 no abre una puerta nueva al error: "Evolución" vive en la misma
respuesta que ya exige el TRM para renderizar cualquier cosa de Reportes, así
que reutiliza, literal, los mismos tres pasos que ya fijan ese comportamiento
en `fx_read_time.py` (`no TRM has been set` / `the user views the current
month's report` / `the report is not shown`) — no hace falta inventar un paso
"la tendencia no se muestra" aparte.

## Nota para quien genere el pipeline (CP5)

Pasos nuevos, sin precedente exacto:

- **Given** `a recorded expense of N CUR in category "X" in YYYY-MM` — extiende
  la familia ya existente en `fx_read_time.py`
  (`a recorded expense of N CUR in category "X" in the current month`) para
  aceptar un mes explícito en vez de solo "actual"/"anterior". Fecha al día 15
  de ese mes — mismo criterio de seguridad que ya usa
  `world.previous_month_day`.
- **When** `the user views the last 12 months of spending trend` — paralelo
  directo de `_view_report`/`when_view_current_report` en `fx_read_time.py`:
  misma llamada a `reports.monthly_report(session, month, today=world.today)`,
  guardada en `world.report`, porque la tendencia vive en la misma respuesta
  del reporte del mes — no hace falta una llamada nueva al servicio.
- **Then**, todos nuevos, leyendo la sección de tendencia que CP5 agregue a
  `world.report`:
  - `the trend's window runs from YYYY-MM to YYYY-MM`
  - `in YYYY-MM the group "X" totals N COP`
  - `in YYYY-MM the total shown is N COP`
  - `the table lists "X"` / `the table does not list "X"`
  - `the table lists "X" before "Y"`
  - `the table lists "X" totaling N COP across the window`
  - `the table lists "X" with N COP in YYYY-MM`
  - `the group for "X" is "Y"`

AC-12 no necesita ningún paso nuevo — ver nota arriba.

---

Feature: La evolución del gasto se lee en la misma pantalla del mes, por grupo y mes a mes

## AC-1 — La ventana muestra siempre los últimos 12 meses, hasta hoy

```gherkin
@backend
Scenario: The trend window always ends at the current month, regardless of older data
  Given today is 2026-08-22
  And a category group "Comida"
  And a category "Restaurantes" in group "Comida"
  And a recorded expense of 100000 COP in category "Restaurantes" in 2025-08
  And a recorded expense of 200000 COP in category "Restaurantes" in 2026-08
  When the user views the last 12 months of spending trend
  Then the trend's window runs from 2025-09 to 2026-08
```

## AC-2 — Cada mes se reparte por grupo de categoría, no por categoría suelta

```gherkin
@backend
Scenario: A month's spend is broken down by category group, not by individual category
  Given today is 2026-08-22
  And a category group "Comida"
  And a category "Restaurantes" in group "Comida"
  And a category "Mercado" in group "Comida"
  And a category group "Transporte"
  And a category "Gasolina" in group "Transporte"
  And a recorded expense of 150000 COP in category "Restaurantes" in 2026-06
  And a recorded expense of 100000 COP in category "Mercado" in 2026-06
  And a recorded expense of 80000 COP in category "Gasolina" in 2026-06
  When the user views the last 12 months of spending trend
  Then in 2026-06 the group "Comida" totals 250000 COP
  And in 2026-06 the group "Transporte" totals 80000 COP
```

## Sobre AC-2 — un cobro con fondo propio, liquidado en un mes histórico

`MonthAggregate._spent_by_cat_month` (`services/month_aggregate.py`) es lo que
alimenta todos los meses de la ventana salvo el actual y el anterior — esos
dos se leen aparte, por la consulta normal del mes en curso. Un cobro con
fondo propio (feature 015, ADR-0057) liquidado en un mes histórico de la
ventana corre el riesgo de quedar fuera de esa consulta y faltarle al grupo de
su categoría — no es una AC nueva, es la misma AC-2 ("se reparte por grupo, no
por categoría suelta") puesta a prueba con un cobro liquidado meses atrás en
vez de con un gasto suelto del mes en curso.

```gherkin
@backend
Scenario: A settled charge with its own fund still counts toward its group's historical total
  Given today is 2026-08-22
  And a category group "Comida"
  And a category "Restaurantes" in group "Comida"
  And a recurring charge "Comida a domicilio" on "Restaurantes" of 15000.00 COP every 6 months, next due 2027-01
  And "Comida a domicilio" is marked to be saved for
  And "Comida a domicilio" was charged 6 months ago
  And a recorded expense of 35000 COP in category "Restaurantes" in 2026-02
  When the user views the last 12 months of spending trend
  Then in 2026-02 the group "Comida" totals 50000 COP
```

## AC-3 — El mes en curso se ve parcial y va creciendo

```gherkin
@backend
Scenario: The current month's bar reflects spend so far, and grows with a new expense
  Given today is 2026-08-22
  And a category group "Comida"
  And a category "Restaurantes" in group "Comida"
  And a recorded expense of 50000 COP in category "Restaurantes" in 2026-08
  When the user views the last 12 months of spending trend
  Then in 2026-08 the total shown is 50000 COP
  When the user records an expense of 30000 COP in category "Restaurantes"
  And the user views the last 12 months of spending trend
  Then in 2026-08 the total shown is 80000 COP
```

## AC-4 — Cada barra muestra su total en pesos, arriba

```gherkin
Scenario: Each month's bar states its own total, in pesos, above the bar
  Given the app is open
  And the last 12 months carry expense history across more than one group
  When the owner opens the "Evolución" tab
  Then each bar shows its month's total in pesos above it
```

## AC-5 — La tabla va de mayor a menor gasto acumulado

```gherkin
@backend
Scenario: The table's rows are ordered by total spend across the window, highest first
  Given today is 2026-08-22
  And a category group "Comida"
  And a category "Restaurantes" in group "Comida"
  And a category "Cafeterías" in group "Comida"
  And a recorded expense of 100000 COP in category "Restaurantes" in 2026-06
  And a recorded expense of 200000 COP in category "Restaurantes" in 2026-07
  And a recorded expense of 50000 COP in category "Cafeterías" in 2026-07
  When the user views the last 12 months of spending trend
  Then the table lists "Restaurantes" before "Cafeterías"
  And the table lists "Restaurantes" totaling 300000 COP across the window
```

## AC-6 — Una categoría sin gasto en toda la ventana no aparece

```gherkin
@backend
Scenario: A category with zero spend across the whole window is left off the table
  Given today is 2026-08-22
  And a category group "Comida"
  And a category "Restaurantes" in group "Comida"
  And a category "Nunca usada" in group "Comida"
  And a recorded expense of 100000 COP in category "Restaurantes" in 2026-06
  When the user views the last 12 months of spending trend
  Then the table lists "Restaurantes"
  And the table does not list "Nunca usada"
```

## AC-7 — Una categoría archivada conserva su historia real

```gherkin
@backend
Scenario: An archived category still shows the real spend it had while active
  Given today is 2026-08-22
  And a category group "Comida"
  And a category "Antojos" in group "Comida"
  And a recorded expense of 120000 COP in category "Antojos" in 2026-01
  And a recorded expense of 90000 COP in category "Antojos" in 2026-02
  And the category "Antojos" is archived
  When the user views the last 12 months of spending trend
  Then the table lists "Antojos" with 120000 COP in 2026-01
  And the table lists "Antojos" with 90000 COP in 2026-02
```

## AC-8 — Una categoría sin grupo cae en "Sin grupo"

```gherkin
@backend
Scenario: A category with no group assigned is bucketed under "Sin grupo"
  Given today is 2026-08-22
  And an expense category "Suscripciones"
  And a recorded expense of 45000 COP in category "Suscripciones" in 2026-06
  When the user views the last 12 months of spending trend
  Then the group for "Suscripciones" is "Sin grupo"
  And in 2026-06 the group "Sin grupo" totals 45000 COP
```

## AC-9 — Los meses anteriores al primer movimiento muestran $0, sin error

```gherkin
@backend
Scenario: Months before the app's first-ever movement read as zero, not as an error
  Given today is 2026-08-22
  And a category group "Comida"
  And a category "Restaurantes" in group "Comida"
  And a recorded expense of 100000 COP in category "Restaurantes" in 2026-06
  When the user views the last 12 months of spending trend
  Then in 2025-09 the total shown is 0 COP
  And in 2025-12 the total shown is 0 COP
```

## AC-10 — Sin ningún gasto, el mismo estado vacío que "Mes"

```gherkin
Scenario: A fresh install with no expenses shows the same empty state as "Mes"
  Given the app is open
  And no expense has ever been recorded
  When the owner opens the "Evolución" tab
  Then the screen shows the same "sin gastos" message the "Mes" tab shows for an empty month
```

## AC-11 — El gasto en dólares de la ventana se prueba también en dólares

```gherkin
@backend
Scenario: Foreign-currency spend in the window converts at today's TRM
  Given today is 2026-08-22
  And a category group "Viajes"
  And a category "Hospedaje" in group "Viajes"
  And the TRM is 4200
  And a recorded expense of 100.00 USD in category "Hospedaje" in 2026-03
  When the user views the last 12 months of spending trend
  Then in 2026-03 the total shown is 420000 COP
  And in 2026-03 the group "Viajes" totals 420000 COP
```

## AC-12 — Sin TRM configurada, "Evolución" falla igual que el resto de Reportes

```gherkin
@backend
Scenario: No TRM configured refuses to load, the same way as the rest of Reportes
  Given no TRM has been set
  When the user views the current month's report
  Then the report is not shown
```
