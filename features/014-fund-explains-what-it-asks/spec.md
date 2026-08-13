# Acceptance specs — 014 fund-explains-what-it-asks

Formalizes `acs.md` (18 ACs, approved by the owner 2026-08-12) as standard
Gherkin.

**The arithmetic already works.** Measured against production on 2026-08-12,
every fund spreads its obligations correctly. What does not exist is the fund
saying so, and what exists and is wrong is the warning. So this suite is red in
two places only: the breakdown, which is new, and the warning's trigger, which
must stop firing where it fires today.

## The rule every scenario comes from

**A fund's figure is the sum of its obligations, each divided by the months left
before it charges — and the screen says so.** Feature 003 already fixed that
arithmetic (AC-4, AC-5) and already fixed the principle one level up: the
month's headline opens into its terms and nothing is unattributable (003, AC-10).
This feature owes the fund the same courtesy.

## The rate

One scalar rate (ADR-0031). The suite uses **4000** so every conversion is exact
and a wrong figure cannot look plausible: `30.00 USD` is `120000.00 COP`.
A scenario that never states a rate must never turn on one.

## The numbers

Every scenario is set in **August 2026** and the fund starts that month, so the
months left are easy to count and hard to fake:

| Obligation | Costs | Charges | Months left | Asks |
|---|---|---|---|---|
| Internet | 80.000 monthly | this month | 1 | 80.000 |
| Dominio | 1.200.000 yearly | 2027-08 | 12 | 100.000 |
| Servidor | 30,00 USD yearly | 2027-08 | 12 | 10.000 |

A monthly charge always divides by one — that is the whole point of AC-13, and
it is why 80.000 appears whole and 100.000 does not.

---

Feature: Un fondo dice de dónde sale su cifra, y su aviso deja de mentir

Background:
  Given today is 2026-08-15
  And the TRM is 4000

## AC-1, AC-2, AC-4 — The figure opens into the charges that produced it

```gherkin
@backend
Scenario: The fund reports one line per charge it is filling for
  Given a recurring charge "Internet" on "Suscripciones" of 80000.00 COP every month, next due 2026-08
  And a recurring charge "Dominio" on "Suscripciones" of 1200000.00 COP every year, next due 2027-08
  And a fund on "Suscripciones" funded from its obligations, starting 2026-08
  When the user views the funds
  Then the fund on "Suscripciones" asks 180000.00 COP this month
  And the fund on "Suscripciones" says "Internet" asks 80000.00 COP
  And the fund on "Suscripciones" says "Dominio" asks 100000.00 COP

@backend
Scenario: Each line carries what the charge costs and the month it lands
  Given a recurring charge "Dominio" on "Suscripciones" of 1200000.00 COP every year, next due 2027-08
  And a fund on "Suscripciones" funded from its obligations, starting 2026-08
  When the user views the funds
  Then the fund on "Suscripciones" says "Dominio" costs 1200000.00 COP
  And the fund on "Suscripciones" says "Dominio" charges in 2027-08

@backend
Scenario: The lines add up to what the fund asks
  Given a recurring charge "Internet" on "Suscripciones" of 80000.00 COP every month, next due 2026-08
  And a recurring charge "Dominio" on "Suscripciones" of 1200000.00 COP every year, next due 2027-08
  And a fund on "Suscripciones" funded from its obligations, starting 2026-08
  When the user views the funds
  Then the lines on "Suscripciones" add up to what it asks

Scenario: The lines add up to the figure above them, in whole pesos
  Given the app is open
  And a fund on "Suscripciones" asking 666666.68 COP, filling for "Uno" at 333333.34 and "Dos" at 333333.34
  When the owner opens the funds
  Then the lines under "Suscripciones" add up to what the row reads

Scenario: The row carries a line for every charge behind its figure
  Given the app is open
  And a fund on "Suscripciones" asking 180000.00 COP, filling for "Internet" at 80000.00 and "Dominio" at 100000.00
  When the owner opens the funds
  Then the row for "Suscripciones" reads 180000.00 COP
  And the row for "Suscripciones" names "Internet" at 80000.00 COP
  And the row for "Suscripciones" names "Dominio" at 100000.00 COP

Scenario: A line says what the charge costs and when it lands
  Given the app is open
  And a fund on "Suscripciones" asking 100000.00 COP, filling for "Dominio" at 100000.00 costing 1200000.00 in 2027-08
  When the owner opens the funds
  Then the line for "Dominio" reads 1200000.00 COP
  And the line for "Dominio" names 2027-08
```

