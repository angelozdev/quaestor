# Acceptance specs — 005 fx-read-time-conversion

Formalizes `acs.md` (14 ACs, approved 2026-07-30) as standard Gherkin.
Amounts are written as plain decimals (`40000.00 COP`) — no thousands
separators. "The TRM" is the single USD→COP rate the app knows (ADR-0031,
amended: single scalar value).

Amended 2026-08-03 by feature 008: every action that files money under a
category now names it, because the app no longer accepts an expense without
one. A `Given` movement (`a recorded expense of …`) is filed under a category
the scenario does not name — the category exists, it is just irrelevant to the
conversion these scenarios pin. An untyped `a category "X"` is an expense
category.

```gherkin
Feature: Read-time FX conversion and cross-currency transfers
```

## AC-1 — Register foreign-currency transactions without a rate

```gherkin
Scenario: Register a USD expense without providing a rate
  Given no TRM has been set
  And an account "Wise" in USD with balance 500.00 USD
  And a category "Comida"
  When the user registers an expense of 100.00 USD from "Wise" in category "Comida"
  Then the expense is recorded with amount 100.00 USD
  And viewing the expense shows no exchange rate
  And "Wise" has balance 400.00 USD
```

## AC-2 — Base-currency figures are computed at read time from the TRM

```gherkin
Scenario: The COP equivalent of a USD transaction follows the current TRM
  Given the TRM is 4000.00
  And a recorded expense of 10.00 USD
  When the user views the expense
  Then its COP equivalent shows 40000.00 COP

Scenario: Monthly report totals convert at the current TRM
  Given the TRM is 4000.00
  And a recorded expense of 10.00 USD in the current month
  And a recorded expense of 50000.00 COP in the current month
  When the user views the current month's report
  Then the month's expense total shows 90000.00 COP

Scenario: Budget spending converts at the current TRM
  Given the TRM is 4000.00
  And a category "Comida" with a recorded expense of 10.00 USD in the current month
  When the user views the current month's budget
  Then the spending for "Comida" shows 40000.00 COP
```

## AC-3 — Correcting the TRM retroactively updates every figure

```gherkin
Scenario: Correcting the TRM updates a closed month's total
  Given the TRM is 4000.00
  And a recorded expense of 10.00 USD dated in a previous month
  When the user sets the TRM to 4100.00
  Then that previous month's report shows an expense total of 41000.00 COP
```

## AC-4 — COP amounts are unaffected by the TRM

```gherkin
Scenario: COP amounts do not move with the TRM
  Given the TRM is 4000.00
  And a recorded expense of 50000.00 COP
  When the user sets the TRM to 4100.00
  Then the expense's COP equivalent shows 50000.00 COP
```

## AC-5 — The TRM is a single value kept fresh by the daily job

```gherkin
Scenario: The daily rate update overwrites the TRM
  Given the TRM is 4000.00
  When the daily rate update sets the TRM to 4050.00
  Then the current TRM is 4050.00

Scenario: A manual correction overwrites the TRM
  Given the TRM is 4050.00
  When the user sets the TRM to 4100.00
  Then the current TRM is 4100.00
```

## AC-6 — Cross-currency transfers record two physical amounts

```gherkin
Scenario: Transfer between accounts in different currencies
  Given an account "Wise" in USD with balance 500.00 USD
  And an account "Bancolombia" in COP with balance 1000000.00 COP
  When the user transfers sending 100.00 USD from "Wise" and receiving 400000.00 COP into "Bancolombia"
  Then "Wise" has balance 400.00 USD
  And "Bancolombia" has balance 1400000.00 COP
  And viewing the transfer shows no exchange rate
```

## AC-7 — Same-currency transfers keep working with one amount

```gherkin
Scenario: Transfer between accounts in the same currency
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  And an account "Nequi" in COP with balance 200000.00 COP
  When the user transfers 100000.00 COP from "Bancolombia" to "Nequi"
  Then "Bancolombia" has balance 900000.00 COP
  And "Nequi" has balance 300000.00 COP
```

