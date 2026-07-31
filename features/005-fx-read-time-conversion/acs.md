---
ac_count: 14
high_priority_count: 8
discovered: 2026-07-30
---

# Acceptance criteria — 005 fx-read-time-conversion

Discovered 2026-07-30 (Checkpoint 2). Source material: ADR-0031, discuss
handoff 2026-07-30, current FX/transfer code. Key decision made during
discovery (amends ADR-0031): **the TRM is a single scalar value — the dated
rate table is dropped**. Under "everything at the current rate", correcting a
past date's rate changes nothing, so a dated series stores history no read
ever uses; storage now matches the chosen semantic.

## AC-1: Register foreign-currency transactions without a rate

- **Priority:** high
- **Type:** happy-path

Registering an expense or income in USD asks only for the amount and the
currency — there is no rate field anywhere in the flow. Registration
succeeds even when no TRM has been set yet; nothing about conversion is
recorded with the transaction.

## AC-2: Base-currency figures are computed at read time from the TRM

- **Priority:** high
- **Type:** happy-path

Every COP figure the app shows — reports, budgets, monthly summaries, goal
progress, planned and recurring items, and each transaction's COP
equivalent — is computed at the moment it is read, as the original amount
converted at the current TRM. No converted amount is ever stored alongside
a transaction.

## AC-3: Correcting the TRM retroactively updates every figure

- **Priority:** high
- **Type:** happy-path

When the user changes the TRM, every report, budget and total — including
already-closed months — reflects the new value on the next read, with no
re-registration or recalculation step. Closed months' totals moving with
the TRM is accepted behavior, not a defect (user decision, ADR-0031).

## AC-4: COP amounts are unaffected by the TRM

- **Priority:** high
- **Type:** happy-path

Transactions in COP convert at identity. Changing the TRM never alters any
pure-COP figure.

## AC-5: The TRM is a single value kept fresh by the daily job

- **Priority:** medium
- **Type:** happy-path

The TRM is one value, not a dated series. The daily job overwrites it each
day; the user can overwrite it manually at any time. Last write wins; the
app presents exactly one "current TRM".

## AC-6: Cross-currency transfers record two physical amounts

- **Priority:** high
- **Type:** happy-path

A transfer between accounts in different currencies takes two explicit
amounts: what was sent (in the source account's currency) and what was
received (in the destination account's currency). The source balance
decreases by the sent amount; the destination balance increases by the
received amount. No rate is stored — the effective rate is implicit in the
ratio of the two amounts.

## AC-7: Same-currency transfers keep working with one amount

- **Priority:** medium
- **Type:** happy-path

A transfer between accounts in the same currency asks for a single amount,
and both balances move by that amount — behavior unchanged from today.

## AC-8: The implied transfer rate is shown as information only

- **Priority:** low
- **Type:** edge-case

When the two accounts' currencies differ, the transfer dialog shows the
implied rate (received ÷ sent) live as the user types, as reference
information only. Any pair of positive amounts is accepted — they are
physical facts of what the bank moved; no ratio is validated or blocked.

## AC-9: Reads fail loud when no TRM is set

- **Priority:** high
- **Type:** error

If no TRM has ever been set, any read that computes base-currency figures
fails with a clear error telling the user to set the TRM — even when all
underlying data is COP (user decision: always require the rate). The app
never silently assumes a rate of 1. Once the TRM is set, the same reads
succeed without further action.

## AC-10: Invalid TRM values are rejected

- **Priority:** medium
- **Type:** error

Setting the TRM to zero or a negative value is rejected with a clear
message; the previously set value (if any) remains in effect.

## AC-11: Invalid transfer input is rejected atomically

- **Priority:** medium
- **Type:** error

A cross-currency transfer missing either amount, or with a zero or negative
amount, is rejected. A transfer where source and destination are the same
account is rejected. On rejection nothing is recorded and no balance moves.

## AC-12: Migration preserves original amounts and drops stored conversions

- **Priority:** high
- **Type:** cross-cutting

A one-time migration on real data removes the per-transaction frozen
conversions and the dated rate history. Every historical transaction keeps
its original amount and currency; afterwards all figures compute per AC-2.
The migration runs with the human at the wheel (low-autonomy path per the
manifest) and a backup (`just backup`) is taken immediately before.

## AC-13: REST and MCP surfaces stay in parity

- **Priority:** high
- **Type:** cross-cutting

Both surfaces expose the same read-time-computed figures (parity per
ADR-0006/0009); MCP formatted output shows COP equivalents computed at
read time, identical to what the UI shows for the same data.

## AC-14: Conversion rounding is consistent

- **Priority:** low
- **Type:** cross-cutting

USD→COP conversion rounds half-up to the COP cent, and the same amount at
the same TRM produces the identical COP figure on every surface.
