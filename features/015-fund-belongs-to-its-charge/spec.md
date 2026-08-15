# Acceptance specs — 015 fund-belongs-to-its-charge

Formalizes `acs.md` (11 ACs, approved by the owner 2026-08-15) as standard
Gherkin.

**Almost all of this is red.** A fund hanging off a charge does not exist: today
one fund covers a whole category and a database constraint forbids a second.
What already works and must keep working is the arithmetic — feature 014
measured it against production — so the scenarios that pin a figure are pinning
the figure the app already computes, moved to a new owner.

## The rule every scenario comes from

**A charge that leaves a whole month free can be saved for on its own, and every
peso it costs is asked once and drained once.** Feature 003 fixed the division
(AC-4, AC-5) and feature 014 made the fund report its terms (ADR-0054). This
feature changes what the fund hangs off, and with it replaces a guess — *which
charge did that spending pay?* — with an answer the movement carries.

## Two nouns, two prepositions

The vocabulary has to keep them apart, because for the length of this feature
both exist:

- **a fund _on_ a category** — the `fixed` and `average` rules, untouched, still
  one per category
- **a fund _for_ a charge** — what marking a charge creates, one per charge

## The rate

One scalar rate (ADR-0031). The suite uses **4000** so every conversion is exact
and a wrong figure cannot look plausible: `50.00 USD` is `200000.00 COP`. A
scenario that never states a rate must never turn on one.

## The numbers

Every scenario is set in **August 2026** and every fund starts that month, so
the months left are easy to count and hard to fake:

| Charge | Costs | Charges | Months left | Asks |
|---|---|---|---|---|
| Seguro | 1.100.000 yearly | 2027-07 | 11 | 100.000 |
| SOAT | 450.000 yearly | 2027-05 | 9 | 50.000 |
| Club de vinos | 600.000 every 6 months | 2026-11 | 3 | 200.000 |
| Opal | 600,00 USD yearly | 2027-08 | 12 | 50,00 USD |
| Netflix | 45.000 monthly | 2026-08 | — | cannot be marked |

AC-6 alone uses production figures, because it is the migration and the whole
point is that it moves nothing: `7.000.000 ÷ 11 = 636.363,64` and
`447.300 ÷ 9 = 49.700,00`, which add to the `686.063,64` the single existing
fund asks today.

## The correction this suite carries

`feature.md` says the migration splits «cuatro fondos de suscripciones» and
cites four figures. Measured on 2026-08-15: there is **one** fund of that rule,
on 🛡️ Auto Insurance, and no fund anywhere has a stated balance. The migration
is **1 → 2**, and AC-6 is written for that. `feature.md` is corrected at CP4.

---

Feature: Un fondo cuelga del cobro que llena, y ningún peso se cuenta dos veces

Background:
  Given today is 2026-08-15
  And the TRM is 4000

## AC-1 — Marking a charge is what creates its fund

```gherkin
@backend
Scenario: Marking a charge creates the fund that saves for it
  Given a recurring charge "Seguro" on "Carro" of 1100000.00 COP every year, next due 2027-07
  When the user marks "Seguro" to save for it
  Then there is a fund for "Seguro"
  And the fund for "Seguro" asks 100000.00 COP this month

@backend
Scenario: The fund saves for its own charge and for no other
  Given a recurring charge "Seguro" on "Carro" of 1100000.00 COP every year, next due 2027-07
  And a recurring charge "SOAT" on "Carro" of 450000.00 COP every year, next due 2027-05
  When the user marks "Seguro" to save for it
  Then the fund for "Seguro" asks 100000.00 COP this month
  And there is no fund for "SOAT"

@backend
Scenario: Two charges in the same category each get their own fund
  Given a recurring charge "Seguro" on "Carro" of 1100000.00 COP every year, next due 2027-07
  And a recurring charge "SOAT" on "Carro" of 450000.00 COP every year, next due 2027-05
  When the user marks "Seguro" to save for it
  And the user marks "SOAT" to save for it
  Then the fund for "Seguro" asks 100000.00 COP this month
  And the fund for "SOAT" asks 50000.00 COP this month
```

```gherkin
Scenario: The charge is marked from the list, with nothing left to confirm
  Given the app is open
  And a repeating charge "Seguro" that can be saved for
  When the owner marks "Seguro"
  Then a fund for "Seguro" exists
  And the owner is still on the list of repeating charges

Scenario: A marked charge is its own row among the funds, under its own name
  Given the app is open
  And a fund for the charge "Seguro" asking 100000.00 COP
  When the owner opens the funds
  Then the row for "Seguro" reads 100000.00 COP
```

