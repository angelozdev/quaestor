# 0038. Engine-made movements carry their own source, and deleting one closes its due date

- **Status:** accepted
- **Date:** 2026-08-02
- **Deciders:** Angelo
- **Superseded by:** —
- **Supersedes:** —

## Context and problem statement

Two loose ends where the recurring engine meets the transaction ledger.

**AC-25.** A movement the engine creates is stored with `source = manual`,
exactly like something the user typed in. The link to its obligation
(`Transaction.recurring_id`) is stored but nothing surfaces it. The one surface
in the app that moves a balance with no user action is also the one that leaves
no trace of having done so, and reconciling a balance that moved overnight means
guessing.

**AC-28.** Deleting an engine-made movement reverses the balance (feature 002)
and leaves its occurrence still marked `posted`, pointing at a row that no
longer exists. The due date is consumed forever: no run brings it back and no
screen shows anything is wrong. This matters more than it looks, because AC-20
refuses to skip a date that was already charged and points the user at deleting
the movement instead — so the correction path AC-20 depends on is the broken one.

## Decision drivers

- **Provenance is what makes an unattended balance change reconcilable.** The
  user has to be able to tell, without opening anything, which movements they
  made and which the engine made.
- **The data is already there.** `recurring_id` has been stored since the start;
  only `source` lies and only the UI is silent.
- **`services/transactions.py` belongs to feature 002.** The recurring engine
  must not become a dependency of it.
- **The codebase already has a seam for this shape.** `POST_CONFIRM_HOOKS` and
  `ROLLOVER_HOOKS` let one service react to another's event, wired once in
  `services/bootstrap.py`.
- **The occurrence and the account must never disagree.** Whatever the delete
  does, it has to leave both telling the same story.

## Considered options

**For provenance (AC-25):**

1. **A new `Source` value** for the engine, plus a badge in the movements list.
2. **Derive it from `recurring_id`** — a movement with an obligation behind it
   was made by the engine.

**For the delete (AC-28):**

3. **A post-delete hook registry** in `transactions.py`; `occurrences.py`
   supplies the hook that closes the date; `bootstrap.py` wires it.
4. **Sync inline** inside `transactions._delete_single`.
5. **A database cascade** on `RecurringOccurrence.transaction_id`.

## Decision outcome

Chosen: **Option 1 for provenance, Option 3 for the delete.**

A distinct `Source` value is chosen over deriving from `recurring_id` because
the two facts are not the same. `recurring_id` says *which obligation this
belongs to*; `source` says *who created this row*. A user can plausibly record a
movement by hand and attach it to an obligation, and that movement must not
claim the engine made it — AC-25's third scenario asserts exactly that
separation. Deriving would collapse the two and make that scenario unassertable.

The post-delete hook is chosen because it keeps the dependency arrow pointing
one way. `transactions.py` gains a registry and no knowledge of recurring items;
`occurrences.py` supplies a function; `bootstrap.py` wires them, the same way it
already wires the goal hooks. Deleting an engine-made movement closes its due
date as `skipped` and clears the dangling `transaction_id`.

A cascade was rejected outright: it would delete the occurrence row, which
throws away the information that this date is settled and lets the next run
charge it again — the opposite of what AC-28 requires.

### Pros and cons of the options

**Option 1 — a new `Source` value**
- Good, because "who made this row" gets its own answer, independent of "what is
  it about".
- Good, because it makes AC-25's hand-entered-vs-engine distinction assertable.
- Bad, because it needs a migration, and on native Postgres enums
  `ALTER TYPE … ADD VALUE` must run in `op.get_context().autocommit_block()`.

**Option 2 — derive from `recurring_id`**
- Good, because no migration at all.
- Bad, because a hand-entered movement attached to an obligation would be
  reported as the engine's, which is a lie the user cannot correct.

**Option 3 — post-delete hook registry**
- Good, because `transactions.py` stays free of any recurring dependency.
- Good, because it reuses a wiring pattern the codebase already has in two
  places.
- Bad, because the behaviour is one indirection away from the code that triggers
  it, and an unregistered hook fails silently. `bootstrap` is idempotent and
  covered by tests, which is the mitigation.

**Option 4 — inline sync**
- Good, because it is the shortest possible change and impossible to
  mis-register.
- Bad, because feature 007's rules end up living inside feature 002's module.

**Option 5 — database cascade**
- Good, because it needs no application code.
- Bad, because deleting the occurrence loses the fact that the date is settled,
  so the next run recreates the charge — it breaks AC-28 rather than
  implementing it.

## Consequences

- Good: a balance that moved overnight is reconcilable from the movements list
  alone, and names the obligation behind it.
- Good: AC-20's escape hatch works — refusing to skip a charged date now points
  at a delete that leaves the obligation and the account agreeing.
- Good: `services/transactions.py` acquires no dependency on the recurring
  engine; the arrow stays `bootstrap → {transactions, occurrences}`.
- Bad / cost: one migration, sharing revision `0008` with ADR-0035's `offered`
  value. A migration written without the autocommit block passes the acceptance
  suite (SQLite stores enums as text) and fails only against production —
  `runbook.md` gates it.
- Bad / cost: every existing reader of `Transaction.source` must tolerate a
  value it has not seen. The frontend type is a bare `string`, so the surface is
  the badge and the MCP formatter.
- Bad / cost: a third hook registry in the services layer. Three is the point at
  which the pattern should be extracted rather than copied a fourth time —
  noted, not done here.

## Confirmation

Feature 007's acceptance spec: AC-25 (3 scenarios — automatic charge marked as
the engine's and naming its obligation, manual-mode charge carrying the same
mark, hand-entered movement not claiming it) and AC-28 (3 scenarios — money
returns and the date closes, a later run does not recharge it, following dates
unaffected). Unit tests in `backend/tests/services/test_occurrences.py` for the
hook and in `backend/tests/services/test_transactions.py` for the registry
firing. Colocated vitest for the badge. The runbook step
`verify-enum-values-live` confirms the value exists in production.
