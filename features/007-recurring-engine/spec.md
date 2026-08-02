# Acceptance specs — 007 recurring-engine

Formalizes `acs.md` (28 ACs, approved 2026-08-02) as standard Gherkin.
Amounts are plain decimals (`25900.00 COP`), no thousands separators.

**Dates.** Due dates are relative to the day the scenario runs (`starting 21
days ago`, `due in 7 days`) so cadence and catch-up are exercised against a
moving today. The end-of-month clamp is the one exception: AC-8 needs a fixed
calendar, so it uses absolute dates and runs the engine "as if it were" a
given day.

**Declared vs already-declared.** A `Given` obligation was declared *before*
its start date, so nothing about it is pending the user's answer and the
engine may charge it unattended (AC-9). The `When the user declares …` form is
the live declaration path, where dates already behind are offered rather than
charged (AC-12). The two are deliberately different steps.

Ten ACs describe decided target behaviour and are expected RED against current
code (ATDD red phase): AC-6, AC-12, AC-13, AC-17, AC-20, AC-21, AC-22, AC-24,
AC-25 and AC-28. The to-pay queue's own behaviour is pinned by feature 006 and
appears here only where this engine feeds it; read-time COP conversion is
pinned by feature 005.

```gherkin
Feature: Recurring engine with due-driven materialization
```

## AC-1 — Declare a repeating obligation once

```gherkin
Scenario: A declared obligation starts charging on its own
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  When the user declares a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 month starting today, paying itself
  And the daily run happens
  Then "Netflix" has been charged 1 time
  And "Bancolombia" has balance 474100.00 COP

Scenario: A declaration keeps what the user described
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a category "Suscripciones"
  When the user declares a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 month starting today in category "Suscripciones", paying itself
  Then "Netflix" is described as 25900.00 COP every 1 month in category "Suscripciones"

Scenario: Money moving between the user's own accounts cannot repeat
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  When the user tries to declare a repeating transfer of 100000.00 COP from "Bancolombia" every 1 month starting today, paying itself
  Then the declaration is rejected
```

## AC-2 — The engine runs itself

```gherkin
Scenario: One run covers every obligation that fell due
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 month starting today, paying itself
  And a repeating payment of 40000.00 COP to "Claro" from "Bancolombia" every 1 month starting today, paying itself
  When the daily run happens
  Then "Netflix" has been charged 1 time
  And "Claro" has been charged 1 time
  And "Bancolombia" has balance 434100.00 COP

Scenario: Charges appear without the user resolving anything
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 month starting today, paying itself
  When the daily run happens
  Then the turn of "Netflix" due today is recorded as paid
  And nothing about "Netflix" is waiting for the user's answer
```

## AC-3 — An automatic obligation pays itself

```gherkin
Scenario: An automatic charge moves the balance on its due date
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 month starting today, paying itself
  When the daily run happens
  Then "Bancolombia" has balance 474100.00 COP
  And "Netflix" was charged today
  And the turn of "Netflix" due today is recorded as paid

Scenario: An automatic charge is never left waiting for approval
  Given the TRM is 4100.00
  And an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 month starting today, paying itself
  When the daily run happens
  And the user views what is outstanding for the next 7 days
  Then the outstanding list for the next 7 days is empty
```

## AC-4 — A manual obligation asks first

```gherkin
Scenario: A manual charge waits and moves no money
  Given the TRM is 4100.00
  And an account "Bancolombia" in COP with balance 2000000.00 COP
  And a repeating payment of 1800000.00 COP to "Arriendo" from "Bancolombia" every 1 month starting today, waiting for approval
  When the daily run happens
  And the user views what is outstanding for the next 7 days
  Then "Bancolombia" has balance 2000000.00 COP
  And the turn of "Arriendo" due today is waiting for approval
  And the outstanding list shows "Arriendo"

Scenario: The balance moves only once the user resolves it
  Given an account "Bancolombia" in COP with balance 2000000.00 COP
  And a repeating payment of 1800000.00 COP to "Arriendo" from "Bancolombia" every 1 month starting today, waiting for approval
  When the daily run happens
  And the user confirms the payment to "Arriendo"
  Then "Bancolombia" has balance 200000.00 COP
```

