---
slug: "2026-08-13-a-meta-swallows-what-it-cannot-take"
title: "A contribution the meta cannot take is still charged to the month"
severity: high
blocks_user: false
workaround: "remove the contribution and make it again — contribute() trims at write time, so the row is rewritten to what now fits"
status: refined

source:
  kind: user
  ref: "browser QA sweep of the sandbox, 2026-08-12 — the owner asked for a full pass over every screen"

repro: |
  1. Open a meta for 8.000.000 COP by 2026-12, starting 2026-08.
  2. In 2026-10 it holds 3.200.000 and asks 1.600.000, so 3.200.000 is missing.
     Contribute exactly that. The meta fills up.
  3. Lower the meta's amount to 5.000.000.
  4. Read the month.

  A second path reaches the same place without an edit: contribute in a month,
  then record the purchase that finished the meta with an earlier date. The
  meta had already finished by the month the contribution sits in, so it takes
  none of it.

expected: "The month is charged what the meta actually took (1.200.000) and the rest stays in the money available — AC-14: «leaves the rest in the month»."
actual: "The month is charged the whole 3.200.000. The meta holds 5.000.000 and gives nothing back (released = 0), so 2.000.000 is in neither: it left the money available and reached no meta."

feature_refs:
  - "features/009-named-goals"

investigation:
  match_mode: auto
  candidates_considered: 3

pin_confirmation:
  feature_refs:
    - feature: "features/009-named-goals"
      spec_path: "features/009-named-goals/spec.md"
      red_run:
        result: red
        command: "./run-acceptance-tests.sh features/009-named-goals"
        output: |
          FAILED test_009_named_goals.py::test_lowering_the_amount_below_what_was_contributed_leaves_the_rest_in_the_month
                 contributed 320000000, expected 120000000
          FAILED test_009_named_goals.py::test_a_meta_that_had_already_finished_leaves_the_whole_contribution_in_the_month
                 contributed 320000000, expected 0
          2 failed, 133 passed in 7.14s

          Each scenario's `money available` assertion was proven red on its own,
          with the `contributed` line removed so it could be reached:
          the money available is 120000000, expected 320000000
          the money available is 180000000, expected 500000000

fix_commits:
  - "9e22458 fix(009): the month charged a contribution the meta never took"

harden_results:
  mutation_score: null
  arch_check: null
  bug_line_mutation_confirmed: false

gap_analysis: []

followups: []
---

# A contribution the meta cannot take is still charged to the month

## The two figures that disagree

`services/metas.py` decides twice what a hand-made contribution is worth, and
only one of the two answers is trimmed.

```python
# _month_of — what the META takes
contributed = min(_contributions_in(agg, meta, month), max(amount - opening - ask, 0))
```

```python
# fold — what the MONTH is charged
contributed=sum(
    to_cop_cents(_contributions_in(agg, meta, agg.year_month), meta.currency, agg.trm) for meta in charged
)
```

The month reads the stored row; the meta reads what fits. `month_available`
subtracts the first (`claimed = … + saved.contributed − saved.released`) and
reports the second (`holds`). The difference is money that left the money
available and reached nothing.

## Why the write path does not catch it

`contribute()` trims to `_room_left` before storing, which is why AC-14's two
existing scenarios are green: they only exercise the moment of contributing.
The room is not a fact about the row — it is recomputed on every read from the
amount, the amendments and the purchases. Any act that shrinks it afterwards
strands part of a row that was legal when it was written:

- lowering the amount (an amendment in the month being read)
- recording the purchase with a date before the month the contribution sits in

Both are ordinary things to do, and neither is refused.

## What the meta does with the rest

Nothing. `released` stays 0, because releasing only happens on the
`opening > amount` branch — the money the *walk* is carrying, not the money a
contribution offered this month. So there is no give-back line to notice
either: the breakdown adds up on its own terms while the total is short.
