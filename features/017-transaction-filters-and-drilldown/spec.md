# Acceptance specs — 017 transaction-filters-and-drilldown

Formalizes `acs.md` (15 ACs, approved by the owner 2026-08-19) as standard
Gherkin.

## Two streams, because `feature.md` declares `acceptance_stream: mixed`

`@backend` scenarios pin what the service/API/MCP layer actually returns —
which movements are in the list, what a rejection carries. Untagged
scenarios pin what the owner sees on screen — the filter bar's shape, the
inline warning, where a click lands — and bind to vitest instead of pytest,
per `run-acceptance-tests.sh`'s handling of a mixed stream.

## Two rows this spec deliberately never picks

The still-negative Tyba and a2censo movements (`id:amount-must-be-positive`,
tracked separately) are never chosen by any scenario below, and no scenario
asserts what "menor que" does with them — see `acs.md`'s intro and
`feature.md`'s Riesgos. Adding a scenario for either would pin a behavior
nobody decided.

---

Feature: Los movimientos se filtran por monto y por grupo, y cada vista lleva a los suyos

## AC-1 — Filtrar movimientos por un monto mínimo y/o máximo

```gherkin
@backend
Scenario: Filtering by an amount range keeps only movements inside it
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  And a category "Comida"
  And the user registers an expense of 50000.00 COP from "Bancolombia" paying "Barato" in category "Comida"
  And the user registers an expense of 150000.00 COP from "Bancolombia" paying "Medio" in category "Comida"
  And the user registers an expense of 500000.00 COP from "Bancolombia" paying "Caro" in category "Comida"
  When the user lists transactions with amount between 100000.00 and 200000.00 COP
  Then the list shows only "Medio"
```

## AC-2 — Filtrar movimientos por grupo trae todas sus categorías juntas

```gherkin
@backend
Scenario: Filtering by group returns the movements of every category in it
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  And a category group "Finanzas"
  And a category "Ahorros" in group "Finanzas"
  And a category "Seguros" in group "Finanzas"
  And a category "Comida"
  And the user registers an expense of 50000.00 COP from "Bancolombia" paying "Fondo" in category "Ahorros"
  And the user registers an expense of 30000.00 COP from "Bancolombia" paying "Poliza" in category "Seguros"
  And the user registers an expense of 20000.00 COP from "Bancolombia" paying "Exito" in category "Comida"
  When the user lists transactions in group "Finanzas"
  Then the list shows "Fondo" and "Poliza" but not "Exito"
```

## AC-3 — La barra de filtros se agrupa por tema y dice cuántos están activos

```gherkin
Scenario: The filter bar groups its controls under Cuándo, Qué, Cuánto and Estado
  Given the app is open
  When the owner views the transaction filters
  Then "Desde" and "Hasta" appear under "Cuándo"
  And "Cuenta", "Categoría", "Grupo", "Etiqueta" and "Tipo" appear under "Qué"
  And "Monto mínimo" and "Monto máximo" appear under "Cuánto"
  And "Estado" appears on its own

Scenario: The filter bar counts how many filters are active
  Given the app is open
  And no filter is set
  When the owner sets the category filter to "Comida"
  And the owner sets "Monto mínimo" to 100000
  Then the filter bar shows "2 filtros activos"

Scenario: Limpiar clears every filter at once
  Given the app is open
  And the owner has set the category filter to "Comida"
  And the owner has set "Monto mínimo" to 100000
  When the owner selects "Limpiar"
  Then no filter is set
```

## AC-4 — "Ver movimientos" desde una categoría abre Transacciones ya filtrada

```gherkin
Scenario: Opening Ver movimientos from a category lands on its filtered list
  Given the app is open
  And a category "Restaurantes"
  When the owner opens "Ver movimientos" for the category "Restaurantes"
  Then the transaction list is filtered to category "Restaurantes"
```

## AC-5 — "Ver movimientos" desde un grupo abre Transacciones ya filtrada

```gherkin
Scenario: Opening Ver movimientos from a group lands on its filtered list
  Given the app is open
  And a category group "Finanzas"
  When the owner opens "Ver movimientos" for the group "Finanzas"
  Then the transaction list is filtered to group "Finanzas"
```

## AC-6 — "Ver movimientos" desde una etiqueta abre Transacciones ya filtrada

```gherkin
Scenario: Opening Ver movimientos from a tag lands on its filtered list
  Given the app is open
  And a recorded expense tagged "viaje"
  When the owner opens "Ver movimientos" for the tag "viaje"
  Then the transaction list is filtered to tag "viaje"
```

## AC-7 — El asistente contesta preguntas de monto y de grupo igual que la pantalla

