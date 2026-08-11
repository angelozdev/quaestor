# Acceptance specs — 012 movement-corrections

Formalizes `acs.md` (30 ACs, approved by the owner 2026-08-10) as standard
Gherkin.

**Nothing specified here exists.** Today `confirm_payment` takes an amount and a
date and nothing else, and the edit dialog tells the owner in small type *"Para
cambiar monto/cuenta, elimina y vuelve a crear."* This is the ATDD red phase in
its pure form.

## The two rules every scenario comes from

**1 — The record survives the correction.** Whatever is corrected, the movement
keeps its identity and everything the correction did not name: its date, its
beneficiary, its category, its tags, the meta it is pointed at, and the
recurring due date it hangs from.

**2 — No money figure moves without being seen, and nothing is saved unless the
arithmetic proves out.** A figure the app derives — a currency conversion, a
transfer's other half — is always offered and never applied silently. After the
write both balances must have moved by exactly the deltas the correction
declared; anything else undoes all of it.

## The rate

One exchange rate, a single scalar (ADR-0031). Every scenario that crosses a
currency states it: `Given the TRM is 4000`. A scenario that never mentions a
rate must never turn on one.

The whole suite uses **4000**, chosen so every conversion is exact and a wrong
figure cannot look plausible: `400000.00 COP` is `100.00 USD`, both ways.

## The cast

```
"Nu Debito"   COP   balance 1000000.00
"RappiCard"   COP   balance       0.00     (a card; spending drives it negative)
"DolarApp"    USD   balance    1000.00
"Prestamos"   COP   balance  500000.00
"Korea"       COP   archived
```

## Streams

Two, per technical ADR-0045. `@backend` → generated pytest against the services
layer: every balance, every refusal, every figure. **Untagged → vitest against
the screen**, and deliberately so — six of the defects feature 009 shipped were
behaviours reachable from Python and from no screen. What a form *offers* is a
screen fact and is specified as one. Nothing is `@browser`: no scenario turns on
width or wrapping.

**Dates are absolute.** Amounts are plain decimals, no thousands separators.

```gherkin
Feature: Corregir un movimiento — la cuenta de la que salió, y el número que lleva
```

## AC-1 — Confirming a payment says which account it came out of

```gherkin
Scenario: The confirmation offers the account it was planned against
  Given the app is open
  And a payment waiting to "Hogaru" of 400000.00 COP from "Nu Debito"
  When the owner opens the confirmation
  Then the confirmation offers an account
  And the account offered is "Nu Debito"

Scenario: The account is named, never numbered
  Given the app is open
  And a payment waiting to "Hogaru" of 400000.00 COP from "Nu Debito"
  When the owner opens the confirmation
  Then the account reads "Nu Debito"
  And no account is shown as a number
```

## AC-2 — Confirming from a different account charges that account, not the planned one

```gherkin
@backend
Scenario: The account actually used is the one that pays
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "RappiCard" in COP with balance 0.00 COP
  And an expense category "Hogar"
  And a planned payment of 400000.00 COP to "Hogaru" from "Nu Debito" due in 2 days in category "Hogar"
  When the user confirms the payment to "Hogaru" from "RappiCard"
  Then "Nu Debito" has balance 1000000.00 COP
  And "RappiCard" has balance -400000.00 COP

@backend
Scenario: Confirming without naming another account behaves as it always has
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an expense category "Hogar"
  And a planned payment of 400000.00 COP to "Hogaru" from "Nu Debito" due in 2 days in category "Hogar"
  When the user confirms the payment to "Hogaru"
  Then "Nu Debito" has balance 600000.00 COP
  And the payment to "Hogaru" is no longer waiting

@backend
Scenario: The account and the real amount are corrected in the same act
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "RappiCard" in COP with balance 0.00 COP
  And an expense category "Hogar"
  And a planned payment of 400000.00 COP to "Hogaru" from "Nu Debito" due in 2 days in category "Hogar"
  When the user confirms the payment to "Hogaru" from "RappiCard" for 420000.00 COP
  Then "Nu Debito" has balance 1000000.00 COP
  And "RappiCard" has balance -420000.00 COP
```