## AC-2 — Only what leaves a month free is offered, and where it is not, the row says why

```gherkin
@backend
Scenario: A charge that leaves a whole month free can be saved for
  Given a recurring charge "Seguro" on "Carro" of 1100000.00 COP every year, next due 2027-07
  When the user views the repeating obligations
  Then "Seguro" can be marked

@backend
Scenario: A charge that comes back the following month cannot be saved for
  Given a recurring charge "Netflix" on "Suscripciones" of 45000.00 COP every month, next due 2026-09
  When the user views the repeating obligations
  Then "Netflix" cannot be marked

@backend
Scenario Outline: What can be marked is read from the rhythm, never from the declared cadence
  Given a recurring charge "Cobro" on "Varios" of 300000.00 COP every <cadence>, next due <due>
  When the user views the repeating obligations
  Then "Cobro" <verdict> be marked

    Examples:
      | cadence  | due     | verdict |
      | year     | 2027-07 | can     |
      | 6 months | 2026-11 | can     |
      | 12 weeks | 2026-11 | can     |
      | 90 days  | 2026-11 | can     |
      | month    | 2026-09 | cannot  |
      | 4 weeks  | 2026-09 | cannot  |
      | 30 days  | 2026-09 | cannot  |
```

```gherkin
Scenario: The list says why a charge cannot be marked
  Given the app is open
  And a repeating charge "Netflix" that cannot be saved for
  When the owner opens the repeating charges
  Then the row for "Netflix" offers no mark
  And the row for "Netflix" says the charge leaves no month to save in
```

## AC-3 — The fund states what the charge costs, when it lands, and what it asks now

```gherkin
@backend
Scenario: The fund reports the three terms its figure comes from
  Given a recurring charge "Seguro" on "Carro" of 1100000.00 COP every year, next due 2027-07
  And "Seguro" is marked to be saved for
  When the user views the funds
  Then the fund for "Seguro" asks 100000.00 COP this month
  And the fund for "Seguro" says the charge costs 1100000.00 COP
  And the fund for "Seguro" says the charge lands in 2027-07

@backend
Scenario: What is missing is divided, not what the charge costs
  Given a recurring charge "Seguro" on "Carro" of 1100000.00 COP every year, next due 2027-07
  And "Seguro" is marked to be saved for
  And the fund for "Seguro" already holds 550000.00 COP
  When the user views the funds
  Then the fund for "Seguro" asks 50000.00 COP this month

@backend
Scenario Outline: The month it is marked in decides the figure, and the charge month never contributes
  Given today is <today>
  And a recurring charge "Seguro" on "Carro" of 1100000.00 COP every year, next due 2027-07
  And "Seguro" is marked to be saved for
  When the user views the funds
  Then the fund for "Seguro" asks <asks> COP this month

    Examples:
      | today      | asks       |
      | 2026-08-15 | 100000.00  |
      | 2027-01-15 | 183333.34  |
      | 2027-04-15 | 366666.67  |
      | 2027-06-15 | 1100000.00 |
```

```gherkin
Scenario: The row carries all three terms, not just the figure
  Given the app is open
  And a fund for the charge "Seguro" asking 100000.00 COP, costing 1100000.00 COP in 2027-07
  When the owner opens the funds
  Then the row for "Seguro" reads 100000.00 COP
  And the row for "Seguro" states 1100000.00 COP
  And the row for "Seguro" names 2027-07
```

## AC-4 — Unmarking removes the whole fund, and touches no movement

```gherkin
@backend
Scenario: Unmarking removes the fund
  Given a recurring charge "Seguro" on "Carro" of 1100000.00 COP every year, next due 2027-07
  And "Seguro" is marked to be saved for
  When the user unmarks "Seguro"
  Then there is no fund for "Seguro"

@backend
Scenario: Unmarking creates, deletes and changes no movement
  Given a recurring charge "Seguro" on "Carro" of 1100000.00 COP every year, next due 2027-07
  And a recorded expense of 300000.00 COP in category "Carro" this month
  And "Seguro" is marked to be saved for
  When the user unmarks "Seguro"
  Then no movement was created, deleted or changed

@backend
Scenario: The month answers again as if the fund had never existed
  Given an income of 5000000.00 COP is due this month
  And a recurring charge "Seguro" on "Carro" of 1100000.00 COP every year, next due 2027-07
  And "Seguro" is marked to be saved for
  When the user unmarks "Seguro"
  And the user views the money available this month
  Then the breakdown shows the funds asking 0.00 COP

@backend
Scenario: Marking again starts from zero, and the figure says so
  Given a recurring charge "Seguro" on "Carro" of 1100000.00 COP every year, next due 2027-07
  And "Seguro" is marked to be saved for
  And the fund for "Seguro" already holds 550000.00 COP
  When the user unmarks "Seguro"
  And the user marks "Seguro" to save for it
  Then the fund for "Seguro" asks 100000.00 COP this month
```

