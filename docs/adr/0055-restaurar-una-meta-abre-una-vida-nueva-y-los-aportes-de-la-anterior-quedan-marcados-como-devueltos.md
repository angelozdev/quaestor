# 0055. Restaurar una meta abre una vida nueva, y los aportes de la anterior quedan marcados como devueltos

- **Status:** accepted
- **Date:** 2026-08-13
- **Deciders:** Angelo
- **Supersedes:** one clause of [0046](0046-a-meta-is-a-named-thing-to-save-for.md) — *"`meta_contribution` carries a meta, a month and an amount"*. The rest of 0046 stands.
- **Superseded by:** —

## Context and problem statement

Fix `2026-08-13-restoring-a-meta-revives-a-contribution-it-promised-to-forget`
reproduced two wrong figures against the services layer. A meta of $5.000.000
opened in agosto, given a $1.000.000 contribution by hand, cancelled in agosto
and restored in agosto **holds $2.000.000** while agosto put only $1.000.000
into it — the cancellation had already handed the contribution back, and the
restore reads the row a second time.

The mirror case loses the money instead of minting it: a contribution made in
julio, with the meta cancelled in agosto and restored in septiembre, stays
listed at $1.000.000 (AC-42) and **no month ever reads it**, because the walk
starts at the new `start_month`.

`restore_meta`'s own docstring already promised the first case would not
happen — *"a restored meta begins at the month it is restored in and fills from
zero. Resuming with the old holdings would give the owner the same money
twice"* — and the code kept only half of that promise: it cleared
`stated_opening` and moved `start_month`, and left every `meta_contribution`
row untouched.

## Decision drivers

- **A contribution is history the owner can read (AC-42).** Deleting the rows
  makes the arithmetic right and takes away the list the owner keeps them for.
- **A past month answers as that month stood (AC-27).** Whatever marks a
  contribution must not change what agosto said before the restore, so the
  marking cannot happen at cancellation time.
- **Nothing may mint or lose money (product ADR-014).** Both halves of the
  defect are the same seam the five money fixes of 2026-08-13 closed: nothing
  tied what the owner offered to what a month actually took.
- **A month is a boundary too coarse to separate the two lives.** Cancelling and
  restoring in the same month is the common case, so any rule phrased as a
  comparison between `cancelled_month` and `start_month` cannot tell the two
  lives apart.
- **A fifth migration on real data is a real cost** (charter §7), so the column
  must be worth its migration and must not need a backfill.

## Considered options

1. **Delete the contributions when the meta is restored.**
2. **A nullable `returned_month` on `meta_contribution`, stamped at restore.**
3. **Stamp the rows at cancellation instead, and let the walk skip them.**
4. **Keep the restored meta holding what the contributions put in, and stop the
   cancellation from handing them back.**

## Decision outcome

Chosen option: **2 — a nullable `returned_month` on `meta_contribution`,
stamped when the meta is restored**, because it is the only option that keeps
the history AC-42 promises, leaves every past month reading exactly what it read
before, and needs no backfill.

### The record

`meta_contribution` carries a meta, a month, an amount and — new —
`returned_month`, nullable, the month a cancellation handed this contribution
back. Every existing row is null, which is the truth for them: no meta in the
database has been restored.

### When it is stamped

**`restore_meta` stamps it, not `cancel_meta`.** Restoring is the act that
severs the two lives; cancelling is not. A cancelled meta that is never restored
goes on answering agosto exactly as agosto stood — its charge, its give-back and
its contributions all read as before — because nothing was stamped.

The stamp is `meta.cancelled_month`, read before the restore clears it. It is
accurate: `cancel_meta` refuses a meta whose purchase was linked, so at
cancellation `min(holds, funded)` is everything the months put in, contributions
included, and all of it went back into that month's money available.

### What reads it

`load_month_aggregate` sums only the rows whose `returned_month` is null. The
walk, the room-left check that bounds a new contribution, and every figure
derived from them follow from that one filter.

`contributions_of` keeps returning every row, marked, because the list is the
history. The owner may still remove a returned one; removing it changes no
figure, which is the correct outcome for a row no month reads.

### What the owner sees

In *Ver aportes*, a returned contribution is shown struck through with the note
that the cancellation gave it back. It stays visible, and it stays clearly not
part of what the meta holds.

### Pros and cons of the options

**1 — delete on restore**
- Good, because it needs no migration and no filter.
- Bad, because it destroys the record AC-42 exists to keep. The owner's only
  trace of a $1.000.000 he set aside would be gone.
- Bad, because it is a destructive write buried inside an undo action.

**2 — `returned_month`, stamped at restore** (chosen)
- Good, because the history survives and the arithmetic is right.
- Good, because past months are untouched: nothing is stamped until a restore
  happens, and after a restore the walk never visits those months anyway.
- Good, because it needs no backfill — null is correct for every existing row.
- Bad, because it is a fifth outstanding migration, and one more column on a
  table ADR-0046 deliberately kept at three.

**3 — stamp at cancellation**
- Good, because the stamp names the act that actually returned the money.
- Bad, because it rewrites the cancellation month: the walk would stop reading
  the contribution in the very month whose give-back included it, so agosto
  would hand back money it no longer says it held. It breaks AC-27 to fix AC-29.

**4 — the restored meta keeps holding the contributions**
- Good, because no row is skipped and no column is added.
- Bad, because it changes what cancelling does — the act the owner just fixed
  three times today — so that a cancellation gives back the instalments but not
  the contributions. The owner rejected it when asked.
- Bad, because a contribution made in a month before the restore would then have
  to be re-read from outside the walk's range, which is the bound every meta
  figure is derived from.

## Consequences

- Good: both halves of the defect close with one filter, and the second half —
  the orphaned contribution — closes without anyone having to notice it.
- Good: `restore_meta`'s docstring becomes true. Half of what it promised was
  enforced by nothing.
- Bad / cost: migration `0018` adds the column, nullable, no backfill. It joins
  the outstanding migrations charter §7 puts on the owner.
- Bad / cost: `meta_contribution` grows a column whose only writer is
  `restore_meta`. A reader who meets the table first will not guess why.

## Confirmation

Four acceptance scenarios in `features/009-named-goals/spec.md` under AC-29 and
AC-42, each proven red against the code as it stood:

- the restored meta asks $1.000.000 and holds $1.000.000, not $2.000.000
- the contribution stays listed, marked as returned
- a contribution made before the restore month is marked too
- *Ver aportes* shows it struck through with the note

Plus the standing guard that a meta which was never cancelled goes on counting
its contributions, so the filter cannot over-reach.