## AC-3 — Every account is offered, including accounts in another currency

```gherkin
Scenario: An account in another currency is on the list
  Given the app is open
  And an account "Nu Debito" in COP
  And an account "DolarApp" in USD
  And a payment waiting to "Hogaru" of 400000.00 COP from "Nu Debito"
  When the owner opens the confirmation
  Then the accounts offered include "DolarApp"
  And the accounts offered include "Nu Debito"
```

## AC-4 — Choosing an account in another currency offers the converted amount

```gherkin
Scenario: The converted figure arrives already filled in
  Given the app is open
  And the TRM is 4000
  And an account "Nu Debito" in COP
  And an account "DolarApp" in USD
  And a payment waiting to "Hogaru" of 400000.00 COP from "Nu Debito"
  When the owner opens the confirmation
  And the owner chooses the account "DolarApp"
  Then the amount offered is 100.00 USD

Scenario: The offered figure is a suggestion, not a decision
  Given the app is open
  And the TRM is 4000
  And an account "Nu Debito" in COP
  And an account "DolarApp" in USD
  And a payment waiting to "Hogaru" of 400000.00 COP from "Nu Debito"
  When the owner opens the confirmation
  And the owner chooses the account "DolarApp"
  And the owner writes the amount 105.00
  Then the amount offered is 105.00 USD

@backend
Scenario: A figure the app derived is never applied on its own
  Given today is 2026-08-10
  And the TRM is 4000
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "DolarApp" in USD with balance 1000.00 USD
  And an expense category "Hogar"
  And a planned payment of 400000.00 COP to "Hogaru" from "Nu Debito" due in 2 days in category "Hogar"
  When the user confirms the payment to "Hogaru" from "DolarApp" for 105.00 USD
  Then "DolarApp" has balance 895.00 USD
  And "Nu Debito" has balance 1000000.00 COP
```

## AC-5 — A payment confirmed against a foreign-currency account is stored in that currency

```gherkin
@backend
Scenario: The movement becomes a dollar movement
  Given today is 2026-08-10
  And the TRM is 4000
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "DolarApp" in USD with balance 1000.00 USD
  And an expense category "Hogar"
  And a planned payment of 400000.00 COP to "Hogaru" from "Nu Debito" due in 2 days in category "Hogar"
  When the user confirms the payment to "Hogaru" from "DolarApp" for 100.00 USD
  Then that movement is for 100.00 USD
  And that movement came out of "DolarApp"
  And "DolarApp" has balance 900.00 USD

@backend
Scenario: Its peso value is read at the rate of the day it is read
  Given today is 2026-08-10
  And the TRM is 4000
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "DolarApp" in USD with balance 1000.00 USD
  And an expense category "Hogar"
  And a planned payment of 400000.00 COP to "Hogaru" from "Nu Debito" due in 2 days in category "Hogar"
  And the user confirms the payment to "Hogaru" from "DolarApp" for 100.00 USD
  And the user sets the TRM to 5000
  When the user views the current month's report
  Then that movement is for 100.00 USD
  And the spending for "Hogar" shows 500000.00 COP
```

## AC-6 — Confirming from another account is a one-month exception

```gherkin
@backend
Scenario: The obligation still names the account it was declared against
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "RappiCard" in COP with balance 0.00 COP
  And an expense category "Hogar"
  And a repeating payment of 400000.00 COP to "Hogaru" from "Nu Debito" every 1 month starting on 2026-08-01 in category "Hogar", waiting for approval
  And the daily run happens
  When the user confirms the payment to "Hogaru" from "RappiCard"
  Then "Hogaru" is still declared against "Nu Debito"

@backend
Scenario: Next month asks against the declared account again
  Given today is 2026-09-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "RappiCard" in COP with balance 0.00 COP
  And an expense category "Hogar"
  And a repeating payment of 400000.00 COP to "Hogaru" from "Nu Debito" every 1 month starting on 2026-08-01 in category "Hogar", waiting for approval
  And the daily run happens
  And the user confirms the payment to "Hogaru" from "RappiCard"
  When the obligations that have come due are raised again
  Then the payment to "Hogaru" is waiting to be resolved
  And the payment still waiting to "Hogaru" is against "Nu Debito"
```

