# Acceptance specs — 008 mandatory-categories

Formalizes `acs.md` (19 ACs, approved 2026-08-02) as standard Gherkin.
Amounts are plain decimals (`50000.00 COP`), no thousands separators. Dates are
relative to the day the scenario runs unless a scenario needs a fixed calendar.

Categories are now typed by direction, so this suite says **expense category**
or **income category** wherever the direction matters. The untyped
`a category "X"` of the earlier suites keeps meaning an expense category.

Balance mechanics are pinned by feature 002's suite, read-time COP conversion by
005's, the outstanding queue by 006's and the recurring engine by 007's — here
they appear only where this feature adds behaviour on top.

Most scenarios here describe decided target behaviour and are expected RED
against current code (ATDD red phase). AC-11 reverses a scenario feature 002's
suite used to assert (`The category can be cleared`, removed 2026-08-03);
AC-16 pins behaviour that already exists so the new rule cannot weaken it, and
AC-6, AC-8, AC-9 and AC-19 run green because the recurring engine already
copies a category onto every charge and the production data is already clean.

**Where each AC is observed.** Every AC except AC-17 is observed at a surface a
person uses — the app, or the assistant. **AC-17 deliberately drops one level
below that**, to the records themselves: it asserts the guarantee survives the
app being circumvented entirely, which no user can witness. That is the point
of the AC, and the only place in this suite where the boundary moves.

**Order is not pinned.** `the categories offered are …` asserts a set, not a
sequence. Nothing in this feature decides how the choices are sorted on screen.

```gherkin
Feature: Every expense and income carries a category
```

## AC-1 — Recording an expense requires a category

```gherkin
Scenario: An expense with no category is refused
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  When the user tries to register an expense of 50000.00 COP from "Bancolombia" paying "Exito" with no category
  Then the registration is rejected
  And the user is told the category is missing
  And "Bancolombia" has balance 500000.00 COP
  And the transaction list does not show the expense

Scenario: The same expense is recorded once it says what it was for
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And an expense category "Comida"
  When the user registers an expense of 50000.00 COP from "Bancolombia" paying "Exito" in category "Comida"
  Then "Bancolombia" has balance 450000.00 COP
  And viewing the expense shows category "Comida"
```

## AC-2 — Recording an income requires a category

```gherkin
Scenario: An income with no category is refused
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  When the user tries to register an income of 2000000.00 COP into "Bancolombia" from "Empresa" with no category
  Then the registration is rejected
  And the user is told the category is missing
  And "Bancolombia" has balance 500000.00 COP

Scenario: The same income is recorded once it says where it came from
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And an income category "Salario"
  When the user registers an income of 2000000.00 COP into "Bancolombia" from "Empresa" in category "Salario"
  Then "Bancolombia" has balance 2500000.00 COP
  And viewing the income shows category "Salario"
```

## AC-3 — A transfer carries no category

```gherkin
Scenario: Moving money between own accounts needs no category
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  And an account "Ahorros" in COP with balance 0.00 COP
  When the user transfers 200000.00 COP from "Bancolombia" to "Ahorros"
  Then "Bancolombia" has balance 800000.00 COP
  And "Ahorros" has balance 200000.00 COP
  And both sides of the transfer show no category

Scenario: Attaching a category to a transfer is refused
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  And an account "Ahorros" in COP with balance 0.00 COP
  And an expense category "Comida"
  When the user tries to transfer 200000.00 COP from "Bancolombia" to "Ahorros" in category "Comida"
  Then the transfer is rejected
  And "Bancolombia" has balance 1000000.00 COP
  And "Ahorros" has balance 0.00 COP
```

## AC-4 — The categories offered match the direction of the money

```gherkin
Scenario: Recording money going out offers only expense categories
  Given an expense category "Comida"
  And an expense category "Transporte"
  And an income category "Salario"
  When the user starts recording an expense
  Then the categories offered are "Comida" and "Transporte"

Scenario: Recording money coming in offers only income categories
  Given an expense category "Comida"
  And an income category "Salario"
  And an income category "Rendimientos"
  When the user starts recording an income
  Then the categories offered are "Rendimientos" and "Salario"

Scenario: A salary cannot be filed under a spending category
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And an expense category "Restaurantes"
  When the user starts recording an income
  Then the categories offered do not include "Restaurantes"
```

## AC-5 — A new category can be created without leaving the form

```gherkin
Scenario: A missing category is created while the movement is being recorded
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  When the user records an expense of 12000.00 COP from "Bancolombia" paying "Banco" creating the category "4x1000"
  Then "Bancolombia" has balance 488000.00 COP
  And viewing the expense shows category "4x1000"

Scenario: What was already typed survives creating the category
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  When the user records an expense of 12000.00 COP from "Bancolombia" paying "Banco" with notes "gravamen" creating the category "4x1000"
  Then viewing the expense shows payee "Banco" and notes "gravamen"
  And viewing the expense shows category "4x1000"

Scenario: The new category is available from then on
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And the user records an expense of 12000.00 COP from "Bancolombia" paying "Banco" creating the category "4x1000"
  When the user starts recording an expense
  Then the categories offered are "4x1000"
```

