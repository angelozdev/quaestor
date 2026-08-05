# Acceptance specs — 003 sinking-funds

Formalizes `acs.md` (30 ACs, approved 2026-08-03) as standard Gherkin.

Amounts are plain decimals (`161400.00 COP`), no thousands separators. **The
figures here are chosen to divide cleanly**; `acs.md` carries the production
numbers that motivated each rule, and those are the motivation, not the
fixtures. Where a rule's arithmetic is the point, the scenario states every
term of it.

Category names are plain (`Internet`, `Seguro`) rather than the emoji ones
production carries, matching the other suites.

**A fund is the one new noun.** It lives on one expense category, carries a
funding rule and a start month, and *asks* for an amount each month. "Asks" is
the whole of its behaviour: the ask is subtracted from the money available, and
nothing about a fund is ever a monthly ritual.

**Two numbers, never merged.** *The money available this month* is a balance —
it never counts income that has not arrived. *The earning rate*, *the cost rate*
and *the margin* are rates, and those are smoothed. Scenarios say which one they
are asserting, always.

Balance mechanics are pinned by feature 002's suite, read-time COP conversion by
005's, the outstanding queue by 006's, the recurring engine by 007's and
category direction by 008's — here they appear only where this feature adds
behaviour on top.

**Every scenario in this suite is expected RED** against current code. Nothing
in it exists: there is no fund, the headline it replaces computes a different
formula, and goals are still a separate concept. This is the ATDD red phase in
its pure form, unlike 008 where some scenarios pinned shipped behaviour.

**Where each AC is observed.** At a surface a person uses — the app or the
assistant — except AC-27, which drops to the records to assert what an upgrade
removes, the same allowance 008's AC-17 took and for the same reason.

**Order is not pinned.** `the breakdown names …` asserts presence, not
position. Nothing here decides how funds are sorted on screen.

```gherkin
Feature: Sinking funds — envelopes, goals and the monthly number become one machine
```

## AC-1 — A fund is created on a category and asks for a monthly amount

```gherkin
Scenario: A fund asks its amount from its start month on
  Given today is 2026-11-10
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-11
  Then the fund on "Tecnologia" asks 100000.00 COP this month

Scenario: A fund asks nothing before its start month
  Given today is 2026-09-10
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-11
  Then the fund on "Tecnologia" asks 0.00 COP this month

Scenario: A fund lowers the money available without anyone assigning it
  Given today is 2026-11-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-11
  Then the money available this month is 4900000.00 COP
```

## AC-2 — A fund asks a fixed amount when the owner names one

```gherkin
Scenario: The fixed amount does not move with spending
  Given today is 2026-11-10
  And an expense category "Restaurantes"
  And a fund on "Restaurantes" that asks a fixed 200000.00 COP each month, starting 2026-11
  And a recorded expense of 350000.00 COP in category "Restaurantes" this month
  Then the fund on "Restaurantes" asks 200000.00 COP this month

Scenario: The fixed amount changes only when the owner changes it
  Given today is 2026-11-10
  And an expense category "Restaurantes"
  And a fund on "Restaurantes" that asks a fixed 200000.00 COP each month, starting 2026-11
  When the user sets the fund on "Restaurantes" to ask a fixed 250000.00 COP each month
  Then the fund on "Restaurantes" asks 250000.00 COP this month
```

## AC-3 — A fund asks the average of what the app has recorded

```gherkin
Scenario: The average divides by the window the owner chose
  Given today is 2026-11-10
  And the app has recorded movements since 5 months ago
  And an expense category "Entretenimiento"
  And a recorded expense of 430950.00 COP in category "Entretenimiento" 2 months ago
  And a fund on "Entretenimiento" averaging the last 3 months, starting 2026-11
  Then the fund on "Entretenimiento" asks 143650.00 COP this month
  And the fund on "Entretenimiento" says it averaged over 3 months

Scenario: A month inside the window with no spending counts as zero
  Given today is 2026-11-10
  And the app has recorded movements since 5 months ago
  And an expense category "Cursos"
  And a recorded expense of 300000.00 COP in category "Cursos" 2 months ago
  And a fund on "Cursos" averaging the last 3 months, starting 2026-11
  Then the fund on "Cursos" asks 100000.00 COP this month

Scenario: A month the app has no data for is not counted at all
  Given today is 2026-11-10
  And the app has recorded movements since 2 months ago
  And an expense category "Servicios"
  And a recorded expense of 200000.00 COP in category "Servicios" 2 months ago
  And a recorded expense of 100000.00 COP in category "Servicios" 1 month ago
  And a fund on "Servicios" averaging the last 12 months, starting 2026-11
  Then the fund on "Servicios" asks 150000.00 COP this month
  And the fund on "Servicios" says it averaged over 2 months

Scenario: The current month does not average itself
  Given today is 2026-11-10
  And the app has recorded movements since 5 months ago
  And an expense category "Mercado"
  And a recorded expense of 300000.00 COP in category "Mercado" 1 month ago
  And a recorded expense of 900000.00 COP in category "Mercado" this month
  And a fund on "Mercado" averaging the last 3 months, starting 2026-11
  Then the fund on "Mercado" asks 100000.00 COP this month

Scenario: The average follows a category whose spending changed
  Given today is 2026-11-10
  And the app has recorded movements since 5 months ago
  And an expense category "Mercado"
  And a recorded expense of 300000.00 COP in category "Mercado" 2 months ago
  And a fund on "Mercado" averaging the last 3 months, starting 2026-11
  And a recorded expense of 600000.00 COP in category "Mercado" 1 month ago
  Then the fund on "Mercado" asks 300000.00 COP this month
```