## AC-3 — What is due now reads differently from what is being saved

```gherkin
@backend
Scenario: A charge landing this month is reported as due, not as saving
  Given a recurring charge "Internet" on "Suscripciones" of 80000.00 COP every month, next due 2026-08
  And a fund on "Suscripciones" funded from its obligations, starting 2026-08
  When the user views the funds
  Then the fund on "Suscripciones" says "Internet" is due this month

@backend
Scenario: A charge landing later is reported as being saved for
  Given a recurring charge "Dominio" on "Suscripciones" of 1200000.00 COP every year, next due 2027-08
  And a fund on "Suscripciones" funded from its obligations, starting 2026-08
  When the user views the funds
  Then the fund on "Suscripciones" says "Dominio" is being saved for

Scenario: The row separates what leaves this month from what stays
  Given the app is open
  And a fund on "Suscripciones" asking 180000.00 COP, filling for "Internet" at 80000.00 due this month and "Dominio" at 100000.00 in 2027-08
  When the owner opens the funds
  Then the line for "Internet" says it is due this month
  And the line for "Dominio" says it is being saved for 2027-08
```

## AC-5 — No figure moves

```gherkin
@backend
Scenario: What the fund asks is what it asked before
  Given a recurring charge "Internet" on "Suscripciones" of 80000.00 COP every month, next due 2026-08
  And a recurring charge "Dominio" on "Suscripciones" of 1200000.00 COP every year, next due 2027-08
  And a fund on "Suscripciones" funded from its obligations, starting 2026-08
  When the user views the funds
  Then the fund on "Suscripciones" asks 180000.00 COP this month
  And the fund on "Suscripciones" says it spreads over 1 months

@backend
Scenario: What the fund holds and carries is what it held and carried before
  Given a recurring charge "Dominio" on "Suscripciones" of 1200000.00 COP every year, next due 2027-08
  And a fund on "Suscripciones" funded from its obligations, starting 2026-08
  And the fund on "Suscripciones" already holds 300000.00 COP
  When the user views the funds
  Then the fund on "Suscripciones" holds 300000.00 COP
  And the fund on "Suscripciones" carries 375000.00 COP into next month
```

## AC-6 — A skipped charge leaves the list

```gherkin
@backend
Scenario: A charge skipped this month is not among the lines
  Given a recurring charge "Internet" on "Suscripciones" of 80000.00 COP every month, next due 2026-08
  And a recurring charge "Dominio" on "Suscripciones" of 1200000.00 COP every year, next due 2027-08
  And a fund on "Suscripciones" funded from its obligations, starting 2026-08
  And the payment to "Internet" was skipped this month
  When the user views the funds
  Then the fund on "Suscripciones" asks 100000.00 COP this month
  And the fund on "Suscripciones" says nothing about "Internet"
```

## AC-7 — A settled charge leaves the list and the next turn takes its place

```gherkin
@backend
Scenario: A charge already paid this month is not among the lines
  Given a recurring charge "Internet" on "Suscripciones" of 80000.00 COP every month, next due 2026-08
  And a recorded expense of 80000.00 COP in category "Suscripciones" this month
  And a fund on "Suscripciones" funded from its obligations, starting 2026-08
  When the user views the funds
  Then the fund on "Suscripciones" says nothing about "Internet" landing this month

@backend
Scenario: The charge comes back for its next turn
  Given a recurring charge "Internet" on "Suscripciones" of 80000.00 COP every month, next due 2026-08
  And a recorded expense of 80000.00 COP in category "Suscripciones" this month
  And a fund on "Suscripciones" funded from its obligations, starting 2026-08
  When the user views the funds
  Then the fund on "Suscripciones" says "Internet" charges in 2026-09
```