```gherkin
Scenario: The unmarked charge leaves the funds
  Given the app is open
  And a fund for the charge "Seguro" asking 100000.00 COP
  When the owner unmarks "Seguro"
  Then the funds name no row for "Seguro"
```

## AC-5 — A hand-typed payment may name the charge it settled

```gherkin
@backend
Scenario: A payment that names its charge closes the cycle and starts the next
  Given a recurring charge "Seguro" on "Carro" of 1100000.00 COP every year, next due 2027-07
  And "Seguro" is marked to be saved for
  When the user records an expense of 1100000.00 COP in category "Carro" settling "Seguro"
  Then the fund for "Seguro" says the charge lands in 2028-07

@backend
Scenario: A payment that names no charge settles none
  Given a recurring charge "Seguro" on "Carro" of 1100000.00 COP every year, next due 2027-07
  And "Seguro" is marked to be saved for
  When the user records an expense of 1100000.00 COP in category "Carro"
  Then the fund for "Seguro" says the charge lands in 2027-07
  And the fund for "Seguro" asks 100000.00 COP this month

@backend
Scenario: A payment made a month early still settles the charge it names
  Given a recurring charge "Club de vinos" on "Restaurantes" of 600000.00 COP every 6 months, next due 2026-11
  And "Club de vinos" is marked to be saved for
  When the user records an expense of 600000.00 COP in category "Restaurantes" settling "Club de vinos"
  Then the fund for "Club de vinos" says the charge lands in 2027-05

@backend
Scenario: A dollar payment settles its dollar charge without passing through pesos
  Given a recurring charge "Opal" on "Tecnología" of 600.00 USD every year, next due 2027-08
  And "Opal" is marked to be saved for
  When the user records an expense of 600.00 USD in category "Tecnología" settling "Opal"
  Then the fund for "Opal" says the charge lands in 2028-08
  And the fund for "Opal" asks 25.00 USD this month
```

```gherkin
Scenario: Saving an expense offers the marked charges of its category
  Given the app is open
  And a category "Carro" holding the marked charges "Seguro" and "SOAT"
  When the owner records an expense in "Carro"
  Then the owner is offered to settle "Seguro"
  And the owner is offered to settle "SOAT"
  And the owner is offered to settle none of them

Scenario: A category with no marked charge offers nothing to settle
  Given the app is open
  And a category "Mercado" holding no marked charge
  When the owner records an expense in "Mercado"
  Then the owner is offered nothing to settle
```

## AC-6 — The migration marks both charges, and the month's figure does not move

```gherkin
@backend
Scenario: The fund on the category becomes one fund per charge, both marked
  Given a recurring charge "Seguro" on "Carro" of 7000000.00 COP every year, next due 2027-07
  And a recurring charge "SOAT" on "Carro" of 447300.00 COP every year, next due 2027-05
  And a fund on "Carro" that asks what its recurring charges need, starting 2026-08
  When the upgrade completes
  Then there is a fund for "Seguro"
  And there is a fund for "SOAT"
  And there is no fund on "Carro"

@backend
Scenario: The migration moves no figure
  Given a recurring charge "Seguro" on "Carro" of 7000000.00 COP every year, next due 2027-07
  And a recurring charge "SOAT" on "Carro" of 447300.00 COP every year, next due 2027-05
  And a fund on "Carro" that asks what its recurring charges need, starting 2026-08
  And the user views the funds
  When the upgrade completes
  And the user views the funds
  Then the fund for "Seguro" asks 636363.64 COP this month
  And the fund for "SOAT" asks 49700.00 COP this month
  And the funds ask 686063.64 COP altogether this month

@backend
Scenario: A fund that averages its category is left exactly as it is
  Given the app has recorded movements since 4 months ago
  And a fund on "Restaurantes" that asks what the category averaged over the last 3 months, starting 2026-08
  When the upgrade completes
  Then there is still a fund on "Restaurantes"
```

## AC-7 — A switched-off charge has no fund

