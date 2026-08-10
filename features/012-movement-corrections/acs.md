---
ac_count: 30
high_priority_count: 23
discovered: 2026-08-10
---

# Acceptance criteria — 012 movement-corrections

Discovered 2026-08-10 with the owner, in the same session as the two discuss
rounds that decided the feature's shape. Every open question those rounds left
is answered here, and every figure quoted was read from the production database
the same day, read-only.

## The two rules

Everything below derives from these. Where an AC seems to add something new, it
is one of these applied to a surface.

**1 — The record survives the correction.** A correction changes exactly the
fields it names. The movement keeps its identity, its date, its beneficiary, its
category, its tags, the meta it is pointed at, and the recurring due date it
hangs from. Deleting and recreating is the thing this feature exists to stop
being necessary: today it loses all of that, and for an engine-made charge it
also marks that month's due date *omitido* forever (ADR-0038).

**2 — No money figure moves without being seen, and no correction is saved
unless the arithmetic proves out.** Whenever a correction implies a new figure —
a currency changed, a transfer's other leg — the app shows the figure it would
use and the owner accepts it or replaces it. It is never applied silently. After
the write, both balances must have moved by exactly the deltas the correction
declared; anything else undoes the whole correction and says so.

## What must never be built

Rebuilding `account.balance` from the sum of its movements. Six of nine accounts
disagree with that sum — Nu Débito by $2.101.837,94, Emergency Fund by
$22.435.146,28 — and none is an error: an account's opening figure is written
straight to its balance and appears in no movement. Writing the sum in would
destroy $2.101.837,94 of real money on Nu Débito alone. The gap between the
stored balance and the movements is data the app never recorded, and closing it
is `id:account-opening-balance-and-audit`, not this feature.

---

## AC-1: Confirming a payment says which account it came out of

- **Priority:** high
- **Type:** happy-path

The dialog that confirms a planned payment offers the account alongside the
amount and the date. The account chosen when the payment was planned comes
already selected, so a payment that came out of the expected account is still
confirmed in one click, exactly as it is today.

Accounts are named, never numbered.

## AC-2: Confirming from a different account charges that account, not the planned one

- **Priority:** high
- **Type:** happy-path

Hogaru is planned on the 1st against Nu Débito for $275.000 and is actually paid
on the 3rd from RappiCard. Confirming it with RappiCard chosen leaves Nu Débito
untouched and takes $275.000 out of RappiCard.

## AC-3: Every account is offered, including accounts in another currency

- **Priority:** high
- **Type:** happy-path

The list is not filtered to the planned account's currency. DolarApp appears
beside Nu Débito.

## AC-4: Choosing an account in another currency offers the converted amount

- **Priority:** high
- **Type:** happy-path

Hogaru's $275.000 planned against Nu Débito, confirmed against DolarApp, offers
**US$87,52** — the division at the app's single rate, 3.142 — already filled in.
The owner may accept it or replace it with what the statement actually says. He
is never made to compute it, and the app never applies it without him seeing it.

## AC-5: A payment confirmed against a foreign-currency account is stored in that currency

- **Priority:** high
- **Type:** happy-path

The movement is then a dollar movement of US$87,52, and its peso value is
derived when read, at the rate of the day it is read (ADR-0031). No rate is
frozen onto it.

## AC-6: Confirming from another account is a one-month exception

- **Priority:** high
- **Type:** happy-path

Hogaru confirmed from RappiCard in August still says Nu Débito in September. The
recurring item's declared account is not touched, not learned from, and not
suggested against. Moving an obligation to a different account for good is done
once, on the obligation itself.

## AC-7: A movement already recorded can move to another account

- **Priority:** high
- **Type:** happy-path

From the movements screen the owner changes which account a recorded expense or
income came out of. The account it left gets the money back; the account it
actually came out of gives it up. Both figures change by the same amount.

## AC-8: A movement's amount can be corrected on its own

- **Priority:** high
- **Type:** happy-path

Tigo was written down as $93.558 and the statement says $95.200. The owner
changes the number. Nu Débito drops by the difference, $1.642, and nothing else
about the movement changes.

## AC-9: A corrected movement is still the same movement

- **Priority:** high
- **Type:** happy-path

After any correction the movement keeps its date, its beneficiary, its category,
its tags, the meta it was pointed at, and its place in every list it was already
in. Nothing has to be typed again.

## AC-10: Each leg of a transfer moves account on its own

- **Priority:** high
- **Type:** happy-path

A transfer has two halves — what left one account and what arrived in another.
The owner corrects which account the money left without saying anything about
where it arrived, and the other way round.

## AC-11: In a same-currency transfer the two halves always carry the same amount

- **Priority:** high
- **Type:** happy-path

$500.000 left Préstamos a terceros and $500.000 arrived at Nu Débito. Correcting
either half to $520.000 moves both to $520.000. Money never appears or
disappears between the two halves of a transfer in one currency.

All 22 same-currency transfers in production carry equal halves today; nothing
models a fee, and this feature does not introduce one.

## AC-12: A transfer across currencies asks for both figures

- **Priority:** high
- **Type:** happy-path

US$1.556,04 left DolarApp and $5.000.000 arrived at Préstamos a terceros. The
two halves are genuinely different numbers, so correcting such a transfer asks
what left and what arrived, and neither is derived from the other.

## AC-13: Moving a leg into another currency offers the converted figure

- **Priority:** high
- **Type:** happy-path

