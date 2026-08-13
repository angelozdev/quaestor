---
slug: "2026-08-13-restoring-a-meta-revives-a-contribution-it-promised-to-forget"
title: "Restoring a cancelled meta charges its month a contribution it had already handed back"
severity: medium
blocks_user: false
workaround: "remove the contribution from the meta's history before restoring it — `Ver aportes` lists it"
status: hardened

source:
  kind: internal
  ref: "found by the CP7 verifier of fix 2026-08-13-a-meta-gives-back-money-no-month-ever-gave-it"

repro: |
  1. Open a meta and contribute 1.000.000 COP to it in November.
  2. Cancel it in November. It hands back everything the months put in.
  3. Restore it, still in November.
  4. Read November.

expected: |
  `restore_meta`'s own docstring: a restored meta "begins at the month it is
  restored in and fills from zero. Resuming with the old holdings would give the
  owner the same money twice."
actual: |
  November charges the new instalment AND the old contribution again — the row
  was never deleted and `start_month` is now November, so the walk reads it a
  second time. Half of what the meta holds came out of a meta that was
  cancelled.

  A contribution made in a month BEFORE the restore is the mirror image: it
  stays listed at face value (AC-42) and no month ever reads it — the same
  "money the owner believes he saved" that
  `2026-08-13-a-contribution-into-a-month-the-meta-never-ran-in` closed on the
  write path.

feature_refs:
  - "features/009-named-goals"

investigation:
  match_mode: auto
  candidates_considered: 1

pin_confirmation:
  feature_refs:
    - ref: "features/009-named-goals"
      red_run:
        result: red
        command: "./run-acceptance-tests.sh features/009-named-goals"
        output: |
          FAILED test_a_restored_meta_does_not_charge_again_a_contribution_the_cancellation_gave_back
            AssertionError: the meta 'Portatil' holds 200000000, expected 100000000
          FAILED test_a_contribution_made_in_a_month_the_restore_left_behind_is_given_back_too
            AttributeError: 'MetaContribution' object has no attribute 'returned_month'
          2 failed, 153 passed
        note: |
          The guard scenario shipped beside them and was GREEN from the first
          run by design — a meta never cancelled goes on counting its
          contributions, so the new filter cannot over-reach.

fix_commits:
  - d70b3ad
  - c9afeb9
  - 24f2411

harden_results:
  mutation_score: null
  arch_check: "Contracts: 2 kept, 0 broken (cd backend && uv run lint-imports)"
  bug_line_mutation_confirmed: true
  bug_line_evidence: |
    Three load-bearing lines, each mutated by hand and each killed:
      1. the stamping loop in `restore_meta` removed → 2 failed, 1 passed
      2. `MetaContribution.returned_month.is_(None)` dropped from the
         aggregate's WHERE → 2 failed, 1 passed
      3. `if row.returned_month is None` removed (the second-cancellation
         guard) → the whole 1190-test backend suite stayed GREEN, and only
         `test_a_second_cancellation_leaves_the_first_ones_give_back_month_alone`,
         written for exactly this, went red. That guard had no test at all
         until c9afeb9.
    The frontend half was proven red the same way: stashing `meta-actions.tsx`
    left 1 failed | 32 passed.

gap_analysis: []

followups: []
---

# Restoring a meta revives a contribution it promised to forget

## The two halves

`restore_meta` rewrites `start_month` to today and clears `stated_opening`, but
`MetaContribution` rows survive untouched. The walk then starts from the new
month, so the rows split in two:

- **made in the restore month** — read again, on top of the money the
  cancellation already handed back.
- **made before it** — read by nothing, listed at face value by AC-42.

Both are the same seam this evening's fixes closed everywhere else: nothing
tied what the owner offered to what a month actually took.

## Note for the pin

The regression needs both halves, and the product question is which way it
goes — delete the rows the restore orphans, or leave them and stop reading the
ones in the restore month. The first loses history AC-42 promises; the second
leaves the owner a list of contributions that did nothing.

## Also filed here: a rounding drift

The give-back cap compares meta-currency ints and converts once, while each
month's ask converts on its own. Over a meta's life the two diverge by ±1 cent
in COP for a foreign-currency meta at some rates — measured at TRM 3333,33 and
4123,77. Sub-peso and not user-visible, but it is the only case where
`released` can exceed what the months put in.