## AC-5 — The cadence is every N periods from the start date

```gherkin
Scenario: Every two weeks lands on the right days
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 8000.00 COP to "Gimnasio" from "Bancolombia" every 2 week starting 28 days ago, paying itself
  When the daily run happens
  Then "Gimnasio" has been charged 3 times
  And "Bancolombia" has balance 476000.00 COP

Scenario: The end date is itself a due date
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 8000.00 COP to "Gimnasio" from "Bancolombia" every 1 week starting 14 days ago ending 7 days ago, paying itself
  When the daily run happens
  Then "Gimnasio" has been charged 2 times

Scenario: An obligation with no end date keeps going
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 8000.00 COP to "Gimnasio" from "Bancolombia" every 1 week starting 21 days ago, paying itself
  When the daily run happens
  Then "Gimnasio" has been charged 4 times
```

## AC-6 — Money coming in repeats automatically

```gherkin
Scenario: A repeating income lands on its own and raises the balance
  Given an account "Bancolombia" in COP with balance 100000.00 COP
  And a repeating income of 4500000.00 COP from "Empresa" into "Bancolombia" every 1 month starting today, paying itself
  When the daily run happens
  Then "Bancolombia" has balance 4600000.00 COP

Scenario: An income that waits for approval cannot be declared
  Given an account "Bancolombia" in COP with balance 100000.00 COP
  When the user tries to declare a repeating income of 4500000.00 COP from "Empresa" into "Bancolombia" every 1 month starting today, waiting for approval
  Then the declaration is rejected

Scenario: No expected income is left where nobody can resolve it
  Given the TRM is 4100.00
  And an account "Bancolombia" in COP with balance 100000.00 COP
  And a repeating income of 4500000.00 COP from "Empresa" into "Bancolombia" every 1 month starting today, paying itself
  When the daily run happens
  And the user views what is outstanding for the next 7 days
  Then the outstanding list for the next 7 days is empty
  And nothing about "Empresa" is waiting for the user's answer
```

## AC-7 — The repeating obligations are visible as a list

```gherkin
Scenario: The list states what each obligation costs and how often
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 month starting today, paying itself
  When the user views the repeating obligations
  Then the list shows "Netflix" at 25900.00 COP every 1 month

Scenario: Switched-off obligations are kept out of the live list
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 month starting today, paying itself
  And a repeating payment of 8000.00 COP to "Gimnasio" from "Bancolombia" every 1 month starting today, paying itself
  When the user switches off "Gimnasio"
  And the user views the repeating obligations
  Then the list shows "Netflix"
  And the list does not show "Gimnasio"

Scenario: Switched-off obligations are still reachable
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 8000.00 COP to "Gimnasio" from "Bancolombia" every 1 month starting today, paying itself
  When the user switches off "Gimnasio"
  And the user views the switched-off obligations
  Then the list shows "Gimnasio"
```

## AC-8 — A monthly obligation survives short months

```gherkin
Scenario: A day-31 obligation lands on the last day of February
  Given an account "Bancolombia" in COP with balance 5000000.00 COP
  And a repeating payment of 100000.00 COP to "Hipoteca" from "Bancolombia" every 1 month starting on 2026-01-31, paying itself
  When the daily run happens as if it were 2026-03-31
  Then "Hipoteca" was charged on 2026-01-31
  And "Hipoteca" was charged on 2026-02-28
  And "Hipoteca" was charged on 2026-03-31

Scenario: A leap-day obligation lands on 28 February in common years
  Given an account "Bancolombia" in COP with balance 5000000.00 COP
  And a repeating payment of 100000.00 COP to "Seguro" from "Bancolombia" every 1 year starting on 2024-02-29, paying itself
  When the daily run happens as if it were 2026-03-01
  Then "Seguro" was charged on 2024-02-29
  And "Seguro" was charged on 2025-02-28
  And "Seguro" was charged on 2026-02-28
```

## AC-9 — A machine that was off catches up