## AC-8 — A fund asked for nothing this month says so

```gherkin
Scenario: A fund with every charge skipped explains the empty month
  Given the app is open
  And a fund on "Suscripciones" asking 0.00 COP with no charge to fill for this month
  When the owner opens the funds
  Then the row for "Suscripciones" reads 0.00 COP
  And the row for "Suscripciones" says there is nothing to set aside this month
```

## AC-9 — A fund whose category lost its charges says so

```gherkin
Scenario: A fund left with no obligations at all says the category has none
  Given the app is open
  And a fund on "Suscripciones" asking 0.00 COP whose category holds no repeating charge
  When the owner opens the funds
  Then the row for "Suscripciones" says the category has no repeating charge left
```

```gherkin
@backend
Scenario: A fund filling for a live charge still counts it
  Given a recurring charge "Internet" on "Suscripciones" of 80000.00 COP every month, next due 2026-08
  And a fund on "Suscripciones" funded from its obligations, starting 2026-08
  When the user views the funds
  Then the fund on "Suscripciones" still has a repeating charge

@backend
Scenario: A rule that ran out months ago is not one the fund is waiting for
  Given a recurring charge "Internet" on "Suscripciones" of 80000.00 COP every month, next due 2026-05
  And "Internet" stops repeating after 2026-05
  And a fund on "Suscripciones" funded from its obligations, starting 2026-08
  When the user views the funds
  Then the fund on "Suscripciones" has no repeating charge left

@backend
Scenario: One live charge is enough, beside a rule that ran out
  Given a recurring charge "Internet" on "Suscripciones" of 80000.00 COP every month, next due 2026-08
  And a recurring charge "Viejo" on "Suscripciones" of 50000.00 COP every month, next due 2026-05
  And "Viejo" stops repeating after 2026-05
  And a fund on "Suscripciones" funded from its obligations, starting 2026-08
  When the user views the funds
  Then the fund on "Suscripciones" still has a repeating charge

@backend
Scenario: A charge whose rule has run out is not a charge the fund is waiting for
  Given a recurring charge "Internet" on "Suscripciones" of 80000.00 COP every month, next due 2026-08
  And "Internet" stops repeating after 2026-08
  And a fund on "Suscripciones" funded from its obligations, starting 2026-08
  And the payment to "Internet" was skipped this month
  When the user views the funds
  Then the fund on "Suscripciones" has no repeating charge left
```

## AC-10 — A charge in another currency reads in pesos

```gherkin
@backend
Scenario: A dollar charge is reported in pesos like the rest
  Given a recurring charge "Servidor" on "Suscripciones" of 30.00 USD every year, next due 2027-08
  And a fund on "Suscripciones" funded from its obligations, starting 2026-08
  When the user views the funds
  Then the fund on "Suscripciones" asks 10000.00 COP this month
  And the fund on "Suscripciones" says "Servidor" costs 120000.00 COP

@backend
Scenario: A different rate produces a different reading of the same charge
  Given the TRM is 5000
  And a recurring charge "Servidor" on "Suscripciones" of 30.00 USD every year, next due 2027-08
  And a fund on "Suscripciones" funded from its obligations, starting 2026-08
  When the user views the funds
  Then the fund on "Suscripciones" says "Servidor" costs 150000.00 COP
```

## AC-11, AC-12 — The warning fires only where something cannot be spread