## AC-4 — A fund derived from obligations sums every obligation in its category

```gherkin
Scenario: Three obligations in one category are added together
  Given today is 2026-11-10
  And an account "Banco" in COP with balance 20000000.00 COP
  And an expense category "Internet"
  And a repeating payment of 85000.00 COP to "Internet Hogar" from "Banco" every 1 month starting on 2026-01-05 in category "Internet", waiting for approval
  And a repeating payment of 38900.00 COP to "Plan de datos" from "Banco" every 1 month starting on 2026-01-05 in category "Internet", waiting for approval
  And a repeating payment of 37500.00 COP to "Plan de datos Mama" from "Banco" every 1 month starting on 2026-01-05 in category "Internet", waiting for approval
  And a fund on "Internet" funded from its obligations, starting 2026-11
  Then the fund on "Internet" asks 161400.00 COP this month

Scenario: A new obligation raises the fund without the owner touching it
  Given today is 2026-11-10
  And an account "Banco" in COP with balance 20000000.00 COP
  And an expense category "Internet"
  And a repeating payment of 85000.00 COP to "Internet Hogar" from "Banco" every 1 month starting on 2026-01-05 in category "Internet", waiting for approval
  And a fund on "Internet" funded from its obligations, starting 2026-11
  When the user declares a repeating payment of 38900.00 COP to "Plan de datos" from "Banco" every 1 month starting on 2026-01-05 in category "Internet", waiting for approval
  Then the fund on "Internet" asks 123900.00 COP this month

Scenario: Obligations of different cycles in one category are each brought to a month
  Given today is 2026-11-10
  And an account "Banco" in COP with balance 20000000.00 COP
  And an expense category "Servicios"
  And a repeating payment of 250000.00 COP to "EPM" from "Banco" every 1 month starting on 2026-01-05 in category "Servicios", waiting for approval
  And a repeating payment of 600000.00 COP to "Antivirus" from "Banco" every 1 year starting on 2027-11-05 in category "Servicios", waiting for approval
  And a fund on "Servicios" funded from its obligations, starting 2026-11
  Then the fund on "Servicios" asks 300000.00 COP this month
```

## AC-5 — A dated obligation is spread over the months that remain

```gherkin
Scenario: A yearly charge is divided by the months between the start and the charge
  Given today is 2026-11-10
  And an account "Banco" in COP with balance 20000000.00 COP
  And an expense category "Seguro"
  And a repeating payment of 447300.00 COP to "SOAT" from "Banco" every 1 year starting on 2027-05-02 in category "Seguro", waiting for approval
  And a fund on "Seguro" funded from its obligations, starting 2026-11
  Then the fund on "Seguro" asks 74550.00 COP this month

Scenario: The ask recomputes as months pass
  Given today is 2027-01-10
  And an account "Banco" in COP with balance 20000000.00 COP
  And an expense category "Seguro"
  And a repeating payment of 447300.00 COP to "SOAT" from "Banco" every 1 year starting on 2027-05-02 in category "Seguro", waiting for approval
  And a fund on "Seguro" funded from its obligations, starting 2026-11
  And the fund on "Seguro" already holds 149100.00 COP
  Then the fund on "Seguro" asks 74550.00 COP this month

Scenario: Putting in more one month lowers the next
  Given today is 2027-01-10
  And an account "Banco" in COP with balance 20000000.00 COP
  And an expense category "Seguro"
  And a repeating payment of 447300.00 COP to "SOAT" from "Banco" every 1 year starting on 2027-05-02 in category "Seguro", waiting for approval
  And a fund on "Seguro" funded from its obligations, starting 2026-11
  And the fund on "Seguro" already holds 297300.00 COP
  Then the fund on "Seguro" asks 37500.00 COP this month

Scenario: A start month further out concentrates the same amount into fewer months
  Given today is 2027-02-10
  And an account "Banco" in COP with balance 20000000.00 COP
  And an expense category "Seguro"
  And a repeating payment of 447300.00 COP to "SOAT" from "Banco" every 1 year starting on 2027-05-02 in category "Seguro", waiting for approval
  And a fund on "Seguro" funded from its obligations, starting 2027-02
  Then the fund on "Seguro" asks 149100.00 COP this month
```

## AC-6 — The fund is whole the month before the charge

```gherkin
Scenario: The month the charge lands does not contribute
  Given today is 2026-11-10
  And an account "Banco" in COP with balance 20000000.00 COP
  And an expense category "Seguro"
  And a repeating payment of 447300.00 COP to "SOAT" from "Banco" every 1 year starting on 2027-05-02 in category "Seguro", waiting for approval
  And a fund on "Seguro" funded from its obligations, starting 2026-11
  Then the fund on "Seguro" says it spreads over 6 months
  And the fund on "Seguro" says it is whole by 2027-04

Scenario: The money is there before the charge day
  Given today is 2027-04-30
  And an account "Banco" in COP with balance 20000000.00 COP
  And an expense category "Seguro"
  And a repeating payment of 447300.00 COP to "SOAT" from "Banco" every 1 year starting on 2027-05-02 in category "Seguro", waiting for approval
  And a fund on "Seguro" funded from its obligations, starting 2026-11
  And the fund on "Seguro" already holds 447300.00 COP
  Then the fund on "Seguro" asks 0.00 COP this month
  And the fund on "Seguro" is on track
```

