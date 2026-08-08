# Acceptance specs — 009 named-goals

Formalizes `acs.md` (38 ACs, approved 2026-08-08) as standard Gherkin.

**Nothing specified here exists.** Migration `0012` dropped `goal`,
`goal_contribution`, `budget` and `transaction.goal_id` on 2026-08-04, and the
app has one noun for planned money — the fund. This is the ATDD red phase in
its pure form.

**Where each AC is observed.** At a surface a person uses — a screen or the
figures a month reports. The assistant is deliberately absent: AC-32 is the
owner's decision that metas ship without it, and its scenarios assert that
absence rather than parity.

**Two streams, per technical ADR-0045.** `acceptance_stream: mixed`. Scenarios
tagged `@backend` are generated as pytest and bind to the services layer —
every figure a month reports. Untagged scenarios bind to vitest, hand-written
against the screen. Nothing here is `@browser`: no scenario turns on width,
overflow or wrapping.

**Dates are absolute**, as in 003 and for the same reason: every meta is month
arithmetic, and "2 months ago" cannot pin $1.600.000 the way a calendar can.
`today is YYYY-MM-DD` sets the scenario clock.

**The running example is the owner's own**, kept from AC discovery so the
figures are ones he has already checked: a *Celular* of $8.000.000 for December
2026, created in August, asking $1.600.000 over five months — August, September,
October, November and December — because the month a meta names is a month it
saves.

Amounts are plain decimals (`8000000.00 COP`), no thousands separators.
Category names are plain rather than the emoji ones production carries,
matching the other suites.

**Order is not pinned.** `the month's report lists …` asserts presence, never
position.

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
Scenario: A meta belongs to no category
  Given today is 2026-08-10
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  And a meta "Celular" of 8000000.00 COP by 2026-12
  Then the fund on "Tecnologia" asks 100000.00 COP this month
  And no meta is listed under "Tecnologia"

@backend
Scenario: A category carries any number of metas without them meeting
  Given today is 2026-08-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12
  And a meta "Televisor" of 5000000.00 COP by 2026-12
  Then the meta "Celular" asks 1600000.00 COP this month
  And the meta "Televisor" asks 1000000.00 COP this month
```

## AC-2 — The month named is a month that saves

```gherkin
@backend
Scenario: The named month is one of the months that save
  Given today is 2026-08-10
  And a meta "Celular" of 8000000.00 COP by 2026-12
  Then the meta "Celular" asks 1600000.00 COP this month

@backend
Scenario: The last month still asks its share
  Given today is 2026-12-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 6400000.00 COP
  Then the meta "Celular" asks 1600000.00 COP this month
  And the meta "Celular" has put by 8000000.00 COP this month

@backend
Scenario: A fund saving toward a charge still stops the month before, unchanged
  Given today is 2026-11-10
  And an expense category "Seguros"
  And a fund on "Seguros" that saves 447300.00 COP by 2027-05, starting 2026-11
  Then the fund on "Seguros" asks 74550.00 COP this month
```

## AC-3 — A meta fills itself, and no month requires an act of saving

```gherkin
@backend
Scenario: Months that pass untouched still advance the meta
  Given today is 2026-10-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  Then the meta "Celular" has put by 4800000.00 COP this month
  And the meta "Celular" asks 1600000.00 COP this month

@backend
Scenario: What is left is spread over the months that remain, rounded up
  Given today is 2026-08-10
  And a meta "Viaje" of 1000000.00 COP by 2026-10
  Then the meta "Viaje" asks 333334.00 COP this month
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
  And the breakdown adds up to the money available
```

## AC-5 — The metas have their own screen

```gherkin
Scenario: The navigation offers Metas beside Fondos y presupuestos
  Given the app is open
  Then the navigation names "Metas" under "Planeación"
  And the navigation still names "Fondos y presupuestos"

Scenario: The metas screen states each meta's amount, month and progress
  Given a meta "Celular" of 8000000.00 COP by 2026-12 with 4800000.00 COP put by
  When the user opens "Metas"
  Then the screen names "Celular"
  And the screen states it wants 8000000.00 COP by diciembre 2026
  And the screen states 4800000.00 COP put by

Scenario: The funds screen never lists a meta
  Given a meta "Celular" of 8000000.00 COP by 2026-12
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month
  When the user opens "Fondos y presupuestos"
  Then the screen names "Tecnologia"
  And the screen does not name "Celular"
