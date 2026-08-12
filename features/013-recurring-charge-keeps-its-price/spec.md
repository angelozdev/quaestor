# Acceptance specs — 013 recurring-charge-keeps-its-price

Formalizes `acs.md` (21 ACs, approved by the owner 2026-08-11) as standard
Gherkin.

**Nothing specified here exists.** Today `create_recurring` refuses outright when
the declared currency is not the account's (`services/recurring.py:112`), and
editing routes the same question through `retarget`, which restates rather than
lets the two differ. This is the ATDD red phase in its pure form.

## The two rules every scenario comes from

**1 — The price is the merchant's, and it does not change because the account
does.** A rule holds the number the merchant announces, in the currency it
announces it in. Which account pays is a separate, later decision.

**2 — No converted figure applies on its own.** When price and account do not
share a currency, the app offers the conversion at its single rate (ADR-0031)
and the owner accepts it or replaces it. The offer is never mandatory — except
where accepting is the only way out of a state AC-2 forbids.

## The rate

One exchange rate, a single scalar (ADR-0031). Every scenario that crosses a
currency states it: `Given the TRM is 4000`. A scenario that never mentions a
rate must never turn on one.

The suite uses **4000** so every conversion is exact and a wrong figure cannot
look plausible: `400000.00 COP` is `100.00 USD`, both ways. The migration
scenarios are the one exception — they carry the owner's real figures, because
what they assert is those exact numbers and nothing else.

## The cast

```
"Nu Debito"   COP   balance 1000000.00
"DolarApp"    USD   balance    1000.00
"Vieja"       COP   archived

"Hevy Pro"    400000.00 COP yearly  from "DolarApp"   ← price and account disagree
"Opal"            40.00 USD monthly from "DolarApp"   ← they agree: the control
```

Every scenario that says `waiting for approval` means the owner confirms it by
hand; `paying itself` means the engine posts it unattended.

## Streams

Two, per technical ADR-0045. `@backend` → generated pytest against the services
layer: every balance, every refusal, every figure that gets stored. **Untagged →
vitest against the screen**, and deliberately so — what a form *offers* before
anything is saved is a screen fact and is specified as one. Nothing is
`@browser`: no scenario turns on width or wrapping.

**Dates are absolute.** Amounts are plain decimals, no thousands separators.

## What this spec deliberately does not touch

The row `| 25900.00 | USD | Bancolombia | … | paying itself |` in feature 007's
AC-18 still passes unchanged, and its assertion is still right — but its
*reason* changes. It used to be refused because a rule's currency had to match
its account's; now it is refused because a rule that pays itself may not
disagree with its account. AC-2 below pins the new reason so the old row cannot
quietly become the only thing holding the rule up.

```gherkin
Feature: Un cobro recurrente guarda el precio del comercio, no la moneda de la cuenta
```

## AC-1 — A rule can hold a price in a currency other than its account's

```gherkin
@backend
Scenario: A peso price on a dollar account is accepted
  Given today is 2026-07-01
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  When the user declares a repeating payment of 400000.00 COP to "Hevy Pro" from "DolarApp" every 1 year starting 2026-07-15 in category "Suscripciones", waiting for approval
  Then "Hevy Pro" is described as 400000.00 COP every 1 year
  And "DolarApp" has balance 1000.00 USD

@backend
Scenario: A dollar price on a peso account is accepted just the same
  Given today is 2026-07-01
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And a category "Suscripciones"
  When the user declares a repeating payment of 40.00 USD to "Opal" from "Nu Debito" every 1 month starting 2026-07-15 in category "Suscripciones", waiting for approval
  Then "Opal" is described as 40.00 USD every 1 month

@backend
Scenario: Saving the rule needs no rate at all
  Given today is 2026-07-01
  And no TRM has been set
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  When the user declares a repeating payment of 400000.00 COP to "Hevy Pro" from "DolarApp" every 1 year starting 2026-07-15 in category "Suscripciones", waiting for approval
  Then "Hevy Pro" is described as 400000.00 COP every 1 year
```

## AC-2 — A rule that pays itself may not disagree with its account

