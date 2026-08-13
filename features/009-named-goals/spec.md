# Acceptance specs — 009 named-goals

Formalizes `acs.md` (41 ACs, revised and approved 2026-08-08) as standard
Gherkin.

**Second draft.** The first (87 scenarios) was audited by spec-guardian and four
adversarial reviewers and returned **not fit as contract**: 23 money figures
wrong across 16 scenarios, 14 contradictions with accepted decisions, 8
scenarios that could not fail, and a step vocabulary that read three ways for
one state. The root cause was a product question nobody had answered. It is
answered now, and this draft is derived from it rather than transcribed from the
criteria's illustrations — which is how the first draft went wrong.

**Nothing specified here exists.** Migration `0012` dropped `goal`,
`goal_contribution`, `budget` and `transaction.goal_id` on 2026-08-04. This is
the ATDD red phase in its pure form.

## The one rule every figure comes from

```
ask(M)    = ⌈ (amount − held entering M) ÷ months from M through the target ⌉
holds(M)  = held entering M + ask(M) + contributions made in M
```

**The month always charges its instalment.** Contributing, completing,
cancelling or editing part-way through a month never gives that month's
instalment back; a contribution is charged on top of it and what drops is every
instalment *after*. An instalment of zero happens only because nothing is
missing, never because an act waived it.

**Rounding is at the cent**, as `fund_ask_calc` already rounds. $1.000.000 over
three months asks `333333.34`, then `333333.33`, then `333333.33`.

The running fold, quoted here so every scenario below can be checked against it:

```
Celular   $8.000.000 by 2026-12, opened 2026-08
  month    enters with    asks       holds
  ago               0   1.600.000   1.600.000
  sep       1.600.000   1.600.000   3.200.000
  oct       3.200.000   1.600.000   4.800.000
  nov       4.800.000   1.600.000   6.400.000
  dic       6.400.000   1.600.000   8.000.000

Televisor $5.000.000 by 2026-12, opened 2026-08 — 1.000.000 a month
```

## Conventions

**`opened YYYY-MM` is the only way a meta gets a history.** No scenario states a
balance for a month; the fold produces it. The first draft had three phrasings
for that state, one differing by a single adverb, and figures that the fold
could not reach. The one exception is AC-34, where the owner *declares* what he
already had, and it reads `stating it already held N COP` — a different act,
never a balance assertion.

**`holds` and `asks`** are the two things a meta reports for a month, defined by
the rule above. Nothing says "put by".