## AC-7 — A movement already recorded can move to another account

```gherkin
@backend
Scenario: The account it left gets the money back and the one it came from gives it up
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "RappiCard" in COP with balance 0.00 COP
  And an expense category "Servicios"
  And the user registers an expense of 100000.00 COP from "Nu Debito" paying "Tigo" in category "Servicios"
  When the user moves that expense to "RappiCard"
  Then "Nu Debito" has balance 1000000.00 COP
  And "RappiCard" has balance -100000.00 COP
  And that expense came out of "RappiCard"

@backend
Scenario: Money coming in moves the same way
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "Prestamos" in COP with balance 500000.00 COP
  And an income category "Salario"
  And the user registers an income of 300000.00 COP into "Nu Debito" from "Empresa"
  When the user moves that income to "Prestamos"
  Then "Nu Debito" has balance 1000000.00 COP
  And "Prestamos" has balance 800000.00 COP

@backend
Scenario: Moving to an account in another currency carries the amount with it
  Given today is 2026-08-10
  And the TRM is 4000
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "DolarApp" in USD with balance 1000.00 USD
  And an expense category "Servicios"
  And the user registers an expense of 400000.00 COP from "Nu Debito" paying "Tigo" in category "Servicios"
  When the user moves that expense to "DolarApp" for 100.00 USD
  Then "Nu Debito" has balance 1000000.00 COP
  And "DolarApp" has balance 900.00 USD
  And that expense is for 100.00 USD
```

## AC-8 — A movement's amount can be corrected on its own

```gherkin
@backend
Scenario: The balance moves by the difference and nothing else
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an expense category "Servicios"
  And the user registers an expense of 100000.00 COP from "Nu Debito" paying "Tigo" in category "Servicios"
  When the user corrects that expense to 120000.00 COP
  Then "Nu Debito" has balance 880000.00 COP
  And that expense is for 120000.00 COP
  And that expense came out of "Nu Debito"

@backend
Scenario: Correcting downward gives the difference back
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an expense category "Servicios"
  And the user registers an expense of 100000.00 COP from "Nu Debito" paying "Tigo" in category "Servicios"
  When the user corrects that expense to 80000.00 COP
  Then "Nu Debito" has balance 920000.00 COP

@backend
Scenario: What the category spent follows the corrected figure
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an expense category "Servicios"
  And the user registers an expense of 100000.00 COP from "Nu Debito" paying "Tigo" in category "Servicios"
  And the user corrects that expense to 120000.00 COP
  When the user views the current month's report
  Then the spending for "Servicios" shows 120000.00 COP
```

## AC-9 — A corrected movement is still the same movement

```gherkin
@backend
Scenario: Everything the correction did not name is untouched
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "RappiCard" in COP with balance 0.00 COP
  And an expense category "Servicios"
  And the user registers an expense of 100000.00 COP from "Nu Debito" paying "Tigo" in category "Servicios"
  And the user adds the tag "recibos" to the expense
  When the user moves that expense to "RappiCard"
  Then viewing the expense shows the tag "recibos"
  And that expense is still the same movement
  And the transaction list shows the expense

@backend
Scenario: The purchase stays pointed at its meta
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 10000000.00 COP
  And an account "RappiCard" in COP with balance 0.00 COP
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12
  And a recorded expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular" this month
  When the user moves that expense to "RappiCard"
  Then that expense is still linked to the meta "Celular"
```

## AC-10 — Each leg of a transfer moves account on its own