```gherkin
@backend
Scenario: Declaring a self-paying rule in another currency is refused
  Given today is 2026-07-01
  And the TRM is 4000
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  When the user tries to declare a repeating payment of 400000.00 COP to "Hevy Pro" from "DolarApp" every 1 year starting 2026-07-15 in category "Suscripciones", paying itself
  Then the declaration is rejected
  And "DolarApp" has balance 1000.00 USD

@backend
Scenario: The refusal names the two ways out
  Given today is 2026-07-01
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  When the user tries to declare a repeating payment of 400000.00 COP to "Hevy Pro" from "DolarApp" every 1 year starting 2026-07-15 in category "Suscripciones", paying itself
  Then the refusal offers to hold the price in USD
  And the refusal offers to wait for approval instead

@backend
Scenario: A rule that disagrees cannot be switched to paying itself
  Given today is 2026-07-01
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  And a repeating payment of 400000.00 COP to "Hevy Pro" from "DolarApp" every 1 year starting 2026-07-15 in category "Suscripciones", waiting for approval
  When the user tries to make "Hevy Pro" pay itself
  Then the change to "Hevy Pro" is rejected
  And "Hevy Pro" is described as 400000.00 COP every 1 year

@backend
Scenario: A self-paying rule cannot be moved into disagreement
  Given today is 2026-07-01
  And the TRM is 4000
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  And a repeating payment of 40.00 USD to "Opal" from "DolarApp" every 1 month starting 2026-07-15 in category "Suscripciones", paying itself
  When the user tries to change the amount of "Opal" to 160000.00 COP
  Then the change to "Opal" is rejected
  And "Opal" is described as 40.00 USD every 1 month

@backend
Scenario: A rule waiting for approval takes the same change
  Given today is 2026-07-01
  And the TRM is 4000
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  And a repeating payment of 40.00 USD to "Opal" from "DolarApp" every 1 month starting 2026-07-15 in category "Suscripciones", waiting for approval
  When the user changes the amount of "Opal" to 160000.00 COP
  Then "Opal" is described as 160000.00 COP every 1 month
```

## AC-3 — The list shows the price and what it would cost today

```gherkin
Scenario: The row carries both figures
  Given the app is open
  And the TRM is 4000
  And an account "DolarApp" in USD
  And a repeating charge "Hevy Pro" of 400000.00 COP from "DolarApp"
  When the owner opens the repeating obligations
  Then the row for "Hevy Pro" reads 400000.00 COP
  And the row for "Hevy Pro" reads about 100.00 USD

Scenario: A rule that agrees with its account shows one figure only
  Given the app is open
  And the TRM is 4000
  And an account "DolarApp" in USD
  And a repeating charge "Opal" of 40.00 USD from "DolarApp"
  When the owner opens the repeating obligations
  Then the row for "Opal" reads 40.00 USD
  And the row for "Opal" shows no converted figure
```

## AC-4 — Without a rate the list shows the price and says nothing else

```gherkin
Scenario: The converted figure disappears, the price stays
  Given the app is open
  And no TRM has been set
  And an account "DolarApp" in USD
  And a repeating charge "Hevy Pro" of 400000.00 COP from "DolarApp"
  When the owner opens the repeating obligations
  Then the row for "Hevy Pro" reads 400000.00 COP
  And the row for "Hevy Pro" shows no converted figure
  And the repeating obligations show no error
```

## AC-5 — The charge is born waiting, in the rule's currency

```gherkin
@backend
Scenario: The turn arrives as a charge waiting for approval
  Given today is 2026-07-15
  And the TRM is 4000
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  And a repeating payment of 400000.00 COP to "Hevy Pro" from "DolarApp" every 1 year starting 2026-07-15 in category "Suscripciones", waiting for approval
  When the daily run happens
  Then the turn of "Hevy Pro" due 2026-07-15 is waiting for approval
  And "Hevy Pro" was charged 400000.00 COP 2026-07-15

@backend
Scenario: The charge is born even with no rate set
  Given today is 2026-07-15
  And no TRM has been set
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  And a repeating payment of 400000.00 COP to "Hevy Pro" from "DolarApp" every 1 year starting 2026-07-15 in category "Suscripciones", waiting for approval
  When the daily run happens
  Then the turn of "Hevy Pro" due 2026-07-15 is waiting for approval
  And "Hevy Pro" was charged 400000.00 COP 2026-07-15
```