```gherkin
@backend
Scenario: Switching a charge off removes its fund
  Given a recurring charge "Seguro" on "Carro" of 1100000.00 COP every year, next due 2027-07
  And "Seguro" is marked to be saved for
  When the user switches off "Seguro"
  Then there is no fund for "Seguro"

@backend
Scenario: Switching it back on brings it back unmarked
  Given a recurring charge "Seguro" on "Carro" of 1100000.00 COP every year, next due 2027-07
  And "Seguro" is marked to be saved for
  And the user switches off "Seguro"
  When the user switches "Seguro" back on
  Then there is no fund for "Seguro"
  And "Seguro" can be marked
```

## AC-8 — No fund outlives its charge

```gherkin
@backend
Scenario: Deleting the charge for good removes its fund
  Given a recurring charge "Seguro" on "Carro" of 1100000.00 COP every year, next due 2027-07
  And "Seguro" is marked to be saved for
  When the user deletes "Seguro"
  Then there is no fund for "Seguro"

@backend
Scenario: A category holding a marked charge refuses to be archived
  Given a recurring charge "Seguro" on "Carro" of 1100000.00 COP every year, next due 2027-07
  And "Seguro" is marked to be saved for
  When the user tries to archive the category "Carro"
  Then the archiving is rejected
  And the user is told to unmark "Seguro" first

@backend
Scenario: Once the charge is unmarked the category archives
  Given a recurring charge "Seguro" on "Carro" of 1100000.00 COP every year, next due 2027-07
  And "Seguro" is marked to be saved for
  And the user unmarks "Seguro"
  When the user archives the category "Carro"
  Then the category "Carro" is archived

@backend
Scenario: A charge edited into a monthly rhythm loses the fund it can no longer justify
  Given a recurring charge "Seguro" on "Carro" of 1100000.00 COP every year, next due 2027-07
  And "Seguro" is marked to be saved for
  When the user changes "Seguro" to charge every month
  Then there is no fund for "Seguro"
  And "Seguro" cannot be marked

@backend
Scenario: A fund exists if and only if its charge is marked and live
  Given a recurring charge "Seguro" on "Carro" of 1100000.00 COP every year, next due 2027-07
  And a recurring charge "SOAT" on "Carro" of 450000.00 COP every year, next due 2027-05
  And a recurring charge "Impuesto" on "Carro" of 800000.00 COP every year, next due 2027-03
  And "Seguro" is marked to be saved for
  And "SOAT" is marked to be saved for
  And "Impuesto" is marked to be saved for
  When the user switches off "SOAT"
  And the user deletes "Impuesto"
  Then the funds name only "Seguro"
```

```gherkin
Scenario: Making a charge monthly says first that its fund goes with it
  Given the app is open
  And a marked charge "Seguro" that charges once a year
  When the owner changes "Seguro" to charge every month
  Then the owner is warned the fund for "Seguro" will be removed
  And the owner is offered to save the change and remove the fund
  And the owner is offered to cancel

Scenario: Cancelling that warning leaves the charge and its fund alone
  Given the app is open
  And a marked charge "Seguro" that charges once a year
  And the owner changed "Seguro" to charge every month
  When the owner cancels the warning
  Then "Seguro" still charges once a year
  And there is still a fund for "Seguro"
```

## AC-9 — A peso is asked once and drained once

```gherkin
@backend
Scenario: The average stops counting what a marked charge already covers
  Given the app has recorded movements since 4 months ago
  And a recurring charge "Club de vinos" on "Restaurantes" of 600000.00 COP every 6 months, next due 2026-11
  And "Club de vinos" was charged 3 months ago
  And a recorded expense of 100000.00 COP in category "Restaurantes" 3 months ago
  And a recorded expense of 100000.00 COP in category "Restaurantes" 2 months ago
  And a recorded expense of 100000.00 COP in category "Restaurantes" 1 month ago
  And a fund on "Restaurantes" that asks what the category averaged over the last 3 months, starting 2026-08
  And "Club de vinos" is marked to be saved for
  When the user views the funds
  Then the fund on "Restaurantes" asks 100000.00 COP this month
  And the fund for "Club de vinos" asks 200000.00 COP this month
  And the funds ask 300000.00 COP altogether this month

@backend
Scenario: With the charge unmarked the average counts every peso the category spent
  Given the app has recorded movements since 4 months ago
  And a recurring charge "Club de vinos" on "Restaurantes" of 600000.00 COP every 6 months, next due 2026-11
  And "Club de vinos" was charged 3 months ago
  And a recorded expense of 100000.00 COP in category "Restaurantes" 3 months ago
  And a recorded expense of 100000.00 COP in category "Restaurantes" 2 months ago
  And a recorded expense of 100000.00 COP in category "Restaurantes" 1 month ago
  And a fund on "Restaurantes" that asks what the category averaged over the last 3 months, starting 2026-08
  When the user views the funds
  Then the fund on "Restaurantes" asks 300000.00 COP this month

@backend
Scenario: A payment that settles a marked charge does not drain the category's fund
  Given a recurring charge "Club de vinos" on "Restaurantes" of 600000.00 COP every 6 months, next due 2026-11
  And a fund on "Restaurantes" that asks a fixed 500000.00 COP each month, starting 2026-08
  And the fund on "Restaurantes" already holds 500000.00 COP
  And "Club de vinos" is marked to be saved for
  When the user records an expense of 600000.00 COP in category "Restaurantes" settling "Club de vinos"
  Then the fund on "Restaurantes" holds 500000.00 COP

@backend
Scenario: A loose expense still drains the category's fund
  Given a fund on "Restaurantes" that asks a fixed 500000.00 COP each month, starting 2026-08
  And the fund on "Restaurantes" already holds 500000.00 COP
  When the user records an expense of 200000.00 COP in category "Restaurantes"
  Then the fund on "Restaurantes" holds 300000.00 COP
```