```gherkin
@backend
Scenario: The side that sent is corrected without touching the side that received
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "Prestamos" in COP with balance 500000.00 COP
  And an account "RappiCard" in COP with balance 0.00 COP
  And the user transfers 200000.00 COP from "Prestamos" to "Nu Debito" dated 2026-08-10
  When the user moves the sending side of the transfer to "RappiCard"
  Then "Prestamos" has balance 500000.00 COP
  And "RappiCard" has balance -200000.00 COP
  And "Nu Debito" has balance 1200000.00 COP

@backend
Scenario: The side that received is corrected without touching the side that sent
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "Prestamos" in COP with balance 500000.00 COP
  And an account "RappiCard" in COP with balance 0.00 COP
  And the user transfers 200000.00 COP from "Prestamos" to "Nu Debito" dated 2026-08-10
  When the user moves the receiving side of the transfer to "RappiCard"
  Then "Nu Debito" has balance 1000000.00 COP
  And "RappiCard" has balance 200000.00 COP
  And "Prestamos" has balance 300000.00 COP

@backend
Scenario: The two sides stay one transfer
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "Prestamos" in COP with balance 500000.00 COP
  And an account "RappiCard" in COP with balance 0.00 COP
  And the user transfers 200000.00 COP from "Prestamos" to "Nu Debito" dated 2026-08-10
  When the user moves the sending side of the transfer to "RappiCard"
  Then the transfer sends 200000.00 COP from "RappiCard" and receives 200000.00 COP into "Nu Debito"
```

## AC-11 — In a same-currency transfer the two halves always carry the same amount

```gherkin
@backend
Scenario: Correcting one half moves both
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "Prestamos" in COP with balance 500000.00 COP
  And the user transfers 200000.00 COP from "Prestamos" to "Nu Debito" dated 2026-08-10
  When the user corrects the transfer to 250000.00 COP
  Then the transfer sends 250000.00 COP from "Prestamos" and receives 250000.00 COP into "Nu Debito"
  And "Prestamos" has balance 250000.00 COP
  And "Nu Debito" has balance 1250000.00 COP

@backend
Scenario: Money never appears between the two halves
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "Prestamos" in COP with balance 500000.00 COP
  And the user transfers 200000.00 COP from "Prestamos" to "Nu Debito" dated 2026-08-10
  When the user tries to correct the transfer to send 250000.00 COP and receive 200000.00 COP
  Then the correction is rejected
  And the user is told the two sides of a transfer in one currency carry the same amount
  And "Prestamos" has balance 300000.00 COP
  And "Nu Debito" has balance 1200000.00 COP
```

## AC-12 — A transfer across currencies asks for both figures

```gherkin
@backend
Scenario: Both figures are stated and neither derives from the other
  Given today is 2026-08-10
  And the TRM is 4000
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "DolarApp" in USD with balance 1000.00 USD
  And the user transfers sending 100.00 USD from "DolarApp" and receiving 400000.00 COP into "Nu Debito"
  When the user corrects the transfer to send 110.00 USD and receive 430000.00 COP
  Then the transfer sends 110.00 USD from "DolarApp" and receives 430000.00 COP into "Nu Debito"
  And "DolarApp" has balance 890.00 USD
  And "Nu Debito" has balance 1430000.00 COP

@backend
Scenario: The two sides of a crossing transfer are allowed to disagree
  Given today is 2026-08-10
  And the TRM is 4000
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "DolarApp" in USD with balance 1000.00 USD
  And the user transfers sending 100.00 USD from "DolarApp" and receiving 400000.00 COP into "Nu Debito"
  When the user corrects the transfer to send 100.00 USD and receive 390000.00 COP
  Then the transfer sends 100.00 USD from "DolarApp" and receives 390000.00 COP into "Nu Debito"
```

## AC-13 — Moving a leg into another currency offers the converted figure

```gherkin
Scenario: The converted figure arrives filled in, exactly as when confirming
  Given the app is open
  And the TRM is 4000
  And an account "Nu Debito" in COP
  And an account "DolarApp" in USD
  And a recorded transfer sending 100.00 USD from "DolarApp" and receiving 400000.00 COP into "Nu Debito"
  When the owner opens the receiving side of the transfer
  And the owner chooses the account "DolarApp"
  Then the amount offered is 100.00 USD

@backend
Scenario: The figure the owner states is the one stored
  Given today is 2026-08-10
  And the TRM is 4000
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "Prestamos" in COP with balance 500000.00 COP
  And an account "DolarApp" in USD with balance 1000.00 USD
  And the user transfers sending 100.00 USD from "DolarApp" and receiving 400000.00 COP into "Nu Debito"
  When the user moves the sending side of the transfer to "Prestamos" for 420000.00 COP
  Then the transfer sends 420000.00 COP from "Prestamos" and receives 400000.00 COP into "Nu Debito"
  And "DolarApp" has balance 1000.00 USD
  And "Prestamos" has balance 80000.00 COP
  And "Nu Debito" has balance 1400000.00 COP
```

