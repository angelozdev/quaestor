# Acceptance specs — 006 planned-payments-to-pay

Formalizes `acs.md` (24 ACs, approved 2026-08-01) as standard Gherkin.
Amounts are plain decimals (`85000.00 COP`), no thousands separators. Due
dates are relative to the day the scenario runs, so the overdue/upcoming
boundary is asserted against a moving today rather than a frozen calendar.

Read-time COP conversion is pinned by feature 005's suite and transfer-pair
mechanics by feature 002's; here they appear only where this feature adds
behaviour on top. AC-8 (restoring a skipped payment) and AC-15 (incomes
leaving the queue) describe decided target behaviour and are expected RED
against current code (ATDD red phase).

Amended 2026-08-03 by feature 008: every action that files money under a
category now names it, because a payment can no longer be planned without one.
A `Given` planned payment is filed under a category the scenario does not name
— the category exists, it is just irrelevant to the queue behaviour it pins.
An untyped `a category "X"` is an expense category.

```gherkin
Feature: Planned payments and the to-pay confirmation queue
```

## AC-1 — Plan a one-off payment

```gherkin
Scenario: Planning a payment leaves the balance untouched
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a category "Carro"
  When the user plans a payment of 300000.00 COP to "Taller" from "Bancolombia" due in 19 days in category "Carro"
  Then "Bancolombia" has balance 500000.00 COP
  And the outstanding list for the next 30 days shows "Taller" as upcoming

Scenario: A planned payment keeps its descriptive details
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a category "Carro"
  When the user plans a payment of 300000.00 COP to "Taller" from "Bancolombia" due in 19 days in category "Carro" with notes "cambio de aceite"
  Then viewing the planned payment to "Taller" shows category "Carro" and notes "cambio de aceite"

Scenario: Planning works before any exchange rate exists
  Given no TRM has been set
  And an account "Bancolombia" in COP with balance 500000.00 COP
  And a category "Servicios"
  When the user plans a payment of 85000.00 COP to "Claro" from "Bancolombia" due in 3 days in category "Servicios"
  Then the payment to "Claro" is waiting to be resolved
```

## AC-2 — The queue separates overdue from upcoming

```gherkin
Scenario: What already fell due and what has not are told apart
  Given the TRM is 4100.00
  And an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 85000.00 COP to "Claro" from "Bancolombia" that fell due 4 days ago
  And a planned payment of 45000.00 COP to "Netflix" from "Bancolombia" due in 4 days
  When the user views what is outstanding for the next 7 days
  Then the outstanding list shows "Claro" as overdue
  And the outstanding list shows "Netflix" as upcoming

Scenario: Each group is ordered earliest first
  Given the TRM is 4100.00
  And an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 30000.00 COP to "Tigo" from "Bancolombia" due in 6 days
  And a planned payment of 45000.00 COP to "Netflix" from "Bancolombia" due in 2 days
  When the user views what is outstanding for the next 7 days
  Then the outstanding list shows "Netflix" above "Tigo"

Scenario: A payment belongs to one group only
  Given the TRM is 4100.00
  And an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 85000.00 COP to "Claro" from "Bancolombia" that fell due 4 days ago
  When the user views what is outstanding for the next 7 days
  Then the outstanding list shows "Claro" exactly once
```

## AC-3 — Overdue stays visible until it is resolved

```gherkin
Scenario: A payment overdue from long ago still surfaces in a future period
  Given the TRM is 4100.00
  And an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 85000.00 COP to "Tigo" from "Bancolombia" that fell due 35 days ago
  When the user views what is outstanding for the 5 days starting 5 days from now
  Then the outstanding list shows "Tigo" as overdue

Scenario: Confirming is what removes an overdue payment from view
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 85000.00 COP to "Tigo" from "Bancolombia" that fell due 35 days ago
  When the user confirms the payment to "Tigo"
  Then the outstanding list for the next 7 days does not show "Tigo"

Scenario: Skipping is the other way an overdue payment leaves the view
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 85000.00 COP to "Tigo" from "Bancolombia" that fell due 35 days ago
  When the user skips the payment to "Tigo"
  Then the outstanding list for the next 7 days does not show "Tigo"
```

## AC-4 — One single total in pesos