## AC-7 — A fund that gets drained raises its ask to still arrive

```gherkin
Scenario: A fund still holding its savings asks only for what is missing
  Given today is 2026-11-10
  And an account "Banco" in COP with balance 20000000.00 COP
  And an expense category "Seguro"
  And a repeating payment of 7200000.00 COP to "Seguro del Carro" from "Banco" every 1 year starting on 2027-05-02 in category "Seguro", waiting for approval
  And a fund on "Seguro" funded from its obligations, starting 2026-11
  And the fund on "Seguro" already holds 3600000.00 COP
  Then the fund on "Seguro" asks 600000.00 COP this month

Scenario: An emptied fund raises its ask for the months that remain
  Given today is 2026-11-10
  And an account "Banco" in COP with balance 20000000.00 COP
  And an expense category "Seguro"
  And a repeating payment of 7200000.00 COP to "Seguro del Carro" from "Banco" every 1 year starting on 2027-05-02 in category "Seguro", waiting for approval
  And a fund on "Seguro" funded from its obligations, starting 2026-11
  And the fund on "Seguro" already holds 0.00 COP
  Then the fund on "Seguro" asks 1200000.00 COP this month

Scenario: Spending the fund on something else raises what it asks next
  Given today is 2026-11-10
  And an account "Banco" in COP with balance 20000000.00 COP
  And an expense category "Seguro"
  And a repeating payment of 7200000.00 COP to "Seguro del Carro" from "Banco" every 1 year starting on 2027-05-02 in category "Seguro", waiting for approval
  And a fund on "Seguro" funded from its obligations, starting 2026-11
  And the fund on "Seguro" already holds 3600000.00 COP
  When the user registers an expense of 3600000.00 COP from "Banco" paying "Taller" in category "Seguro"
  Then the fund on "Seguro" asks 1200000.00 COP this month
  And the fund on "Seguro" is behind
```

## AC-8 — A fund accumulates or resets, and the choice is offered only where it exists

```gherkin
Scenario: An accumulating fund carries its balance into the next month
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-11, accumulating
  Then the fund on "Tecnologia" holds 100000.00 COP

Scenario: A resetting fund starts each month fresh
  Given today is 2026-12-10
  And an expense category "Restaurantes"
  And a fund on "Restaurantes" that asks a fixed 200000.00 COP each month, starting 2026-11, resetting
  Then the fund on "Restaurantes" holds 0.00 COP

Scenario: A fund saving toward a date is not asked whether it accumulates
  Given today is 2026-11-10
  And an account "Banco" in COP with balance 20000000.00 COP
  And an expense category "Seguro"
  And a repeating payment of 447300.00 COP to "SOAT" from "Banco" every 1 year starting on 2027-05-02 in category "Seguro", waiting for approval
  When the user creates a fund on "Seguro" funded from its obligations, starting 2026-11
  Then the fund on "Seguro" accumulates
  And the fund on "Seguro" was not asked whether it accumulates

Scenario: A fund saving toward a date refuses to reset
  Given today is 2026-11-10
  And an expense category "Ahorro Viaje"
  When the user tries to create a fund on "Ahorro Viaje" targeting 3000000.00 COP by 2027-05, starting 2026-11, resetting
  Then the fund is rejected
  And the user is told a fund saving toward a date must accumulate
```

## AC-9 — The money available this month is what is left after every fund

```gherkin
Scenario: Income minus every fund minus what no fund covers
  Given today is 2026-11-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Restaurantes"
  And an expense category "Mercado"
  And a fund on "Restaurantes" that asks a fixed 200000.00 COP each month, starting 2026-11
  And a fund on "Mercado" that asks a fixed 300000.00 COP each month, starting 2026-11
  And a recorded expense of 150000.00 COP in category "Transporte" this month
  Then the money available this month is 4350000.00 COP

Scenario: Spending inside a fund does not reduce the money available twice
  Given today is 2026-11-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Restaurantes"
  And a fund on "Restaurantes" that asks a fixed 200000.00 COP each month, starting 2026-11
  When the user registers an expense of 150000.00 COP from "Banco" paying "Andres" in category "Restaurantes"
  Then the money available this month is 4800000.00 COP

Scenario: A category with no fund spends straight from the money available
  Given today is 2026-11-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Transporte"
  When the user registers an expense of 150000.00 COP from "Banco" paying "Uber" in category "Transporte"
  Then the money available this month is 4850000.00 COP
```

## AC-10 — The headline shows its work

```gherkin
Scenario: The breakdown names the income, every fund and the uncovered spending
  Given today is 2026-11-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Restaurantes"
  And an expense category "Mercado"
  And a fund on "Restaurantes" that asks a fixed 200000.00 COP each month, starting 2026-11
  And a fund on "Mercado" that asks a fixed 300000.00 COP each month, starting 2026-11
  And a recorded expense of 150000.00 COP in category "Transporte" this month
  When the user views the money available this month
  Then the breakdown shows income of 5000000.00 COP
  And the breakdown names "Restaurantes" at 200000.00 COP
  And the breakdown names "Mercado" at 300000.00 COP
  And the breakdown shows uncovered spending of 150000.00 COP
  And the breakdown adds up to the money available

Scenario: A fund asking nothing this month is still named in the breakdown
  Given today is 2026-11-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Seguro"
  And a fund on "Seguro" that asks a fixed 100000.00 COP each month, starting 2027-01
  When the user views the money available this month
  Then the breakdown names "Seguro" at 0.00 COP
```