```

## AC-6 — The purchase is linked on the movement, once

```gherkin
@backend
Scenario: An expense is pointed at a meta when it is recorded
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 6400000.00 COP
  When the user records an expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  Then the meta "Celular" is complete

@backend
Scenario: An expense pointed at nothing behaves as it does today
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 6400000.00 COP
  When the user records an expense of 200000.00 COP in category "Tecnologia"
  Then the fund on "Tecnologia" reports 200000.00 COP spent this month
  And the meta "Celular" is running
```

## AC-7 — A linked expense leaves the category's fund untouched

```gherkin
@backend
Scenario: The category's fund does not count the linked purchase
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 6400000.00 COP
  When the user records an expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  Then the fund on "Tecnologia" reports 0.00 COP spent this month

@backend
Scenario: A linked purchase does not read as an overspend on its category
  Given today is 2026-12-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 6400000.00 COP
  When the user records an expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  Then the breakdown shows uncovered spending of 0.00 COP
```

## AC-8 — Linking the purchase completes the meta and asks what comes next

```gherkin
@backend
Scenario: The linked purchase completes the meta
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 6400000.00 COP
  When the user records an expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  Then the meta "Celular" is complete
  And the meta "Celular" asks 0.00 COP this month

Scenario: Completing offers three things to do next
  Given a meta "Celular" of 8000000.00 COP by 2026-12 that has just been completed by its purchase
  When the user opens "Metas"
  Then the screen offers to close "Celular"
  And the screen offers to keep "Celular" with a new amount
  And the screen offers to keep "Celular" with a new month
```

## AC-9 — Reaching the amount stops the asking

```gherkin
@backend
Scenario: A meta that has everything it needs asks for nothing
  Given today is 2026-10-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 3200000.00 COP
  When the user contributes 3200000.00 COP to "Celular"
  Then the meta "Celular" has put by 8000000.00 COP this month
  And the meta "Celular" asks 0.00 COP this month

@backend
Scenario: A meta that is whole stops lowering the money available
  Given today is 2026-11-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 8000000.00 COP
  Then the money available this month is 5000000.00 COP
```

## AC-10 — The owner may put in extra, and it costs that month

```gherkin
@backend
Scenario: A contribution raises what the meta holds and lowers what it asks
  Given today is 2026-09-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 1600000.00 COP
  When the user contributes 2000000.00 COP to "Celular"
  Then the meta "Celular" has put by 5200000.00 COP this month
  And the meta "Celular" asks 933334.00 COP this month

@backend
Scenario: A contribution costs the month it is made
  Given today is 2026-09-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 1600000.00 COP
  When the user contributes 2000000.00 COP to "Celular"
  Then the money available this month is 2066666.00 COP

@backend
Scenario: The contribution does not carry into the next month
  Given today is 2026-10-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 1600000.00 COP
  And a contribution of 2000000.00 COP to "Celular" made 2026-09
  Then the money available this month is 4066666.00 COP
```

## AC-11 — A meta can be edited while it runs

```gherkin
@backend
Scenario: Raising the amount recomputes what it asks
  Given today is 2026-10-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 3200000.00 COP
  When the user sets the meta "Celular" to want 9000000.00 COP
  Then the meta "Celular" asks 1400000.00 COP this month

@backend
Scenario: Moving the month recomputes what it asks
  Given today is 2026-10-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 3200000.00 COP
  When the user sets the meta "Celular" to be wanted by 2027-03
  Then the meta "Celular" asks 800000.00 COP this month

@backend
Scenario: Renaming a meta keeps everything it has put by
  Given today is 2026-10-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 3200000.00 COP
  When the user renames the meta "Celular" to "Telefono"
  Then the meta "Telefono" has put by 4800000.00 COP this month
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
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 3200000.00 COP
  When the user records an expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  Then the breakdown shows uncovered spending of 3200000.00 COP
  And the money available this month is -1800000.00 COP

@backend
Scenario: Only the uncovered part leaves the month, never the whole purchase
  Given today is 2026-10-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 3200000.00 COP
  When the user records an expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  Then the breakdown shows uncovered spending of 3200000.00 COP
  And the meta "Celular" is complete
```

## AC-13 — A purchase that cost more than the meta held completes it anyway

```gherkin
@backend
Scenario: The excess leaves the month and the meta closes
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 6400000.00 COP
  When the user records an expense of 9000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  Then the meta "Celular" is complete
  And the breakdown shows uncovered spending of 1000000.00 COP