```gherkin
Scenario: Days without running are caught up one date at a time
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 8000.00 COP to "Almuerzo" from "Bancolombia" every 1 day starting 3 days ago, paying itself
  When the daily run happens
  Then "Almuerzo" has been charged 4 times
  And "Bancolombia" has balance 468000.00 COP

Scenario: Each caught-up charge keeps its own day
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 8000.00 COP to "Almuerzo" from "Bancolombia" every 1 day starting 3 days ago, paying itself
  When the daily run happens
  Then "Almuerzo" was charged 3 days ago
  And "Almuerzo" was charged today

Scenario: The catch-up does not stop to ask
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 8000.00 COP to "Almuerzo" from "Bancolombia" every 1 day starting 3 days ago, paying itself
  When the daily run happens
  Then nothing about "Almuerzo" is waiting for the user's answer
```

## AC-10 — Running twice in a day changes nothing

```gherkin
Scenario: A second run in the same day creates nothing
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 month starting today, paying itself
  When the daily run happens
  And the daily run happens again
  Then "Netflix" has been charged 1 time
  And "Bancolombia" has balance 474100.00 COP
```

## AC-11 — An obligation that has not started waits

```gherkin
Scenario: Nothing happens before the start date
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 month starting in 3 days, paying itself
  When the daily run happens
  And the daily run happens again
  Then "Netflix" has been charged 0 times
  And "Bancolombia" has balance 500000.00 COP
```

## AC-12 — Dates already passed are offered, never imposed

```gherkin
Scenario: Declaring with a start date already behind offers the passed dates
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  When the user declares a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting 21 days ago, paying itself
  Then the user is offered 4 passed dates for "Netflix"
  And "Netflix" has been charged 0 times
  And "Bancolombia" has balance 500000.00 COP

Scenario: Only the accepted dates become charges
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  When the user declares a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting 21 days ago, paying itself
  And the user accepts 2 of the passed dates for "Netflix"
  Then "Netflix" has been charged 2 times
  And "Bancolombia" has balance 448200.00 COP

Scenario: An accepted date keeps its own real date
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  When the user declares a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting 21 days ago, paying itself
  And the user accepts every passed date for "Netflix"
  Then "Netflix" was charged 21 days ago
  And "Netflix" was charged 7 days ago

Scenario: Declined dates are never charged and never offered again
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  When the user declares a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting 21 days ago, paying itself
  And the user declines every passed date for "Netflix"
  And the daily run happens
  Then "Netflix" has been charged 0 times
  And "Bancolombia" has balance 500000.00 COP
  And the user is offered 0 passed dates for "Netflix"

Scenario: Declining every date leaves the obligation live from its next date
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  When the user declares a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting 21 days ago, paying itself
  And the user declines every passed date for "Netflix"
  And the daily run happens as if it were in 7 days
  Then "Netflix" has been charged 1 time

Scenario: Moving the start date back offers the dates it opens
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting today, paying itself
  When the daily run happens
  And the user moves the start of "Netflix" back to 21 days ago
  Then the user is offered 3 passed dates for "Netflix"
  And "Netflix" has been charged 1 time
```

## AC-13 — An obligation that has ended switches itself off

```gherkin
Scenario: An obligation past its end date leaves the live list
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 8000.00 COP to "Gimnasio" from "Bancolombia" every 1 week starting 14 days ago ending 7 days ago, paying itself
  When the daily run happens
  And the user views the repeating obligations
  Then "Gimnasio" is switched off
  And the list does not show "Gimnasio"

Scenario: Extending the end date brings it back
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 8000.00 COP to "Gimnasio" from "Bancolombia" every 1 week starting 14 days ago ending 7 days ago, paying itself
  When the daily run happens
  And the user extends the end of "Gimnasio" to in 14 days
  Then "Gimnasio" is live
```

## AC-14 — Editing changes only what has not happened yet