## AC-11 — The fund pays its own obligation and the headline does not move

```gherkin
Scenario: The charge the fund saved for does not move the money available
  Given today is 2027-05-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Seguro"
  And a fund on "Seguro" that asks a fixed 74550.00 COP each month, starting 2026-11, accumulating
  And the fund on "Seguro" already holds 447300.00 COP
  When the user registers an expense of 447300.00 COP from "Banco" paying "SOAT" in category "Seguro"
  Then the money available this month is 4925450.00 COP
  And the fund on "Seguro" holds 0.00 COP

Scenario: The next cycle begins once the fund has paid
  Given today is 2027-05-10
  And an account "Banco" in COP with balance 20000000.00 COP
  And an expense category "Seguro"
  And a repeating payment of 447300.00 COP to "SOAT" from "Banco" every 1 year starting on 2027-05-02 in category "Seguro", waiting for approval
  And a fund on "Seguro" funded from its obligations, starting 2026-11
  And the fund on "Seguro" already holds 447300.00 COP
  When the user registers an expense of 447300.00 COP from "Banco" paying "SOAT" in category "Seguro"
  Then the fund on "Seguro" says it is whole by 2028-04
```

## AC-12 — The record still shows the payment in the month it happened

```gherkin
Scenario: A movement paid by a fund appears in the month's report like any other
  Given today is 2027-05-10
  And an account "Banco" in COP with balance 20000000.00 COP
  And an expense category "Seguro"
  And a fund on "Seguro" that asks a fixed 74550.00 COP each month, starting 2026-11, accumulating
  And the fund on "Seguro" already holds 447300.00 COP
  When the user registers an expense of 447300.00 COP from "Banco" paying "SOAT" in category "Seguro"
  And the user views the current month's report
  Then the spending for "Seguro" shows 447300.00 COP

Scenario: The transaction itself is unchanged by the fund that paid it
  Given today is 2027-05-10
  And an account "Banco" in COP with balance 20000000.00 COP
  And an expense category "Seguro"
  And a fund on "Seguro" that asks a fixed 74550.00 COP each month, starting 2026-11, accumulating
  And the fund on "Seguro" already holds 447300.00 COP
  When the user registers an expense of 447300.00 COP from "Banco" paying "SOAT" in category "Seguro"
  And the user views the expense
  Then viewing the expense shows category "Seguro"
  And viewing the expense shows payee "SOAT" and notes ""
```

## AC-13 — Spending past a fund reduces the headline by the excess only

```gherkin
Scenario: Only the excess leaves the money available
  Given today is 2026-11-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Restaurantes"
  And a fund on "Restaurantes" that asks a fixed 200000.00 COP each month, starting 2026-11
  When the user registers an expense of 350000.00 COP from "Banco" paying "Andres" in category "Restaurantes"
  Then the money available this month is 4650000.00 COP

Scenario: A fund does not carry a negative balance into the next month
  Given today is 2026-12-10
  And an expense category "Restaurantes"
  And a fund on "Restaurantes" that asks a fixed 200000.00 COP each month, starting 2026-11, resetting
  And a recorded expense of 350000.00 COP in category "Restaurantes" 1 month ago
  Then the fund on "Restaurantes" holds 0.00 COP

Scenario: An accumulating fund overspent falls to zero, not below
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-11, accumulating
  And a recorded expense of 400000.00 COP in category "Tecnologia" 1 month ago
  Then the fund on "Tecnologia" holds 0.00 COP
```

## AC-14 — Income that does not arrive monthly counts in the month it is due

```gherkin
Scenario: A quarterly income counts nothing in the months before it is due
  Given today is 2026-08-10
  And an income category "Bonos"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 3000000.00 COP from "Bono" into "Banco" every 3 month starting on 2026-09-30 in category "Bonos", paying itself
  Then the money available this month is 0.00 COP

Scenario: A quarterly income counts in full in the month it is due
  Given today is 2026-09-10
  And an income category "Bonos"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 3000000.00 COP from "Bono" into "Banco" every 3 month starting on 2026-09-30 in category "Bonos", paying itself
  Then the money available this month is 3000000.00 COP

Scenario: The money available never counts income that has not arrived
  Given today is 2026-08-10
  And an income category "Salario"
  And an income category "Bonos"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a repeating income of 3000000.00 COP from "Bono" into "Banco" every 3 month starting on 2026-09-30 in category "Bonos", paying itself
  When the user views the money available this month
  Then the breakdown shows income of 5000000.00 COP
```

## AC-14b — What the owner earns and what the owner costs are their own numbers, and those are smoothed