## AC-6 — A charge waiting moves no balance

```gherkin
@backend
Scenario: The dollar account is untouched while the charge waits
  Given today is 2026-07-15
  And the TRM is 4000
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  And a repeating payment of 400000.00 COP to "Hevy Pro" from "DolarApp" every 1 year starting 2026-07-15 in category "Suscripciones", waiting for approval
  When the daily run happens
  Then "DolarApp" has balance 1000.00 USD
```

## AC-7 — Confirming offers the conversion, and it can be replaced

```gherkin
Scenario: A repeating charge priced in another currency offers its conversion
  Given the app is open
  And the TRM is 4000
  And an account "DolarApp" in USD
  And a payment waiting to "Hevy Pro" of 400000.00 COP from "DolarApp"
  When the owner opens the confirmation
  Then the amount offered is 100.00 USD

Scenario: The owner replaces the conversion with what the bank really took
  Given the app is open
  And the TRM is 4000
  And an account "DolarApp" in USD
  And a payment waiting to "Hevy Pro" of 400000.00 COP from "DolarApp"
  When the owner opens the confirmation
  And the owner writes the amount 102.00
  Then the amount offered is 102.00 USD

Scenario: A charge that agrees with its account is offered its own figure
  Given the app is open
  And the TRM is 4000
  And an account "DolarApp" in USD
  And a payment waiting to "Opal" of 40.00 USD from "DolarApp"
  When the owner opens the confirmation
  Then the amount offered is 40.00 USD
```

## AC-8 — What is recorded is stated in the account's currency

```gherkin
@backend
Scenario: The movement keeps the dollars, not the pesos
  Given today is 2026-07-15
  And the TRM is 4000
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  And a repeating payment of 400000.00 COP to "Hevy Pro" from "DolarApp" every 1 year starting 2026-07-15 in category "Suscripciones", waiting for approval
  And the daily run happens
  When the user confirms the payment to "Hevy Pro" for 102.00 USD
  Then "Hevy Pro" was charged 102.00 USD 2026-07-15
  And the turn of "Hevy Pro" due 2026-07-15 is recorded as paid

@backend
Scenario: Confirming without restating it is refused
  Given today is 2026-07-15
  And the TRM is 4000
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  And a repeating payment of 400000.00 COP to "Hevy Pro" from "DolarApp" every 1 year starting 2026-07-15 in category "Suscripciones", waiting for approval
  And the daily run happens
  When the user tries to confirm the payment to "Hevy Pro"
  Then the confirmation is rejected
  And "DolarApp" has balance 1000.00 USD

@backend
Scenario: The rule keeps its own price after the charge is recorded
  Given today is 2026-07-15
  And the TRM is 4000
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  And a repeating payment of 400000.00 COP to "Hevy Pro" from "DolarApp" every 1 year starting 2026-07-15 in category "Suscripciones", waiting for approval
  And the daily run happens
  When the user confirms the payment to "Hevy Pro" for 102.00 USD
  Then "Hevy Pro" is described as 400000.00 COP every 1 year
```

## AC-9 — The balance moves by the figure in the account's currency

```gherkin
@backend
Scenario: The dollar account falls by the dollars, never by the pesos
  Given today is 2026-07-15
  And the TRM is 4000
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  And a repeating payment of 400000.00 COP to "Hevy Pro" from "DolarApp" every 1 year starting 2026-07-15 in category "Suscripciones", waiting for approval
  And the daily run happens
  When the user confirms the payment to "Hevy Pro" for 102.00 USD
  Then "DolarApp" has balance 898.00 USD

@backend
Scenario: Accepting the offered figure moves exactly that
  Given today is 2026-07-15
  And the TRM is 4000
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  And a repeating payment of 400000.00 COP to "Hevy Pro" from "DolarApp" every 1 year starting 2026-07-15 in category "Suscripciones", waiting for approval
  And the daily run happens
  When the user confirms the payment to "Hevy Pro" for 100.00 USD
  Then "DolarApp" has balance 900.00 USD
```