```gherkin
Scenario: Raising the amount leaves earlier charges alone
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting 7 days ago, paying itself
  When the daily run happens
  And the user changes the amount of "Netflix" to 31900.00 COP
  And the daily run happens as if it were in 7 days
  Then "Netflix" was charged 25900.00 COP 7 days ago
  And "Netflix" was charged 31900.00 COP in 7 days

Scenario: Editing never re-dates or removes an existing charge
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting 7 days ago, paying itself
  When the daily run happens
  And the user changes the amount of "Netflix" to 31900.00 COP
  Then "Netflix" has been charged 2 times
  And "Netflix" was charged 25900.00 COP 7 days ago
```

## AC-15 — Skipping one date leaves the rest alone

```gherkin
Scenario: A skipped date charges nothing and the others continue
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting today, paying itself
  When the user skips the turn of "Netflix" due in 7 days
  And the daily run happens as if it were in 14 days
  Then "Netflix" has been charged 2 times
  And the turn of "Netflix" due in 7 days is skipped

Scenario: A skipped date is not raised again by a later run
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting today, paying itself
  When the user skips the turn of "Netflix" due in 7 days
  And the daily run happens as if it were in 14 days
  And the daily run happens as if it were in 14 days
  Then "Netflix" has been charged 2 times

Scenario: Skipping a date moves no money
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting today, paying itself
  When the user skips the turn of "Netflix" due in 7 days
  Then "Bancolombia" has balance 500000.00 COP
```

## AC-16 — Pausing keeps what already happened

```gherkin
Scenario: Switching off leaves earlier charges untouched
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting 7 days ago, paying itself
  When the daily run happens
  And the user switches off "Netflix"
  And the daily run happens as if it were in 7 days
  Then "Netflix" has been charged 2 times
  And "Bancolombia" has balance 448200.00 COP

Scenario: Switching off something already off changes nothing
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting today, paying itself
  When the user switches off "Netflix"
  And the user switches off "Netflix"
  Then "Netflix" is switched off
```

## AC-17 — Resuming picks up from today

```gherkin
Scenario: The paused stretch is not charged on resuming
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 8000.00 COP to "Gimnasio" from "Bancolombia" every 1 week starting 21 days ago, paying itself
  When the daily run happens as if it were 21 days ago
  And the user switches off "Gimnasio"
  And the user switches "Gimnasio" back on
  And the daily run happens
  Then "Gimnasio" has been charged 2 times
  And "Bancolombia" has balance 484000.00 COP

Scenario: The obligation carries on normally after resuming
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 8000.00 COP to "Gimnasio" from "Bancolombia" every 1 week starting 21 days ago, paying itself
  When the daily run happens as if it were 21 days ago
  And the user switches off "Gimnasio"
  And the user switches "Gimnasio" back on
  And the daily run happens as if it were in 7 days
  Then "Gimnasio" has been charged 3 times
```

## AC-18 — An impossible obligation is refused

```gherkin
Scenario Outline: A declaration that cannot hold is refused
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And an archived account "Vieja" in COP
  And a category "Suscripciones"
  And an archived category "Obsoleta"
  When the user tries to declare a repeating payment of <amount> <currency> to "Netflix" from "<account>" every <count> <unit> starting today in category "<category>", paying itself
  Then the declaration is rejected
  And "Bancolombia" has balance 500000.00 COP

  Examples:
    | amount    | currency | account     | count | unit  | category      |
    | 0.00      | COP      | Bancolombia | 1     | month | Suscripciones |
    | -25900.00 | COP      | Bancolombia | 1     | month | Suscripciones |
    | 25900.00  | XYZ      | Bancolombia | 1     | month | Suscripciones |
    | 25900.00  | USD      | Bancolombia | 1     | month | Suscripciones |
    | 25900.00  | COP      | Vieja       | 1     | month | Suscripciones |
    | 25900.00  | COP      | Fantasma    | 1     | month | Suscripciones |
    | 25900.00  | COP      | Bancolombia | 0     | month | Suscripciones |
    | 25900.00  | COP      | Bancolombia | 1     | month | Obsoleta      |

Scenario: An end date before the start is refused
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  When the user tries to declare a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting today ending 7 days ago, paying itself
  Then the declaration is rejected

Scenario: The same rules hold when editing
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting today, paying itself
  When the user tries to change the amount of "Netflix" to 0.00 COP
  Then the change to "Netflix" is rejected
  And "Netflix" is described as 25900.00 COP every 1 week
```

