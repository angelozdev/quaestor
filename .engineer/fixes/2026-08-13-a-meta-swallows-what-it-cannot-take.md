---
slug: "2026-08-13-a-meta-swallows-what-it-cannot-take"
title: "The month charges a hand contribution the meta never took, and charges twice one it did"
severity: high
blocks_user: false
workaround: "remove the contribution and make it again — contribute() trims at write time, so the row is rewritten to what now fits. No workaround for the double charge: unlink the purchase or do not contribute in the month you buy in."
status: hardened

source:
  kind: user
  ref: "browser QA sweep of the sandbox, 2026-08-12 — the owner asked for a full pass over every screen"

repro: |
  ONE — the month charges what the meta never took.

  1. Open a meta for 8.000.000 COP by 2026-12, starting 2026-08.
  2. In 2026-10 it holds 3.200.000 and asks 1.600.000, so 3.200.000 is missing.
     Contribute exactly that. The meta fills up.
  3. Lower the meta's amount to 5.000.000.
  4. Read the month.

  A second path reaches the same place without an edit: contribute in a month,
  then record the purchase that finished the meta with an earlier date.

  TWO — the month charges the same contribution again as a gap.

  1. Open a meta for 6.000.000 COP by 2026-12, starting 2026-10. It asks
     2.000.000 and 4.000.000 is missing. Contribute exactly that: it holds
     6.000.000.
  2. Record the 6.000.000 purchase, linked to the meta, in the same month.
  3. Read the month, on an income of 10.000.000.

expected: |
  ONE — the month is charged what the meta actually took (1.200.000) and the
  rest stays in the money available. AC-14: "leaves the rest in the month".

  TWO — the purchase costs the month nothing beyond what the meta set aside.
  AC-43: "only what the meta cannot cover costs the month"; a phone against a
  meta that already holds its price "costs December nothing beyond the
  instalment".
actual: |
  ONE — the month is charged the whole 3.200.000. The meta holds 5.000.000 and
  gives nothing back (released = 0), so 2.000.000 is in neither: it left the
  money available and reached no meta.

  TWO — the same contribution is charged twice, once as `contributed` and once
  as `uncovered`. Two metas both holding 8.000.000 against the same 8.000.000
  phone, on an income of 5.000.000:

    filled by instalments   uncovered         0,00   free       200.000,00
    filled by a contribution uncovered 5.333.333,33  free    -8.333.333,33

  8.533.333,33 apart, for the same phone and the same money saved.

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
          ONE — two scenarios added under AC-14:
          FAILED test_lowering_the_amount_below_what_was_contributed_leaves_the_rest_in_the_month
                 contributed 320000000, expected 120000000
          FAILED test_a_meta_that_had_already_finished_leaves_the_whole_contribution_in_the_month
                 contributed 320000000, expected 0
          2 failed, 133 passed in 7.14s

          Each scenario's `money available` assertion was proven red on its own,
          with the `contributed` line removed so it could be reached:
          the money available is 120000000, expected 320000000
          the money available is 180000000, expected 500000000

          TWO — three scenarios added under AC-13 and AC-43:
          FAILED test_only_what_a_meta_filled_by_hand_did_not_cover_leaves_the_month
                 uncovered 500000000, expected 100000000
          FAILED test_a_purchase_a_meta_filled_by_hand_covers_costs_the_month_nothing_more
                 uncovered 400000000, expected 0
          FAILED test_a_planned_purchase_a_meta_filled_by_hand_covers_costs_the_month_nothing
                 uncovered 400000000, expected 0
          3 failed, 135 passed in 7.11s

fix_commits:
  - "9e22458 fix(009): the month charged a contribution the meta never took"
  - "f509133 fix(009): the month charged the same contribution a second time"

harden_results:
  mutation_score: null
  arch_check: "pass — cd backend && uv run lint-imports: Contracts: 2 kept, 0 broken"
  bug_line_mutation_confirmed: true