## AC-14 — The screen stops telling the owner to delete and recreate

```gherkin
Scenario: The instruction to delete and recreate is gone
  Given the app is open
  And a recorded expense of 100000.00 COP from "Nu Debito"
  When the owner opens that expense
  Then the owner is not told to delete and create it again

Scenario: The account is offered rather than described
  Given the app is open
  And an account "Nu Debito" in COP
  And an account "RappiCard" in COP
  And a recorded expense of 100000.00 COP from "Nu Debito"
  When the owner opens that expense
  Then the account reads "Nu Debito"
  And no account is shown as a number
  And the accounts offered include "RappiCard"

Scenario: The amount is offered rather than described
  Given the app is open
  And a recorded expense of 100000.00 COP from "Nu Debito"
  When the owner opens that expense
  Then the amount offered is 100000.00 COP
```

## AC-15 — An archived account is never offered as a destination

```gherkin
Scenario: A retired account is not on the list when confirming
  Given the app is open
  And an account "Nu Debito" in COP
  And an archived account "Korea" in COP
  And a payment waiting to "Hogaru" of 400000.00 COP from "Nu Debito"
  When the owner opens the confirmation
  Then the accounts offered do not include "Korea"

Scenario: A retired account is not on the list when correcting
  Given the app is open
  And an account "Nu Debito" in COP
  And an archived account "Korea" in COP
  And a recorded expense of 100000.00 COP from "Nu Debito"
  When the owner opens that expense
  Then the accounts offered do not include "Korea"

@backend
Scenario: Nothing lands in a retired account even when asked directly
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an archived account "Korea" in COP
  And an expense category "Servicios"
  And the user registers an expense of 100000.00 COP from "Nu Debito" paying "Tigo" in category "Servicios"
  When the user tries to move that expense to "Korea"
  Then the correction is rejected
  And the user is told a retired account takes nothing new
  And "Nu Debito" has balance 900000.00 COP
```

## AC-16 — A movement can still be moved *out* of an archived account

```gherkin
@backend
Scenario: What is already in a retired account is not stuck there
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "Korea" in COP with balance 300000.00 COP
  And an expense category "Servicios"
  And the user registers an expense of 100000.00 COP from "Korea" paying "Tigo" in category "Servicios"
  And the account "Korea" is retired
  When the user moves that expense to "Nu Debito"
  Then "Korea" has balance 300000.00 COP
  And "Nu Debito" has balance 900000.00 COP
  And that expense came out of "Nu Debito"
```

## AC-17 — Correcting a purchase does not reopen the meta it completed

```gherkin
@backend
Scenario: A meta that was bought stays bought, whatever the corrected number says
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 10000000.00 COP
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12
  And a recorded expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular" this month
  When the user corrects that expense to 500.00 COP
  Then the meta "Celular" is complete
  And that expense is still linked to the meta "Celular"

@backend
Scenario: Moving the purchase to another account leaves the meta alone
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 10000000.00 COP
  And an account "RappiCard" in COP with balance 0.00 COP
  And an expense category "Tecnologia"
  And a meta "Celular" of 8000000.00 COP by 2026-12
  And a recorded expense of 8000000.00 COP in category "Tecnologia" linked to the meta "Celular" this month
  When the user moves that expense to "RappiCard"
  Then the meta "Celular" is complete
  And that expense is still linked to the meta "Celular"
```

## AC-18 — Correcting an engine-made charge keeps it attached to its due date