```gherkin
Scenario: The total covers both groups at today's rate
  Given the TRM is 4100.00
  And an account "Bancolombia" in COP with balance 500000.00 COP
  And an account "Amex" in USD
  And a planned payment of 85000.00 COP to "Claro" from "Bancolombia" that fell due 2 days ago
  And a planned payment of 1000.00 USD to "SaaS" from "Amex" due in 3 days
  When the user views what is outstanding for the next 7 days
  Then the outstanding total is 4185000.00 COP

Scenario: Amounts already in pesos count at face value
  Given the TRM is 4100.00
  And an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 85000.00 COP to "Claro" from "Bancolombia" due in 3 days
  When the user views what is outstanding for the next 7 days
  Then the outstanding total is 85000.00 COP
```

## AC-5 — Confirming a payment moves the balance

```gherkin
Scenario: Confirming turns what was owed into a real movement
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 80000.00 COP to "Enel" from "Bancolombia" due in 2 days
  When the user confirms the payment to "Enel"
  Then "Bancolombia" has balance 420000.00 COP
  And the outstanding list for the next 7 days does not show "Enel"

Scenario: The real amount can differ from what was planned
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 80000.00 COP to "Enel" from "Bancolombia" due in 2 days
  When the user confirms the payment to "Enel" for 95000.00 COP
  Then "Bancolombia" has balance 405000.00 COP
  And the payment to "Enel" counts as spent for 95000.00 COP

Scenario: The real date can differ from what was planned
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 80000.00 COP to "Enel" from "Bancolombia" due in 2 days
  When the user confirms the payment to "Enel" dated 3 days ago
  Then the payment to "Enel" is recorded 3 days ago
```

## AC-6 — Confirming a planned transfer creates both sides

```gherkin
Scenario: Confirming a proposed savings contribution moves both accounts
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  And an account "Ahorros" in COP with balance 0.00 COP
  And "Bancolombia" is the account transfers come from
  And a proposed savings contribution of 100000.00 COP into "Ahorros"
  When the user confirms the transfer into "Ahorros"
  Then "Bancolombia" has balance 900000.00 COP
  And "Ahorros" has balance 100000.00 COP
  And the transfer into "Ahorros" is recorded as one movement out and one movement in

Scenario: The resulting transfer deletes as a pair
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  And an account "Ahorros" in COP with balance 0.00 COP
  And "Bancolombia" is the account transfers come from
  And a proposed savings contribution of 100000.00 COP into "Ahorros"
  And the user confirms the transfer into "Ahorros"
  When the user deletes the transfer into "Ahorros"
  Then "Bancolombia" has balance 1000000.00 COP
  And "Ahorros" has balance 0.00 COP
```

## AC-7 — Skipping removes a payment without touching money

```gherkin
Scenario: Skipping cancels without moving money
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 60000.00 COP to "Gimnasio" from "Bancolombia" due in 3 days
  When the user skips the payment to "Gimnasio"
  Then "Bancolombia" has balance 500000.00 COP
  And the outstanding list for the next 7 days does not show "Gimnasio"
  And nothing is recorded as spent for "Gimnasio"

Scenario: Skipping one month of an obligation leaves the obligation alive
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a monthly obligation of 50000.00 COP to "Acueducto" from "Bancolombia" that the user approves by hand, already due
  When the user skips the payment to "Acueducto"
  Then this month's turn of the obligation to "Acueducto" is marked skipped
  And the obligation to "Acueducto" is still active
```

## AC-8 — A skip can be undone

```gherkin
Scenario: A payment skipped by mistake returns to the queue
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 85000.00 COP to "Claro" from "Bancolombia" due in 3 days
  And the user skips the payment to "Claro"
  When the user restores the skipped payment to "Claro"
  Then the outstanding list for the next 7 days shows "Claro" as upcoming
  And the restored payment to "Claro" is for 85000.00 COP due in 3 days

Scenario: Restoring a skip moves no money
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 85000.00 COP to "Claro" from "Bancolombia" due in 3 days
  And the user skips the payment to "Claro"
  When the user restores the skipped payment to "Claro"
  Then "Bancolombia" has balance 500000.00 COP

Scenario: A restored payment can then be confirmed like any other
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 85000.00 COP to "Claro" from "Bancolombia" due in 3 days
  And the user skips the payment to "Claro"
  And the user restores the skipped payment to "Claro"
  When the user confirms the payment to "Claro"
  Then "Bancolombia" has balance 415000.00 COP
```

## AC-9 — One queue for every kind of obligation