```gherkin
@backend
Scenario: A yearly charge landing next month is announced before the fund exists
  Given a recurring charge "Seguro" on "Auto" of 6000000.00 COP every year, next due 2026-09
  When the user starts creating a fund on "Auto" funded from its obligations, starting 2026-08
  Then the user is warned it would ask 6000000.00 COP this month

@backend
Scenario: The warning names the charge that cannot be spread
  Given a recurring charge "Seguro" on "Auto" of 6000000.00 COP every year, next due 2026-09
  When the user starts creating a fund on "Auto" funded from its obligations, starting 2026-08
  Then the warning names "Seguro"

@backend
Scenario: The warning quotes the charge, not the whole fund
  Given a recurring charge "Seguro" on "Auto" of 6000000.00 COP every year, next due 2026-09
  And a recurring charge "Lavado" on "Auto" of 50000.00 COP every month, next due 2026-08
  When the user starts creating a fund on "Auto" funded from its obligations, starting 2026-08
  Then the warning states 6000000.00 COP

@backend
Scenario: Two charges with no months to spread over are both named
  Given a recurring charge "Seguro" on "Auto" of 6000000.00 COP every year, next due 2026-09
  And a recurring charge "SOAT" on "Auto" of 500000.00 COP every year, next due 2026-09
  When the user starts creating a fund on "Auto" funded from its obligations, starting 2026-08
  Then the warning names "Seguro"
  And the warning names "SOAT"
  And the warning states 6500000.00 COP

@backend
Scenario: A charge that lands every two months is announced when it has no month left
  Given a recurring charge "Peaje" on "Auto" of 400000.00 COP every 2 months, next due 2026-09
  When the user starts creating a fund on "Auto" funded from its obligations, starting 2026-08
  Then the warning names "Peaje"
  And the warning states 400000.00 COP

@backend
Scenario: A single cent still has no month to fall in
  Given a recurring charge "Seguro" on "Auto" of 6000000.00 COP every year, next due 2026-09
  When the user starts creating a fund on "Auto" funded from its obligations, starting 2026-08, opening with 5999999.99 COP
  Then the warning states 0.01 COP

@backend
Scenario: Nothing is announced when the fund already holds what the charge needs
  Given a recurring charge "Seguro" on "Auto" of 6000000.00 COP every year, next due 2026-09
  When the user starts creating a fund on "Auto" funded from its obligations, starting 2026-08, opening with 6000000.00 COP
  Then the user was not warned

@backend
Scenario: The owner may create it anyway
  Given a recurring charge "Seguro" on "Auto" of 6000000.00 COP every year, next due 2026-09
  When the user creates a fund on "Auto" funded from its obligations, starting 2026-08
  Then the fund on "Auto" asks 6000000.00 COP this month
```

## AC-13 — A monthly charge never triggers the warning

```gherkin
@backend
Scenario: A charge that lands every month is not a surprise
  Given a recurring charge "Internet" on "Suscripciones" of 80000.00 COP every month, next due 2026-08
  When the user starts creating a fund on "Suscripciones" funded from its obligations, starting 2026-08
  Then the user was not warned

@backend
Scenario: A monthly charge beside a well-spread yearly one is not a surprise either
  Given a recurring charge "Internet" on "Suscripciones" of 80000.00 COP every month, next due 2026-08
  And a recurring charge "Dominio" on "Suscripciones" of 1200000.00 COP every year, next due 2027-08
  When the user starts creating a fund on "Suscripciones" funded from its obligations, starting 2026-08
  Then the user was not warned

@backend
Scenario: A monthly charge in its last month is still not a surprise
  Given a recurring charge "EPM" on "Services" of 250000.00 COP every month, next due 2026-08
  And "EPM" stops repeating after 2026-08
  When the user starts creating a fund on "Services" funded from its obligations, starting 2026-08
  Then the user was not warned

@backend
Scenario Outline: The four categories that warn today stop warning
  Given a recurring charge "<monthly>" on "<category>" of <amount> COP every month, next due 2026-08
  When the user starts creating a fund on "<category>" funded from its obligations, starting 2026-08
  Then the user was not warned

    Examples:
      | category      | monthly           | amount     |
      | Services      | EPM               | 250000.00  |
      | Fitness       | Smart Fit         | 120000.00  |
      | AI Tools      | Superwhisper      | 26675.00   |
      | Phone         | Plan de datos     | 38900.00   |
```

