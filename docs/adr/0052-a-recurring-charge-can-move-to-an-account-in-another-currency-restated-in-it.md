# 0052. A recurring charge can move to an account in another currency, restated in it

- **Status:** accepted
- **Date:** 2026-08-11
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

`update_recurring` declares in its own docstring that *"type and currency are
immutable"*, and `RecurringUpdate` carries no `currency` field, so moving a
recurring charge to an account that holds another currency is refused at
`services/recurring.py:257`. No ADR ever decided that — it is a rule that exists
only in a docstring and a guard.

The refusal became visible while fixing
`.engineer/fixes/2026-08-11-a-recurring-charge-cannot-live-in-a-dollar-account.md`,
which found that the screen hard-coded pesos and had no currency control at all.
Fixing the create path exposed the move path: the screen now relabels the amount
box to the chosen account's currency while leaving the stored cents alone, so a
$26.900 charge moved to a dollar account reads **US$26.900,00** — a figure 3.142
times the truth — and the save is refused anyway. Offering a wrong number that
leads to a dead end is the exact defect class feature 012 spent its verification
removing from three other screens.

The owner's real data is the reason this matters rather than being a tidy-up:
Opal, Hevy Pro, DolarApp Premium and Smart Fit are dollar subscriptions charged
to DolarApp, named by `id:fund-smooths-an-annual-charge` on the roadmap.

## Decision drivers

- **Nothing may show a figure it will not use.** Rule 2 of feature 012's ACs, and
  the reason ADR-0051 exists. A relabelled box that keeps the old cents breaks it.
- **What cannot be done should not be offered.** A dead end is a defect even when
  it refuses correctly.
- **The shape is already decided and already verified.** ADR-0051's `retarget`
  answers the identical question for a posted movement: pointing a row at an
  account in another currency requires the amount restated in that currency, and
  the app offers the conversion for the owner to accept or replace.
- **A recurring item holds no balance.** Changing its currency moves no money —
  it changes what future occurrences will ask for. Occurrences already
  materialized are ordinary transactions with their own currency and are not
  touched, which the docstring already promises for every other field.

## Considered options

1. **Offer only accounts holding the charge's own currency.** The picker hides the
   rest; the refusal becomes unreachable.
2. **Let the currency change, restated in the new one** — the `retarget` contract,
   applied to a recurring rule.
3. **Leave it refused and restate the box anyway.** The state the fix landed in.

## Decision outcome

Chosen option: **2 — let the currency change, restated in the new one**, decided
by the owner on 2026-08-11 over option 1, which was the cheaper recommendation
put to him.

**The currency follows the account and is never stated separately.** When the
destination account holds a different currency than the item, the new amount
**must** be stated in that currency; without it the move is refused, exactly as
`transactions.retarget` refuses. The screen offers the converted figure at the
app's single rate (ADR-0031) for the owner to accept or replace, never applying
it silently.

`RecurringUpdate` therefore grows **no** `currency` field. The account already
determines it — the guard being removed exists precisely to keep the two in
step — so a separate field could only ever agree redundantly or disagree
wrongly. `account_id` and `amount`, both already on the wire, are the whole
change.

Occurrences already materialized keep the currency they were written with. That
is not a special case — `update_recurring` has always said changes reach only
future un-materialized occurrences — and it composes with feature 012: an
occurrence already planned in the old currency is corrected one at a time through
`POST /transactions/{id}/correction`, which proves its own arithmetic.

### Pros and cons of the options

**1 — only same-currency accounts**
- Good, because it is one line on the screen and removes the dead end outright.
- Good, because it needs no backend change and no ADR.
- Bad, because it takes away something the owner can attempt today and answers
  his real need — a peso charge that moved to DolarApp — with "you cannot".
- Bad, because the workaround is to delete the rule and rebuild it, losing its
  history: the same delete-and-recreate that feature 012 exists to stop.

**2 — the currency changes, restated**
- Good, because it reuses a contract already accepted, implemented and
  mutation-tested (`retarget`, ADR-0051), rather than inventing a second shape
  for the same question.
- Good, because the owner's four dollar subscriptions become expressible without
  losing the rule that generates them.
- Bad / cost: a guard replaced by another guard, and their tests. Nothing grows
  on the wire — the currency is derived from the account rather than stated.

**3 — refuse but relabel**
- Bad, because it shows a figure 3.142× the truth and then refuses. Rejected
  outright: it is the defect, not a resolution of it.

## Consequences

- Good: the screen stops offering a move it cannot complete, and stops printing a
  number that is not the charge's.
- Good: one contract answers "this row points at an account in another currency"
  for both posted movements and recurring rules.
- Bad / cost: `type` stays immutable and now looks arbitrary beside a mutable
  currency. That asymmetry is real and deliberate — a type change would rewrite
  what the rule *means* (an expense becoming income), while a currency change
  restates what it asks for. If it ever needs revisiting it gets its own ADR.
- Bad / cost: an owner who moves a charge across currencies and had planned
  occurrences waiting will find them still stated in the old currency. That is
  the pre-existing rule for every other field, and correcting them one at a time
  is exactly what feature 012 shipped.

## Confirmation

Regression tests pin both halves before the change lands: moving a recurring
charge to an account in another currency without a restated amount is refused,
and with one, the item and its future occurrences are stated in the new currency.
On the screen, a vitest case asserts the box offers the converted figure rather
than relabelling the old cents — the assertion that would have caught the
US$26.900 the fix briefly produced.

`backend/scripts/mutate.py` over `services/recurring.py` is the standing check
that the new guard can actually fail; the module is not in any feature's opt-in
list today, so this ADR is where that debt is recorded.