```gherkin
@backend
Scenario: The month stays charged, not omitted
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "RappiCard" in COP with balance 0.00 COP
  And an expense category "Hogar"
  And a repeating payment of 400000.00 COP to "Hogaru" from "Nu Debito" every 1 month starting on 2026-08-01 in category "Hogar", paying itself
  And the daily run happens
  When the user moves that charge to "RappiCard"
  Then the due date behind "Hogaru" is still charged
  And "Hogaru" was charged 400000.00 COP on 2026-08-01

@backend
Scenario: Correcting the figure keeps the charge attached too
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an expense category "Hogar"
  And a repeating payment of 400000.00 COP to "Hogaru" from "Nu Debito" every 1 month starting on 2026-08-01 in category "Hogar", paying itself
  And the daily run happens
  When the user corrects that charge to 420000.00 COP
  Then the due date behind "Hogaru" is still charged
  And "Nu Debito" has balance 580000.00 COP
```

## AC-19 — Correcting one month never teaches the obligation

```gherkin
@backend
Scenario: The declared figure does not follow the corrected one
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an expense category "Hogar"
  And a repeating payment of 400000.00 COP to "Hogaru" from "Nu Debito" every 1 month starting on 2026-08-01 in category "Hogar", paying itself
  And the daily run happens
  When the user corrects that charge to 420000.00 COP
  Then "Hogaru" is described as 400000.00 COP every 1 month

@backend
Scenario: The obligation still lists the figure it declares, not the corrected one
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 5000000.00 COP
  And an expense category "Hogar"
  And a repeating payment of 400000.00 COP to "Hogaru" from "Nu Debito" every 1 month starting on 2026-08-01 in category "Hogar", paying itself
  And the daily run happens
  And the user corrects that charge to 420000.00 COP
  When the user views the repeating obligations
  Then the list shows "Hogaru" at 400000.00 COP every 1 month
  And "Hogaru" was charged 420000.00 COP on 2026-08-01
```

## AC-20 — A movement that has not moved money corrects without moving any

```gherkin
@backend
Scenario: Correcting a payment still waiting moves no balance
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "RappiCard" in COP with balance 0.00 COP
  And an expense category "Hogar"
  And a planned payment of 400000.00 COP to "Hogaru" from "Nu Debito" due in 2 days in category "Hogar"
  When the user moves the payment still waiting to "RappiCard"
  Then "Nu Debito" has balance 1000000.00 COP
  And "RappiCard" has balance 0.00 COP
  And the payment still waiting to "Hogaru" is against "RappiCard"

@backend
Scenario: What it will ask for follows the correction
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "RappiCard" in COP with balance 0.00 COP
  And an expense category "Hogar"
  And a planned payment of 400000.00 COP to "Hogaru" from "Nu Debito" due in 2 days in category "Hogar"
  And the user moves the payment still waiting to "RappiCard"
  When the user confirms the payment to "Hogaru"
  Then "RappiCard" has balance -400000.00 COP
  And "Nu Debito" has balance 1000000.00 COP
```

## AC-21 — A correction that changes nothing changes nothing

```gherkin
@backend
Scenario: Saving without changing anything leaves every balance where it was
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an expense category "Servicios"
  And the user registers an expense of 100000.00 COP from "Nu Debito" paying "Tigo" in category "Servicios"
  When the user corrects that expense to 100000.00 COP
  Then "Nu Debito" has balance 900000.00 COP

@backend
Scenario: Moving a movement to the account it already came out of charges nothing twice
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an expense category "Servicios"
  And the user registers an expense of 100000.00 COP from "Nu Debito" paying "Tigo" in category "Servicios"
  When the user moves that expense to "Nu Debito"
  Then "Nu Debito" has balance 900000.00 COP

@backend
Scenario: The same correction applied twice lands once
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an expense category "Servicios"
  And the user registers an expense of 100000.00 COP from "Nu Debito" paying "Tigo" in category "Servicios"
  And the user corrects that expense to 120000.00 COP
  When the user corrects that expense to 120000.00 COP
  Then "Nu Debito" has balance 880000.00 COP
```

