# 0037. A recurring item that ended is derived at read time; resuming offers the stretch left behind

- **Status:** accepted (amended 2026-08-02 after independent review — see Amendment)
- **Date:** 2026-08-02
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

Two of feature 007's target behaviours need lifecycle state the model does not
have, and both were flagged at `consistency-check` (W3, W4).

**W3 — AC-13.** An obligation whose end date has passed stays in the active list
forever, producing nothing. The obvious fix is to have the system write
`RecurringItem.active = false`. But ADR-0005 gives that flag one meaning — *the
user soft-deleted this, and `restore` brings it back*. Writing it from the
system overloads it: restoring an ended obligation would re-activate something
that still produces nothing, and the list could no longer tell "I switched this
off" from "this finished".

**W4 — AC-17.** Resuming a paused obligation charges the entire paused stretch
on the first run after the resume, turning a pause into a deferral. A gym at
8.000 a week paused for 21 days charges 24.000 at once on resume. The only date
anchor stored is `start_date`, which is why. And that behaviour is not an
accident: ADR-0013's consequences state downtime self-healing as a feature.

## Decision drivers

- **ADR-0005's uniform two-state lifecycle is worth keeping.** One reversible
  pattern across goals, recurring items and masters is easier to reason about
  than per-entity rules.
- **"The user switched this off" and "this finished" are different facts** and
  the list has to distinguish them.
- **Downtime catch-up must survive.** AC-9 needs the next run to materialize
  every missed date; only the *paused* stretch is excluded.
- **Invisible state costs more than visible state.** A watermark column has to
  be kept in step by every path that pauses or resumes; a written-down skipped
  date is something the user can see and question.
- **The scenario where off and on happen the same day is real.** Any rule keyed
  on "how long was it paused" degenerates there.

## Considered options

**For "ended" (W3):**

1. **Derive it at read time** — ended ⟺ `end_date is not None and end_date <
   today`. `active` keeps its ADR-0005 meaning.
2. **Write `active = false` from the system** when the end date passes.
3. **A third lifecycle state** on the item, superseding ADR-0005's two-state
   model for `RecurringItem`.

**For the paused stretch (W4):**

4. **Close it on resume** — `restore` writes `skipped` occurrences for every due
   date that has already passed and was never materialized.
5. **A watermark column** (`paused_on` / `resumed_on`) that materialization
   reads as a lower bound.
6. **Offer it on resume** — `restore` writes `offered` occurrences for those
   dates, and the user accepts or declines each, exactly as for AC-12.

## Decision outcome

Chosen: **Option 1 for "ended", Option 6 for the pause.** Together they add zero
columns and leave ADR-0005 untouched.

(Option 4 was chosen first and is preserved below with the reasoning that led
to it; the Amendment at the end of this record explains what was wrong with it
and why Option 6 replaced it.)

Deriving "ended" costs one comparison and keeps `active` honest: it still means
only what the user did. The live list filters ended items out; the switched-off
list includes them; extending the end date brings an item back with no state
write at all.

One consequence has to be stated plainly: **the live list stops being the set
the engine charges.** An obligation that has ended can still hold a due date
that was never materialized because the machine was off, and that date is still
owed. `services/occurrences.py` therefore runs its own query rather than reusing
`list_recurring(active=True)`.

Closing the paused stretch on resume is chosen over a watermark because it puts
the record where the user can see it, and because the watermark degenerates in
AC-17's own first scenario: the obligation is switched off and back on the same
day, so any interval derived from "when was it paused" is empty and the missed
dates get charged anyway. "Every past due date with no occurrence is closed when
you resume" has no such hole. What it does have is a different one, found in
review and recorded in the Amendment below: it cannot tell *why* a past date is
unclaimed.

### Pros and cons of the options

**Option 1 — derive "ended"**
- Good, because ADR-0005 needs no supersede and no migration is required.
- Good, because `active` keeps one meaning, so "I switched this off" and "this
  finished" stay distinguishable.
- Bad, because two acceptance handler bindings must read the derived state
  rather than the raw flag.
- Bad, because "the live list" and "what the engine charges" become two
  different queries, and that has to be remembered.