```gherkin
Scenario: The earning rate smooths a quarterly income across its cycle
  Given today is 2026-08-10
  And an income category "Salario"
  And an income category "Bonos"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a repeating income of 3000000.00 COP from "Bono" into "Banco" every 3 month starting on 2026-09-30 in category "Bonos", paying itself
  Then the earning rate is 6000000.00 COP a month

Scenario: The earning rate is the same in the month the quarterly income lands
  Given today is 2026-09-10
  And an income category "Salario"
  And an income category "Bonos"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a repeating income of 3000000.00 COP from "Bono" into "Banco" every 3 month starting on 2026-09-30 in category "Bonos", paying itself
  Then the earning rate is 6000000.00 COP a month
  And the money available this month is 8000000.00 COP

Scenario: The cost rate is every fund's ask plus the obligations no fund covers
  Given today is 2026-11-10
  And an account "Banco" in COP with balance 20000000.00 COP
  And an expense category "Restaurantes"
  And an expense category "Arriendo"
  And a fund on "Restaurantes" that asks a fixed 200000.00 COP each month, starting 2026-11
  And a repeating payment of 1000000.00 COP to "Arrendador" from "Banco" every 1 month starting on 2026-01-05 in category "Arriendo", waiting for approval
  Then the cost rate is 1200000.00 COP a month

Scenario: The margin is what the earning rate leaves after the cost rate
  Given today is 2026-11-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Restaurantes"
  And a fund on "Restaurantes" that asks a fixed 200000.00 COP each month, starting 2026-11
  Then the earning rate is 5000000.00 COP a month
  And the cost rate is 200000.00 COP a month
  And the margin is 4800000.00 COP a month

Scenario: The rate and the balance differ when a quarterly income has not landed
  Given today is 2026-08-10
  And an income category "Salario"
  And an income category "Bonos"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a repeating income of 3000000.00 COP from "Bono" into "Banco" every 3 month starting on 2026-09-30 in category "Bonos", paying itself
  Then the earning rate is 6000000.00 COP a month
  And the money available this month is 5000000.00 COP
```

## AC-14c — Once the month's real income is recorded, the numbers use it

```gherkin
Scenario: Expected income holds the place until the money arrives
  Given today is 2026-11-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-11-25 in category "Salario", paying itself
  Then the money available this month is 5000000.00 COP

Scenario: What actually arrived replaces what was expected
  Given today is 2026-11-20
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-11-25 in category "Salario", paying itself
  When the user registers an income of 4200000.00 COP into "Banco" from "Empresa" in category "Salario"
  Then the money available this month is 4200000.00 COP

Scenario: An income is never counted twice
  Given today is 2026-11-26
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-11-25 in category "Salario", paying itself
  Then the money available this month is 5000000.00 COP

Scenario: Money recorded without any obligation behind it counts from the moment it is recorded
  Given today is 2026-11-10
  And an account "Banco" in COP with balance 20000000.00 COP
  And an income category "Rendimientos"
  When the user registers an income of 250000.00 COP into "Banco" from "Banco" in category "Rendimientos"
  Then the money available this month is 250000.00 COP
```

## AC-15 — Income that stops is a change the owner makes, not something the app detects

```gherkin
Scenario: An income that has not arrived is never flagged by the app
  Given today is 2026-08-10
  And an income category "Bonos"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 3000000.00 COP from "Bono" into "Banco" every 3 month starting on 2026-09-30 in category "Bonos", paying itself
  Then the earning rate is 1000000.00 COP a month
  And nothing about "Bono" is waiting for the user's answer

Scenario: Switching the income off changes every number at once
  Given today is 2026-10-10
  And an income category "Salario"
  And an income category "Bonos"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a repeating income of 3000000.00 COP from "Bono" into "Banco" every 3 month starting on 2026-09-30 in category "Bonos", paying itself
  When the user switches off "Bono"
  Then the earning rate is 5000000.00 COP a month

Scenario: Lowering the income lowers the rate with no separate recalculation
  Given today is 2026-10-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  When the user sets the repeating income from "Empresa" to 4000000.00 COP
  Then the earning rate is 4000000.00 COP a month
```

## AC-16 — Every figure is derived from what is known now, including past months

```gherkin
Scenario: A past month recomputes without an income switched off later
  Given today is 2026-10-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a repeating income of 2000000.00 COP from "Socio" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  When the user switches off "Socio"
  And the user views the money available for 2026-09
  Then the money available that month is 5000000.00 COP

Scenario: A past month recomputes with a fund created afterwards
  Given today is 2026-11-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Restaurantes"
  When the user creates a fund on "Restaurantes" that asks a fixed 200000.00 COP each month, starting 2026-09
  And the user views the money available for 2026-09
  Then the money available that month is 4800000.00 COP

Scenario: No month is stored as a snapshot
  Given today is 2026-11-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And the user viewed the money available for 2026-09
  When the user switches off "Empresa"
  And the user views the money available for 2026-09
  Then the money available that month is 0.00 COP
```

## AC-17 — A skipped charge lowers its fund's ask that month

```gherkin
Scenario: Skipping a charge lowers what its fund asks that month
  Given today is 2026-11-10
  And an account "Banco" in COP with balance 20000000.00 COP
  And an expense category "Internet"
  And a repeating payment of 85000.00 COP to "Internet Hogar" from "Banco" every 1 month starting on 2026-11-05 in category "Internet", waiting for approval
  And a repeating payment of 38900.00 COP to "Plan de datos" from "Banco" every 1 month starting on 2026-11-05 in category "Internet", waiting for approval
  And a repeating payment of 37500.00 COP to "Plan de datos Mama" from "Banco" every 1 month starting on 2026-11-05 in category "Internet", waiting for approval
  And a fund on "Internet" funded from its obligations, starting 2026-11
  When the user skips the payment to "Plan de datos Mama"
  Then the fund on "Internet" asks 123900.00 COP this month

Scenario: The skipped amount returns to the money available
  Given today is 2026-11-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Internet"
  And a repeating payment of 37500.00 COP to "Plan de datos Mama" from "Banco" every 1 month starting on 2026-11-05 in category "Internet", waiting for approval
  And a fund on "Internet" funded from its obligations, starting 2026-11
  When the user skips the payment to "Plan de datos Mama"
  Then the money available this month is 5000000.00 COP

Scenario: The next month asks the full amount again
  Given today is 2026-12-10
  And an account "Banco" in COP with balance 20000000.00 COP
  And an expense category "Internet"
  And a repeating payment of 37500.00 COP to "Plan de datos Mama" from "Banco" every 1 month starting on 2026-11-05 in category "Internet", waiting for approval
  And a fund on "Internet" funded from its obligations, starting 2026-11
  And the payment to "Plan de datos Mama" was skipped last month
  Then the fund on "Internet" asks 37500.00 COP this month
```

