# Acceptance specs — 002 transactions-crud

Formalizes `acs.md` (16 ACs, approved 2026-07-31) as standard Gherkin.
Amounts are plain decimals (`50000.00 COP`), no thousands separators.
Cross-currency transfer mechanics and read-time COP conversion are already
pinned by feature 005's suite — here they appear only where this feature
adds behavior on top. The URL half of AC-8 (filters live in the page URL)
is covered by the frontend's own tests (no e2e layer per the charter);
these scenarios pin the filtering behavior itself. AC-5 and AC-6 scenarios
describe decided target behavior and are expected RED against current code
(ATDD red phase).

Amended 2026-08-03 by feature 008: every action that files money under a
category now names it, because the app no longer accepts an expense or an
income without one. A `Given` movement (`a recorded expense of …`) is filed
under a category the scenario does not name — the category exists, it is just
irrelevant to what the scenario pins. An untyped `a category "X"` is an expense
category; income categories are written `an income category "X"`. AC-3's
`The category can be cleared` scenario was removed; 008's AC-11 replaces it
with the opposite rule.

```gherkin
Feature: Transactions CRUD with tags, categories and read-time FX
```

## AC-1 — Record an expense or income

```gherkin
Scenario: Registering an expense moves the balance down
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  And a category "Comida"
  When the user registers an expense of 50000.00 COP from "Bancolombia" paying "Exito" in category "Comida"
  Then the expense is recorded with amount 50000.00 COP
  And "Bancolombia" has balance 950000.00 COP

Scenario: Registering an income moves the balance up
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  And an income category "Sueldo"
  When the user registers an income of 2000000.00 COP into "Bancolombia" from "Salario" in category "Sueldo"
  Then "Bancolombia" has balance 3000000.00 COP

Scenario: A registration keeps its descriptive details
  Given an account "Bancolombia" in COP with balance 100000.00 COP
  And a category "Comida"
  When the user registers an expense of 20000.00 COP from "Bancolombia" paying "Exito" in category "Comida" dated 2026-07-15 with notes "mercado"
  Then viewing the expense shows payee "Exito", category "Comida", date 2026-07-15 and notes "mercado"
```

## AC-2 — A transfer is an atomic pair

```gherkin
Scenario: A transfer records two linked movements
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  And an account "Nequi" in COP with balance 200000.00 COP
  When the user transfers 100000.00 COP from "Bancolombia" to "Nequi"
  Then the transfer is recorded as two movements linked as one transfer
  And "Bancolombia" has balance 900000.00 COP
  And "Nequi" has balance 300000.00 COP

Scenario: A transfer counts as neither income nor expense
  Given the TRM is 4000.00
  And an account "Bancolombia" in COP with balance 1000000.00 COP
  And an account "Nequi" in COP with balance 200000.00 COP
  When the user transfers 100000.00 COP from "Bancolombia" to "Nequi"
  Then the current month's report shows an expense total of 0.00 COP
  And the current month's report shows an income total of 0.00 COP
```

## AC-3 — Editing touches only balance-safe fields

```gherkin
Scenario: Editing descriptive fields never moves the balance
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  And a category "Comida"
  And a category "Mercado"
  And the user registers an expense of 50000.00 COP from "Bancolombia" paying "Exito" in category "Mercado"
  When the user edits the expense changing payee to "Carulla", category to "Comida", date to 2026-07-12 and notes to "corregido"
  Then viewing the expense shows payee "Carulla", category "Comida", date 2026-07-12 and notes "corregido"
  And "Bancolombia" has balance 950000.00 COP
```

## AC-4 — Deleting is permanent and reverses the balance

```gherkin
Scenario: Deleting an expense restores the balance
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  And a category "Comida"
  And the user registers an expense of 50000.00 COP from "Bancolombia" paying "Exito" in category "Comida"
  When the user deletes the expense
  Then "Bancolombia" has balance 1000000.00 COP
  And the transaction list does not show the expense

Scenario: Deleting a tagged transaction leaves other transactions' tags intact
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  And a recorded expense of 10000.00 COP tagged "viaje"
  And a recorded expense of 20000.00 COP tagged "viaje"
  When the user deletes the first expense
  Then the remaining expense still carries the tag "viaje"
```

## AC-5 — A mistaken transfer can be deleted as a pair