## AC-6 — A recurring item requires a category, and its charges inherit it

```gherkin
Scenario: A repeating obligation with no category is refused
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  When the user tries to declare a repeating payment of 85000.00 COP to "Claro" from "Bancolombia" every 1 month starting today with no category, paying itself
  Then the declaration is rejected
  And the user is told the category is missing

Scenario: A charge that posts is born with the obligation's category
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And an expense category "Servicios"
  And a repeating payment of 85000.00 COP to "Claro" from "Bancolombia" every 1 month starting today in category "Servicios", paying itself
  When the daily run happens
  Then the charge to "Claro" from today shows category "Servicios"

Scenario: A charge that waits for approval is born with the obligation's category
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And an expense category "Servicios"
  And a repeating payment of 1800000.00 COP to "Arriendo" from "Bancolombia" every 1 month starting today in category "Servicios", waiting for approval
  When the daily run happens
  Then the charge to "Arriendo" from today shows category "Servicios"

Scenario: A repeating income needs an income category
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And an income category "Salario"
  And a repeating income of 4500000.00 COP from "Empresa" into "Bancolombia" every 1 month starting today in category "Salario", paying itself
  When the daily run happens
  Then the charge from "Empresa" from today shows category "Salario"
```

## AC-7 — A planned payment requires a category

```gherkin
Scenario: Planning a payment with no category is refused
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  When the user tries to plan a payment of 300000.00 COP to "Taller" from "Bancolombia" due in 19 days with no category
  Then the plan is rejected
  And the user is told the category is missing

Scenario: A payment that is only owed already says what it is for
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And an expense category "Carro"
  When the user plans a payment of 300000.00 COP to "Taller" from "Bancolombia" due in 19 days in category "Carro"
  Then viewing the planned payment to "Taller" shows category "Carro"
```

## AC-8 — Changing a recurring item's category leaves its existing charges alone

```gherkin
Scenario: Re-classifying an obligation applies from that point forward
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And an expense category "Servicios"
  And an expense category "Hogar"
  And a repeating payment of 85000.00 COP to "Claro" from "Bancolombia" every 1 month starting today in category "Servicios", paying itself
  And the daily run happens
  When the user moves the repeating payment to "Claro" to category "Hogar"
  Then the charge to "Claro" from today shows category "Servicios"
  And the repeating payment to "Claro" is in category "Hogar"

Scenario: A single charge can be re-classified on its own
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And an expense category "Servicios"
  And an expense category "Hogar"
  And a repeating payment of 85000.00 COP to "Claro" from "Bancolombia" every 1 month starting today in category "Servicios", paying itself
  And the daily run happens
  When the user moves the charge to "Claro" from today to category "Hogar"
  Then the charge to "Claro" from today shows category "Hogar"
  And the repeating payment to "Claro" is in category "Servicios"
```

## AC-9 — A skipped charge carries a category too

```gherkin
Scenario: Declining a charge does not drop what it was for
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And an expense category "Servicios"
  And a repeating payment of 85000.00 COP to "Claro" from "Bancolombia" every 1 month starting today in category "Servicios", waiting for approval
  And the daily run happens
  When the user skips the turn of "Claro" due today
  Then the turn of "Claro" due today is skipped
  And the charge to "Claro" from today shows category "Servicios"

Scenario: Skipping a planned payment does not drop what it was for
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And an expense category "Carro"
  And a planned payment of 300000.00 COP to "Taller" from "Bancolombia" due in 3 days in category "Carro"
  When the user skips the payment to "Taller"
  Then viewing the planned payment to "Taller" shows category "Carro"
```

## AC-10 — An archived category keeps its history

```gherkin
Scenario: Archiving removes a category from the choices but not from the past
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And an expense category "Antojos"
  And the user registers an expense of 20000.00 COP from "Bancolombia" paying "Exito" in category "Antojos"
  When the user archives the category "Antojos"
  Then viewing the expense shows category "Antojos"
  And the categories offered for an expense do not include "Antojos"

Scenario: Restoring the category brings it back as a choice
  Given an expense category "Antojos"
  And the user archives the category "Antojos"
  When the user restores the category "Antojos"
  Then the categories offered are "Antojos"
```

## AC-11 — A category cannot be stripped off a movement that already has one

```gherkin
Scenario: Clearing the category of an expense is refused
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And an expense category "Comida"
  And the user registers an expense of 20000.00 COP from "Bancolombia" paying "Exito" in category "Comida"
  When the user tries to clear the expense's category
  Then the edit is rejected
  And viewing the expense shows category "Comida"

Scenario: Swapping one category for another is allowed
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And an expense category "Comida"
  And an expense category "Mercado"
  And the user registers an expense of 20000.00 COP from "Bancolombia" paying "Exito" in category "Comida"
  When the user moves the expense to category "Mercado"
  Then viewing the expense shows category "Mercado"
```

## AC-12 — A category created from the form is born with the right direction