## AC-18 — A fund covering money in another currency asks in the currency of the headline

```gherkin
Scenario: A dollar obligation is asked for in COP
  Given today is 2026-11-10
  And an account "Banco USD" in USD with balance 5000.00 USD
  And the TRM is 4000.00
  And an expense category "Gimnasio"
  And a repeating payment of 30.00 USD to "Smart Fit" from "Banco USD" every 1 month starting on 2026-01-05 in category "Gimnasio", waiting for approval
  And a fund on "Gimnasio" funded from its obligations, starting 2026-11
  Then the fund on "Gimnasio" asks 120000.00 COP this month

Scenario: The ask moves with the rate rather than freezing at creation
  Given today is 2026-11-10
  And an account "Banco USD" in USD with balance 5000.00 USD
  And the TRM is 4000.00
  And an expense category "Gimnasio"
  And a repeating payment of 30.00 USD to "Smart Fit" from "Banco USD" every 1 month starting on 2026-01-05 in category "Gimnasio", waiting for approval
  And a fund on "Gimnasio" funded from its obligations, starting 2026-11
  When the user sets the TRM to 4500.00
  Then the fund on "Gimnasio" asks 135000.00 COP this month

Scenario: A yearly dollar obligation is brought to a month and to COP
  Given today is 2026-11-10
  And an account "Banco USD" in USD with balance 5000.00 USD
  And the TRM is 4000.00
  And an expense category "Software"
  And a repeating payment of 60.00 USD to "Opal" from "Banco USD" every 1 year starting on 2027-11-05 in category "Software", waiting for approval
  And a fund on "Software" funded from its obligations, starting 2026-11
  Then the fund on "Software" asks 20000.00 COP this month
```

## AC-19 — A fund that already holds money is told so once

```gherkin
Scenario: The opening balance counts toward what the fund still needs
  Given today is 2026-11-10
  And an expense category "Ahorro Viaje"
  When the user creates a fund on "Ahorro Viaje" targeting 3000000.00 COP by 2027-05, starting 2026-11, opening with 1200000.00 COP
  Then the fund on "Ahorro Viaje" holds 1200000.00 COP
  And the fund on "Ahorro Viaje" asks 300000.00 COP this month

Scenario: The fund never reads an account balance
  Given today is 2026-11-10
  And an account "Ahorros" in COP with balance 9000000.00 COP
  And an expense category "Ahorro Viaje"
  When the user creates a fund on "Ahorro Viaje" targeting 3000000.00 COP by 2027-05, starting 2026-11, opening with 1200000.00 COP
  Then the fund on "Ahorro Viaje" holds 1200000.00 COP

Scenario: A later change to the account leaves the fund alone
  Given today is 2026-11-10
  And an income category "Salario"
  And an account "Ahorros" in COP with balance 9000000.00 COP
  And an expense category "Ahorro Viaje"
  And a fund on "Ahorro Viaje" targeting 3000000.00 COP by 2027-05, starting 2026-11, opening with 1200000.00 COP
  When the user registers an income of 5000000.00 COP into "Ahorros" from "Empresa" in category "Salario"
  Then the fund on "Ahorro Viaje" holds 1200000.00 COP
```

## AC-20 — The app starts with no funds at all

```gherkin
Scenario: A fresh app proposes no funds
  Given today is 2026-11-10
  And an account "Banco" in COP with balance 20000000.00 COP
  And an expense category "Internet"
  And a repeating payment of 85000.00 COP to "Internet Hogar" from "Banco" every 1 month starting on 2026-01-05 in category "Internet", waiting for approval
  When the user views the funds
  Then no fund is listed

Scenario: Spending history alone creates no fund
  Given today is 2026-11-10
  And the app has recorded movements since 5 months ago
  And an expense category "Mercado"
  And a recorded expense of 300000.00 COP in category "Mercado" 1 month ago
  When the user views the funds
  Then no fund is listed

Scenario: Once created, a rule computes its own amount without being asked again
  Given today is 2026-11-10
  And the app has recorded movements since 5 months ago
  And an expense category "Mercado"
  And a recorded expense of 300000.00 COP in category "Mercado" 1 month ago
  When the user creates a fund on "Mercado" averaging the last 3 months, starting 2026-11
  Then the fund on "Mercado" asks 100000.00 COP this month
```

## AC-21 — A category holding a fund cannot be archived