gap_analysis:
  - category: incomplete_spec
    phase: atdd
    finding: "AC-14's three scenarios all stop at the moment of contributing, where `contribute()` trims correctly. None reads a month afterwards. The room is recomputed on every read, so the write-time trim only ever covered half the criterion."
    followup_kind: extend_spec
  - category: incomplete_spec
    phase: atdd
    finding: "Every AC-12, AC-13 and AC-43 scenario fills its meta by instalments alone, so AC-43's word 'cover' was never put to the test with a hand contribution inside it. The double charge lived beside 1.325 green tests because no scenario ever combined the two acts."
    followup_kind: extend_spec
  - category: inadequate_verification
    phase: harden
    finding: "Feature 009's CP8 swept metas.py at 95.3% and saw neither defect — mutation cannot see a bug the code and the tests agree on. Its own gap is separate and real: no test anywhere contributed to a meta in a second currency, so hard-coding \"COP\" on the fold line survived every suite. CHARTER §6's foreign-currency rule was written for screens that write money and does not reach a figure converted at read time."
    followup_kind: add_verification

followups:
  - category: incomplete_spec
    action: "Two scenarios under AC-14 reading the month after the room shrank — by an edit, and by a back-dated purchase"
    status: applied
  - category: incomplete_spec
    action: "Three scenarios under AC-13 and AC-43 with a meta filled by hand and a purchase in the same month, posted and planned"
    status: applied
  - category: inadequate_verification
    action: "A contribution to a meta in dollars under AC-14; the contribution steps now name a currency and refuse one the meta is not held in; CHARTER §6 amended so a figure the app converts is tested in another currency whether or not anyone writes it"
    status: applied
---

# A hand contribution reaches the month wrong, in both directions

Two defects, one sentence: **nothing tied what a meta actually took to what the
month was charged for it.** `_month_of` decided what fitted; two other places
went back to the stored row or to a formula that predates contributions.

## One — charged for what the meta never took

```python
# _month_of — what the META takes
contributed = min(_contributions_in(agg, meta, month), max(amount - opening - ask, 0))

# fold — what the MONTH was charged
contributed=sum(
    to_cop_cents(_contributions_in(agg, meta, agg.year_month), meta.currency, agg.trm) for meta in charged
)
```

`contribute()` trims to `_room_left` before storing, which is why AC-14's three
existing scenarios were green: they only exercise the moment of contributing.
The room is not a fact about the row — it is recomputed on every read from the
amount, the amendments and the purchases. Any act that shrinks it afterwards
strands part of a row that was legal when it was written:

- lowering the amount (an amendment in the month being read)
- recording the purchase with a date before the month the contribution sits in

`released` stayed 0, because releasing only happens on the `opening > amount`
branch — the money the walk carries, never the money a contribution offered
this month. So there was no give-back line to notice either.

**Closed by:** `_Month` carries what the meta took; `fold` sums that. After it,
`_contributions_in` has exactly one caller, which is the point.

## Two — charged again for what it did

```python
# _meta_uncovered, before
uncovered_excess_calc(spent, month.opening, month.ask)
```

That is the fund's shape. A fund's month is what it opened with plus what it
asks, and a fund takes no hand contributions. A meta's month is what it
**holds**, which includes them. So a purchase the meta had already covered by
hand came back as a gap, and the month paid for it twice — once as
`contributed`, once as `uncovered`.

AC-12's own wording ("less what the meta opened the month with, less what it
asks this month") is the fund-shaped restatement, and it gives the right answer
in its own example because that example has no contribution. AC-13 and AC-43
say what is covered is what the meta **holds**. Three criteria to one.

**Closed by:** `uncovered_excess_calc(spent, covered)` — the caller says what
was covered, because the two callers do not agree on what covers. The fund
passes `opening + ask`, the meta passes `holds`, and the meta cannot forget the
contribution again.

## What the fix does not do

Three neighbours were found while verifying it and are **not** closed here.
Two have their own artifacts and the owner's decision already recorded:

- `2026-08-13-a-contribution-into-a-month-the-meta-never-ran-in` — accepted,
  reaches nothing. Decided: refuse it.
- `2026-08-13-a-stated-opening-above-the-amount-mints-money` — the month is
  handed money that never entered it. Decided: refuse it.

The third is display, not money: a stranded contribution is still listed at
face value in the meta's history (AC-42), so the owner reads "aporté 3.200.000"
beside a meta that took 1.200.000 of it.
