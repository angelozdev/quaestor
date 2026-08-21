# Acceptance specs — 019 fund-opening-balance

Formalizes `acs.md` (6 ACs, approved 2026-08-20) as standard Gherkin.

## Dos flujos, porque `feature.md` declara `acceptance_stream: mixed`

`@backend` fija el fechado real: qué mes queda registrado cuando se declara un
saldo, y qué figura devuelve cada mes que se consulta después. El escenario
sin etiqueta (AC-1) fija lo que el dueño ve en la pantalla de Fondos — el
campo nuevo en el formulario de crear, y la columna "Tiene" reflejando lo
declarado — y se ata a vitest en vez de pytest, según el manejo de un flujo
mixto de `run-acceptance-tests.sh`. Por ADR-0045, el escenario sin etiqueta no
necesita pasos automatizables: solo el título `Scenario:` debe coincidir,
literal, con el título de un test de vitest.

## Sobre AC-2

`create_fund(opening_balance=...)` ya fecha correctamente al mes de arranque
hoy — ADR-041 lo llama "la mitad ya correcta". Se fija igual a nivel de
aceptación (no solo unit test) porque hasta esta feature el camino completo,
desde el formulario, era inalcanzable: nadie podía ejercitarlo salvo un test.

## Nota para quien genere el pipeline (CP5)

El paso existente `a fund on "X" that asks a fixed Y COP each month, starting
Z` (regla `fixed`, en `acceptance/handlers/sinking_funds.py`) no acepta hoy la
cláusula `, opening with N COP` que sí tienen las reglas `funded from its
obligations` y `targeting ... by ...`. AC-2 la necesita sobre la regla `fixed`
— extender esa misma cláusula opcional al patrón `_FIXED`, no inventar una
nueva.

También son steps nuevos, sin precedente exacto: `in YYYY-MM the fund on "X"
holds N COP` (extensión directa del patrón ya existente en
`fund_per_charge.py`, `in YYYY-MM the fund for "X" asks N CURRENCY`, aplicado
a `holds` sobre un fondo de categoría vía `fund_status(...).holds`); y `the
user sets the fund on "X" to hold N COP` (paralelo directo al ya existente
`the user sets the fund on "X" to ask a fixed N COP each month`, mismo
`set_fund`, cambiando `balance=` en vez de `rule=`/`amount=`).

---

Feature: El saldo inicial de un fondo respeta el mes en que se dijo

## AC-1 — Declarar el saldo al crear el fondo, desde la pantalla

```gherkin
Scenario: The create-fund form lets the owner say what it already holds
  Given the app is open
  And an expense category "Tecnologia" exists
  When the owner creates a fund on "Tecnologia" asking a fixed 200000.00 COP each month starting "2026-01", declaring an opening balance of 500000.00 COP
  Then the Funds screen shows "Tecnologia" holds $500.000 this month
```

## AC-2 — Lo declarado al crear rige hacia adelante, mes a mes

```gherkin
@backend
Scenario: An opening balance stated at creation keeps building month after month
  Given today is 2026-01-15
  And a fund on "Tecnologia" that asks a fixed 200000.00 COP each month, starting 2026-01, opening with 500000.00 COP
  Then the fund on "Tecnologia" holds 500000.00 COP this month
  And in 2026-02 the fund on "Tecnologia" holds 700000.00 COP
  And in 2026-03 the fund on "Tecnologia" holds 900000.00 COP
```

## AC-3 — Declarar un saldo nuevo después de creado el fondo lo fecha al momento en que se dice

```gherkin
@backend
Scenario: Stating a fund's balance afterward is dated to today, not to a chosen month
  Given today is 2026-01-15
  And a fund on "Tecnologia" that asks a fixed 200000.00 COP each month, starting 2025-11
  When the user sets the fund on "Tecnologia" to hold 500000.00 COP
  Then the fund on "Tecnologia" holds 500000.00 COP this month
```

## AC-4 — Un mes anterior a cuando se declaró un saldo no lo ve

```gherkin
@backend
Scenario: A month before the balance was ever stated does not see it
  Given today is 2026-01-15
  And a fund on "Tecnologia" that asks a fixed 200000.00 COP each month, starting 2025-11
  When the user sets the fund on "Tecnologia" to hold 500000.00 COP
  Then in 2025-12 the fund on "Tecnologia" holds 0.00 COP
```

## AC-5 — Declarar un saldo nuevo reemplaza al anterior por completo

```gherkin
@backend
Scenario: A second stated balance replaces the first one entirely
  Given today is 2026-01-15
  And a fund on "Tecnologia" that asks a fixed 200000.00 COP each month, starting 2025-11
  And the user sets the fund on "Tecnologia" to hold 500000.00 COP
  And today is 2026-02-15
  When the user sets the fund on "Tecnologia" to hold 300000.00 COP
  Then the fund on "Tecnologia" holds 300000.00 COP this month
  And in 2026-01 the fund on "Tecnologia" holds 0.00 COP
```

## AC-6 — Crear un fondo sin declarar saldo se comporta igual que hoy

```gherkin
@backend
Scenario: Creating a fund without stating a balance starts it at zero, same as before this feature
  Given today is 2026-01-15
  And a fund on "Tecnologia" that asks a fixed 200000.00 COP each month, starting 2026-01
  Then the fund on "Tecnologia" holds 0.00 COP this month
```