## AC-14 — The rule is not offered where nothing can be spread

```gherkin
@backend
Scenario: A category mixing a monthly charge with a yearly one has something to spread
  Given a recurring charge "Internet" on "Suscripciones" of 80000.00 COP every month, next due 2026-08
  And a recurring charge "Dominio" on "Suscripciones" of 1200000.00 COP every year, next due 2027-08
  When the user starts creating a fund on "Suscripciones" funded from its obligations, starting 2026-08
  Then the category has something to spread

@backend
Scenario: A category holding only monthly charges has nothing to spread
  Given a recurring charge "Internet" on "Suscripciones" of 80000.00 COP every month, next due 2026-08
  When the user starts creating a fund on "Suscripciones" funded from its obligations, starting 2026-08
  Then the category has nothing to spread
```

```gherkin
Scenario: A category holding only monthly charges is not offered the rule
  Given the app is open
  And a category "Phone" whose repeating charges all land every month
  When the owner starts a new fund on "Phone"
  Then the rule that saves for repeating charges is not offered

Scenario: A category holding a charge that can be spread is offered the rule
  Given the app is open
  And a category "Suscripciones" holding a charge that lands once a year
  When the owner starts a new fund on "Suscripciones"
  Then the rule that saves for repeating charges is offered
```

## AC-15 — Without a rate the fund refuses as it does today

```gherkin
@backend
Scenario: A dollar charge with no rate set is refused, not half-read
  Given no TRM has been set
  And a recurring charge "Servidor" on "Suscripciones" of 30.00 USD every year, next due 2027-08
  And a fund on "Suscripciones" funded from its obligations, starting 2026-08
  When the user tries to view the funds
  Then the reading is refused for want of a rate
```

## AC-16 — The breakdown is read, never stored

```gherkin
@backend
Scenario: The same month read twice at different rates reports different figures
  Given a recurring charge "Servidor" on "Suscripciones" of 30.00 USD every year, next due 2027-08
  And a fund on "Suscripciones" funded from its obligations, starting 2026-08
  And the user views the funds
  When the TRM is set to 5000
  And the user views the funds
  Then the fund on "Suscripciones" says "Servidor" costs 150000.00 COP

@backend
Scenario: The records hold no breakdown of their own
  Given a recurring charge "Dominio" on "Suscripciones" of 1200000.00 COP every year, next due 2027-08
  And a fund on "Suscripciones" funded from its obligations, starting 2026-08
  When the user views the funds
  Then the records hold no stored breakdown
```

## AC-17 — Reading the month costs no more than it did

```gherkin
@backend
Scenario: Five funds are read in the same number of queries as one
  Given five categories each holding a repeating charge and a fund funded from its obligations
  When the user views the funds
  Then the month was read once, not once for each fund
```

## AC-18 — The assistant is not touched

```gherkin
@backend
Scenario: The assistant reports the figure exactly as it does today
  Given a recurring charge "Internet" on "Suscripciones" of 80000.00 COP every month, next due 2026-08
  And a recurring charge "Dominio" on "Suscripciones" of 1200000.00 COP every year, next due 2027-08
  And a fund on "Suscripciones" funded from its obligations, starting 2026-08
  When the assistant is asked about the fund on "Suscripciones"
  Then the assistant's answer states 180000.00 COP
  And the assistant's answer names no charge behind it

@backend
Scenario: The corrected warning reaches the assistant without being asked to
  Given a recurring charge "Internet" on "Suscripciones" of 80000.00 COP every month, next due 2026-08
  When the assistant is asked to preview a fund on "Suscripciones" funded from its obligations
  Then the assistant's answer carries no warning
```