The half reading *US$1.556,04 arrived at DolarApp* is moved to Nu Débito, which
holds pesos. It can no longer be dollars. The app offers **$4.889.078** — the
multiplication at 3.142 — already filled in, and the owner accepts or replaces
it. The same behaviour as confirming a payment (AC-4); the two screens do not
differ.

## AC-14: The screen stops telling the owner to delete and recreate

- **Priority:** high
- **Type:** happy-path

The edit dialog says today, in small type, *"Para cambiar monto/cuenta, elimina
y vuelve a crear."* When this ships, that instruction is false and is gone. The
same dialog also shows the account as `cuenta #5`; it shows its name.

## AC-15: An archived account is never offered as a destination

- **Priority:** high
- **Type:** edge-case

Korea is archived. It appears nowhere in the account list of a confirm or a
correction. Archiving an account means nothing new lands in it.

## AC-16: A movement can still be moved *out* of an archived account

- **Priority:** medium
- **Type:** edge-case

The refusal is one-directional. Archiving says *put nothing new here*, not *what
is here is stuck*. Korea holds no movements in production, so this decides a
rule rather than a case.

## AC-17: Correcting a purchase does not reopen the meta it completed

- **Priority:** high
- **Type:** edge-case

The iPhone was bought for $7.000.000 and the meta closed. Correcting that
purchase — to another account, to another currency, to another number — leaves
the meta exactly as it is: still fulfilled, still closed, none of its figures
recomputed. The purchase stops the meta and nothing after that moves it
(ADR-0048).

## AC-18: Correcting an engine-made charge keeps it attached to its due date

- **Priority:** high
- **Type:** edge-case

Deleting an engine-made charge deliberately marks that month's due date
*omitido* and unlinks it, because the money came back and the date must not stay
marked charged while pointing at a row that no longer exists (ADR-0038).
Correcting keeps the row, so none of that reasoning applies: August's Hogaru
stays August's Hogaru, charged, linked, corrected.

## AC-19: Correcting one month never teaches the obligation

- **Priority:** high
- **Type:** edge-case

August's Hogaru corrected to $282.000 leaves the recurring item declaring
$275.000. September asks for $275.000. The declaration is changed on the
declaration, never by side effect.

## AC-20: A movement that has not moved money corrects without moving any

- **Priority:** medium
- **Type:** edge-case

A payment still waiting to be confirmed, or one that was skipped, never moved a
balance. Correcting its account or its amount moves none either — only what it
will ask for when it is confirmed.

## AC-21: A correction that changes nothing changes nothing

- **Priority:** medium
- **Type:** edge-case

Opening the dialog and saving without touching anything leaves every balance
where it was. Confirming the same correction twice does not charge twice.

## AC-22: A transfer's two halves cannot end up on the same account

- **Priority:** medium
- **Type:** edge-case

Moving one half onto the account the other half already uses is refused. A
transfer from an account to itself is not a transfer.

## AC-23: A correction proves its own arithmetic, or none of it happens

- **Priority:** high
- **Type:** error

Before the correction the app reads both balances. It knows exactly how much
each must move. After the correction it reads them again, and if either moved by
anything other than that exact figure — including not moving at all — the whole
correction is undone, both accounts are left as they were, and the owner is told
it did not go through.

The check is deliberately blind to what the balances were. An account that
already disagrees with the sum of its movements by $2.101.837,94 disagrees by
exactly $2.101.837,94 afterwards. This neither repairs old drift nor creates
new drift, which is the pair of failures it exists to prevent: a change that
silently is not saved, and a balance moved by more than the movement.

## AC-24: A correction never leaves a movement worth nothing or less

- **Priority:** high
- **Type:** error

An amount of zero or a negative amount is refused, in every currency, on every
surface, exactly as it is when the movement is first recorded.

## AC-25: A correction pointing at an account that does not exist is refused

- **Priority:** medium
- **Type:** error

Nothing is written and no balance moves.

## AC-26: A corrected movement still obeys what a movement must carry

- **Priority:** high
- **Type:** error

An expense still carries an expense category and an income an income category;
a transfer still carries none (ADR-0042). A correction cannot be used as a way
around a rule that holds for the life of the movement.

## AC-27: A correction cannot be triggered from outside the app

- **Priority:** low
- **Type:** error

Corrections are the only path that moves two stored balances at once. They are
protected exactly as every other write in the app is (ADR-0020).

## AC-28: The assistant gains nothing

- **Priority:** high
- **Type:** cross-cutting

The assistant keeps the tools it has and gets no new ability to correct a
movement, move it between accounts, or change what it is worth. Correcting is
done on a screen where the owner sees what he is changing before it happens.
This is a deliberate refusal, decided 2026-08-10, not an omission to be closed
later.

## AC-29: A correction moves balances and nothing else

- **Priority:** high
- **Type:** cross-cutting

Budgets, funds, metas, the savings split and the money-available figure are
computed without ever asking which account a movement came out of. Moving a
movement between accounts changes two balances and not one other figure on any
screen. Correcting an amount changes what its category spent, exactly as
recording that amount in the first place would have.

## AC-30: The account and the amount are reachable the way every other field is

- **Priority:** medium
- **Type:** cross-cutting

The new controls carry labels that belong to them, so each is reachable by its
label like every other field in the same dialog. Feature 009 shipped two
controls in the plan dialog that were not, and it was found only afterwards.
