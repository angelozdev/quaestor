# 0051. A posted movement is restated, not destroyed, and every correction proves its own arithmetic

- **Status:** accepted
- **Date:** 2026-08-10
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

A posted movement's account, amount and currency cannot be changed. Nothing
records that as a decision: the only statement of it is a docstring on
`update_transaction` — *"amount/account/currency/type are immutable here, so no
balance ever moves"* — which describes what that function does, not a rule the
system holds. Feature 012 makes them changeable, so the rule has to be written
down before it is replaced.

The reason they were immutable is real: moving a posted row between accounts has
to move two stored balances, and `account.balance` is a stored column that
nothing recomputes. Firefly III allows the same edit and shipped two defects of
exactly this shape — [#4589](https://github.com/firefly-iii/firefly-iii/issues/4589),
a source/destination change that silently does not save, and
[#3921](https://github.com/firefly-iii/firefly-iii/issues/3921), balances
altered by past transactions — and ships a database-repair command for the
aftermath. The question is not whether to allow the edit, which the owner
decided; it is how to allow it without joining that list.

## Decision drivers

- **The record must survive.** Delete-and-recreate, the only remedy today, costs
  the movement its identity, category, tags and meta link, and for an
  engine-made charge it also marks that month's due date skipped and unlinks it
  (ADR-0038). The whole point of the feature is to stop paying that price.
- **The stored balance cannot be rebuilt.** `account` carries no opening-balance
  column, so the sum of a movement's history does not reproduce its balance —
  six of nine production accounts disagree with that sum, by up to
  $22.435.146,28, and none of those gaps is an error. Any design that recomputes
  a balance from movements destroys real money.
- **The dangerous path must be visible.** Corrections move two stored balances at
  once, which nothing else in the app does.
- **No new storage.** The owner declined the opening-balance column (and with it
  a migration, CHARTER §7 and the `migrations/**` autonomy cap) during the
  feature's discuss.

## Considered options

1. **Restate the row in place: reverse its balance effect, mutate it, re-apply,
   then verify both balances moved by exactly the declared deltas — reading them
   back from the database — or roll the whole thing back.**
2. **Delete and recreate under the covers**, preserving the fields by copying
   them onto the new row.
3. **Mutate the row and adjust the balances, with no verification** — the
   straightforward version, and what Firefly III does.
4. **Derive `account.balance` from the movements** and let corrections be plain
   row edits, so no balance arithmetic exists to get wrong.

## Decision outcome

Chosen option: **1 — restate in place, and prove the arithmetic before
committing.**

The reversal machinery it needs already exists and is already trusted:
`_delta_balance_of` and `_reverse_balance` in `services/transactions.py` are what
`delete_transaction` uses, and every one of production's 25 transfer pairs was
deleted through them. A correction is the same two halves as a delete followed by
a create — undo the effect, apply the new one — with the row kept rather than
thrown away.

The verification is what separates this from option 3, and one detail decides
whether it is real: **the two balances are re-read from the database after the
write, not from the session's in-memory copies.** Comparing in-memory objects
would only check the code against itself. Re-reading catches a change that was
computed correctly and never persisted, which is Firefly's #4589 exactly.

The check is deliberately blind to the starting figures. It asserts that each
account *moved by* its expected delta, never what it *is*. An account already
off by $2.101.837,94 is off by exactly that afterwards. This neither repairs old
drift nor creates new drift — auditing history needs the opening balance and is
`id:account-opening-balance-and-audit`, not this.

**Corrections do not enter through `update_transaction`.** That function's
promise — no balance ever moves — stays true, and correcting gets its own
explicitly named path through the service and the API. Folding balance-moving
fields into the balance-safe editor would hide the most dangerous write in the
app inside the most innocent one.

### Pros and cons of the options

**1 — Restate in place, verified**
- Good, because the movement keeps its identity and everything the correction did
  not name, which is the feature's entire purpose.
- Good, because it reuses reversal code already exercised by every delete rather
  than introducing a second way to move a balance.
- Good, because the failure mode that broke Firefly twice is detected and undone
  rather than persisted.
- Bad, because the correction path must be kept in step with any future change to
  how a movement affects a balance — mitigated by both paths sharing
  `_delta_balance_of`.

**2 — Delete and recreate under the covers**
- Good, because it reuses two existing operations with no new balance arithmetic.
- Bad, because the identity is still lost — a new row means a new id, and every
  pre-delete hook fires, so an engine-made charge would still have its due date
  marked skipped (ADR-0038). It reproduces the exact damage the feature exists to
  avoid, only invisibly.

**3 — Mutate and adjust, unverified**
- Good, because it is the least code.
- Bad, because it is precisely what Firefly III ships, and the two defects it
  produced are both silent: the owner would find a wrong balance months later by
  comparing against the bank, which is how RappiCard's balance came to be
  adjusted by hand on 2026-08-09 with no record of why.

**4 — Derive the balance from the movements**
- Good, because a derived figure cannot drift, and it is what the design
  literature recommends over a stored one.
- Bad, because it is not available: with no opening balance recorded, deriving
  Nu Débito's balance yields $4.128.707,68 against a real $6.230.545,62 —
  destroying $2.101.837,94. It becomes possible only after
  `id:account-opening-balance-and-audit`.

## Consequences

- Good: a movement can be corrected without losing its date, beneficiary,
  category, tags, meta link or recurring due date.
- Good: the two failure modes that produced Firefly's #4589 and #3921 are caught
  at write time and rolled back, so this feature cannot add to the drift the
  accounts already carry.
- Good: `update_transaction` keeps its guarantee, so the balance-safe editor
  stays balance-safe and reviewers can still tell the two apart by name.
- Bad / cost: two extra account reads per correction, and a correction path that
  must be kept in step with the balance rules — both accepted.
- Bad / cost: pre-existing drift stays invisible. This decision explicitly does
  not address it; `id:account-opening-balance-and-audit` does.
- Bad / cost: the assistant is left unable to correct anything (product decision,
  2026-08-10), so the MCP surface is deliberately not at parity with REST here —
  a documented exception to ADR-0009.

## Confirmation

- `features/012-movement-corrections/spec.md` AC-23 binds three scenarios to the
  verification: a balance that refuses to move, a balance that moves by more than
  declared, and one proving the check ignores what the balance was to begin with.
  All three assert the correction is rolled back and the owner told.
- Mutation testing covers `services/transactions.py` and `services/planned.py`
  for this feature (see `features/012-movement-corrections/plan.md`), so a
  verification that cannot fail is caught as a surviving mutant.
- The import-linter contracts already forbid a layer reaching upward; correcting
  adds no new edge, living beside the reversal code it reuses.
- A reviewer checks that no balance-moving field ever appears on
  `update_transaction` or its request model.
