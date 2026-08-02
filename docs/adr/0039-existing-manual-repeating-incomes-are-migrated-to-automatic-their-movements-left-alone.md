# 0039. Existing manual repeating incomes are migrated to automatic, their movements left alone

- **Status:** accepted
- **Date:** 2026-08-02
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

Feature 007's AC-6 refuses a repeating income in `manual` mode: it produces a
`planned` income transaction, and the outstanding queue shows only money going
out (feature 006, AC-15), so that money waits in a room with no door — no
screen can confirm it, and another one appears every period.

`create_recurring` and `update_recurring` now refuse the combination. That
closes the door for new rows and says nothing about the rows that predate it.
`consistency-check` raised this as W8 and the plan parked it as a human-gated
step: count them in production first. The count came back as one row in the dev
sandbox (`Salario`, 3.000.000 COP monthly, not yet started, zero occurrences);
production is the local Postgres and is counted by the human when the migration
runs.

Two questions had to be answered separately: what happens to the **item**, and
what happens to the **transactions it already produced**.

## Decision drivers

- **A validation that only guards the front door leaves the house full.** An
  untouched manual income keeps producing unconfirmable money after the rule
  lands, which is the exact defect AC-6 exists to remove.
- **The engine is the only surface that moves a balance unattended.** Anything
  a migration posts is money moving without the user ever agreeing to it.
- **A transaction is history.** ADR-0005's whole stance is that the ledger is
  append-mostly and is never rewritten to tidy something up.
- **Whether an expected income actually arrived is knowable only by the user.**
  The migration cannot tell "the salary came, nobody recorded it" from "the
  salary never came".
- **The rule must hold everywhere the schema does.** Dev sandbox, the in-memory
  databases the test suite builds, and production Postgres.

## Considered options

**For the item:**

1. **Flip `mode` to `auto`.** Every existing repeating income starts recording
   itself from its next due date.
2. **Leave existing rows and grandfather them.** The rule applies to new
   declarations only.
3. **Switch the item off** (`active = false`) and let the user re-declare.

**For the transactions already materialized as `planned`:**

4. **Leave them exactly as they are.**
5. **Post them**, moving the balance by each amount.
6. **Cancel them** (`skipped`), which moves no balance and empties the limbo.

## Decision outcome

Chosen: **Option 1 for the item, Option 4 for its transactions.**

Flipping the mode is the only option that actually closes the defect. Option 2
leaves the orphan producing more orphans — the validation would be decoration.
Option 3 is worse than the disease: switching off a salary silently stops a
real obligation the user still has, and costs them a re-declaration.

Leaving the already-materialized transactions alone is chosen because the two
alternatives both destroy information a migration has no standing to judge.
Posting them (Option 5) moves real balances by amounts the user never
confirmed — the engine's one dangerous power, exercised retroactively and in
bulk. Cancelling them (Option 6) moves no money but erases the record that this
income was expected, which may be exactly what the user wants to look at when
reconciling. Which of the two is right differs per row, so it is a decision for
the user, not for a migration. The migration reports how many rows it changed
so the human can go looking.

Revision `0009` therefore does one `UPDATE`: `mode = 'auto'` where
`type = 'income' AND mode = 'manual'`. `downgrade` is a no-op — restoring
`manual` would recreate the orphan, and the service layer would refuse to save
it anyway.

### Pros and cons of the options

**Option 1 — flip the mode**
- Good, because the defect is actually gone rather than merely fenced off.
- Good, because it is the state the user would have chosen had the rule existed.
- Bad, because an income the user deliberately wanted to confirm by hand now
  records itself. That intent had no working surface anyway, which is the point.

**Option 2 — grandfather existing rows**
- Good, because it touches no data.
- Bad, because the orphan keeps producing one unconfirmable income per period,
  forever. The validation becomes documentation.

**Option 3 — switch the item off**
- Good, because nothing is recorded that the user did not re-approve.
- Bad, because a live obligation silently stops and the user finds out by
  noticing money missing from a forecast.

**Option 4 — leave the transactions**
- Good, because no balance moves and no record is destroyed.
- Bad, because the `planned` rows stay in the ledger with no screen that
  resolves them. They are inert — feature 006 keeps them out of the queue and
  they never touch a balance — but they are untidy.

**Option 5 — post them**
- Good, because the limbo empties and the balance reflects money that probably
  did arrive.
- Bad, because "probably" is doing far too much work for an operation that
  moves real money in bulk with no confirmation.

**Option 6 — cancel them**
- Good, because the limbo empties and no balance moves.
- Bad, because it destroys the record that this money was expected, which is
  the only trace the user has to reconcile against.

## Consequences

- Good: after `0009`, the combination that AC-6 forbids does not exist anywhere
  — not in production, not in the sandbox, not in a freshly migrated database.
- Good: the same revision runs on every database the schema reaches, so the
  test suite's in-memory databases are migrated by construction. Seeded
  revision tests in `backend/tests/db/test_migration_0009.py` assert the change
  and, just as importantly, that expenses waiting for approval are untouched.
- Bad / cost: a repeating income now moves the balance on its due date without
  asking. If the real deposit differed, the user corrects that movement — which
  is what AC-6 describes as the intended workflow.
- Bad / cost: any `planned` income transactions already materialized stay in
  the ledger unresolved. The migration prints its row count so the human knows
  whether to go looking; `runbook.md` carries the follow-up.
- Bad / cost: `downgrade` does not restore the previous state. The revision is
  one-way by design, and this is stated in the revision docstring.

## Confirmation

`backend/tests/db/test_migration_0009.py` seeds a database at revision `0008`
with a manual income, an automatic income, a manual expense and an automatic
expense, upgrades, and asserts only the first moved. Feature 007's acceptance
scenario "An income that waits for approval cannot be declared" covers the
front door. The runbook step `count-manual-recurring-incomes` records what
production actually held before the change.