```gherkin
Scenario: Deleting a transfer removes both sides and restores both balances
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  And an account "Nequi" in COP with balance 200000.00 COP
  And the user transfers 100000.00 COP from "Bancolombia" to "Nequi"
  When the user deletes the transfer
  Then "Bancolombia" has balance 1000000.00 COP
  And "Nequi" has balance 200000.00 COP
  And the transaction list shows no transfer

Scenario: Deleting the receiving side deletes the whole pair
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  And an account "Nequi" in COP with balance 200000.00 COP
  And the user transfers 100000.00 COP from "Bancolombia" to "Nequi"
  When the user deletes the receiving side of the transfer
  Then "Bancolombia" has balance 1000000.00 COP
  And "Nequi" has balance 200000.00 COP
  And the transaction list shows no transfer

Scenario: Deleting a cross-currency transfer restores each physical amount
  Given an account "Wise" in USD with balance 500.00 USD
  And an account "Bancolombia" in COP with balance 1000000.00 COP
  And the user transfers sending 100.00 USD from "Wise" and receiving 400000.00 COP into "Bancolombia"
  When the user deletes the transfer
  Then "Wise" has balance 500.00 USD
  And "Bancolombia" has balance 1000000.00 COP
```

## AC-6 — Tags work on every surface, add and remove

```gherkin
Scenario: Tagging at creation
  Given an account "Bancolombia" in COP with balance 100000.00 COP
  And a category "Comida"
  When the user registers an expense of 20000.00 COP from "Bancolombia" paying "Exito" in category "Comida" tagged "viaje" and "comida"
  Then viewing the expense shows the tags "viaje" and "comida"

Scenario: Adding a tag while editing
  Given an account "Bancolombia" in COP with balance 100000.00 COP
  And a recorded expense of 20000.00 COP tagged "viaje"
  When the user adds the tag "reembolso" to the expense
  Then viewing the expense shows the tags "viaje" and "reembolso"

Scenario: Removing a tag from a transaction
  Given an account "Bancolombia" in COP with balance 100000.00 COP
  And a recorded expense of 20000.00 COP tagged "viaje"
  When the user removes the tag "viaje" from the expense
  Then viewing the expense shows no tags

Scenario: Re-applying an existing tag never duplicates it
  Given an account "Bancolombia" in COP with balance 100000.00 COP
  And a recorded expense of 20000.00 COP tagged "viaje"
  When the user adds the tag "viaje" to the expense
  Then viewing the expense shows the tag "viaje" exactly once
```

## AC-7 — Lists show the most recent activity first

```gherkin
Scenario: The list orders by the transaction's own date, newest first
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  And a category "Comida"
  And the user registers an expense of 10000.00 COP from "Bancolombia" paying "A" in category "Comida" dated 2026-07-20
  And the user registers an expense of 10000.00 COP from "Bancolombia" paying "B" in category "Comida" dated 2026-07-12
  When the user views the transaction list
  Then the list shows "A" above "B"

Scenario: Planned obligations appear at their due-date position
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  And a category "Comida"
  And the user registers an expense of 10000.00 COP from "Bancolombia" paying "Exito" in category "Comida" dated 2026-07-10
  And a planned payment of 80000.00 COP to "Arriendo" due 2026-07-25
  When the user views the transaction list
  Then the list shows "Arriendo" above "Exito"
```

## AC-8 — Filters combine

```gherkin
Scenario: Category and date-range filters combine
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  And a category "Comida"
  And a category "Transporte"
  And the user registers an expense of 10000.00 COP from "Bancolombia" paying "Exito" in category "Comida" dated 2026-07-10
  And the user registers an expense of 20000.00 COP from "Bancolombia" paying "Uber" in category "Transporte" dated 2026-07-10
  And the user registers an expense of 30000.00 COP from "Bancolombia" paying "Carulla" in category "Comida" dated 2026-07-20
  When the user lists transactions in category "Comida" between 2026-07-01 and 2026-07-15
  Then the list shows only "Exito"
```

## AC-9 — COP equivalents are read-time on this surface

```gherkin
Scenario: Listing transactions without a TRM fails with a clear message
  Given no TRM has been set
  And a recorded expense of 50000.00 COP
  When the user views the transaction list
  Then the list is not shown
  And the user is told to set the TRM
```

## AC-10 — A transfer side is never edited blind

```gherkin
Scenario: Editing one side leaves the other untouched
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  And an account "Nequi" in COP with balance 200000.00 COP
  And the user transfers 100000.00 COP from "Bancolombia" to "Nequi" dated 2026-07-10
  When the user changes the date of the sending side to 2026-07-12
  Then the sending side shows date 2026-07-12
  And the receiving side shows date 2026-07-10

Scenario: A transfer side identifies its counterpart
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  And an account "Nequi" in COP with balance 200000.00 COP
  And the user transfers 100000.00 COP from "Bancolombia" to "Nequi"
  When the user views the sending side of the transfer
  Then it is identified as part of a transfer
  And its counterpart in "Nequi" is reachable from it
```

