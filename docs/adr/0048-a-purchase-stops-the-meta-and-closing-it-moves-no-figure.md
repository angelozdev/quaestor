# 0048. A purchase stops the meta, and closing it moves no figure

- **Status:** accepted
- **Date:** 2026-08-09
- **Deciders:** Angelo
- **Supersedes:** one clause of [0046](0046-a-meta-is-a-named-thing-to-save-for.md) — *"an instalment of zero happens only because nothing is missing, never because completing, cancelling or editing waived it"*
- **Superseded by:** —

## Context and problem statement

A fresh agent verified feature 009 against its 45 acceptance criteria (handoff
`2026-08-09T1111-verify-implementation.md`) and reproduced three wrong figures
against the running REST surface. One was the `Cerrar` button on a meta whose
purchase had been made.

`close_meta` archives the meta and leaves `cancelled_month` null. `load_month`
kept an archived meta alive only through that month, so a **closed** meta
matched neither branch and disappeared from every month, past ones included.
An $8.000.000 phone bought in August against a meta holding $6.400.000 stopped
costing August the moment the button was pressed — from `$3.400.000 free ·
$1.280.000 uncovered` to `$5.000.000 free · $0 uncovered`.

Making the meta visible again exposed the defect underneath it. `_month_of`
does not know a purchase was made, so a meta went on asking its instalment
every month afterwards: a phone bought in October kept asking $1.600.000 in
November and December, saving toward a thing already owned. Closing was the
only way to stop that, and closing was what erased the past. The two defects
had been holding each other up, which is why the green suite saw neither.

## Decision drivers

- **AC-39 and AC-27 must both hold.** Closing releases nothing, and a past
  month answers as that month stood. Any fix that satisfies one by breaking the
  other is not a fix.
- **Three migrations are already outstanding and human-owned** (charter §7). A
  fourth on real data is a real cost, not a formality.
- **ADR-0046's load-bearing rule protects an identity, not a habit.** The
  identity `income − Σ asks − contributed + released − uncovered = free` must
  keep holding exactly, and the uncovered term is defined as
  `spent − opening − ask` in the month of the purchase.

## Considered options

1. **Record the month the meta was closed and stop it from there.**
2. **Stop the meta the month after its purchase; closing only leaves the list.**
3. **Keep a closed meta on the screen forever so nothing has to be decided.**

## Decision outcome

Chosen option: **(2) the purchase stops the meta**, because it fixes both
defects with arithmetic the owner has already entered, and needs no fourth
migration.

Concretely:

- `_month_of` returns `ask = 0, holds = opening` for every month **strictly
  after** the first month carrying a purchase linked to the meta. The purchase
  month itself is untouched: what it asks is part of what covered the purchase,
  and the uncovered term reads it.
- `load_month` keeps a closed meta in `agg.metas`, so the month it was bought in
  goes on charging the gap the purchase left.
- `statuses()` drops closed metas, so the screen loses them the way AC-29 says
  an archived meta leaves the list. The arithmetic and the list are separate
  questions and are now answered separately.
- `list_archived` excludes them and `restore_meta` refuses them: cancelling
  hands money back and is reversible, closing hands nothing back and is not.

### Pros and cons of the options

**(1) Record the closed month**
- Good, because it expresses "finished on this date" directly, which reads well.
- Bad, because it needs migration 0017 on real data while 0015 and 0016 are
  still unapplied.
- Bad, because it leaves the underlying defect alive: a meta the owner forgets
  to close still saves for something he owns.

**(2) The purchase stops the meta**
- Good, because both defects fall out of one change, and the fact it reads —
  the purchase — is already recorded.
- Good, because it needs no schema change.
- Bad, because it narrows ADR-0046's stated rule, which has to be written down
  rather than absorbed silently. This ADR is that writing down.

**(3) Keep a closed meta listed forever**
- Good, because nothing has to be decided about the list.
- Bad, because AC-29 already decided it — an archived meta is out of the list —
  and the screen's own copy was written for a meta that renders with no badge
  and no actions.

### What is narrowed in ADR-0046, exactly

ADR-0046 states: *"The month always charges its instalment. An instalment of
zero happens only because nothing is missing, never because completing,
cancelling or editing waived it."*

That rule exists so the money-available identity and the consumo/ahorro/libre
split cannot disagree in a month the owner acted in, which is what the CP3
audits found in the first spec. **Every act it names still charges.** What is
added is that a purchase ends the series from the *following* month, which is
not a month the owner acted in and in which the meta contributes nothing to any
term. The identity is unchanged: the ask term is smaller because there is no
longer anything to ask for.

## Consequences

- Good: `Cerrar` becomes what its label says. The meta leaves the screen and no
  figure moves — the only reading of AC-39 that does not contradict AC-27.
- Good: a meta bought before it filled stops asking whether or not the owner
  remembers to close it. The gap is charged once, in the month of the purchase.
- Good: no migration. The behaviour derives from the linked purchase.
- Bad / cost: `_month_of` now needs the purchase months, which `_bought_in`
  reads off the aggregate the fold already loaded — no new query, but one more
  thing the per-month step depends on.
- Bad / cost: ADR-0046 can no longer be read alone on this point.

## Confirmation

`backend/tests/services/test_metas.py` pins all three behaviours by name:
`test_closing_a_bought_meta_leaves_the_purchase_costing_the_month_it_was_made_in`,
`test_a_bought_meta_stops_asking_the_month_after_the_purchase`, and
`test_a_closed_meta_is_not_listed_among_the_cancelled_ones`. Each fails against
the code as it stood before this decision.

`test_load_issues_bounded_query_count` still asserts `BOUNDED_LOADS = 13` — this
decision adds no statement to the fold.