## AC-10 — Without a rate there is no offer, but there is a confirmation

```gherkin
Scenario: The box arrives empty and says why
  Given the app is open
  And no TRM has been set
  And an account "DolarApp" in USD
  And a payment waiting to "Hevy Pro" of 400000.00 COP from "DolarApp"
  When the owner opens the confirmation
  Then no amount is offered
  And the confirmation says the rate is missing

@backend
Scenario: A figure written by hand is taken without any rate
  Given today is 2026-07-15
  And no TRM has been set
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  And a repeating payment of 400000.00 COP to "Hevy Pro" from "DolarApp" every 1 year starting 2026-07-15 in category "Suscripciones", waiting for approval
  And the daily run happens
  When the user confirms the payment to "Hevy Pro" for 102.00 USD
  Then "Hevy Pro" was charged 102.00 USD 2026-07-15
  And "DolarApp" has balance 898.00 USD
```

## AC-11 — Confirming from another account still works

```gherkin
@backend
Scenario: The account that really paid is the one charged
  Given today is 2026-07-15
  And the TRM is 4000
  And an account "DolarApp" in USD with balance 1000.00 USD
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And a category "Suscripciones"
  And a repeating payment of 400000.00 COP to "Hevy Pro" from "DolarApp" every 1 year starting 2026-07-15 in category "Suscripciones", waiting for approval
  And the daily run happens
  When the user confirms the payment to "Hevy Pro" from "Nu Debito" for 400000.00 COP
  Then "Nu Debito" has balance 600000.00 COP
  And "DolarApp" has balance 1000.00 USD

@backend
Scenario: The rule keeps declaring its own account
  Given today is 2026-07-15
  And the TRM is 4000
  And an account "DolarApp" in USD with balance 1000.00 USD
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And a category "Suscripciones"
  And a repeating payment of 400000.00 COP to "Hevy Pro" from "DolarApp" every 1 year starting 2026-07-15 in category "Suscripciones", waiting for approval
  And the daily run happens
  When the user confirms the payment to "Hevy Pro" from "Nu Debito" for 400000.00 COP
  Then "Hevy Pro" is charged to "DolarApp"
```

## AC-12 — A rule whose price and account agree behaves exactly as before

```gherkin
@backend
Scenario: It can still pay itself
  Given today is 2026-07-15
  And the TRM is 4000
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  And a repeating payment of 40.00 USD to "Opal" from "DolarApp" every 1 month starting 2026-07-15 in category "Suscripciones", paying itself
  When the daily run happens
  Then the turn of "Opal" due 2026-07-15 is recorded as paid
  And "DolarApp" has balance 960.00 USD

@backend
Scenario: Nothing is converted anywhere along the way
  Given today is 2026-07-15
  And no TRM has been set
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  And a repeating payment of 40.00 USD to "Opal" from "DolarApp" every 1 month starting 2026-07-15 in category "Suscripciones", paying itself
  When the daily run happens
  Then "Opal" was charged 40.00 USD 2026-07-15
  And "DolarApp" has balance 960.00 USD
```

## AC-13 — Moving the account offers the conversion, and demands it only when the rule pays itself