## AC-11 — Boundary values are honored

```gherkin
Scenario: One-cent registrations are accepted
  Given an account "Bancolombia" in COP with balance 100.00 COP
  And a category "Comida"
  When the user registers an expense of 0.01 COP from "Bancolombia" paying "Minimo" in category "Comida"
  Then the expense is recorded with amount 0.01 COP
  And "Bancolombia" has balance 99.99 COP

Scenario: The date-range filter includes its boundary days
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  And a category "Comida"
  And the user registers an expense of 10000.00 COP from "Bancolombia" paying "Primero" in category "Comida" dated 2026-07-01
  And the user registers an expense of 10000.00 COP from "Bancolombia" paying "Ultimo" in category "Comida" dated 2026-07-15
  And the user registers an expense of 10000.00 COP from "Bancolombia" paying "Fuera" in category "Comida" dated 2026-07-16
  When the user lists transactions between 2026-07-01 and 2026-07-15
  Then the list shows "Primero" and "Ultimo" but not "Fuera"
```

## AC-12 — Invalid registrations are rejected whole

```gherkin
Scenario Outline: An invalid registration is rejected and nothing changes
  Given an account "Bancolombia" in COP with balance 100000.00 COP
  And a category "Comida"
  When the user registers an expense of <amount> <currency> from "Bancolombia" in category "Comida"
  Then the registration is rejected
  And "Bancolombia" has balance 100000.00 COP

  Examples:
    | amount  | currency |
    | 0       | COP      |
    | -50.00  | COP      |
    | 100.00  | USD      |
    | 100.00  | XYZ      |

Scenario: Registering into an archived account is rejected
  Given an archived account "Vieja" in COP
  And a category "Comida"
  When the user registers an expense of 10000.00 COP from "Vieja" in category "Comida"
  Then the registration is rejected

Scenario: Registering with an archived category is rejected
  Given an account "Bancolombia" in COP with balance 100000.00 COP
  And an archived category "Vieja"
  When the user registers an expense of 10000.00 COP from "Bancolombia" paying "Exito" in category "Vieja"
  Then the registration is rejected
  And "Bancolombia" has balance 100000.00 COP
```

## AC-13 — Failed multi-part writes leave nothing behind

```gherkin
Scenario: A transfer to an unknown account leaves everything intact
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  When the user transfers 100000.00 COP from "Bancolombia" to "Fantasma"
  Then the transfer is rejected
  And "Bancolombia" has balance 1000000.00 COP
  And the transaction list shows no transfer
```

## AC-14 — Missing transactions answer clearly

```gherkin
Scenario Outline: Acting on a missing transaction answers "not found"
  When the user tries to <action> a transaction that does not exist
  Then the user is told it does not exist

  Examples:
    | action |
    | view   |
    | edit   |
    | delete |
```

## AC-15 — The agent is a co-equal surface

```gherkin
Scenario: The assistant records a tagged expense like the app
  Given the TRM is 4000.00
  And an account "Bancolombia" in COP with balance 100000.00 COP
  And a category "Comida"
  When the assistant records an expense of 20000.00 COP from "Bancolombia" paying "Exito" in category "Comida" tagged "viaje"
  Then the transaction list shows the expense
  And viewing the expense shows the tag "viaje"
  And the expense records the assistant as its origin

Scenario: The assistant removes a tag like the app
  Given the TRM is 4000.00
  And an account "Bancolombia" in COP with balance 100000.00 COP
  And a recorded expense of 20000.00 COP tagged "viaje"
  When the assistant removes the tag "viaje" from the expense
  Then viewing the expense shows no tags

Scenario: The app and the assistant list the same filtered movements
  Given the TRM is 4000.00
  And an account "Bancolombia" in COP with balance 100000.00 COP
  And a recorded expense of 10000.00 COP tagged "viaje"
  And a recorded expense of 20000.00 COP tagged "trabajo"
  When the user lists transactions tagged "viaje" in the app
  And the assistant lists transactions tagged "viaje"
  Then both show the same movements
```

## AC-16 — The surface requires a session

```gherkin
Scenario: Without a session the transaction list is denied
  Given the user has no session
  When they request the transaction list
  Then access is denied
```