```gherkin
@backend
Scenario: The app and the assistant list the same amount-filtered movements
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  And a category "Comida"
  And the user registers an expense of 50000.00 COP from "Bancolombia" paying "Barato" in category "Comida"
  And the user registers an expense of 150000.00 COP from "Bancolombia" paying "Caro" in category "Comida"
  When the user lists transactions with amount at least 100000.00 COP in the app
  And the assistant lists transactions with amount at least 100000.00 COP
  Then both show the same movements

@backend
Scenario: The app and the assistant list the same group-filtered movements
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  And a category group "Finanzas"
  And a category "Ahorros" in group "Finanzas"
  And a category "Comida"
  And the user registers an expense of 50000.00 COP from "Bancolombia" paying "Fondo" in category "Ahorros"
  And the user registers an expense of 20000.00 COP from "Bancolombia" paying "Exito" in category "Comida"
  When the user lists transactions in group "Finanzas" in the app
  And the assistant lists transactions in group "Finanzas"
  Then both show the same movements
```

## AC-8 — Un solo extremo del rango de monto alcanza

```gherkin
@backend
Scenario: A minimum amount alone excludes cheaper movements
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  And a category "Comida"
  And the user registers an expense of 50000.00 COP from "Bancolombia" paying "Barato" in category "Comida"
  And the user registers an expense of 150000.00 COP from "Bancolombia" paying "Caro" in category "Comida"
  When the user lists transactions with amount at least 100000.00 COP
  Then the list shows only "Caro"

@backend
Scenario: A maximum amount alone excludes pricier movements
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  And a category "Comida"
  And the user registers an expense of 50000.00 COP from "Bancolombia" paying "Barato" in category "Comida"
  And the user registers an expense of 150000.00 COP from "Bancolombia" paying "Caro" in category "Comida"
  When the user lists transactions with amount at most 100000.00 COP
  Then the list shows only "Barato"
```

## AC-9 — Un rango de monto invertido se avisa, no se ignora en silencio

```gherkin
Scenario: An inverted amount range is rejected with a clear warning
  Given the app is open
  When the owner sets "Monto mínimo" to 500000 and "Monto máximo" to 100000
  Then the app shows "El monto mínimo no puede ser mayor que el máximo"
```

## AC-10 — Un grupo sin categorías activas no rompe el filtro

```gherkin
@backend
Scenario: Filtering by a group with no active categories returns no movements, not an error
  Given a category group "Antiguo"
  And a category "Descontinuada" in group "Antiguo"
  And the user archives the category "Descontinuada"
  When the user lists transactions in group "Antiguo"
  Then the list is empty
```

## AC-11 — El drill-down funciona también desde una categoría, grupo o etiqueta archivada

```gherkin
Scenario: Ver movimientos still works from an archived category
  Given the app is open
  And an archived category "Descontinuada"
  When the owner opens "Ver movimientos" for the category "Descontinuada"
  Then the transaction list is filtered to category "Descontinuada"
```

## AC-12 — Grupo y categoría elegidos juntos se combinan como cualquier otro par de filtros

```gherkin
@backend
Scenario: A group filter and an unrelated category filter combine with AND
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  And a category group "Finanzas"
  And a category "Ahorros" in group "Finanzas"
  And a category "Comida"
  And the user registers an expense of 50000.00 COP from "Bancolombia" paying "Fondo" in category "Ahorros"
  And the user registers an expense of 20000.00 COP from "Bancolombia" paying "Exito" in category "Comida"
  When the user lists transactions in group "Finanzas" in category "Comida"
  Then the list is empty
```

## AC-13 — El filtro de monto puede traer una fila distinta mañana, sin que el movimiento cambie

```gherkin
@backend
Scenario: A movement below the COP threshold today is excluded
  Given the TRM is 4000.00
  And an account "DolarApp" in USD with balance 100.00 USD
  And a category "Suscripciones"
  And the user registers an expense of 24.00 USD from "DolarApp" paying "Netflix" in category "Suscripciones"
  When the user lists transactions with amount at least 100000.00 COP
  Then the list is empty

@backend
Scenario: The same movement is included after the TRM rises
  Given the TRM is 4000.00
  And an account "DolarApp" in USD with balance 100.00 USD
  And a category "Suscripciones"
  And the user registers an expense of 24.00 USD from "DolarApp" paying "Netflix" in category "Suscripciones"
  And the user sets the TRM to 4500.00
  When the user lists transactions with amount at least 100000.00 COP
  Then the list shows only "Netflix"
```

## AC-14 — Sin la TRM del día, el filtro de monto se bloquea igual que cualquier lectura que convierte moneda

```gherkin
@backend
Scenario: Filtering by amount without a TRM set fails the same way any conversion does
  Given no TRM has been set
  And a recorded expense of 50000.00 COP
  When the user lists transactions with amount at least 10000.00 COP
  Then the list is not shown
  And the user is told, in English as before, that no TRM was set
```

## AC-15 — El filtro de monto se prueba con un movimiento en una cuenta de otra moneda

```gherkin
@backend
Scenario: The amount filter compares a foreign-currency movement in pesos
  Given the TRM is 4000.00
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  And the user registers an expense of 40.00 USD from "DolarApp" paying "Netflix" in category "Suscripciones"
  When the user lists transactions with amount at least 100000.00 COP
  Then the list shows only "Netflix"
```