```gherkin
Scenario: Three kinds of obligation share one list
  Given the TRM is 4100.00
  And an account "Bancolombia" in COP with balance 1000000.00 COP
  And an account "Ahorros" in COP with balance 0.00 COP
  And "Bancolombia" is the account transfers come from
  And a planned payment of 300000.00 COP to "Taller" from "Bancolombia" due in 3 days
  And a monthly obligation of 50000.00 COP to "Acueducto" from "Bancolombia" that the user approves by hand, already due
  And a proposed savings contribution of 200000.00 COP into "Ahorros"
  When the user views what is outstanding for the next 7 days
  Then the outstanding list shows "Taller"
  And the outstanding list shows "Acueducto"
  And the outstanding list shows the proposed savings contribution

Scenario: A monthly obligation is resolved with the same action as a one-off
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a monthly obligation of 50000.00 COP to "Acueducto" from "Bancolombia" that the user approves by hand, already due
  When the user confirms the payment to "Acueducto"
  Then "Bancolombia" has balance 450000.00 COP
```

## AC-10 — Resolving a recurring obligation keeps it in step

```gherkin
Scenario: Confirming settles this month's turn of the obligation
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a monthly obligation of 50000.00 COP to "Acueducto" from "Bancolombia" that the user approves by hand, already due
  When the user confirms the payment to "Acueducto"
  Then this month's turn of the obligation to "Acueducto" is settled

Scenario: A settled turn is not raised again
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a monthly obligation of 50000.00 COP to "Acueducto" from "Bancolombia" that the user approves by hand, already due
  And the user confirms the payment to "Acueducto"
  When the obligations that have come due are raised again
  Then the outstanding list for the next 7 days does not show "Acueducto"
```

## AC-11 — What falls due today counts as upcoming

```gherkin
Scenario: A payment due today is upcoming
  Given the TRM is 4100.00
  And an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 45000.00 COP to "Netflix" from "Bancolombia" due today
  When the user views what is outstanding for the next 7 days
  Then the outstanding list shows "Netflix" as upcoming

Scenario: A payment due yesterday is overdue
  Given the TRM is 4100.00
  And an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 45000.00 COP to "Netflix" from "Bancolombia" that fell due 1 days ago
  When the user views what is outstanding for the next 7 days
  Then the outstanding list shows "Netflix" as overdue
```

## AC-12 — The period caps both groups

```gherkin
Scenario: Nothing due after the period appears
  Given the TRM is 4100.00
  And an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 900000.00 COP to "Arriendo" from "Bancolombia" due in 9 days
  When the user views what is outstanding for the next 3 days
  Then the outstanding list is empty

Scenario: Widening the period brings it into view
  Given the TRM is 4100.00
  And an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 900000.00 COP to "Arriendo" from "Bancolombia" due in 9 days
  When the user views what is outstanding for the next 30 days
  Then the outstanding list shows "Arriendo" as upcoming
```

## AC-13 — The retrospective view carries no overdue

```gherkin
Scenario: A past month's account of what was pending excludes older debts
  Given the TRM is 4100.00
  And an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 100000.00 COP to "Deuda vieja" from "Bancolombia" that fell due in a month before last
  When the user views the report for last month
  Then the report for last month reports nothing pending

Scenario: The same payment is still visible in the outstanding list
  Given the TRM is 4100.00
  And an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 100000.00 COP to "Deuda vieja" from "Bancolombia" that fell due in a month before last
  When the user views what is outstanding for the next 7 days
  Then the outstanding list shows "Deuda vieja" as overdue
```

## AC-14 — An empty queue says so

```gherkin
Scenario: Nothing outstanding is stated plainly
  Given the TRM is 4100.00
  And an account "Bancolombia" in COP with balance 500000.00 COP
  When the user views what is outstanding for the next 7 days
  Then the outstanding list is empty
  And the outstanding total is 0.00 COP

Scenario: A group with no items is left out entirely
  Given the TRM is 4100.00
  And an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 45000.00 COP to "Netflix" from "Bancolombia" due in 3 days
  When the user views what is outstanding for the next 7 days
  Then the outstanding list has no overdue group

Scenario: The assistant says there is nothing outstanding
  Given the TRM is 4100.00
  And an account "Bancolombia" in COP with balance 500000.00 COP
  When the assistant is asked what is outstanding for the next 7 days
  Then the assistant's answer says nothing is outstanding
```