## AC-19 — What an obligation is cannot be changed

```gherkin
Scenario: The kind of movement cannot change
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 month starting today, paying itself
  When the user tries to turn "Netflix" into an income
  Then the change to "Netflix" is rejected

Scenario: The currency cannot change
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 month starting today, paying itself
  When the user tries to change the currency of "Netflix" to USD
  Then the change to "Netflix" is rejected
```

## AC-20 — A date already charged cannot be skipped

```gherkin
Scenario: Skipping a date whose money already moved is refused
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting today, paying itself
  When the daily run happens
  And the user tries to skip the turn of "Netflix" due today
  Then the skip is rejected
  And the user is told that date was already charged

Scenario: The refusal leaves the money and the record as they were
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting today, paying itself
  When the daily run happens
  And the user tries to skip the turn of "Netflix" due today
  Then the skip is rejected
  And "Bancolombia" has balance 474100.00 COP
  And the turn of "Netflix" due today is recorded as paid
```

## AC-21 — Only real due dates can be skipped

```gherkin
Scenario: A date the obligation never falls on cannot be skipped
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting today, paying itself
  When the user tries to skip the turn of "Netflix" due in 3 days
  Then the skip is rejected

Scenario: The refusal records nothing
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting today, paying itself
  When the user tries to skip the turn of "Netflix" due in 3 days
  And the daily run happens as if it were in 7 days
  Then the skip is rejected
  And "Netflix" has been charged 2 times
```

## AC-22 — An account retired later stops the charges

```gherkin
Scenario: An obligation on a retired account stops charging
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting today, paying itself
  When the account "Bancolombia" is retired
  And the daily run happens
  Then "Netflix" has been charged 0 times
  And "Bancolombia" has balance 500000.00 COP
  And the daily run reports "Netflix" as needing attention

Scenario: Pointing it at a live account resumes it
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And an account "Nequi" in COP with balance 300000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting today, paying itself
  When the account "Bancolombia" is retired
  And the daily run happens
  And the user moves "Netflix" to the account "Nequi"
  And the daily run happens again
  Then "Netflix" has been charged 1 time
  And "Nequi" has balance 274100.00 COP
```

## AC-23 — The same date is never charged twice

```gherkin
Scenario: Overlapping runs never double a date
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting today, paying itself
  When the daily run happens
  And the daily run happens again
  And the daily run happens as if it were today
  Then "Netflix" has been charged 1 time
  And "Bancolombia" has balance 474100.00 COP

Scenario: An edit between runs does not raise a charged date again
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting today, paying itself
  When the daily run happens
  And the user changes the amount of "Netflix" to 31900.00 COP
  And the daily run happens again
  Then "Netflix" has been charged 1 time
  And "Bancolombia" has balance 474100.00 COP

Scenario: Resuming after a pause does not double a charged date
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting today, paying itself
  When the daily run happens
  And the user switches off "Netflix"
  And the user switches "Netflix" back on
  And the daily run happens again
  Then "Netflix" has been charged 1 time
```

## AC-24 — One broken obligation does not cost the day

```gherkin
Scenario: The healthy obligations still land
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And an account "Nequi" in COP with balance 200000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting today, paying itself
  And a repeating payment of 40000.00 COP to "Claro" from "Bancolombia" every 1 week starting today, paying itself
  And a repeating payment of 15000.00 COP to "Spotify" from "Nequi" every 1 week starting today, paying itself
  When the account "Nequi" is retired
  And the daily run happens
  Then "Netflix" has been charged 1 time
  And "Claro" has been charged 1 time
  And "Spotify" has been charged 0 times
  And "Bancolombia" has balance 434100.00 COP

Scenario: The failure is reported naming the obligation
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And an account "Nequi" in COP with balance 200000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting today, paying itself
  And a repeating payment of 15000.00 COP to "Spotify" from "Nequi" every 1 week starting today, paying itself
  When the account "Nequi" is retired
  And the daily run happens
  Then the daily run reports "Spotify" as needing attention
  And the daily run does not report "Netflix" as needing attention

Scenario: The broken one is picked up once it is fixed
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And an account "Nequi" in COP with balance 200000.00 COP
  And a repeating payment of 15000.00 COP to "Spotify" from "Nequi" every 1 week starting today, paying itself
  When the account "Nequi" is retired
  And the daily run happens
  And the account "Nequi" is brought back
  And the daily run happens again
  Then "Spotify" has been charged 1 time
  And "Nequi" has balance 185000.00 COP
```