```gherkin
Scenario: The move offers a figure in the new account's currency
  Given the app is open
  And the TRM is 4000
  And an account "DolarApp" in USD
  And an account "Nu Debito" in COP
  And a repeating charge "Opal" of 40.00 USD from "DolarApp"
  When the owner moves "Opal" to "Nu Debito"
  Then the amount offered is 160000.00 COP

@backend
Scenario: A rule waiting for approval may decline the conversion
  Given today is 2026-07-01
  And the TRM is 4000
  And an account "DolarApp" in USD with balance 1000.00 USD
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And a category "Suscripciones"
  And a repeating payment of 40.00 USD to "Opal" from "DolarApp" every 1 month starting 2026-07-15 in category "Suscripciones", waiting for approval
  When the user moves "Opal" to the account "Nu Debito"
  Then "Opal" is described as 40.00 USD every 1 month
  And "Opal" is charged to "Nu Debito"

@backend
Scenario: A rule waiting for approval may accept it
  Given today is 2026-07-01
  And the TRM is 4000
  And an account "DolarApp" in USD with balance 1000.00 USD
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And a category "Suscripciones"
  And a repeating payment of 40.00 USD to "Opal" from "DolarApp" every 1 month starting 2026-07-15 in category "Suscripciones", waiting for approval
  When the user moves "Opal" to the account "Nu Debito" restating it at 160000.00 COP
  Then "Opal" is described as 160000.00 COP every 1 month
  And "Opal" is charged to "Nu Debito"

@backend
Scenario: A rule that pays itself must accept it
  Given today is 2026-07-01
  And the TRM is 4000
  And an account "DolarApp" in USD with balance 1000.00 USD
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And a category "Suscripciones"
  And a repeating payment of 40.00 USD to "Opal" from "DolarApp" every 1 month starting 2026-07-15 in category "Suscripciones", paying itself
  When the user tries to move "Opal" to the account "Nu Debito"
  Then the change to "Opal" is rejected
  And "Opal" is charged to "DolarApp"

@backend
Scenario: A rule that pays itself moves once the figure is restated
  Given today is 2026-07-01
  And the TRM is 4000
  And an account "DolarApp" in USD with balance 1000.00 USD
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And a category "Suscripciones"
  And a repeating payment of 40.00 USD to "Opal" from "DolarApp" every 1 month starting 2026-07-15 in category "Suscripciones", paying itself
  When the user moves "Opal" to the account "Nu Debito" restating it at 160000.00 COP
  Then "Opal" is described as 160000.00 COP every 1 month
  And "Opal" is charged to "Nu Debito"

@backend
Scenario: The app never switches the mode by itself
  Given today is 2026-07-01
  And the TRM is 4000
  And an account "DolarApp" in USD with balance 1000.00 USD
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And a category "Suscripciones"
  And a repeating payment of 40.00 USD to "Opal" from "DolarApp" every 1 month starting 2026-07-15 in category "Suscripciones", paying itself
  When the user tries to move "Opal" to the account "Nu Debito"
  Then the change to "Opal" is rejected
  And "Opal" still pays itself
```

## AC-14 — A charge already waiting keeps the price it was born with

```gherkin
@backend
Scenario: Raising the rule's price leaves the waiting charge alone
  Given today is 2026-07-15
  And the TRM is 4000
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  And a repeating payment of 400000.00 COP to "Hevy Pro" from "DolarApp" every 1 year starting 2026-07-15 in category "Suscripciones", waiting for approval
  And the daily run happens
  When the user changes the amount of "Hevy Pro" to 440000.00 COP
  Then "Hevy Pro" was charged 400000.00 COP 2026-07-15
  And "Hevy Pro" is described as 440000.00 COP every 1 year
```

## AC-15 — Charges already recorded are never touched

```gherkin
@backend
Scenario: A recorded charge keeps its figure when the rule's price changes
  Given today is 2026-07-15
  And the TRM is 4000
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  And a repeating payment of 400000.00 COP to "Hevy Pro" from "DolarApp" every 1 year starting 2026-07-15 in category "Suscripciones", waiting for approval
  And the daily run happens
  And the user confirms the payment to "Hevy Pro" for 102.00 USD
  When the user changes the amount of "Hevy Pro" to 440000.00 COP
  Then "Hevy Pro" was charged 102.00 USD 2026-07-15
  And "DolarApp" has balance 898.00 USD

@backend
Scenario: A recorded charge keeps its figure when the rule's account changes
  Given today is 2026-07-15
  And the TRM is 4000
  And an account "DolarApp" in USD with balance 1000.00 USD
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And a category "Suscripciones"
  And a repeating payment of 400000.00 COP to "Hevy Pro" from "DolarApp" every 1 year starting 2026-07-15 in category "Suscripciones", waiting for approval
  And the daily run happens
  And the user confirms the payment to "Hevy Pro" for 102.00 USD
  When the user moves "Hevy Pro" to the account "Nu Debito"
  Then "Hevy Pro" was charged 102.00 USD 2026-07-15
  And "DolarApp" has balance 898.00 USD
  And "Nu Debito" has balance 1000000.00 COP
```