## AC-15 — The queue shows only what is owed

```gherkin
Scenario: Expected incoming money stays out of the outstanding list
  Given the TRM is 4100.00
  And an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned income of 5000000.00 COP into "Bancolombia" due in 3 days
  And a planned payment of 85000.00 COP to "Claro" from "Bancolombia" due in 4 days
  When the user views what is outstanding for the next 7 days
  Then the outstanding list shows "Claro" as upcoming
  And the outstanding list has exactly 1 item
  And the outstanding total is 85000.00 COP

Scenario: Money that was expected to come in and has not stays out too
  Given the TRM is 4100.00
  And an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned income of 5000000.00 COP into "Bancolombia" that fell due 3 days ago
  When the user views what is outstanding for the next 7 days
  Then the outstanding list is empty
  And the outstanding total is 0.00 COP
```

## AC-16 — An impossible period is rejected

```gherkin
Scenario: A period that ends before it starts is refused
  Given the TRM is 4100.00
  And an account "Bancolombia" in COP with balance 500000.00 COP
  When the user tries to view what is outstanding for a period that ends before it starts
  Then the request is rejected as an impossible period
```

## AC-17 — Planning rejects impossible data

```gherkin
Scenario Outline: Impossible amounts are refused
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a category "Servicios"
  When the user tries to plan a payment of <amount> COP to "Claro" from "Bancolombia" due in 3 days in category "Servicios"
  Then the plan is rejected
  And the outstanding list for the next 7 days is empty

  Examples:
    | amount   |
    | 0.00     |
    | -5000.00 |

Scenario: A payment cannot be planned against an account that does not exist
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a category "Servicios"
  When the user tries to plan a payment of 85000.00 COP to "Claro" from "Cuenta fantasma" due in 3 days in category "Servicios"
  Then the plan is rejected

Scenario: A payment cannot be planned against an archived account
  Given an archived account "Vieja" in COP
  And a category "Servicios"
  When the user tries to plan a payment of 85000.00 COP to "Claro" from "Vieja" due in 3 days in category "Servicios"
  Then the plan is rejected

Scenario: A payment cannot be planned in a currency the account does not hold
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a category "Servicios"
  When the user tries to plan a payment of 1000.00 USD to "SaaS" from "Bancolombia" due in 3 days in category "Servicios"
  Then the plan is rejected

Scenario: A payment cannot be planned under an archived category
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And an archived category "Suscripciones"
  When the user tries to plan a payment of 85000.00 COP to "Claro" from "Bancolombia" due in 3 days in category "Suscripciones"
  Then the plan is rejected
```

## AC-18 — What is no longer pending cannot be resolved again

```gherkin
Scenario: Confirming twice is refused and the balance moves once
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 85000.00 COP to "Claro" from "Bancolombia" due in 3 days
  And the user confirms the payment to "Claro"
  When the user tries to confirm the payment to "Claro" again
  Then the user is told it is no longer pending
  And "Bancolombia" has balance 415000.00 COP

Scenario: Skipping something already confirmed is refused
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 85000.00 COP to "Claro" from "Bancolombia" due in 3 days
  And the user confirms the payment to "Claro"
  When the user tries to skip the payment to "Claro"
  Then the user is told it is no longer pending

Scenario: Confirming something that was never owed is refused
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a recorded expense of 50000.00 COP tagged "mercado"
  When the user tries to confirm that recorded expense
  Then the user is told it is no longer pending
```

## AC-19 — A transfer that cannot complete is refused whole

```gherkin
Scenario: Without an account for transfers to come from, nothing moves
  Given an account "Ahorros" in COP with balance 0.00 COP
  And a proposed savings contribution of 100000.00 COP into "Ahorros"
  When the user tries to confirm the transfer into "Ahorros"
  Then the confirmation is rejected
  And "Ahorros" has balance 0.00 COP
  And the proposed savings contribution into "Ahorros" is still waiting

Scenario: An amount adjusted to zero is refused
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  And an account "Ahorros" in COP with balance 0.00 COP
  And "Bancolombia" is the account transfers come from
  And a proposed savings contribution of 100000.00 COP into "Ahorros"
  When the user tries to confirm the transfer into "Ahorros" for 0.00 COP
  Then the confirmation is rejected
  And "Bancolombia" has balance 1000000.00 COP
  And "Ahorros" has balance 0.00 COP

Scenario: Accounts in different currencies are refused
  Given an account "Bancolombia" in COP with balance 1000000.00 COP
  And an account "Amex" in USD
  And "Bancolombia" is the account transfers come from
  And a proposed savings contribution of 100000.00 COP into "Amex"
  When the user tries to confirm the transfer into "Amex"
  Then the confirmation is rejected
  And "Bancolombia" has balance 1000000.00 COP
```