## AC-22 — A transfer's two halves cannot end up on the same account

```gherkin
@backend
Scenario: A transfer from an account to itself is refused
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "Prestamos" in COP with balance 500000.00 COP
  And the user transfers 200000.00 COP from "Prestamos" to "Nu Debito" dated 2026-08-10
  When the user tries to move the sending side of the transfer to "Nu Debito"
  Then the correction is rejected
  And the user is told the two sides of a transfer cannot be the same account
  And "Prestamos" has balance 300000.00 COP
  And "Nu Debito" has balance 1200000.00 COP
```

## AC-23 — A correction proves its own arithmetic, or none of it happens

```gherkin
@backend
Scenario: A balance that does not move as declared undoes the whole correction
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "RappiCard" in COP with balance 0.00 COP
  And an expense category "Servicios"
  And the user registers an expense of 100000.00 COP from "Nu Debito" paying "Tigo" in category "Servicios"
  And the balance of "RappiCard" refuses to move
  When the user tries to move that expense to "RappiCard"
  Then the correction is rejected
  And the user is told the correction did not go through
  And "Nu Debito" has balance 900000.00 COP
  And "RappiCard" has balance 0.00 COP
  And that expense came out of "Nu Debito"

@backend
Scenario: A balance that moves by more than declared undoes it too
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an expense category "Servicios"
  And the user registers an expense of 100000.00 COP from "Nu Debito" paying "Tigo" in category "Servicios"
  And the balance of "Nu Debito" moves by more than it is told to
  When the user tries to correct that expense to 120000.00 COP
  Then the correction is rejected
  And "Nu Debito" has balance 900000.00 COP
  And that expense is for 100000.00 COP

@backend
Scenario: The check does not care what the balance was to begin with
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "RappiCard" in COP with balance 0.00 COP
  And an expense category "Servicios"
  And the user registers an expense of 100000.00 COP from "Nu Debito" paying "Tigo" in category "Servicios"
  And "Nu Debito" was adjusted by hand to 777777.77 COP
  When the user moves that expense to "RappiCard"
  Then "Nu Debito" has balance 877777.77 COP
  And "RappiCard" has balance -100000.00 COP
```

## AC-24 — A correction never leaves a movement worth nothing or less

```gherkin
@backend
Scenario: Zero is refused
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an expense category "Servicios"
  And the user registers an expense of 100000.00 COP from "Nu Debito" paying "Tigo" in category "Servicios"
  When the user tries to correct that expense to 0.00 COP
  Then the correction is rejected
  And "Nu Debito" has balance 900000.00 COP

@backend
Scenario: Less than zero is refused
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an expense category "Servicios"
  And the user registers an expense of 100000.00 COP from "Nu Debito" paying "Tigo" in category "Servicios"
  When the user tries to correct that expense to -50000.00 COP
  Then the correction is rejected
  And "Nu Debito" has balance 900000.00 COP

@backend
Scenario: Confirming against another account cannot be used to reach zero either
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "RappiCard" in COP with balance 0.00 COP
  And an expense category "Hogar"
  And a planned payment of 400000.00 COP to "Hogaru" from "Nu Debito" due in 2 days in category "Hogar"
  When the user tries to confirm the payment to "Hogaru" from "RappiCard" for 0.00 COP
  Then the confirmation is rejected
  And "RappiCard" has balance 0.00 COP
```

## AC-25 — A correction pointing at an account that does not exist is refused

```gherkin
@backend
Scenario: Nothing is written and no balance moves
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an expense category "Servicios"
  And the user registers an expense of 100000.00 COP from "Nu Debito" paying "Tigo" in category "Servicios"
  When the user tries to move that expense to an account that does not exist
  Then the user is told it does not exist
  And "Nu Debito" has balance 900000.00 COP
  And that expense came out of "Nu Debito"
```

## AC-26 — A corrected movement still obeys what a movement must carry