## AC-16 — The refusals that already exist go on refusing

```gherkin
@backend
Scenario Outline: A declaration that cannot hold is still refused
  Given today is 2026-07-01
  And the TRM is 4000
  And an account "DolarApp" in USD with balance 1000.00 USD
  And an archived account "Vieja" in COP
  And a category "Suscripciones"
  When the user tries to declare a repeating payment of <amount> <currency> to "Hevy Pro" from "<account>" every <count> <unit> starting 2026-07-15 in category "Suscripciones", waiting for approval
  Then the declaration is rejected
  And "DolarApp" has balance 1000.00 USD

  Examples:
    | amount     | currency | account   | count | unit  |
    | 0.00       | COP      | DolarApp  | 1     | year  |
    | -400000.00 | COP      | DolarApp  | 1     | year  |
    | 400000.00  | XYZ      | DolarApp  | 1     | year  |
    | 400000.00  | COP      | Vieja     | 1     | year  |
    | 400000.00  | COP      | Fantasma  | 1     | year  |
    | 400000.00  | COP      | DolarApp  | 0     | year  |

@backend
Scenario: A repeating transfer is still refused, whatever its currency
  Given today is 2026-07-01
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  When the user tries to declare a repeating transfer of 400000.00 COP from "DolarApp" every 1 year starting 2026-07-15 in category "Suscripciones", waiting for approval
  Then the declaration is rejected
```

## AC-17 — The assistant is neither given anything nor taken anything away

```gherkin
@backend
Scenario: The assistant can declare what the app can declare
  Given today is 2026-07-01
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  When the assistant declares a repeating payment of 400000.00 COP to "Hevy Pro" from "DolarApp" every 1 year starting 2026-07-15 in category "Suscripciones", waiting for approval
  Then "Hevy Pro" is described as 400000.00 COP every 1 year

@backend
Scenario: The assistant is refused exactly where the app is refused
  Given today is 2026-07-01
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  When the assistant tries to declare a repeating payment of 400000.00 COP to "Hevy Pro" from "DolarApp" every 1 year starting 2026-07-15 in category "Suscripciones", paying itself
  Then the declaration is rejected
```

## AC-18 — A waiting charge counts by its own currency

```gherkin
@backend
Scenario: The month reads the waiting charge as pesos, not as dollars
  Given today is 2026-07-15
  And the TRM is 4000
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  And a repeating payment of 400000.00 COP to "Hevy Pro" from "DolarApp" every 1 year starting 2026-07-15 in category "Suscripciones", waiting for approval
  When the daily run happens
  Then the month 2026-07 reports 400000.00 COP still unconfirmed

@backend
Scenario: A waiting charge in the account's own currency is read the same way
  Given today is 2026-07-15
  And the TRM is 4000
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  And a repeating payment of 40.00 USD to "Opal" from "DolarApp" every 1 month starting 2026-07-15 in category "Suscripciones", waiting for approval
  When the daily run happens
  Then the month 2026-07 reports 160000.00 COP still unconfirmed
```

## AC-19 — The migration leaves the two rules with their true price

These carry the owner's real figures rather than the suite's round ones: what
they assert is those exact numbers on those exact rules.