@backend
Scenario: The meta's amount is not rewritten to the price paid
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 6400000.00 COP
  When the user records an expense of 9000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  Then the meta "Celular" wants 8000000.00 COP by 2026-12
```

## AC-14 — A contribution larger than what is missing is trimmed to fit

```gherkin
@backend
Scenario: Only what is missing is taken
  Given today is 2026-10-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 3200000.00 COP
  When the user contributes 5000000.00 COP to "Celular"
  Then the user is told 3200000.00 COP was put in, which is what was missing
  And the meta "Celular" has put by 8000000.00 COP this month

@backend
Scenario: The rest stays in the month
  Given today is 2026-10-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 3200000.00 COP
  When the user contributes 5000000.00 COP to "Celular"
  Then the money available this month is 1800000.00 COP
```

## AC-15 — Cancelling gives back what was put by, in the month it is cancelled

```gherkin
@backend
Scenario: What the meta held is released into the month it is cancelled
  Given today is 2026-10-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user cancels the meta "Celular"
  Then the money available this month is 9800000.00 COP

@backend
Scenario: A cancelled meta stops asking
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
  Then the meta "Televisor" has put by 3000000.00 COP this month
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
  When the user sets the meta "Celular" to want 4000000.00 COP
  Then the meta "Celular" is complete
  And the money available this month is 5800000.00 COP
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
  Then the breakdown shows the metas asking 2600000.00 COP
  And the money available this month is 2400000.00 COP

@backend
Scenario: A purchase linked to one meta leaves the others alone
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 6400000.00 COP
  And a meta "Televisor" of 5000000.00 COP by 2026-12, opened 2026-08 holding 4000000.00 COP
  When the user records an expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  Then the meta "Celular" is complete
  And the meta "Televisor" is running
  And the meta "Televisor" has put by 5000000.00 COP this month
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
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 8000000.00 COP
  Then the meta "Celular" is waiting on its purchase
  And the meta "Celular" asks 0.00 COP this month

@backend
Scenario: A meta bought in its month is not waiting
  Given today is 2027-01-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 8000000.00 COP
  And a recorded expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular" 1 month ago
  Then no meta is waiting on its purchase
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
Scenario: A contribution of nothing is refused
  Given today is 2026-10-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user contributes 0.00 COP to "Celular"
  Then the contribution is rejected
  And the meta "Celular" has put by 4800000.00 COP this month
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
```

## AC-23 — Only an expense can be linked, and only to one meta

```gherkin
@backend
Scenario: Money coming in cannot be pointed at a meta
  Given today is 2026-12-10
  And an income category "Salario"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 6400000.00 COP
  When the user records an income of 8000000.00 COP in category "Salario" linked to the meta "Celular"
  Then the movement is rejected
  And the user is told only money going out can be pointed at a meta

@backend
Scenario: One expense cannot be pointed at two metas
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 6400000.00 COP
  And a meta "Televisor" of 5000000.00 COP by 2026-12, opened 2026-08 holding 4000000.00 COP
  When the user records an expense of 12000000.00 COP in category "Tecnologia" linked to the metas "Celular" and "Televisor"
  Then the movement is rejected
  And the user is told an expense goes to one meta at a time
```

## AC-24 — A meta in dollars with no rate for the month says so

```gherkin
@backend
Scenario: Without a rate the meta refuses to guess what it asks
  Given today is 2026-08-10
  And no exchange rate is set for this month
  And a meta "Curso" of 2000.00 USD by 2027-01
  When the user views the money available this month
  Then the app says the rate for this month is missing
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
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  And a meta "Televisor" of 5000000.00 COP by 2026-12, opened 2026-08 holding 4000000.00 COP
  And a recorded expense of 5000000.00 COP in category "Tecnologia" linked to the meta "Televisor" this month
  When the user cancels the meta "Televisor"
  Then the fund on "Tecnologia" reports 0.00 COP spent this month
```

## AC-26 — A meta may be held in dollars

```gherkin
@backend
Scenario: What a dollar meta asks is stated in its own currency
  Given today is 2026-08-10
  And the exchange rate this month is 4000.00 COP per USD
  And a meta "Curso" of 2000.00 USD by 2027-01
  Then the meta "Curso" asks 333.34 USD this month