## AC-10 — The app says no, and says why

```gherkin
@backend
Scenario: A charge landing this very month cannot be marked
  Given a recurring charge "Seguro" on "Carro" of 1100000.00 COP every year, next due 2026-08
  When the user tries to mark "Seguro" to save for it
  Then the marking is rejected
  And the user is told to mark it once it has been paid

@backend
Scenario: A charge landing next month is accepted, and asks the whole amount at once
  Given a recurring charge "Seguro" on "Carro" of 1100000.00 COP every year, next due 2026-09
  When the user marks "Seguro" to save for it
  Then the fund for "Seguro" asks 1100000.00 COP this month

@backend
Scenario: Money coming in cannot be marked
  Given a repeating income "Prima" on "Salario" of 3000000.00 COP every year, next due 2027-06
  When the user tries to mark "Prima" to save for it
  Then the marking is rejected
  And the user is told a fund only covers money going out

@backend
Scenario: A charge with no turn left cannot be marked
  Given a recurring charge "Seguro" on "Carro" of 1100000.00 COP every year, next due 2026-05
  And "Seguro" stops repeating after 2026-05
  When the user tries to mark "Seguro" to save for it
  Then the marking is rejected
  And the user is told the charge has no turn left

@backend
Scenario: A charge already marked cannot be marked twice
  Given a recurring charge "Seguro" on "Carro" of 1100000.00 COP every year, next due 2027-07
  And "Seguro" is marked to be saved for
  When the user tries to mark "Seguro" to save for it
  Then the marking is rejected
  And the user is told "Seguro" already has a fund
```

```gherkin
Scenario: A refused marking says why on the screen, and leaves the charge alone
  Given the app is open
  And a repeating charge "Netflix" that comes back every month
  When the owner marks "Netflix"
  Then the screen says why "Netflix" cannot be marked
  And "Netflix" is left unmarked
```

## AC-11 — The fund speaks the currency of its charge

```gherkin
@backend
Scenario: A charge in dollars is saved for in dollars
  Given a recurring charge "Opal" on "Tecnología" of 600.00 USD every year, next due 2027-08
  And "Opal" is marked to be saved for
  When the user views the funds
  Then the fund for "Opal" asks 50.00 USD this month
  And the fund for "Opal" says the charge costs 600.00 USD

@backend
Scenario: Only the month's total converts
  Given an income of 5000000.00 COP is due this month
  And a recurring charge "Opal" on "Tecnología" of 600.00 USD every year, next due 2027-08
  And "Opal" is marked to be saved for
  When the user views the money available this month
  Then the breakdown shows the funds asking 200000.00 COP

@backend
Scenario: A different rate moves the total and leaves the fund's own figure untouched
  Given a recurring charge "Opal" on "Tecnología" of 600.00 USD every year, next due 2027-08
  And "Opal" is marked to be saved for
  When the TRM is set to 5000
  And the user views the funds
  Then the fund for "Opal" asks 50.00 USD this month
  And the fund for "Opal" says the charge costs 600.00 USD
```

```gherkin
Scenario: The row of a dollar charge reads entirely in dollars
  Given the app is open
  And a fund for the charge "Opal" asking 50.00 USD, holding 150.00 USD of 600.00 USD
  When the owner opens the funds
  Then the row for "Opal" reads 50.00 USD
  And the row for "Opal" says it holds 150.00 USD of 600.00 USD
  And the row for "Opal" states no figure in COP
```