```gherkin
@backend
Scenario: Hevy Pro comes out priced in pesos, waiting for approval, on DolarApp
  Given today is 2026-08-11
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  And a repeating payment of 30.22 USD to "Hevy Pro" from "DolarApp" every 1 year starting 2026-07-15 in category "Suscripciones", paying itself
  When the stored prices are migrated
  Then "Hevy Pro" is described as 99900.00 COP every 1 year
  And "Hevy Pro" is charged to "DolarApp"
  And "Hevy Pro" waits for approval

@backend
Scenario: Smart Fit comes out priced in pesos, waiting for approval, on DolarApp
  Given today is 2026-08-11
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  And a repeating payment of 37.20 USD to "Smart Fit" from "DolarApp" every 1 month starting 2026-08-01 in category "Suscripciones", paying itself
  When the stored prices are migrated
  Then "Smart Fit" is described as 120000.00 COP every 1 month
  And "Smart Fit" is charged to "DolarApp"
  And "Smart Fit" waits for approval

@backend
Scenario: The migration moves no money and rewrites no recorded charge
  Given today is 2026-08-11
  And the TRM is 4000
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  And a repeating payment of 30.22 USD to "Hevy Pro" from "DolarApp" every 1 year starting 2026-07-15 in category "Suscripciones", paying itself
  And the daily run happens
  When the stored prices are migrated
  Then "Hevy Pro" was charged 30.22 USD 2026-07-15
  And "DolarApp" has balance 969.78 USD

@backend
Scenario: A rule the migration does not name is left exactly as it was
  Given today is 2026-08-11
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  And a repeating payment of 9.99 USD to "Opal" from "DolarApp" every 1 month starting 2026-08-01 in category "Suscripciones", paying itself
  When the stored prices are migrated
  Then "Opal" is described as 9.99 USD every 1 month
  And "Opal" still pays itself
```

## AC-20 — The migration carries the prices, it does not compute them

```gherkin
@backend
Scenario: The written price is the merchant's, not a conversion
  Given today is 2026-08-11
  And the TRM is 3142
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  And a repeating payment of 30.22 USD to "Hevy Pro" from "DolarApp" every 1 year starting 2026-07-15 in category "Suscripciones", paying itself
  When the stored prices are migrated
  Then "Hevy Pro" is described as 99900.00 COP every 1 year

@backend
Scenario: A different rate produces the very same price
  Given today is 2026-08-11
  And the TRM is 4400
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  And a repeating payment of 30.22 USD to "Hevy Pro" from "DolarApp" every 1 year starting 2026-07-15 in category "Suscripciones", paying itself
  When the stored prices are migrated
  Then "Hevy Pro" is described as 99900.00 COP every 1 year

@backend
Scenario: No rate at all produces the very same price
  Given today is 2026-08-11
  And no TRM has been set
  And an account "DolarApp" in USD with balance 1000.00 USD
  And a category "Suscripciones"
  And a repeating payment of 37.20 USD to "Smart Fit" from "DolarApp" every 1 month starting 2026-08-01 in category "Suscripciones", paying itself
  When the stored prices are migrated
  Then "Smart Fit" is described as 120000.00 COP every 1 month
```

## AC-21 — A charge shows the price of the rule that produced it

```gherkin
Scenario: The recorded charge carries its rule's price beside it
  Given the app is open
  And the TRM is 4000
  And an account "DolarApp" in USD
  And a repeating charge "Hevy Pro" of 400000.00 COP from "DolarApp"
  And a charge to "Hevy Pro" recorded as 102.00 USD from "DolarApp"
  When the owner opens the movement
  Then the movement reads 102.00 USD
  And the movement names the rule price 400000.00 COP

Scenario: A charge whose rule agrees with its account shows nothing extra
  Given the app is open
  And the TRM is 4000
  And an account "DolarApp" in USD
  And a repeating charge "Opal" of 40.00 USD from "DolarApp"
  And a charge to "Opal" recorded as 40.00 USD from "DolarApp"
  When the owner opens the movement
  Then the movement reads 40.00 USD
  And the movement names no rule price

Scenario: A movement that came from no rule shows nothing extra
  Given the app is open
  And the TRM is 4000
  And an account "DolarApp" in USD
  And a movement to "Amazon" recorded as 25.00 USD from "DolarApp"
  When the owner opens the movement
  Then the movement reads 25.00 USD
  And the movement names no rule price

Scenario: A charge from a rule that was switched off shows nothing extra
  Given the app is open
  And the TRM is 4000
  And an account "DolarApp" in USD
  And a repeating charge "Hevy Pro" of 400000.00 COP from "DolarApp"
  And a charge to "Hevy Pro" recorded as 102.00 USD from "DolarApp"
  And "Hevy Pro" has been switched off
  When the owner opens the movement
  Then the movement reads 102.00 USD
  And the movement names no rule price
```