## AC-8 — The implied transfer rate is shown as information only

```gherkin
Scenario: The transfer form shows the implied rate between currencies
  Given an account "Wise" in USD
  And an account "Bancolombia" in COP
  When the user prepares a transfer sending 100.00 USD from "Wise" and receiving 400000.00 COP into "Bancolombia"
  Then the transfer form shows an implied rate of 4000.00

Scenario: A transfer with an off-market implied rate is accepted
  Given an account "Wise" in USD with balance 500.00 USD
  And an account "Bancolombia" in COP with balance 1000000.00 COP
  When the user transfers sending 100.00 USD from "Wise" and receiving 1.00 COP into "Bancolombia"
  Then "Wise" has balance 400.00 USD
  And "Bancolombia" has balance 1000001.00 COP
```

## AC-9 — Reads fail loud when no TRM is set

```gherkin
Scenario: Viewing a report with no TRM set fails with a clear message
  Given no TRM has been set
  And a recorded expense of 50000.00 COP
  When the user views the current month's report
  Then the report is not shown
  And the user is told to set the TRM

Scenario: Setting the TRM unblocks reading
  Given no TRM has been set
  And a recorded expense of 50000.00 COP
  When the user sets the TRM to 4000.00
  Then the current month's report shows an expense total of 50000.00 COP
```

## AC-10 — Invalid TRM values are rejected

```gherkin
Scenario Outline: Setting an invalid TRM is rejected
  Given the TRM is 4000.00
  When the user sets the TRM to <value>
  Then the change is rejected
  And the current TRM is 4000.00

  Examples:
    | value   |
    | 0       |
    | -100.00 |
```

## AC-11 — Invalid transfer input is rejected atomically

```gherkin
Scenario Outline: A cross-currency transfer with an invalid amount is rejected
  Given an account "Wise" in USD with balance 500.00 USD
  And an account "Bancolombia" in COP with balance 1000000.00 COP
  When the user transfers sending <sent> USD from "Wise" and receiving <received> COP into "Bancolombia"
  Then the transfer is rejected
  And "Wise" has balance 500.00 USD
  And "Bancolombia" has balance 1000000.00 COP

  Examples:
    | sent   | received  |
    | 0      | 400000.00 |
    | 100.00 | 0         |
    | -50.00 | 400000.00 |
    | 100.00 | -400000.00 |

Scenario: A transfer to the same account is rejected
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  When the user transfers 100000.00 COP from "Bancolombia" to "Bancolombia"
  Then the transfer is rejected
  And "Bancolombia" has balance 1000000.00 COP
```

## AC-12 — Migration preserves original amounts and drops stored conversions

```gherkin
Scenario: Upgrading preserves every transaction's original amount
  Given transactions recorded before the upgrade, including foreign-currency ones
  When the upgrade completes
  Then every transaction still shows its original amount and currency
  And viewing any transaction shows no exchange rate
```

## AC-13 — REST and MCP surfaces stay in parity

```gherkin
Scenario: The app and the assistant interface show the same COP equivalent
  Given the TRM is 4000.00
  And a recorded expense of 10.00 USD
  When the user views the expense in the app
  And the assistant interface lists the same expense
  Then both show a COP equivalent of 40000.00 COP
```

## AC-14 — Conversion rounding is consistent

```gherkin
Scenario Outline: USD to COP conversion rounds half-up to the cent
  Given the TRM is <trm>
  And a recorded expense of <usd> USD
  When the user views the expense
  Then its COP equivalent shows <cop> COP

  Examples:
    | trm     | usd  | cop      |
    | 4122.50 | 0.01 | 41.23    |
    | 4122.50 | 0.03 | 123.68   |
    | 4000.00 | 10.00 | 40000.00 |
```