**Option 2 — the system writes `active = false`**
- Good, because every existing reader keeps working unchanged.
- Bad, because `restore` then re-activates something that produces nothing.
- Bad, because it silently contradicts ADR-0005, which CLAUDE.md forbids.

**Option 3 — a third lifecycle state**
- Good, because the fact is explicit and queryable.
- Bad, because it supersedes ADR-0005's uniform lifecycle for one entity, and
  buys a migration for something derivable from a date already stored.

**Option 4 — close the stretch on resume**
- Good, because the pause leaves a visible record instead of hidden state.
- Good, because it holds when off and on happen on the same day.
- Bad, because resuming writes rows, so it is no longer a pure flag flip.
- **Fatal, found only under independent review:** it cannot tell a date the
  pause consumed from a date the engine was down for, and writes both off.

**Option 6 — offer the stretch on resume**
- Good, because it decides nothing the user did not decide. The two causes are
  indistinguishable from inside `restore`, and the user is the one who can tell
  them apart.
- Good, because it reuses AC-12's whole mechanism — the `offered` status, the
  three service calls, the REST and MCP surface, the dialog — for nothing.
- Good, because it makes the engine consistent: passed dates are offered, never
  imposed, in both directions.
- Bad, because resuming an obligation now leaves a question outstanding rather
  than resolving itself.

**Option 5 — a watermark column**
- Good, because materialization stays a single query with a lower bound.
- Bad, because it is invisible to the user and must be maintained by every path.
- Bad, because it produces the wrong answer in AC-17's first scenario.

## Consequences

- Good: ADR-0005 stands unchanged and no migration is needed for either
  behaviour.
- Good: pausing means pausing — resuming never charges the stretch in one lump.
  The dates are put to the user, who declines the ones the pause consumed.
- Good: a date the engine never reached is never written off without the user
  seeing it. Downtime and a pause are both survivable, and the user resolves
  the ambiguity between them.
- Bad / cost: ADR-0013's consequence "scheduler downtime of N days is
  self-healing — the next run materializes the missed occurrences in one pass"
  now holds for downtime only, not for a deliberate pause. That is a narrowing,
  not a reversal; ADR-0013 is not superseded.
- Bad / cost: the live list and the materialization set diverge, which is a
  distinction a future reader can miss. `arch-check` cannot catch it; the AC-13
  scenarios and a unit test on an ended item with an unmaterialized date are the
  guard.
- Bad / cost: two acceptance handler bindings change with the design.
- Bad / cost: resuming an obligation can leave dates awaiting an answer. They
  are inert until answered — no balance moves and the daily run steps over
  them — but an obligation resumed and forgotten holds an open question.

## Amendment — 2026-08-02, after independent review

The original decision (Option 4) wrote every unclaimed past date off as
`skipped` on resume, and this record claimed that "AC-9's catch-up after
downtime is provably unaffected, because it does not go through `restore`".
**That claim was false**, and the implementer wrote both the claim and the code
without noticing, which is what Principle 7's independent verification exists
to catch.

Downtime does not go through `restore` — but a pause *following* downtime drags
the outage's dates in with it. Reproduced: an engine last run on 1 January, two
weekly dates missed to an outage, and a user who switches the obligation off and
back on **the same day** on 22 January. Both missed dates were written off:
16.000 COP the user still owed, gone with no notice.

`restore` cannot distinguish the two causes, and no amount of stored state fixes
that cheaply — a `paused_on` watermark degenerates in AC-17's own first
scenario, where off and on happen with no time between them.

So `restore` stops deciding. It offers the dates instead (Option 6), and the
user accepts what the outage lost and declines what the pause consumed. This
required no change to any approved scenario — all 201 acceptance scenarios stay
green, including AC-17's two — because none of them asserts the state those
dates land in, only that they are not charged.

## Confirmation

Feature 007's acceptance spec: AC-13 (2 scenarios — leaves the live list,
extending brings it back), AC-17 (2 scenarios — the paused stretch is not
charged, the obligation carries on afterwards), AC-16 and AC-23's resume
scenario as regression guards, and AC-9's three scenarios as the guard that
downtime catch-up did not change. Unit tests in
`backend/tests/services/test_recurring.py` cover the end-date boundary (end =
today, end = yesterday, no end date) and in `test_occurrences.py` the case of an
ended item still holding an unmaterialized date.