```gherkin
Scenario: A category created while recording an income is an income category
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And the user records an income of 300000.00 COP into "Bancolombia" from "Banco" creating the category "Rendimientos"
  When the user starts recording an income
  Then the categories offered are "Rendimientos"

Scenario: A category created while recording an expense is an expense category
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And the user records an expense of 12000.00 COP from "Bancolombia" paying "Banco" creating the category "4x1000"
  When the user starts recording an income
  Then the categories offered do not include "4x1000"
```

## AC-13 — Creating a category that already exists is refused

```gherkin
Scenario: A name that is already in use is refused
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And an expense category "Vuelos"
  When the user tries to record an expense of 900000.00 COP from "Bancolombia" paying "Avianca" creating the category "Vuelos"
  Then the registration is rejected
  And the user is told that category already exists

Scenario: A name matching an archived category offers to restore it
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And an expense category "Vuelos"
  And the user archives the category "Vuelos"
  When the user tries to record an expense of 900000.00 COP from "Bancolombia" paying "Avianca" creating the category "Vuelos"
  Then the registration is rejected
  And the user is offered to restore the archived category "Vuelos"
```

## AC-14 — The rule holds on every way in, not just the form

```gherkin
Scenario: The assistant cannot record an uncategorised expense either
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  When the assistant tries to record an expense of 20000.00 COP from "Bancolombia" paying "Exito" with no category
  Then the registration is rejected
  And "Bancolombia" has balance 500000.00 COP

Scenario: The assistant cannot plan an uncategorised payment either
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  When the assistant tries to plan a payment of 85000.00 COP to "Claro" from "Bancolombia" due in 3 days with no category
  Then the plan is rejected

Scenario: The assistant cannot declare an uncategorised obligation either
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  When the assistant tries to declare a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 month starting today with no category, paying itself
  Then the declaration is rejected
```

## AC-15 — A category of the wrong direction is refused

```gherkin
Scenario: An income filed under a spending category is refused
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And an expense category "Restaurantes"
  When the user tries to register an income of 6223101.00 COP into "Bancolombia" from "Empresa" in category "Restaurantes"
  Then the registration is rejected
  And the user is told the category does not match the direction of the money
  And "Bancolombia" has balance 500000.00 COP

Scenario: An expense filed under an income category is refused
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And an income category "Salario"
  When the user tries to register an expense of 50000.00 COP from "Bancolombia" paying "Exito" in category "Salario"
  Then the registration is rejected
  And "Bancolombia" has balance 500000.00 COP

Scenario: A repeating income cannot be declared under a spending category
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And an expense category "Restaurantes"
  When the user tries to declare a repeating income of 4500000.00 COP from "Empresa" into "Bancolombia" every 1 month starting today in category "Restaurantes", paying itself
  Then the declaration is rejected
```

## AC-16 — An unknown or archived category is refused

```gherkin
Scenario: A category that does not exist is refused
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  When the user tries to register an expense of 50000.00 COP from "Bancolombia" paying "Exito" in category "Inventada"
  Then the registration is rejected
  And the user is told which category was at fault

Scenario: An archived category is refused for a new movement
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And an archived category "Suscripciones"
  When the user tries to register an expense of 50000.00 COP from "Bancolombia" paying "Netflix" in category "Suscripciones"
  Then the registration is rejected
  And the user is told which category was at fault
```

## AC-17 — The records cannot hold an uncategorised expense or income

```gherkin
Scenario: An uncategorised expense cannot be forced into the records
  When money going out with no category is forced into the records, bypassing the app
  Then the records refuse to hold it

Scenario: An uncategorised income cannot be forced into the records
  When money coming in with no category is forced into the records, bypassing the app
  Then the records refuse to hold it

Scenario: A categorised transfer cannot be forced into the records
  Given an expense category "Comida"
  When a transfer carrying category "Comida" is forced into the records, bypassing the app
  Then the records refuse to hold it

Scenario: A transfer with no category is held without complaint
  When a transfer with no category is forced into the records, bypassing the app
  Then the records hold it
```

## AC-18 — The change refuses to apply while any movement is uncategorised

```gherkin
Scenario: The upgrade refuses while an expense is still uncategorised
  Given 3 categorised movements and 1 uncategorised expense recorded before the upgrade
  When the upgrade is attempted
  Then the upgrade is refused
  And the refusal says 1 expense is still uncategorised

Scenario: The upgrade refuses while an income is still uncategorised
  Given 3 categorised movements and 2 uncategorised incomes recorded before the upgrade
  When the upgrade is attempted
  Then the upgrade is refused
  And the refusal says 2 incomes are still uncategorised

Scenario: Uncategorised transfers do not block the upgrade
  Given 3 categorised movements recorded before the upgrade
  And 3 transfers recorded before the upgrade with no category
  When the upgrade completes
  Then every transfer still shows no category
```

## AC-19 — The existing data is already clean

```gherkin
Scenario: Every movement keeps the category it had before the upgrade
  Given 3 categorised movements recorded before the upgrade
  When the upgrade completes
  Then every expense and income still shows the category it had
  And no expense or income is left uncategorised
```
