# 0034. Skipping a planned payment is reversible

- **Status:** accepted
- **Date:** 2026-08-01
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

`services.planned.skip_payment` moves a `planned` transaction to `skipped` and
nothing moves it back. The P3 temporal-engine design
(`docs/superpowers/specs/2026-06-16-P3-temporal-engine-design.md`) framed
skipping as cancellation — "marks a standalone `planned` tx as skipped
(canceled)" — with `confirm_payment` as the only transition out of `planned`
and no inverse for either.

A skip is a one-click action on the outstanding queue, offered on every row
next to Confirmar. Hitting it by mistake costs the user the obligation: the
payment leaves the queue, the amount and due date are only recoverable by
reading them off the transaction list and planning the payment again by hand.
Feature 006's AC-8 (approved 2026-08-01) requires that a mistaken skip be
undoable with the original payee, amount, due date and account intact.

## Decision drivers

- **Asymmetric cost of a misclick.** Confirming by mistake is recoverable —
  the posted transaction can be deleted and the balance reverses (feature 002,
  AC-4). Skipping by mistake is not. The cheaper action is the more dangerous
  one, which is backwards.
- **The data is already there.** A skipped row keeps its payee, amount,
  currency, due date, account, category and notes, and its recurring
  occurrence link. Nothing needs to be reconstructed; only a status moves.
- **Recurring obligations must not be corrupted.** A skipped occurrence is the
  marker that stops `materialize_due` from recreating that due date. Restoring
  the payment without restoring the occurrence would leave the two out of step.
- **`confirm_payment` stays the single door to `posted`.** Whatever we add must
  not create a second path into the balance-moving state.
- **Local-only, single user.** No audit or compliance requirement forces
  skipped to be immutable.

## Considered options

1. **A `restore_payment` service function: `skipped -> planned`**, mirroring
   `skip_payment` (which is `planned -> skipped`), syncing the linked
   recurring occurrence back to `planned`.
2. **Keep skipping terminal; offer "plan it again" instead** — a shortcut on
   the skipped row that opens the plan form pre-filled from it, creating a new
   payment.
3. **Undo window only** — hold the skip for a few seconds before committing it,
   with an inline undo, after which it is terminal.
4. **Make `skipped` a soft-delete** and reuse the masters' archive/restore
   lifecycle (ADR-0005) for transactions.

## Decision outcome

Chosen option: **1 — a `restore_payment` service function moving `skipped` back
to `planned`.**

The status column already models the lifecycle; skipping was terminal by
omission, not by design. Adding the inverse of an existing transition is the
smallest change that satisfies AC-8, and it keeps one row representing one
obligation across its whole life — the same row the user skipped is the one
that comes back, so its identity, recurring link and history are preserved.

`restore_payment` refuses anything not in `skipped` (`IllegalTransition`),
moves no money, and syncs a linked `RecurringOccurrence` back to `planned`.
`confirm_payment` remains the only transition into `posted`.

Option 2 satisfies the letter of AC-8 but breaks its spirit: a new row means a
new identity, so a restored recurring obligation would be an orphan detached
from its occurrence, and `materialize_due` would still see a skipped occurrence
and refuse to raise that due date again — producing a duplicate-looking payment
with no link back. Option 3 covers the misclick but not the case AC-8 was
written for ("me di cuenta al día siguiente"); it can still be added later as a
convenience on top of option 1. Option 4 is a larger change than the problem
warrants: ADR-0005's archive/restore lifecycle is about masters (accounts,
categories, goals, recurring items), and transactions deliberately delete
permanently (feature 002, AC-4) — bending them into a soft-delete model would
contradict that decision.

### Pros and cons of the options

**1. `restore_payment` (`skipped -> planned`)**
- Good, because the row keeps its identity, its recurring link and its history.
- Good, because it is the exact inverse of an existing transition — same
  shape, same guards, same occurrence sync.
- Good, because `confirm_payment` stays the only way into `posted`.
- Bad / cost, because the status lifecycle stops being a one-way flow, so any
  future reader of `skipped` can no longer assume it is final.

**2. Plan it again from the skipped row**
- Good, because zero new transitions; the existing create path is reused.
- Bad, because the restored payment is a different row: the recurring
  occurrence stays skipped and detached, and the queue can show a payment the
  recurring machinery does not know about.
- Bad, because the user's mental model ("devuélvelo a la lista") does not match
  "we made you a copy".

**3. Undo window only**
- Good, because it is the cheapest to build and covers the most common slip.
- Bad, because it does not cover next-day regret, which is the case AC-8
  describes.

**4. Soft-delete lifecycle for transactions (ADR-0005 style)**
- Good, because it would make the lifecycle uniform across the whole schema.
- Bad, because it contradicts feature 002's AC-4, where deleting a transaction
  was deliberately made permanent and balance-reversing.
- Bad, because it is a schema-and-semantics change for a problem that needs one
  status transition.

## Consequences

- Good: a mistaken skip costs one click to undo instead of re-entering the
  payment by hand, and the recurring obligation it came from stays in step.
- Good: no schema change and no migration — `skipped` already exists as a
  status, and every field needed to restore the payment is already stored.
- Good: symmetric surfaces — `restore_payment` lands in REST and MCP alongside
  `confirm_payment` and `skip_payment`, classified write-destructive like
  `skip_payment`, so the assistant cannot restore payments on its own.
- Bad / cost: `skipped` is no longer terminal. Code and future ADRs must not
  assume a skipped transaction is final; the monthly report and the retrospective
  view are unaffected today (both read `planned` only), but any future feature
  that treats `skipped` as an archive tombstone has to account for this.
- Bad / cost: the P3 design document's "skipped (canceled)" wording is now
  stale. It is a pre-DAE design doc, superseded in practice by this ADR and by
  `features/006-planned-payments-to-pay/acs.md` AC-8; flag it during
  `consistency-check` rather than editing the historical record.
- Follow-up: an inline undo right after skipping (option 3) remains available as
  a convenience layered on top of this, decided against for now — the restore
  action lives on the transaction list, where skipped payments are already
  visible and filterable by status.

## Confirmation

- Acceptance: `features/006-planned-payments-to-pay/spec.md`, AC-8 — three
  scenarios (a skipped payment returns to the queue with its original amount
  and due date; restoring moves no money; a restored payment can then be
  confirmed). Red until this ADR is implemented.
- Unit: `backend/tests/services/test_planned.py` — restoring a non-skipped
  transaction raises `IllegalTransition`; restoring one that came from a manual
  recurring occurrence returns that occurrence to `planned`; `materialize_due`
  does not duplicate the due date afterwards.
- Wire parity: `backend/tests/api/test_planned.py` and
  `backend/tests/mcp/test_temporal.py` — the restore action exists on both
  surfaces, and `restore_payment` is classified write-destructive (absent from
  `LLM_ALLOWED_TOOLS`).
- Code-review checklist: any new branch on `TxStatus.skipped` must state
  whether it assumes finality; per this ADR it cannot.