@backend
Scenario: What it costs the month moves with the rate
  Given today is 2026-09-10
  And the exchange rate this month is 4400.00 COP per USD
  And a meta "Curso" of 2000.00 USD by 2027-01, opened 2026-08
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  Then the breakdown shows the metas asking 1466696.00 COP

@backend
Scenario: The dollars still arrive whole
  Given today is 2027-01-10
  And the exchange rate this month is 4400.00 COP per USD
  And a meta "Curso" of 2000.00 USD by 2027-01, opened 2026-08 holding 1666.66 USD
  Then the meta "Curso" asks 333.34 USD this month
  And the meta "Curso" has put by 2000.00 USD this month
```

## AC-27 — Every figure is derived from the month being read

```gherkin
@backend
Scenario: A past month is answered as that month stood
  Given today is 2026-12-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user views the metas for 2026-09
  Then the meta "Celular" had put by 3200000.00 COP that month

@backend
Scenario: Cancelling now does not rewrite what a past month reported
  Given today is 2026-12-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And the meta "Celular" was cancelled 2026-12
  When the user views the metas for 2026-09
  Then the meta "Celular" had put by 3200000.00 COP that month

@backend
Scenario: Asking twice gives the same answer
  Given today is 2026-10-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user views the metas for 2026-09
  And the user views the metas for 2026-09
  Then the meta "Celular" had put by 3200000.00 COP that month
```

## AC-28 — The link can be removed or moved

```gherkin
@backend
Scenario: Unlinking gives the purchase back to the category's fund
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 6400000.00 COP
  And a recorded expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular" this month
  When the user unlinks that expense from its meta
  Then the fund on "Tecnologia" reports 8000000.00 COP spent this month
  And the meta "Celular" is running

@backend
Scenario: Moving the link recomputes both metas
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 6400000.00 COP
  And a meta "Televisor" of 5000000.00 COP by 2026-12, opened 2026-08 holding 4000000.00 COP
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
Scenario: A restored meta asks again
  Given today is 2026-11-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  And the meta "Celular" was cancelled 2026-10
  When the user restores the meta "Celular"
  Then the meta "Celular" is running
  And the meta "Celular" asks 4000000.00 COP this month

Scenario: An archived meta is not offered when an expense is recorded
  Given a meta "Celular" of 8000000.00 COP by 2026-12 that has been cancelled
  When the user records an expense
  Then the meta "Celular" is not offered to link
```

## AC-30 — The metas screen says what a meta is

```gherkin
Scenario: The screen carries the same explaining panel every screen carries
  Given the app is open
  When the user opens "Metas"
  Then the screen offers "¿Cómo funciona esto?"

Scenario: The panel separates the three words
  Given the app is open
  When the user opens "Metas"
  And the user opens "¿Cómo funciona esto?"
  Then the panel says a meta is a named thing with an end, belonging to no category
  And the panel says a fondo carries a category's leftover money forward
  And the panel says a presupuesto is a ceiling that resets

Scenario: The empty screen says what a meta is and starts one
  Given there are no metas
  When the user opens "Metas"
  Then the screen says what a meta is
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
```

## AC-32 — The assistant knows nothing about metas

```gherkin
@backend
Scenario: The assistant has no way to make a meta
  Given today is 2026-08-10
  When the assistant is asked to create a meta
  Then the assistant has no way to do it

@backend
Scenario: The assistant's fund answers never mention metas
  Given today is 2026-08-10
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  And a meta "Celular" of 8000000.00 COP by 2026-12
  When the assistant is asked about the funds
  Then the assistant's answer does not name "Celular"
```

## AC-33 — The link changes what the month plans, never what the reports say

```gherkin
@backend
Scenario: The spending report counts the linked purchase in full
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 6400000.00 COP
  And a recorded expense of 200000.00 COP in category "Tecnologia" this month
  When the user records an expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  Then the spending report for "Tecnologia" this month is 8200000.00 COP
  And the fund on "Tecnologia" reports 200000.00 COP spent this month

@backend
Scenario: Every category's report adds up to what left the accounts
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And an expense category "Mercado"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 6400000.00 COP
  And a recorded expense of 850000.00 COP in category "Mercado" this month
  When the user records an expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  Then the spending report this month totals 8850000.00 COP