```gherkin
@backend
Scenario: An expense still carries an expense category after being corrected
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "RappiCard" in COP with balance 0.00 COP
  And an expense category "Servicios"
  And the user registers an expense of 100000.00 COP from "Nu Debito" paying "Tigo" in category "Servicios"
  When the user moves that expense to "RappiCard"
  Then that expense is still in category "Servicios"

@backend
Scenario: A transfer still carries no category after being corrected
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "Prestamos" in COP with balance 500000.00 COP
  And an account "RappiCard" in COP with balance 0.00 COP
  And the user transfers 200000.00 COP from "Prestamos" to "Nu Debito" dated 2026-08-10
  When the user moves the sending side of the transfer to "RappiCard"
  Then that transfer carries no category
```

## AC-27 — A correction cannot be triggered from outside the app

```gherkin
@backend
Scenario: Without a session nothing is corrected
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an expense category "Servicios"
  And the user registers an expense of 100000.00 COP from "Nu Debito" paying "Tigo" in category "Servicios"
  And the user has no session
  When they try to correct that expense
  Then access is denied
  And "Nu Debito" has balance 900000.00 COP
```

## AC-28 — The assistant gains nothing

```gherkin
@backend
Scenario: The assistant is not able to move a movement between accounts
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "RappiCard" in COP with balance 0.00 COP
  And an expense category "Servicios"
  And the user registers an expense of 100000.00 COP from "Nu Debito" paying "Tigo" in category "Servicios"
  When the assistant is asked to move that expense to another account
  Then the assistant cannot do it
  And "Nu Debito" has balance 900000.00 COP

@backend
Scenario: The assistant is not able to change what a movement is worth
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an expense category "Servicios"
  And the user registers an expense of 100000.00 COP from "Nu Debito" paying "Tigo" in category "Servicios"
  When the assistant is asked to change what that expense is worth
  Then the assistant cannot do it
  And "Nu Debito" has balance 900000.00 COP

@backend
Scenario: What the assistant could already do still works
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an expense category "Servicios"
  And the user registers an expense of 100000.00 COP from "Nu Debito" paying "Tigo" in category "Servicios"
  When the assistant removes the tag "recibos" from the expense
  Then viewing the expense shows no tags
```

## AC-29 — A correction moves balances and nothing else

```gherkin
@backend
Scenario: Moving a movement between accounts leaves the month's figures alone
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an account "RappiCard" in COP with balance 0.00 COP
  And an expense category "Servicios"
  And an income category "Salario"
  And a fund on "Servicios" that asks a fixed 200000.00 COP each month, starting 2026-08
  And a repeating income of 3000000.00 COP from "Empresa" into "Nu Debito" every 1 month starting on 2026-08-01 in category "Salario", paying itself
  And the user registers an expense of 100000.00 COP from "Nu Debito" paying "Tigo" in category "Servicios"
  When the user moves that expense to "RappiCard"
  Then the fund on "Servicios" spent 100000.00 COP this month
  And the money available this month is 2800000.00 COP

@backend
Scenario: Correcting the figure moves what its category spent, and only that
  Given today is 2026-08-10
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an expense category "Servicios"
  And an income category "Salario"
  And a fund on "Servicios" that asks a fixed 200000.00 COP each month, starting 2026-08
  And a repeating income of 3000000.00 COP from "Empresa" into "Nu Debito" every 1 month starting on 2026-08-01 in category "Salario", paying itself
  And the user registers an expense of 100000.00 COP from "Nu Debito" paying "Tigo" in category "Servicios"
  When the user corrects that expense to 120000.00 COP
  Then the fund on "Servicios" spent 120000.00 COP this month
  And the money available this month is 2800000.00 COP
```

## AC-30 — The account and the amount are reachable the way every other field is

```gherkin
Scenario: The account offered when confirming is reachable by its label
  Given the app is open
  And a payment waiting to "Hogaru" of 400000.00 COP from "Nu Debito"
  When the owner opens the confirmation
  Then the account is reachable by its label
  And the amount is reachable by its label

Scenario: The account offered when correcting is reachable by its label
  Given the app is open
  And a recorded expense of 100000.00 COP from "Nu Debito"
  When the owner opens that expense
  Then the account is reachable by its label
  And the amount is reachable by its label
```
