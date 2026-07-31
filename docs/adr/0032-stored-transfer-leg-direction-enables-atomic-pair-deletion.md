# 0032. Stored transfer-leg direction enables atomic pair deletion

- **Status:** accepted (backfill rationale amended 2026-07-31, see Amendment)
- **Date:** 2026-07-31
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

A transfer is stored as two `Transaction` rows sharing a `transfer_group_id`,
both with a positive `amount` (P0 rule: sign lives in `type`, and `transfer`
has no sign). Nothing records which leg debited the source account and which
credited the destination, so `delete_transaction` refuses transfer legs — the
balance reversal would be a guess. Feature 002's AC-5 (approved 2026-07-31)
requires deleting a mistaken transfer as an atomic pair, reversing both
balances exactly. Spec: `features/002-transactions-crud/spec.md` (AC-5).

## Decision drivers

- Balance integrity: reversal must be exact for both legs, including
  cross-currency pairs where the two amounts differ (ADR-0031).
- P0 invariant: `amount` is always positive; sign is derived, never stored in
  the amount.
- Existing real data: 634+ transactions in the local production Postgres
  include historical transfer pairs that must become deletable too.
- Small blast radius: reports and budgets filter by `type` and never read
  transfer legs' direction.

## Considered options

1. New `transfer_direction` column (`out` | `in`) on `Transaction`, set at
   creation, backfilled by migration.
2. Signed amounts (negative for the outgoing leg).
3. A separate `TransferGroup` entity owning from/to account ids.
4. No schema change — infer direction at runtime from insertion order
   (lower id in the group = outgoing).

## Decision outcome

Chosen option: **1 — stored `transfer_direction` column**, because it makes
the reversal a fact read from the row, keeps the positive-amount invariant,
and needs only one nullable column plus a one-time backfill.

The backfill exploits a historical invariant: `transactions.transfer()` (P0
through feature 005) and `goals.contribute_to_goal()` persist the source leg
first via `session.add_all([leg_from, leg_to, ...])`, so within each
`transfer_group_id` the lower `id` is the outgoing leg. Alembic revision 0006
materializes that once; from then on direction is data, not inference.
Deletion of either leg loads the pair by group, reverses each balance per its
direction, and removes both rows atomically.

## Amendment — 2026-07-31 (Checkpoint 6 refine)

The invariant above was asserted for "every version of `transfer()`" without
auditing the other two creation paths. It is wrong for one of them:

| Creation path | Persistence order | Lower id is |
|---|---|---|
| `transactions.transfer()` | `add_all([leg_from, leg_to])` | outgoing ✅ |
| `goals.contribute_to_goal()` | `add_all([leg_from, leg_to])` | outgoing ✅ |
| `planned._confirm_transfer()` | destination is the pre-existing planned row; source leg created at confirm time | **incoming** ❌ |

Two consequences followed, both now closed:

1. `planned._confirm_transfer()` and `goals.contribute_to_goal()` never set
   `transfer_direction` at all, so every transfer created through them after
   revision 0006 was born NULL and permanently undeletable — AC-5 held only
   for transfers created via `transfer()`. All three paths now set the
   direction explicitly at creation.
2. Historical pairs originating from a confirmed planned payment were
   backfilled inverted, so deleting one would have moved both balances the
   wrong way. Revision 0007 corrects them, identifying such pairs by their
   creation spread — legs written in one `add_all` share a creation instant,
   while a planned row predates its confirmation by more than a minute.

The runbook's post-0006 verification ("each group has exactly one `out` and
one `in_`, zero NULL") passes just as well on an inverted pair, which is why
it did not surface this. Revision 0007 must be verified against real data with
a stated expected row count, not a shape check.

### Pros and cons of the options

**1. Stored direction column**
- Good, because reversal is exact and self-describing; one nullable column.
- Good, because the fragile insertion-order invariant is consulted exactly
  once (in the backfill) instead of forever.
- Bad, because it needs an Alembic migration over real data (low-autonomy
  path, runbook with backup-first).

**2. Signed amounts**
- Good, because direction and magnitude collapse into one field.
- Bad, because it breaks the P0 positive-amount invariant and would touch
  every consumer of `amount` across services, reports and formatters.

**3. TransferGroup entity**
- Good, because from/to become first-class and future transfer metadata has a
  home.
- Bad, because it adds a table, joins and lifecycle for what one column
  answers; no current requirement needs the extra shape.

**4. Runtime inference by id order**
- Good, because no migration.
- Bad, because a hidden invariant becomes load-bearing forever; any future
  reordering or import path silently corrupts reversals.

## Consequences

- Good: mistaken transfers become correctable with one action (AC-5); the
  deletion path is uniform with expense/income deletion.
- Bad / cost: Alembic revision 0006 (add column + backfill) must run on the
  real database — human at the wheel per the manifest's low-autonomy path,
  with the 005 runbook lesson applied: backup taken with only the `db`
  container up, since migrations auto-run on api-container boot.
- `transfer()` gains one line per leg; `delete_transaction` loses its
  transfer rejection and gains the pair branch.

## Confirmation

Acceptance scenarios AC-5 (three, including cross-currency) in
`features/002-transactions-crud/spec.md` pin the behavior; unit tests cover
the backfill heuristic and pair reversal; CP8 mutation runs over
`services/transactions.py`. Migration verified on real data via
`features/002-transactions-crud/runbook.md`.