```gherkin
Scenario: Archiving a category that holds a fund is refused
  Given today is 2026-11-10
  And an expense category "Seguro"
  And a fund on "Seguro" that asks a fixed 100000.00 COP each month, starting 2026-11, accumulating
  And the fund on "Seguro" already holds 3000000.00 COP
  When the user tries to archive the category "Seguro"
  Then the change is rejected
  And the user is told the category holds a fund of 3000000.00 COP

Scenario: The category archives once its fund is gone
  Given today is 2026-11-10
  And an expense category "Seguro"
  And a fund on "Seguro" that asks a fixed 100000.00 COP each month, starting 2026-11, accumulating
  When the user deletes the fund on "Seguro"
  And the user archives the category "Seguro"
  Then the categories offered do not include "Seguro"

Scenario: The refusal leaves the money set aside untouched
  Given today is 2026-11-10
  And an expense category "Seguro"
  And a fund on "Seguro" that asks a fixed 100000.00 COP each month, starting 2026-11, accumulating
  And the fund on "Seguro" already holds 3000000.00 COP
  When the user tries to archive the category "Seguro"
  Then the fund on "Seguro" holds 3000000.00 COP
```

## AC-22 — A fund cannot be created on an income category

```gherkin
Scenario: A fund on an income category is refused
  Given today is 2026-11-10
  And an income category "Salario"
  When the user tries to create a fund on "Salario" that asks a fixed 100000.00 COP each month, starting 2026-11
  Then the fund is rejected
  And the user is told a fund only covers money going out

Scenario: The refused fund does not touch the money available
  Given today is 2026-11-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an income category "Bonos"
  When the user tries to create a fund on "Bonos" that asks a fixed 100000.00 COP each month, starting 2026-11
  Then the money available this month is 5000000.00 COP
```

## AC-23 — The average rule is refused where nothing has ever been spent

```gherkin
Scenario: Averaging a category with no spending at all is refused
  Given today is 2026-11-10
  And the app has recorded movements since 5 months ago
  And an expense category "Reembolsable"
  When the user tries to create a fund on "Reembolsable" averaging the last 3 months, starting 2026-11
  Then the fund is rejected
  And the user is told to name a fixed amount instead

Scenario: One month of spending is enough to average
  Given today is 2026-11-10
  And the app has recorded movements since 5 months ago
  And an expense category "Peajes"
  And a recorded expense of 90000.00 COP in category "Peajes" 2 months ago
  When the user creates a fund on "Peajes" averaging the last 3 months, starting 2026-11
  Then the fund on "Peajes" asks 30000.00 COP this month
  And the fund on "Peajes" says it averaged over 3 months

Scenario: Spending only in the current month does not count as history
  Given today is 2026-11-10
  And the app has recorded movements since 5 months ago
  And an expense category "Peajes"
  And a recorded expense of 90000.00 COP in category "Peajes" this month
  When the user tries to create a fund on "Peajes" averaging the last 3 months, starting 2026-11
  Then the fund is rejected
```

## AC-24 — A target that cannot be reached is announced before the fund exists

```gherkin
Scenario: An implausible target warns before the fund is created
  Given today is 2026-08-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Ahorro Viaje"
  When the user starts creating a fund on "Ahorro Viaje" targeting 10000000.00 COP by 2026-08, starting 2026-08
  Then the user is warned it would ask 10000000.00 COP this month
  And no fund is listed

Scenario: The owner may go ahead and the fund asks it in full
  Given today is 2026-08-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Ahorro Viaje"
  When the user starts creating a fund on "Ahorro Viaje" targeting 10000000.00 COP by 2026-08, starting 2026-08
  And the user goes ahead anyway
  Then the fund on "Ahorro Viaje" asks 10000000.00 COP this month
  And the money available this month is -5000000.00 COP

Scenario: A reachable target is created without a warning
  Given today is 2026-08-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Ahorro Viaje"
  When the user creates a fund on "Ahorro Viaje" targeting 3000000.00 COP by 2027-08, starting 2026-08
  Then the fund on "Ahorro Viaje" asks 250000.00 COP this month
  And the user was not warned
```

## AC-25 — A category carries at most one fund

```gherkin
Scenario: A second fund on the same category is refused
  Given today is 2026-11-10
  And an expense category "Restaurantes"
  And a fund on "Restaurantes" that asks a fixed 200000.00 COP each month, starting 2026-11
  When the user tries to create a fund on "Restaurantes" averaging the last 3 months, starting 2026-11
  Then the fund is rejected
  And the user is told "Restaurantes" already has a fund

Scenario: The existing fund is unchanged by the refusal
  Given today is 2026-11-10
  And an expense category "Restaurantes"
  And a fund on "Restaurantes" that asks a fixed 200000.00 COP each month, starting 2026-11
  When the user tries to create a fund on "Restaurantes" averaging the last 3 months, starting 2026-11
  Then the fund on "Restaurantes" asks 200000.00 COP this month
```

## AC-26 — Goals disappear as a concept

```gherkin
Scenario: The app offers no way to create a goal
  Given today is 2026-11-10
  When the user looks for the goals
  Then the goals are not offered

Scenario: The assistant offers no way to create a goal
  Given today is 2026-11-10
  When the assistant is asked to create a goal
  Then the assistant has no way to do it

Scenario: A fund expresses the same intention without naming an account
  Given today is 2026-11-10
  And an expense category "Ahorro Viaje"
  When the user creates a fund on "Ahorro Viaje" targeting 3000000.00 COP by 2027-05, starting 2026-11
  Then the fund on "Ahorro Viaje" asks 500000.00 COP this month
  And the fund on "Ahorro Viaje" names no account

Scenario: The month end no longer proposes a contribution
  Given today is 2026-11-10
  And an expense category "Ahorro Viaje"
  And a fund on "Ahorro Viaje" targeting 3000000.00 COP by 2027-05, starting 2026-11
  When the daily run happens
  Then the outstanding list for the next 60 days is empty
```

## AC-27 — The proposed goal transfers that were never confirmed are removed with them