## AC-20 — Without an exchange rate there is no queue

```gherkin
Scenario: The outstanding list is withheld until a rate exists
  Given no TRM has been set
  And an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 85000.00 COP to "Claro" from "Bancolombia" due in 3 days
  When the user views what is outstanding for the next 7 days
  Then the outstanding list is not shown
  And the user is told to set the TRM

Scenario: Skipping still works with no rate set
  Given no TRM has been set
  And an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 85000.00 COP to "Claro" from "Bancolombia" due in 3 days
  When the user skips the payment to "Claro"
  Then the payment to "Claro" is no longer waiting

Scenario: Once a rate is set the same list appears
  Given no TRM has been set
  And an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 85000.00 COP to "Claro" from "Bancolombia" due in 3 days
  When the user sets the TRM to 4100.00
  Then the outstanding list for the next 7 days shows "Claro" as upcoming
```

## AC-21 — Confirming is all or nothing

```gherkin
Scenario: A failure recording the savings contribution undoes the whole confirmation
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 85000.00 COP to "Claro" from "Bancolombia" due in 3 days
  And the savings contribution that follows a confirmation cannot be recorded
  When the user tries to confirm the payment to "Claro"
  Then the confirmation is rejected
  And "Bancolombia" has balance 500000.00 COP
  And the payment to "Claro" is waiting to be resolved

Scenario: A failed confirmation leaves the obligation's turn unsettled
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a monthly obligation of 50000.00 COP to "Acueducto" from "Bancolombia" that the user approves by hand, already due
  And the savings contribution that follows a confirmation cannot be recorded
  When the user tries to confirm the payment to "Acueducto"
  Then the confirmation is rejected
  And this month's turn of the obligation to "Acueducto" is still waiting
```

## AC-22 — Resolved items never come back

```gherkin
Scenario: A confirmed payment is gone from every period
  Given the TRM is 4100.00
  And an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 85000.00 COP to "Claro" from "Bancolombia" that fell due 4 days ago
  And the user confirms the payment to "Claro"
  When the user views what is outstanding for the 90 days starting 60 days ago
  Then the outstanding list is empty

Scenario: A skipped payment stays gone until it is restored
  Given the TRM is 4100.00
  And an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 85000.00 COP to "Claro" from "Bancolombia" that fell due 4 days ago
  And the user skips the payment to "Claro"
  When the user views what is outstanding for the 90 days starting 60 days ago
  Then the outstanding list is empty
```

## AC-23 — Amounts follow today's rate

```gherkin
Scenario: Changing the rate changes the same unresolved list
  Given the TRM is 4000.00
  And an account "Amex" in USD
  And a planned payment of 1000.00 USD to "SaaS" from "Amex" due in 3 days
  When the user sets the TRM to 4500.00
  Then the outstanding total for the next 7 days is 4500000.00 COP
  And the payment to "SaaS" is still for 1000.00 USD
```

## AC-24 — Every queue action exists outside the app

```gherkin
Scenario: The assistant reports the same outstanding figures as the app
  Given the TRM is 4100.00
  And an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 85000.00 COP to "Claro" from "Bancolombia" that fell due 2 days ago
  And a planned payment of 45000.00 COP to "Netflix" from "Bancolombia" due in 3 days
  When the assistant is asked what is outstanding for the next 7 days
  Then the assistant's answer shows "Claro" as overdue
  And the assistant's answer shows "Netflix" as upcoming
  And the assistant's answer shows a total of 130000.00 COP

Scenario: A payment can be planned by talking to the assistant
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a category "Servicios"
  When the assistant plans a payment of 85000.00 COP to "Claro" from "Bancolombia" due in 3 days in category "Servicios"
  Then the outstanding list for the next 7 days shows "Claro" as upcoming

Scenario: Confirming and skipping are reachable outside the app
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And a planned payment of 85000.00 COP to "Claro" from "Bancolombia" due in 3 days
  When the assistant confirms the payment to "Claro"
  Then "Bancolombia" has balance 415000.00 COP
```