## AC-25 — Every charge says where it came from

```gherkin
Scenario: An automatic charge is recognisable in the movements list
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 month starting today, paying itself
  When the daily run happens
  Then the movements list shows the charge to "Netflix" as made by the engine
  And that movement names "Netflix" as the obligation behind it

Scenario: A manual charge carries the same mark
  Given an account "Bancolombia" in COP with balance 2000000.00 COP
  And a repeating payment of 1800000.00 COP to "Arriendo" from "Bancolombia" every 1 month starting today, waiting for approval
  When the daily run happens
  Then the movements list shows the charge to "Arriendo" as made by the engine

Scenario: A movement the user entered by hand is not marked as the engine's
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  When the user registers an expense of 30000.00 COP from "Bancolombia" to "Tienda"
  Then the movements list shows the charge to "Tienda" as entered by hand
```

## AC-26 — Everything works by conversation too

```gherkin
Scenario: The assistant can declare an obligation
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  When the assistant declares a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 month starting today, paying itself
  And the daily run happens
  Then "Netflix" has been charged 1 time

Scenario: The assistant reports the same obligations the screen shows
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 month starting today, paying itself
  When the assistant is asked about the repeating obligations
  Then the assistant's answer names "Netflix"
  And the assistant's answer shows 25900.00 COP for "Netflix"

Scenario: The assistant is offered the passed dates rather than defaulting
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  When the assistant declares a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting 21 days ago, paying itself
  Then the user is offered 4 passed dates for "Netflix"
  And "Netflix" has been charged 0 times
```

## AC-27 — Undoing a skip returns the date to pending

```gherkin
Scenario: Undoing a skip brings the obligation's date back to pending
  Given the TRM is 4100.00
  And an account "Bancolombia" in COP with balance 2000000.00 COP
  And a repeating payment of 1800000.00 COP to "Arriendo" from "Bancolombia" every 1 month starting today, waiting for approval
  When the daily run happens
  And the user skips the payment to "Arriendo"
  And the user restores the skipped payment to "Arriendo"
  Then the turn of "Arriendo" due today is waiting for approval
  And "Bancolombia" has balance 2000000.00 COP

Scenario: The restored date is not charged a second time by a later run
  Given an account "Bancolombia" in COP with balance 2000000.00 COP
  And a repeating payment of 1800000.00 COP to "Arriendo" from "Bancolombia" every 1 month starting today, waiting for approval
  When the daily run happens
  And the user skips the payment to "Arriendo"
  And the user restores the skipped payment to "Arriendo"
  And the daily run happens again
  Then "Arriendo" has been charged 1 time
```

## AC-28 — Deleting a charge the engine made closes that date

```gherkin
Scenario: Deleting the charge returns the money and closes the date
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting today, paying itself
  When the daily run happens
  And the user deletes the charge to "Netflix" from today
  Then "Bancolombia" has balance 500000.00 COP
  And the turn of "Netflix" due today is skipped

Scenario: A later run does not charge the deleted date again
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting today, paying itself
  When the daily run happens
  And the user deletes the charge to "Netflix" from today
  And the daily run happens again
  Then "Netflix" has been charged 0 times
  And "Bancolombia" has balance 500000.00 COP

Scenario: The following dates are unaffected
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a repeating payment of 25900.00 COP to "Netflix" from "Bancolombia" every 1 week starting today, paying itself
  When the daily run happens
  And the user deletes the charge to "Netflix" from today
  And the daily run happens as if it were in 7 days
  Then "Netflix" has been charged 1 time
  And "Netflix" was charged in 7 days
```