**One exchange rate, not one per month** (ADR-0031, amended 2026-07-30: *"the
TRM is a single scalar value, not a dated series"*). The bound step is
`Given the TRM is N`. The first draft invented a dated rate table that was
deleted in the same migration that created the scalar.

**Two streams**, per technical ADR-0045. `@backend` → generated pytest against
the services layer, every figure a month reports. Untagged → vitest against the
screen. Nothing is `@browser`: no scenario turns on width or wrapping.

**Dates are absolute**, without exception. Amounts are plain decimals, no
thousands separators. Category names are plain rather than production's emoji
ones, as in the other suites.

**Order is not pinned.** `the report lists …` asserts presence, never position.

```gherkin
Feature: Metas — a named thing to save for, beside the fund and inside no category
```

## AC-1 — A meta is a named amount with a month, and it belongs to nothing else

```gherkin
@backend
Scenario: A meta is created with a name, an amount and a month
  Given today is 2026-08-10
  When the user creates a meta "Celular" of 8000000.00 COP by 2026-12
  Then the meta "Celular" is running
  And the meta "Celular" wants 8000000.00 COP by 2026-12

@backend
Scenario: A meta names no category, and its category's fund is undisturbed
  Given today is 2026-08-10
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  And a meta "Celular" of 8000000.00 COP by 2026-12
  Then the meta "Celular" names no category
  And the fund on "Tecnologia" asks 100000.00 COP this month

@backend
Scenario: Two metas whose purchases fall in one category never meet
  Given today is 2026-08-10
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  And a meta "Celular" of 8000000.00 COP by 2026-12
  And a meta "Televisor" of 5000000.00 COP by 2026-12
  Then the meta "Celular" asks 1600000.00 COP this month
  And the meta "Televisor" asks 1000000.00 COP this month
  And the fund on "Tecnologia" asks 100000.00 COP this month
```

## AC-2 — The month named is a month that saves

```gherkin
@backend
Scenario: The named month is one of the months that save
  Given today is 2026-08-10
  And a meta "Celular" of 8000000.00 COP by 2026-12
  Then the meta "Celular" asks 1600000.00 COP this month

@backend
Scenario: The last month asks its share like any other
  Given today is 2026-12-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  Then the meta "Celular" asks 1600000.00 COP this month
  And the meta "Celular" holds 8000000.00 COP this month

@backend
Scenario: A fund saving toward a charge still stops the month before, unchanged
  Given today is 2026-11-10
  And an expense category "Seguros"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating payment of 447300.00 COP to "SOAT" from "Banco" every 1 year starting on 2027-05-02 in category "Seguros", waiting for approval
  And a fund on "Seguros" funded from its obligations, starting 2026-11
  Then the fund on "Seguros" asks 74550.00 COP this month
```

## AC-3 — A meta fills itself, and no month requires an act of saving

```gherkin
@backend
Scenario: Months that pass untouched still advance the meta
  Given today is 2026-10-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  Then the meta "Celular" holds 4800000.00 COP this month
  And the meta "Celular" asks 1600000.00 COP this month

@backend
Scenario: An amount that does not divide is rounded up at the cent
  Given today is 2026-08-10
  And a meta "Viaje" of 1000000.00 COP by 2026-10
  Then the meta "Viaje" asks 333333.34 COP this month

@backend
Scenario: The last month asks only what is still missing
  Given today is 2026-10-10
  And a meta "Viaje" of 1000000.00 COP by 2026-10, opened 2026-08
  Then the meta "Viaje" asks 333333.33 COP this month
  And the meta "Viaje" holds 1000000.00 COP this month
```

## AC-4 — What the metas ask lowers the money available

```gherkin
@backend
Scenario: A meta lowers the money available without anyone assigning it
  Given today is 2026-08-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a meta "Celular" of 8000000.00 COP by 2026-12
  Then the money available this month is 3400000.00 COP

@backend
Scenario: The breakdown states what the metas ask, apart from what the funds ask
  Given today is 2026-08-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  And a meta "Celular" of 8000000.00 COP by 2026-12
  When the user views the money available this month
  Then the breakdown shows the funds asking 100000.00 COP
  And the breakdown shows the metas asking 1600000.00 COP
  And the breakdown shows 0.00 COP contributed by hand
  And the breakdown shows 0.00 COP released by a cancelled meta
  And the breakdown adds up to the money available

@backend
Scenario: A month the owner acted on names all six terms
  Given today is 2026-10-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a meta "Televisor" of 5000000.00 COP by 2026-12, opened 2026-08
  When the user contributes 500000.00 COP to "Celular"
  And the user cancels the meta "Televisor"
  And the user views the money available this month
  Then the breakdown shows the metas asking 2600000.00 COP
  And the breakdown shows 500000.00 COP contributed by hand
  And the breakdown shows 3000000.00 COP released by a cancelled meta
  And the breakdown adds up to the money available
```

## AC-5 — The metas have their own screen

```gherkin
Scenario: The navigation offers Metas beside Fondos y presupuestos
  Given the app is open
  Then the navigation offers "Metas" under "Planeación"
  And the navigation offers "Fondos y presupuestos"

Scenario: The metas screen states each meta's amount, month, holdings, ask and progress
  Given a meta "Celular" of 8000000.00 COP by 2026-12 holding 4800000.00 COP and asking 1600000.00 COP
  When the owner opens the "Metas" screen
  Then the screen names "Celular"
  And the screen states it wants 8000000.00 COP by diciembre 2026
  And the screen states it holds 4800000.00 COP
  And the screen states it asks 1600000.00 COP this month
  And the screen states it is 60 percent of the way there

Scenario: The funds screen never lists a meta
  Given a meta "Celular" of 8000000.00 COP by 2026-12 holding 4800000.00 COP and asking 1600000.00 COP
  And a fondo on "Tecnologia" asking 100000.00 COP this month
  When the owner opens the "Fondos y presupuestos" screen
  Then the screen names "Tecnologia"
  And the screen does not name "Celular"
```

## AC-6 — The purchase is linked on the movement, once

```gherkin
@backend
Scenario: An expense is pointed at a meta when it is recorded
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user records an expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  Then the meta "Celular" is complete

@backend
Scenario: An expense pointed at nothing behaves as it does today
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user records an expense of 200000.00 COP in category "Tecnologia"
  Then the fund on "Tecnologia" spent 200000.00 COP this month
  And the meta "Celular" is running
```

## AC-7 — A linked expense leaves the category's fund untouched

```gherkin
@backend
Scenario: The category's fund counts the linked purchase in no way at all
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-12
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user records an expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  Then the fund on "Tecnologia" spent 0.00 COP this month
  And the fund on "Tecnologia" holds 0.00 COP
  And the fund on "Tecnologia" carries 100000.00 COP into next month

@backend
Scenario: A linked purchase does not read as an overspend on its category
  Given today is 2026-12-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 30000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-12
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user records an expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  And the user views the money available this month
  Then the breakdown shows uncovered spending of 0.00 COP
```

## AC-8 — Linking the purchase completes the meta and asks what comes next

```gherkin
@backend
Scenario: The month of the purchase still charges the meta's instalment
  Given today is 2026-12-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 30000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user records an expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  Then the meta "Celular" is complete
  And the meta "Celular" asks 1600000.00 COP this month
  And the money available this month is 3400000.00 COP

@backend
Scenario: A completed meta asks nothing in the months that follow
  Given today is 2027-01-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a recorded expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular" on 2026-12-12
  Then the meta "Celular" asks 0.00 COP this month

Scenario: Completing offers three things to do next
  Given a meta "Celular" of 8000000.00 COP by 2026-12 that has just been completed by its purchase
  When the owner opens the "Metas" screen
  Then the screen offers to close "Celular"
  And the screen offers to keep "Celular" with a new amount
  And the screen offers to keep "Celular" with a new month
@backend
Scenario: A meta nobody kept on asks nothing after its purchase
  Given today is 2026-11-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 6000000.00 COP by 2026-12, opened 2026-10
  And a recorded expense of 6000000.00 COP in category "Tecnologia" linked to the meta "Celular" on 2026-10-12
  Then the meta "Celular" asks 0.00 COP this month
  And the meta "Celular" holds 2000000.00 COP this month

@backend
Scenario: A meta kept on with a new amount asks again
  Given today is 2026-11-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 6000000.00 COP by 2026-12, opened 2026-10
  And a recorded expense of 6000000.00 COP in category "Tecnologia" linked to the meta "Celular" on 2026-10-12
  When the user sets the meta "Celular" to want 8000000.00 COP
  Then the meta "Celular" asks 3000000.00 COP this month
```

## AC-9 — Reaching the amount stops the asking

```gherkin
@backend
Scenario: A meta filled by a contribution still charged that month's instalment
  Given today is 2026-10-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user contributes 3200000.00 COP to "Celular"
  Then the meta "Celular" holds 8000000.00 COP this month
  And the meta "Celular" asks 1600000.00 COP this month

@backend
Scenario: A meta that is whole asks nothing from the next month on
  Given today is 2026-11-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a contribution of 3200000.00 COP to "Celular" made 2026-10
  Then the meta "Celular" asks 0.00 COP this month
  And the money available this month is 5000000.00 COP
```

## AC-10 — The owner may put in extra, and it costs that month

```gherkin
@backend
Scenario: A contribution is charged on top of the month's instalment
  Given today is 2026-09-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user contributes 2000000.00 COP to "Celular"
  Then the meta "Celular" asks 1600000.00 COP this month
  And the meta "Celular" holds 5200000.00 COP this month

@backend
Scenario: The month pays both
  Given today is 2026-09-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user contributes 2000000.00 COP to "Celular"
  Then the money available this month is 1400000.00 COP

@backend
Scenario: What drops is every instalment after it
  Given today is 2026-10-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a contribution of 2000000.00 COP to "Celular" made 2026-09
  Then the meta "Celular" asks 933333.34 COP this month
  And the money available this month is 4066666.66 COP
```

## AC-11 — A meta can be edited while it runs

```gherkin
@backend
Scenario: Raising the amount recomputes the month being edited
  Given today is 2026-10-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user sets the meta "Celular" to want 9000000.00 COP
  Then the meta "Celular" asks 1933333.34 COP this month

@backend
Scenario: Moving the month recomputes what it asks
  Given today is 2026-10-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user sets the meta "Celular" to be wanted by 2027-03
  Then the meta "Celular" asks 800000.00 COP this month

@backend
Scenario: Renaming a meta keeps everything it holds
  Given today is 2026-10-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user renames the meta "Celular" to "Telefono"
  Then the meta "Telefono" holds 4800000.00 COP this month

@backend
Scenario: Moving the month after raising the amount keeps the new amount
  Given today is 2026-10-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user sets the meta "Celular" to want 9000000.00 COP
  And the user sets the meta "Celular" to be wanted by 2027-03
  Then the meta "Celular" wants 9000000.00 COP by 2027-03
  And the meta "Celular" asks 966666.67 COP this month

@backend
Scenario: Raising the amount after moving the month keeps the new month
  Given today is 2026-10-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user sets the meta "Celular" to be wanted by 2027-03
  And the user sets the meta "Celular" to want 9000000.00 COP
  Then the meta "Celular" wants 9000000.00 COP by 2027-03
  And the meta "Celular" asks 966666.67 COP this month
```

## AC-12 — Buying before the money is whole leaves a visible gap

```gherkin
@backend
Scenario: What was never put by leaves the month's money available
  Given today is 2026-10-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user records an expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  And the user views the money available this month
  Then the breakdown shows uncovered spending of 3200000.00 COP
  And the money available this month is 200000.00 COP

@backend
Scenario: Buying early enough puts the month in the red
  Given today is 2026-09-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user records an expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  And the user views the money available this month
  Then the breakdown shows uncovered spending of 4800000.00 COP
  And the money available this month is -1400000.00 COP

@backend
Scenario: A gap in a category that also carries a fund is charged once
  Given today is 2026-10-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user records an expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  And the user views the money available this month
  Then the breakdown shows uncovered spending of 3200000.00 COP
  And the fund on "Tecnologia" spent 0.00 COP this month
  And the money available this month is 100000.00 COP
```

## AC-13 — A purchase that cost more than the meta held completes it anyway

```gherkin
@backend
Scenario: The excess leaves the month and the meta closes
  Given today is 2026-12-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 30000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user records an expense of 9000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  And the user views the money available this month
  Then the meta "Celular" is complete
  And the breakdown shows uncovered spending of 1000000.00 COP
  And the money available this month is 2400000.00 COP

@backend
Scenario: The meta's amount is not rewritten to the price paid
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user records an expense of 9000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  Then the meta "Celular" wants 8000000.00 COP by 2026-12

@backend
Scenario: Only what a meta filled by hand did not cover leaves the month
  Given today is 2026-10-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 30000000.00 COP
  And a repeating income of 10000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Tecnologia"
  And a meta "Celular" of 6000000.00 COP by 2026-12, opened 2026-10
  And a contribution of 4000000.00 COP to "Celular" made 2026-10
  When the user records an expense of 7000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  And the user views the money available this month
  Then the meta "Celular" holds 6000000.00 COP this month
  And the breakdown shows uncovered spending of 1000000.00 COP
  And the money available this month is 3000000.00 COP
```

## AC-14 — A contribution larger than what is missing is trimmed to fit

```gherkin
@backend
Scenario: Only what is missing is taken
  Given today is 2026-10-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user contributes 5000000.00 COP to "Celular"
  Then the user is told 3200000.00 COP was put in, which is what was missing
  And the meta "Celular" holds 8000000.00 COP this month

@backend
Scenario: The rest stays in the month
  Given today is 2026-10-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user contributes 5000000.00 COP to "Celular"
  Then the money available this month is 200000.00 COP
@backend
Scenario: A meta that has finished takes no more money
  Given today is 2026-11-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 6000000.00 COP by 2026-12, opened 2026-10
  And a recorded expense of 6000000.00 COP in category "Tecnologia" linked to the meta "Celular" on 2026-10-12
  When the user contributes 2000000.00 COP to "Celular"
  Then the contribution is rejected
  And the meta "Celular" holds 2000000.00 COP this month

@backend
Scenario: Lowering the amount below what was contributed leaves the rest in the month
  Given today is 2026-10-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a contribution of 3200000.00 COP to "Celular" made 2026-10
  When the user sets the meta "Celular" to want 5000000.00 COP
  And the user views the money available this month
  Then the meta "Celular" holds 5000000.00 COP this month
  And the breakdown shows 1200000.00 COP contributed by hand
  And the money available this month is 3200000.00 COP

@backend
Scenario: A contribution to a meta in dollars reaches the month at the rate
  Given today is 2026-10-10
  And the TRM is 4000
  And a meta "Portatil" of 1200.00 USD by 2026-12, opened 2026-10
  When the user contributes 800.00 USD to "Portatil"
  And the user views the money available this month
  Then the meta "Portatil" holds 1200.00 USD this month
  And the breakdown shows 3200000.00 COP contributed by hand

@backend
Scenario: A meta that had already finished leaves the whole contribution in the month
  Given today is 2026-10-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a contribution of 3200000.00 COP to "Celular" made 2026-10
  And a recorded expense of 3200000.00 COP in category "Tecnologia" linked to the meta "Celular" on 2026-09-12
  When the user views the money available this month
  Then the meta "Celular" holds 3200000.00 COP this month
  And the breakdown shows 0.00 COP contributed by hand
  And the money available this month is 5000000.00 COP
```

## AC-15 — Cancelling gives back what was put by, in the month it is cancelled

```gherkin
@backend
Scenario: What the meta held is released, and the month keeps its instalment
  Given today is 2026-10-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user cancels the meta "Celular"
  Then the money available this month is 8200000.00 COP

@backend
Scenario: A cancelled meta asks nothing from the next month on
  Given today is 2026-11-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And the meta "Celular" was cancelled 2026-10
  Then the money available this month is 5000000.00 COP

@backend
Scenario: Nothing is carried from a cancelled meta into another one
  Given today is 2026-10-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a meta "Televisor" of 5000000.00 COP by 2026-12, opened 2026-08
  When the user cancels the meta "Celular"
  Then the meta "Televisor" holds 3000000.00 COP this month
  And the meta "Televisor" asks 1000000.00 COP this month
@backend
Scenario: Cancelling gives back what the meta held and not a peso more
  Given today is 2026-10-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 30000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a contribution of 2000000.00 COP to "Celular" made 2026-10
  When the user cancels the meta "Celular"
  And the user views the money available this month
  Then the breakdown shows 2000000.00 COP contributed by hand
  And the breakdown shows 6800000.00 COP released by a cancelled meta
  And the money available this month is 8200000.00 COP
```

## AC-16 — Lowering the amount below what is saved completes the meta

```gherkin
@backend
Scenario: The meta completes and the excess is released into the month
  Given today is 2026-10-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user sets the meta "Celular" to want 3000000.00 COP
  Then the meta "Celular" is complete
  And the meta "Celular" asks 0.00 COP this month
  And the money available this month is 5200000.00 COP
@backend
Scenario: A meta closed after being lowered leaves the screen too
  Given today is 2026-11-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user sets the meta "Celular" to want 3000000.00 COP
  And the user closes the meta "Celular"
  Then the meta "Celular" is not listed
```

## AC-17 — Several metas run at once without interfering

```gherkin
@backend
Scenario: Every meta asks its own share and the month subtracts them all
  Given today is 2026-08-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a meta "Celular" of 8000000.00 COP by 2026-12
  And a meta "Televisor" of 5000000.00 COP by 2026-12
  When the user views the money available this month
  Then the breakdown shows the metas asking 2600000.00 COP
  And the money available this month is 2400000.00 COP

@backend
Scenario: A purchase linked to one meta leaves the others alone
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a meta "Televisor" of 5000000.00 COP by 2026-12, opened 2026-08
  When the user records an expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  Then the meta "Celular" is complete
  And the meta "Televisor" is running
  And the meta "Televisor" holds 5000000.00 COP this month

@backend
Scenario: A meta the owner restarts after buying runs again
  Given today is 2026-09-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 1000000.00 COP by 2026-12, opened 2026-08
  And a recorded expense of 1000000.00 COP in category "Tecnologia" linked to the meta "Celular" on 2026-08-20
  When the user sets the meta "Celular" to want 3000000.00 COP
  Then the meta "Celular" is running
  And the meta "Celular" asks 700000.00 COP this month
  And the user contributes 100000.00 COP to "Celular"

@backend
Scenario: A meta nobody touched after buying stays finished
  Given today is 2026-09-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 1000000.00 COP by 2026-12, opened 2026-08
  And a recorded expense of 1000000.00 COP in category "Tecnologia" linked to the meta "Celular" on 2026-08-20
  Then the meta "Celular" is complete
```

## AC-18 — A meta created for the month in course asks for the whole thing

```gherkin
@backend
Scenario: One month left means the whole amount now
  Given today is 2026-08-10
  And a meta "Celular" of 8000000.00 COP by 2026-08
  Then the meta "Celular" asks 8000000.00 COP this month
```

## AC-19 — The month arrives with nothing bought, and the app says so

```gherkin
@backend
Scenario: A meta whose month has passed unbought is named as waiting
  Given today is 2027-01-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  Then the meta "Celular" is waiting on its purchase
  And the meta "Celular" asks 0.00 COP this month

@backend
Scenario: A meta bought in its month is not waiting
  Given today is 2027-01-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a recorded expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular" on 2026-12-12
  Then no meta is waiting on its purchase

@backend
Scenario: A purchase made after the month completes the meta the same way
  Given today is 2027-01-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user records an expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  Then the meta "Celular" is complete
  And no meta is waiting on its purchase
```

## AC-20 — A meta with no month, or a month already past, is refused

```gherkin
@backend
Scenario: A meta without a month is refused
  Given today is 2026-08-10
  When the user creates a meta "Celular" of 8000000.00 COP with no month
  Then the meta is rejected
  And the user is told a meta needs the month it is wanted by

@backend
Scenario: A month already gone is refused
  Given today is 2026-08-10
  When the user creates a meta "Celular" of 8000000.00 COP by 2026-07
  Then the meta is rejected
  And the user is told there is no way to save into the past

@backend
Scenario: Editing a meta into the past is refused
  Given today is 2026-10-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user sets the meta "Celular" to be wanted by 2026-09
  Then the meta is rejected
  And the meta "Celular" wants 8000000.00 COP by 2026-12

@backend
Scenario: A meta whose month is behind it may still be renewed forward
  Given today is 2027-01-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user sets the meta "Celular" to be wanted by 2027-06
  Then the meta "Celular" wants 8000000.00 COP by 2027-06
```

## AC-21 — An amount of zero or less is refused

```gherkin
@backend
Scenario: A meta of nothing is refused
  Given today is 2026-08-10
  When the user creates a meta "Celular" of 0.00 COP by 2026-12
  Then the meta is rejected
  And the user is told a meta needs an amount above zero

@backend
Scenario: Editing the amount down to nothing is refused
  Given today is 2026-10-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user sets the meta "Celular" to want 0.00 COP
  Then the meta is rejected
  And the meta "Celular" wants 8000000.00 COP by 2026-12

@backend
Scenario: A contribution of nothing is refused
  Given today is 2026-10-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user contributes 0.00 COP to "Celular"
  Then the contribution is rejected
  And the meta "Celular" holds 4800000.00 COP this month
```

## AC-22 — A name already in use is refused

```gherkin
@backend
Scenario: Two metas may not carry the same name
  Given today is 2026-08-10
  And a meta "Celular" of 8000000.00 COP by 2026-12
  When the user creates a meta "Celular" of 3000000.00 COP by 2027-03
  Then the meta is rejected
  And the user is told that name is already held by another meta

@backend
Scenario: A cancelled meta frees its name
  Given today is 2026-10-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And the meta "Celular" was cancelled 2026-10
  When the user creates a meta "Celular" of 3000000.00 COP by 2027-03
  Then the meta "Celular" wants 3000000.00 COP by 2027-03

@backend
Scenario: Restoring a meta whose name has been taken is refused
  Given today is 2026-11-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And the meta "Celular" was cancelled 2026-10
  And a meta "Celular" of 3000000.00 COP by 2027-03, opened 2026-11
  When the user restores the meta cancelled in 2026-10
  Then the restore is rejected
  And the user is told another meta already holds that name
```

## AC-23 — Only an expense can be linked, and only to one meta

```gherkin
@backend
Scenario: Money coming in cannot be pointed at a meta
  Given today is 2026-12-10
  And an income category "Salario"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user records an income of 8000000.00 COP in category "Salario" linked to the meta "Celular"
  Then the movement is rejected
  And the user is told only money going out can be pointed at a meta

@backend
Scenario: Money moving between the owner's own accounts cannot be pointed at a meta
  Given today is 2027-01-15
  And an account "Banco" in COP with balance 20000000.00 COP
  And an account "Visa" in COP with balance 0.00 COP
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user transfers 8000000.00 COP from "Banco" to "Visa" linked to the meta "Celular"
  Then the movement is rejected
  And the user is told a transfer is not a purchase

@backend
Scenario: One expense cannot be pointed at two metas
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a meta "Televisor" of 5000000.00 COP by 2026-12, opened 2026-08
  And a recorded expense of 12000000.00 COP in category "Tecnologia" linked to the meta "Celular" this month
  When the user also points that expense at the meta "Televisor"
  Then the movement is rejected
  And the user is told an expense goes to one meta at a time
```

## AC-24 — A meta in dollars with no rate says so

```gherkin
@backend
Scenario: Without a rate the money available refuses to guess
  Given today is 2026-08-10
  And no TRM has been set
  And a meta "Curso" of 2000.00 USD by 2027-01
  When the user views the money available this month
  Then the user is told to set the TRM
```

## AC-25 — A meta that no longer exists cannot be linked or contributed to

```gherkin
@backend
Scenario: A cancelled meta takes no contribution
  Given today is 2026-10-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And the meta "Celular" was cancelled 2026-10
  When the user contributes 1000000.00 COP to "Celular"
  Then the contribution is rejected

@backend
Scenario: A cancelled meta takes no new link
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And the meta "Celular" was cancelled 2026-10
  When the user records an expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  Then the movement is rejected

@backend
Scenario: Movements already linked keep their link and stay out of the fund
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-12
  And a meta "Televisor" of 5000000.00 COP by 2026-12, opened 2026-08
  And a recorded expense of 5000000.00 COP in category "Tecnologia" linked to the meta "Televisor" this month
  When the user closes the meta "Televisor"
  Then that expense is still linked to the meta "Televisor"
  And the fund on "Tecnologia" spent 0.00 COP this month

@backend
Scenario: A planned payment cannot be pointed at a cancelled meta
  Given today is 2026-08-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And the user cancels the meta "Celular"
  When the user plans an expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  Then the planned payment is rejected
  And the user is told a cancelled meta takes no new link
```

## AC-26 — A meta may be held in dollars

```gherkin
@backend
Scenario: What a dollar meta asks is stated in dollars
  Given today is 2026-08-10
  And the TRM is 4000.00
  And a meta "Curso" of 2000.00 USD by 2027-01
  Then the meta "Curso" asks 333.34 USD this month

@backend
Scenario: Only the peso cost is converted, at the one rate
  Given today is 2026-08-10
  And the TRM is 4000.00
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a meta "Curso" of 2000.00 USD by 2027-01
  When the user views the money available this month
  Then the breakdown shows the metas asking 1333360.00 COP

@backend
Scenario: Changing the rate moves every month's peso cost together
  Given today is 2026-08-10
  And the TRM is 4400.00
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a meta "Curso" of 2000.00 USD by 2027-01
  When the user views the money available this month
  Then the breakdown shows the metas asking 1466696.00 COP

@backend
Scenario: The dollars still arrive whole
  Given today is 2027-01-10
  And the TRM is 4000.00
  And a meta "Curso" of 2000.00 USD by 2027-01, opened 2026-08
  Then the meta "Curso" asks 333.33 USD this month
  And the meta "Curso" holds 2000.00 USD this month
@backend
Scenario: What a dollar meta costs the month is saved in pesos like anything else
  Given today is 2026-08-10
  And the TRM is 4000.00
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a meta "Curso" of 2000.00 USD by 2027-01
  Then the month reports 1333360.00 COP as ahorro
  And consumo, ahorro and libre add up to the income this month
```

## AC-27 — Every figure is derived from the month being read

```gherkin
@backend
Scenario: A past month is answered as that month stood
  Given today is 2026-12-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user views the metas for 2026-09
  Then the meta "Celular" held 3200000.00 COP that month

@backend
Scenario: Cancelling now does not rewrite what a past month reported
  Given today is 2026-12-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And the meta "Celular" was cancelled 2026-12
  When the user views the metas for 2026-09
  Then the meta "Celular" held 3200000.00 COP that month

@backend
Scenario: A change made now does not move a month that came before it
  Given today is 2026-12-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And the user viewed the metas for 2026-09
  When the user contributes 1000000.00 COP to "Celular"
  And the user views the metas for 2026-09
  Then the meta "Celular" held 3200000.00 COP that month
@backend
Scenario: A month the meta ran through still names it after it is closed
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a recorded expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular" this month
  When the user closes the meta "Celular"
  And the user views the metas for 2026-10
  Then the meta "Celular" held 4800000.00 COP that month
```

## AC-28 — The link can be removed or moved

```gherkin
@backend
Scenario: Unlinking gives the purchase back to the category's fund
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-12
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a recorded expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular" this month
  When the user unlinks that expense from its meta
  Then the fund on "Tecnologia" spent 8000000.00 COP this month
  And the meta "Celular" is running

@backend
Scenario: Moving the link recomputes both metas
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a meta "Televisor" of 5000000.00 COP by 2026-12, opened 2026-08
  And a recorded expense of 5000000.00 COP in category "Tecnologia" linked to the meta "Celular" this month
  When the user points that expense at the meta "Televisor" instead
  Then the meta "Televisor" is complete
  And the meta "Celular" is running
```

## AC-29 — A meta is archived and restored, never destroyed

```gherkin
@backend
Scenario: Cancelling archives rather than destroys
  Given today is 2026-10-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user cancels the meta "Celular"
  Then the meta "Celular" is not listed
  And the meta "Celular" can be restored

@backend
Scenario: A restored meta starts again from nothing
  Given today is 2026-11-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And the meta "Celular" was cancelled 2026-10
  When the user restores the meta "Celular"
  Then the meta "Celular" is running
  And the meta "Celular" holds 4000000.00 COP this month
  And the meta "Celular" asks 4000000.00 COP this month

Scenario: An archived meta is not offered when an expense is recorded
  Given a meta "Celular" of 8000000.00 COP by 2026-12 that has been cancelled
  When the owner starts recording an expense
  Then the meta "Celular" is not offered to link
```

## AC-30 — The metas screen says what a meta is

```gherkin
Scenario: The screen carries the same explaining panel every screen carries
  Given the app is open
  When the owner opens the "Metas" screen
  Then the screen offers "¿Cómo funciona esto?"
  And the control sits where every other screen puts it

Scenario: The panel separates the three words
  Given the app is open
  When the owner opens the "Metas" screen
  And the owner opens "¿Cómo funciona esto?"
  Then the panel states that a meta is a named thing with an end, belonging to no category
  And the panel states that a fondo carries a category's leftover money forward
  And the panel states that a presupuesto is a ceiling that resets

Scenario: The empty screen says what a meta is and starts one
  Given there are no metas
  When the owner opens the "Metas" screen
  Then the screen states that a meta is a named thing with an end, belonging to no category
  And the screen offers to create the first one
```

## AC-31 — The money available breaks down into terms that add up

```gherkin
@backend
Scenario: The metas are their own term, never folded into the funds
  Given today is 2026-08-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  And a meta "Celular" of 8000000.00 COP by 2026-12
  When the user views the money available this month
  Then the breakdown shows income of 5000000.00 COP
  And the breakdown shows the funds asking 100000.00 COP
  And the breakdown shows the metas asking 1600000.00 COP
  And the breakdown shows uncovered spending of 0.00 COP
  And the breakdown adds up to the money available
  And the money available this month is 3300000.00 COP
@backend
Scenario: Closing a meta leaves it in the breakdown that still charges it
  Given today is 2026-12-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 30000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a recorded expense of 9600000.00 COP in category "Tecnologia" linked to the meta "Celular" this month
  When the user closes the meta "Celular"
  And the user views the money available this month
  Then the breakdown names the meta "Celular"
  And the breakdown shows the metas asking 1600000.00 COP
  And the breakdown shows uncovered spending of 1600000.00 COP
  And the money available this month is 1800000.00 COP
```

## AC-32 — The assistant names metas when it explains a number, and does nothing else

```gherkin
@backend
Scenario: The assistant's money-available answer names each meta
  Given today is 2026-08-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  And a meta "Celular" of 8000000.00 COP by 2026-12
  When the assistant is asked how much is available this month
  Then the assistant's answer names "Tecnologia"
  And the assistant's answer names "Celular"
  And the assistant's answer states 3300000.00 COP

@backend
Scenario: The assistant has no way to make a meta
  Given today is 2026-08-10
  When the assistant is asked to create a meta
  Then the assistant has no way to do it

@backend
Scenario: The assistant has no way to contribute to one
  Given today is 2026-10-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the assistant is asked to contribute to a meta
  Then the assistant has no way to do it

@backend
Scenario: The assistant does not name a meta that asks nothing
  Given today is 2026-09-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 1000000.00 COP by 2026-12, opened 2026-08
  And a recorded expense of 1000000.00 COP in category "Tecnologia" linked to the meta "Celular" on 2026-08-20
  And the user closes the meta "Celular"
  When the assistant is asked how much is available this month
  Then the assistant's answer does not name "Celular"

@backend
Scenario: The assistant says which meta gave money back, and why
  Given today is 2026-09-10
  And an expense category "Tecnologia"
  And a meta "Moto" of 6000000.00 COP by 2026-12, opened 2026-08
  And a contribution of 2000000.00 COP to "Moto" made 2026-08
  And the user sets the meta "Moto" to want 1000000.00 COP
  When the assistant is asked how much is available this month
  Then the assistant's answer says "Moto" gave back 2200000.00 COP because its amount was lowered
```

## AC-33 — The link changes what the month plans, never what the reports say

```gherkin
@backend
Scenario: The spending report counts the linked purchase in full
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-12
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a recorded expense of 200000.00 COP in category "Tecnologia" this month
  When the user records an expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  And the user views the current month's report
  Then the spending for "Tecnologia" shows 8200000.00 COP
  And the fund on "Tecnologia" spent 200000.00 COP this month

@backend
Scenario: Every category's report adds up to what left the accounts
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And an expense category "Mercado"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a recorded expense of 850000.00 COP in category "Mercado" this month
  When the user records an expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  And the user views the current month's report
  Then the current month's report shows an expense total of 8850000.00 COP
```

## AC-34 — A meta can be told what it already holds

```gherkin
@backend
Scenario: What is already saved lowers what the meta asks
  Given today is 2026-08-10
  When the user creates a meta "Celular" of 8000000.00 COP by 2026-12 stating it already held 3000000.00 COP
  Then the meta "Celular" asks 1000000.00 COP this month
  And the meta "Celular" holds 4000000.00 COP this month

@backend
Scenario: What is already saved costs no month
  Given today is 2026-08-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  When the user creates a meta "Celular" of 8000000.00 COP by 2026-12 stating it already held 3000000.00 COP
  Then the money available this month is 4000000.00 COP

@backend
Scenario: The statement is made for one month and never re-read
  Given today is 2026-10-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 stating it already held 3000000.00 COP
  Then the meta "Celular" holds 6000000.00 COP this month
```

## AC-35 — Deleting the linked movement reopens the meta

```gherkin
@backend
Scenario: Deleting the purchase puts the meta back to running
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a recorded expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular" this month
  When the user deletes that expense
  Then the meta "Celular" is running
  And the meta "Celular" holds 8000000.00 COP this month

@backend
Scenario: The category's fund takes nothing back from a deleted movement
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-12
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a recorded expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular" this month
  When the user deletes that expense
  Then the fund on "Tecnologia" spent 0.00 COP this month
```

## AC-36 — The month's report lists the metas beside the funds, and totals both

```gherkin
@backend
Scenario: The month's report names every meta and what it asks
  Given today is 2026-08-10
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  And a meta "Celular" of 8000000.00 COP by 2026-12
  And a meta "Televisor" of 5000000.00 COP by 2026-12
  When the user views the current month's report
  Then the report lists the meta "Celular" asking 1600000.00 COP
  And the report lists the meta "Televisor" asking 1000000.00 COP
  And the report states the month asks 2700000.00 COP in all

@backend
Scenario: The funds stay listed by category and the metas by meta
  Given today is 2026-08-10
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  And a meta "Celular" of 8000000.00 COP by 2026-12
  When the user views the current month's report
  Then the report lists "Tecnologia" asking 100000.00 COP
  And the report lists the meta "Celular" under the metas, not under a category
@backend
Scenario: The report names a meta closed in the month it reports
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a recorded expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular" this month
  When the user closes the meta "Celular"
  And the user views the current month's report
  Then the report lists the meta "Celular" asking 1600000.00 COP
  And the report states the month asks 1600000.00 COP in all

@backend
Scenario: The report totals what a meta cancelled this month still asked
  Given today is 2026-10-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user cancels the meta "Celular"
  And the user views the current month's report
  Then the report lists the meta "Celular" asking 1600000.00 COP
  And the report states the month asks 1600000.00 COP in all
```

## AC-37 — The month opens into consumo, ahorro and libre, and adds up exactly

```gherkin
@backend
Scenario: A presupuesto is consumo and a fondo that accumulates is ahorro
  Given today is 2026-12-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 30000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Restaurantes"
  And a fund on "Restaurantes" that asks a fixed 600000.00 COP each month, starting 2026-12, resetting
  And an expense category "Mercado"
  And a fund on "Mercado" that asks a fixed 600000.00 COP each month, starting 2026-12
  And an expense category "Regalos"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a meta "Televisor" of 5000000.00 COP by 2026-12, opened 2026-08
  And a recorded expense of 800000.00 COP in category "Regalos" this month
  Then the month reports 1400000.00 COP as consumo
  And the month reports 3200000.00 COP as ahorro
  And the month reports 400000.00 COP as libre

@backend
Scenario: The three terms and the income add up exactly
  Given today is 2026-12-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 30000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Restaurantes"
  And a fund on "Restaurantes" that asks a fixed 600000.00 COP each month, starting 2026-12, resetting
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  Then the month reports 600000.00 COP as consumo
  And the month reports 1600000.00 COP as ahorro
  And the month reports 2800000.00 COP as libre
  And consumo, ahorro and libre add up to the income this month

@backend
Scenario: The share is stated as a percentage of the income
  Given today is 2026-12-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 30000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Mercado"
  And a fund on "Mercado" that asks a fixed 600000.00 COP each month, starting 2026-12
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a meta "Televisor" of 5000000.00 COP by 2026-12, opened 2026-08
  Then the month reports 64 percent of the income as ahorro

@backend
Scenario: A month the owner contributed in still adds up
  Given today is 2026-09-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 30000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user contributes 2000000.00 COP to "Celular"
  Then the month reports 3600000.00 COP as ahorro
  And the month reports 1400000.00 COP as libre
  And consumo, ahorro and libre add up to the income this month

@backend
Scenario: A month a meta was cancelled in still adds up
  Given today is 2026-10-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 30000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user cancels the meta "Celular"
  Then the month reports -3200000.00 COP as ahorro
  And the month reports 8200000.00 COP as libre
  And consumo, ahorro and libre add up to the income this month

@backend
Scenario: Any month can be read, so months can be compared
  Given today is 2026-12-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 30000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user views the month's report for 2026-09
  Then that month reports 1600000.00 COP as ahorro
@backend
Scenario: Closing a meta moves nothing in the month's split
  Given today is 2026-12-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 30000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a recorded expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular" this month
  When the user closes the meta "Celular"
  Then the month reports 1600000.00 COP as ahorro
  And the month reports 3400000.00 COP as libre
  And consumo, ahorro and libre add up to the income this month
```

## AC-38 — Ahorro is what was set aside, never what was left over

```gherkin
@backend
Scenario: The month the purchase happens still reports what was set aside
  Given today is 2026-12-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 30000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Tecnologia"
  And an expense category "Mercado"
  And a fund on "Mercado" that asks a fixed 600000.00 COP each month, starting 2026-12
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a meta "Televisor" of 5000000.00 COP by 2026-12, opened 2026-08
  When the user records an expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  Then the month reports 3200000.00 COP as ahorro
  And the month reports 64 percent of the income as ahorro
  And the month reports 0.00 COP as consumo

@backend
Scenario: A purchase the meta could not cover is consumo for the part it could not
  Given today is 2026-10-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 30000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user records an expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  Then the month reports 3200000.00 COP as consumo
  And the month reports 1600000.00 COP as ahorro
  And the month reports 200000.00 COP as libre
```

## AC-39 — Closing a completed meta releases nothing

```gherkin
@backend
Scenario: Closing after the purchase gives no money back
  Given today is 2027-01-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 30000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a recorded expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular" on 2026-12-12
  When the user closes the meta "Celular"
  Then the money available this month is 5000000.00 COP

@backend
Scenario: A meta that was bought cannot be cancelled for its money back
  Given today is 2027-01-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a recorded expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular" on 2026-12-12
  When the user cancels the meta "Celular"
  Then the cancellation is rejected
  And the user is told a meta that was bought is closed, not cancelled

@backend
Scenario: A meta cannot be closed as of a month before it existed
  Given today is 2026-09-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user closes the meta "Celular" as of 2026-07
  Then the close is rejected
  And the user is told a meta that is still running is cancelled, not closed
```

## AC-40 — The fund no longer saves toward a date

```gherkin
@backend
Scenario: A fund cannot be told to reach an amount by a date
  Given today is 2026-11-10
  And an expense category "Tecnologia"
  When the user creates a fund on "Tecnologia" targeting 2000000.00 COP by 2027-03, starting 2026-11
  Then the fund is rejected
  And the user is told to make a meta instead

@backend
Scenario: The three rules that remain are unchanged
  Given today is 2026-11-10
  And an expense category "Restaurantes"
  And a fund on "Restaurantes" that asks a fixed 200000.00 COP each month, starting 2026-11
  And an expense category "Seguros"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating payment of 447300.00 COP to "SOAT" from "Banco" every 1 year starting on 2027-05-02 in category "Seguros", waiting for approval
  And a fund on "Seguros" funded from its obligations, starting 2026-11
  Then the fund on "Restaurantes" asks 200000.00 COP this month
  And the fund on "Seguros" asks 74550.00 COP this month

Scenario: The create form offers three ways, not four
  Given the app is open
  When the owner starts creating a fund
  Then the form offers a fixed amount
  And the form offers the average of what the category has cost
  And the form offers what the category's obligations need
  And the form does not offer to reach an amount by a date
```

## AC-41 — A category can say that spending in it is saving

```gherkin
@backend
Scenario: Spending in a category marked as saving counts as ahorro
  Given today is 2026-12-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 30000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Inversion" where spending is saving
  And a recorded expense of 1000000.00 COP in category "Inversion" this month
  Then the month reports 1000000.00 COP as ahorro
  And the month reports 0.00 COP as consumo
  And the month reports 4000000.00 COP as libre

@backend
Scenario: The same spending without the mark is consumo
  Given today is 2026-12-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 30000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Inversion"
  And a recorded expense of 1000000.00 COP in category "Inversion" this month
  Then the month reports 1000000.00 COP as consumo
  And the month reports 0.00 COP as ahorro

@backend
Scenario: The mark changes nothing else about the category
  Given today is 2026-12-10
  And an expense category "Inversion" where spending is saving
  And a recorded expense of 1000000.00 COP in category "Inversion" this month
  When the user views the current month's report
  Then the spending for "Inversion" shows 1000000.00 COP

@backend
Scenario: A category is not marked as saving unless the owner says so
  Given today is 2026-12-10
  And an expense category "Restaurantes"
  Then spending in "Restaurantes" is not saving
```

## AC-42 — A contribution is a listed record, and it can be removed

```gherkin
@backend
Scenario: Every contribution is listed on its meta
  Given today is 2026-10-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a contribution of 500000.00 COP to "Celular" made 2026-09
  When the user contributes 300000.00 COP to "Celular"
  Then the meta "Celular" lists a contribution of 500000.00 COP made 2026-09
  And the meta "Celular" lists a contribution of 300000.00 COP made 2026-10

@backend
Scenario: Removing a contribution puts the meta back
  Given today is 2026-09-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a contribution of 2000000.00 COP to "Celular" made 2026-09
  When the user removes that contribution
  Then the meta "Celular" holds 3200000.00 COP this month
  And the meta "Celular" asks 1600000.00 COP this month

@backend
Scenario: Removing a contribution gives its month the money back
  Given today is 2026-09-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a contribution of 2000000.00 COP to "Celular" made 2026-09
  When the user removes that contribution
  Then the money available this month is 3400000.00 COP

@backend
Scenario: Removing a contribution raises the instalments that had dropped
  Given today is 2026-10-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a contribution of 2000000.00 COP to "Celular" made 2026-09
  When the user removes that contribution
  Then the meta "Celular" asks 1600000.00 COP this month
```

## AC-43 — A planned expense is netted against its meta the same way

```gherkin
@backend
Scenario: A planned purchase a full meta covers costs the month nothing
  Given today is 2026-12-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 30000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user plans an expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  And the user views the money available this month
  Then the breakdown shows uncovered spending of 0.00 COP
  And the money available this month is 3400000.00 COP

@backend
Scenario: A planned purchase the meta cannot cover costs the month the gap
  Given today is 2026-10-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 30000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user plans an expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  And the user views the money available this month
  Then the breakdown shows uncovered spending of 3200000.00 COP
  And the money available this month is 200000.00 COP

@backend
Scenario: The meta keeps running until the payment is made
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user plans an expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  Then the meta "Celular" is running

@backend
Scenario: Paying it completes the meta
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a planned expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular" this month
  When the user confirms that payment
  Then the meta "Celular" is complete

@backend
Scenario: Skipping it leaves the meta as it was
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And a planned expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular" this month
  When the user skips that payment
  Then the meta "Celular" is running
  And the meta "Celular" holds 8000000.00 COP this month
@backend
Scenario: A purchase owed but not yet paid leaves the meta asking the month after
  Given today is 2026-10-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 6000000.00 COP by 2026-12, opened 2026-10
  And a planned expense of 6000000.00 COP in category "Tecnologia" linked to the meta "Celular" this month
  When the user views the metas for 2026-11
  Then the meta "Celular" held 4000000.00 COP that month

@backend
Scenario: A purchase a meta filled by hand covers costs the month nothing more
  Given today is 2026-10-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 30000000.00 COP
  And a repeating income of 10000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Tecnologia"
  And a meta "Celular" of 6000000.00 COP by 2026-12, opened 2026-10
  And a contribution of 4000000.00 COP to "Celular" made 2026-10
  When the user records an expense of 6000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  And the user views the money available this month
  Then the breakdown shows uncovered spending of 0.00 COP
  And the money available this month is 4000000.00 COP

@backend
Scenario: A planned purchase a meta filled by hand covers costs the month nothing
  Given today is 2026-10-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 30000000.00 COP
  And a repeating income of 10000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Tecnologia"
  And a meta "Celular" of 6000000.00 COP by 2026-12, opened 2026-10
  And a contribution of 4000000.00 COP to "Celular" made 2026-10
  When the user plans an expense of 6000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  And the user views the money available this month
  Then the breakdown shows uncovered spending of 0.00 COP
  And the money available this month is 4000000.00 COP
```

## AC-44 — The metas list puts what needs an answer first

```gherkin
Scenario: The ones waiting on an answer come first
  Given a meta "Celular" that was completed by its purchase
  And a meta "Viaje" whose month passed with nothing bought
  And a meta "Televisor" running toward diciembre 2027
  And a meta "Camara" running toward marzo 2028
  When the owner opens the "Metas" screen
  Then the screen lists "Celular" and "Viaje" above "Televisor"
  And the screen lists "Televisor" above "Camara"

Scenario: Archived metas are not in the list
  Given a meta "Celular" running toward diciembre 2027
  And a meta "Moto" that has been cancelled
  When the owner opens the "Metas" screen
  Then the screen names "Celular"
  And the screen does not name "Moto"

Scenario: The list reads on a phone without scrolling sideways
  Given a meta "Celular" of 8000000.00 COP by 2026-12 holding 4800000.00 COP and asking 1600000.00 COP
  When the owner opens the "Metas" screen on a phone
  Then the screen states it holds 4800000.00 COP
  And the screen states it asks 1600000.00 COP this month
  And the page does not scroll sideways
```

## AC-45 — The form says what the meta will ask before it is created

```gherkin
@backend
Scenario: What a meta would ask is known before it exists
  Given today is 2026-08-10
  When the user asks what a meta of 8000000.00 COP by 2026-12 would ask
  Then the answer is 1600000.00 COP a month

@backend
Scenario: A meta bigger than the month is announced with its figure
  Given today is 2026-08-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  When the user asks what a meta of 80000000.00 COP by 2026-09 would ask
  Then the user is warned it would ask 40000000.00 COP a month
  And the user is warned that is more than the month has

@backend
Scenario: A dollar meta bigger than the month is announced too
  Given today is 2026-08-10
  And the TRM is 4000.00
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  When the user asks what a meta of 20000.00 USD by 2026-09 would ask
  Then the user is warned it would ask 10000.00 USD a month
  And the user is warned that is more than the month has

@backend
Scenario: The owner may go ahead anyway
  Given today is 2026-08-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And the user was warned a meta of 80000000.00 COP by 2026-09 would ask 40000000.00 COP a month
  When the user creates the meta anyway, naming it "Casa"
  Then the meta "Casa" wants 80000000.00 COP by 2026-09

Scenario: The create button says what it is about to do
  Given the app is open
  When the owner starts creating a meta of 80000000.00 COP by 2026-09
  Then the form states it would ask 40000000.00 COP a month
  And the button offers to create it anyway
```