```

## AC-34 — A meta can be told what it already holds

```gherkin
@backend
Scenario: What is already saved lowers what the meta asks
  Given today is 2026-08-10
  When the user creates a meta "Celular" of 8000000.00 COP by 2026-12 already holding 3000000.00 COP
  Then the meta "Celular" asks 1000000.00 COP this month
  And the meta "Celular" has put by 3000000.00 COP this month

@backend
Scenario: What is already saved costs no month
  Given today is 2026-08-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 20000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  When the user creates a meta "Celular" of 8000000.00 COP by 2026-12 already holding 3000000.00 COP
  Then the money available this month is 4000000.00 COP

@backend
Scenario: The statement is made for one month and never re-read
  Given today is 2026-10-10
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 already holding 3000000.00 COP
  Then the meta "Celular" has put by 6000000.00 COP this month
```

## AC-35 — Deleting the linked movement reopens the meta

```gherkin
@backend
Scenario: Deleting the purchase puts the meta back to running
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 6400000.00 COP
  And a recorded expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular" this month
  When the user deletes that expense
  Then the meta "Celular" is running
  And the meta "Celular" has put by 8000000.00 COP this month

@backend
Scenario: The category's fund takes nothing back from a deleted movement
  Given today is 2026-12-10
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 6400000.00 COP
  And a recorded expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular" this month
  When the user deletes that expense
  Then the fund on "Tecnologia" reports 0.00 COP spent this month
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
  When the user views the month's report
  Then the report lists the meta "Celular" asking 1600000.00 COP
  And the report lists the meta "Televisor" asking 1000000.00 COP
  And the report states the month asks 2700000.00 COP in all

@backend
Scenario: The funds stay listed by category and the metas by meta
  Given today is 2026-08-10
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  And a meta "Celular" of 8000000.00 COP by 2026-12
  When the user views the month's report
  Then the report lists "Tecnologia" asking 100000.00 COP
  And the report does not list "Tecnologia" asking 1700000.00 COP
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
  And a presupuesto on "Restaurantes" that asks a fixed 600000.00 COP each month, starting 2026-12
  And an expense category "Mercado"
  And a fondo on "Mercado" that asks a fixed 600000.00 COP each month, starting 2026-12
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 6400000.00 COP
  And a meta "Televisor" of 5000000.00 COP by 2026-12, opened 2026-08 holding 4000000.00 COP
  And a recorded expense of 800000.00 COP in category "Regalos" this month
  Then the month reports 1400000.00 COP as consumo
  And the month reports 2700000.00 COP as ahorro
  And the month reports 900000.00 COP as libre

@backend
Scenario: The three terms and the income add up exactly
  Given today is 2026-12-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 30000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Restaurantes"
  And a presupuesto on "Restaurantes" that asks a fixed 600000.00 COP each month, starting 2026-12
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 6400000.00 COP
  Then consumo, ahorro and libre add up to the income this month

@backend
Scenario: The share is stated as a percentage of the income
  Given today is 2026-12-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 30000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And an expense category "Mercado"
  And a fondo on "Mercado" that asks a fixed 600000.00 COP each month, starting 2026-12
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 6400000.00 COP
  And a meta "Televisor" of 5000000.00 COP by 2026-12, opened 2026-08 holding 4000000.00 COP
  Then the month reports 54 percent of the income as ahorro

@backend
Scenario: Any month can be read, so months can be compared
  Given today is 2026-12-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 30000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08
  When the user views the month's report for 2026-09
  Then that month reports 1600000.00 COP as ahorro
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
  And a fondo on "Mercado" that asks a fixed 600000.00 COP each month, starting 2026-12
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 6400000.00 COP
  And a meta "Televisor" of 5000000.00 COP by 2026-12, opened 2026-08 holding 4000000.00 COP
  When the user records an expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular"
  Then the month reports 2700000.00 COP as ahorro
  And the month reports 54 percent of the income as ahorro

@backend
Scenario: A contribution made this month counts as ahorro this month
  Given today is 2026-09-10
  And an income category "Salario"
  And an account "Banco" in COP with balance 30000000.00 COP
  And a repeating income of 5000000.00 COP from "Empresa" into "Banco" every 1 month starting on 2026-01-05 in category "Salario", paying itself
  And a meta "Celular" of 8000000.00 COP by 2026-12, opened 2026-08 holding 1600000.00 COP
  When the user contributes 2000000.00 COP to "Celular"
  Then the month reports 3600000.00 COP as ahorro
```