```gherkin
Scenario: The unconfirmed proposals are gone after the upgrade
  Given goal proposals recorded before the upgrade, none of them confirmed
  When the upgrade is attempted
  Then the upgrade completes
  And the outstanding list for the next 60 days is empty
  And the records hold no goal

Scenario: Everything else recorded before the upgrade survives it
  Given goal proposals recorded before the upgrade, none of them confirmed
  And ordinary movements recorded alongside them
  When the upgrade is attempted
  Then the upgrade completes
  And every expense and income still shows the category it had
  And every transfer still shows no category
```

## AC-28 — The assistant reaches funds exactly as the browser does

```gherkin
Scenario: The assistant creates a fund
  Given today is 2026-11-10
  And an expense category "Restaurantes"
  When the assistant creates a fund on "Restaurantes" that asks a fixed 200000.00 COP each month, starting 2026-11
  Then the fund on "Restaurantes" asks 200000.00 COP this month

Scenario: The assistant lists the funds
  Given today is 2026-11-10
  And an expense category "Restaurantes"
  And a fund on "Restaurantes" that asks a fixed 200000.00 COP each month, starting 2026-11
  When the assistant is asked about the funds
  Then the assistant's answer names "Restaurantes"

Scenario: The assistant answers with the money available and its breakdown
  Given today is 2026-11-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Restaurantes"
  And a fund on "Restaurantes" that asks a fixed 200000.00 COP each month, starting 2026-11
  When the assistant is asked how much is available this month
  Then the assistant's answer names "Restaurantes"
  And the assistant's answer states 4800000.00 COP

Scenario: The assistant meets the same refusal on an income category
  Given today is 2026-11-10
  And an income category "Salario"
  When the assistant tries to create a fund on "Salario" that asks a fixed 100000.00 COP each month, starting 2026-11
  Then the fund is rejected
  And the user is told a fund only covers money going out

Scenario: The assistant meets the same refusal on a second fund
  Given today is 2026-11-10
  And an expense category "Restaurantes"
  And a fund on "Restaurantes" that asks a fixed 200000.00 COP each month, starting 2026-11
  When the assistant tries to create a fund on "Restaurantes" averaging the last 3 months, starting 2026-11
  Then the fund is rejected
  And the user is told "Restaurantes" already has a fund

Scenario: The assistant deletes a fund
  Given today is 2026-11-10
  And an expense category "Restaurantes"
  And a fund on "Restaurantes" that asks a fixed 200000.00 COP each month, starting 2026-11
  When the assistant deletes the fund on "Restaurantes"
  And the user views the funds
  Then no fund is listed
```

## AC-29 — A bill that arrives for a different amount costs what it really cost

```gherkin
Scenario: A charge that costs more than it declared takes the difference too
  Given today is 2026-11-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-11-05 in category "Salario", paying itself
  And an expense category "Servicios"
  And a repeating payment of 200000.00 COP to "EPM" from "Banco" every 1 month starting on 2026-11-05 in category "Servicios", waiting for approval
  When the daily run happens
  And the user confirms the payment to "EPM" for 250000.00 COP
  Then the money available this month is 4750000.00 COP

Scenario: A charge that costs less than it declared gives the difference back
  Given today is 2026-11-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-11-05 in category "Salario", paying itself
  And an expense category "Servicios"
  And a repeating payment of 200000.00 COP to "EPM" from "Banco" every 1 month starting on 2026-11-05 in category "Servicios", waiting for approval
  When the daily run happens
  And the user confirms the payment to "EPM" for 150000.00 COP
  Then the money available this month is 4850000.00 COP

Scenario: Money that already left still counts when the obligation is switched off
  Given today is 2026-11-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-11-05 in category "Salario", paying itself
  And an expense category "Servicios"
  And a repeating payment of 200000.00 COP to "EPM" from "Banco" every 1 month starting on 2026-11-05 in category "Servicios", waiting for approval
  When the daily run happens
  And the user confirms the payment to "EPM"
  And the user switches off "EPM"
  Then the money available this month is 4800000.00 COP
```

## AC-30 — A fund says it is behind when the month left it worse than not touching it would

```gherkin
Scenario: A fund that spent past everything it had says it is behind
  Given today is 2026-11-10
  And an account "Banco" in COP with balance 20000000.00 COP
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 300000.00 COP each month, starting 2026-11
  And the fund on "Tecnologia" already holds 350000.00 COP
  When the user registers an expense of 900000.00 COP from "Banco" paying "Alkosto" in category "Tecnologia"
  Then the fund on "Tecnologia" is behind

Scenario: A fund that spent every peso it had and no more is on track
  Given today is 2026-11-10
  And an account "Banco" in COP with balance 20000000.00 COP
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 300000.00 COP each month, starting 2026-11
  And the fund on "Tecnologia" already holds 350000.00 COP
  When the user registers an expense of 650000.00 COP from "Banco" paying "Alkosto" in category "Tecnologia"
  Then the fund on "Tecnologia" is on track

Scenario: A fund holding nothing yet still says it is behind when the month overspends it
  Given today is 2026-11-10
  And an account "Banco" in COP with balance 20000000.00 COP
  And an expense category "Ahorro Viaje"
  And a fund on "Ahorro Viaje" targeting 3000000.00 COP by 2027-05, starting 2026-11
  When the user registers an expense of 2000000.00 COP from "Banco" paying "Agencia" in category "Ahorro Viaje"
  Then the fund on "Ahorro Viaje" is behind
```
