---
slug: "2026-08-13-a-meta-gives-back-money-no-month-ever-gave-it"
title: "A meta hands back money the months never put in, and drops money they did"
severity: high
blocks_user: false
workaround: "none — every path is an ordinary act on the metas screen"
status: closed

source:
  kind: internal
  ref: "found by two independent CP7 verifiers of the fixes 2026-08-13-a-contribution-into-a-month-the-meta-never-ran-in and 2026-08-13-a-stated-opening-above-the-amount-mints-money"

repro: |
  THREE MINTS, one shape: `released` was bounded by what the meta HOLDS, and
  what it holds is not what the months paid for.

  A — lower the amount below a stated opening.
    Open a meta of 8.000.000 stating it already holds 8.000.000 (legal), then
    lower it to 3.000.000.

  B — cancel a meta that was told what it already held.
    AC-34's own example: 8.000.000 by December, opened October, stating
    3.000.000. Cancel it in October.

  C — buy the thing, then keep the meta with a new amount (AC-8).
    Five instalments of 1.000.000 fill a 5.000.000 meta; the 5.000.000 phone is
    linked in December; in January the owner says he now wants 1.000.000.

  AND ONE LOSS, the same seam read from the other side:

  D — lower the amount and cancel in the same month.
    A meta holding 4.800.000 put there by the months, lowered to 1,00 and
    cancelled in November.

expected: |
  A, B, C — a month is given back only what it gave. AC-15: "releasing more
  than was ever taken would mint money, which is what product ADR-014 exists to
  prevent". AC-39 for C: "a real purchase would vanish from the month and its
  money would reappear".

  D — both give-backs. AC-16 frees the excess "by AC-15's rule", and cancelling
  frees what is left; a month may hold one act or both.
actual: |
  A  the month was handed  5.000.000 on an income of 0
  B  October ever took     1.666.666,67
     October got back      4.666.666,67   — 3.000.000 minted
  C  January released      4.000.000
     free                  9.000.000 on an income of 5.000.000
     the owner paid 1.000.000 net for a 5.000.000 phone
  D  the months put in     4.800.000
     the month got back            1,00  — 4.799.999 lost

feature_refs:
  - "features/009-named-goals"

investigation:
  match_mode: auto
  candidates_considered: 1

pin_confirmation:
  feature_refs:
    - feature: "features/009-named-goals"
      spec_path: "features/009-named-goals/spec.md"
      red_run:
        result: red
        command: "./run-acceptance-tests.sh features/009-named-goals, with metas.py reverted to HEAD"
        output: |
          A and B, plus the floor and the form, on the code as it stood:
          FAILED test_lowering_below_a_stated_opening_gives_back_only_what_the_months_put_in
          FAILED test_cancelling_gives_back_only_what_the_months_put_in
          FAILED test_a_meta_cannot_be_told_it_already_holds_less_than_nothing
          FAILED test_the_form_refuses_a_statement_the_creation_would_refuse
          4 failed, 143 passed in 7.84s

          C and D, and the two lines the first ledger left unpinned, each proven
          by hand-applying its own mutant and watching exactly its own scenario
          fall:
          drop `- spent`      -> test_keeping_a_bought_meta_with_a_new_amount_frees_nothing_the_thing_ate
                                 test_keeping_a_bought_meta_with_a_new_amount_frees_what_the_thing_left_over
          cancel drops the lowering -> test_lowering_and_cancelling_in_one_month_gives_back_both
          drop `- released`   -> test_a_second_lowering_gives_back_only_what_is_left_of_what_the_months_put_in
          `stated_opening <= 0` -> test_a_meta_may_be_told_it_already_holds_nothing

fix_commits:
  - "d4ef558 fix(009): a meta gives back only what the months put in"
  - "f67fa29 fix(009): what the purchase ate stops being money the meta can give back"

harden_results:
  mutation_score: 0.957
  arch_check: "pass — cd backend && uv run lint-imports: Contracts: 2 kept, 0 broken"
  bug_line_mutation_confirmed: true

handoff_path: .engineer/handoffs/2026-08-13-metas-refuse-what-cannot-land-close.md

gap_analysis:
  - category: incomplete_spec
    phase: atdd
    finding: "AC-15 states the rule in words — releasing more than was ever taken would mint money — and every scenario under it fills its meta by instalments alone, where what it holds and what the months paid are the same number. The criterion was never put in front of a case where they differ, and there are three: a stated opening, a purchase, and a second give-back in the same month."
    followup_kind: extend_spec
  - category: inadequate_verification
    phase: harden
    finding: "Three rounds were needed and each found the previous round's fix incomplete: the ceiling at creation, then the ledger, then the ledger against the wrong quantity. Every round's suites were green. What found each was an independent agent told to break the fix rather than to confirm it, and in two of the three cases the decisive evidence was a hand-applied mutant on the line the fix had just written."
    followup_kind: add_verification

followups:
  - category: incomplete_spec
    action: "Seven scenarios: cancelling and lowering against a stated opening (AC-15, AC-16), a second lowering, lowering and cancelling in one month, and keeping a bought meta with a new amount at full price and under it (AC-39)"
    status: applied
  - category: inadequate_verification
    action: "Each of the four lines the ledger rests on was mutated by hand and shown to fall to exactly one scenario; `- spent` was hoisted out of three branches into one so the rule has a single site"
    status: applied
---

# A meta hands back money the months never put in

## One seam, four symptoms

`released` was bounded by what the meta **holds**. What it holds is not what the
months paid for it — two things get in without a month behind them:

- **what the owner said he already had** (AC-34: "costs no month"), and
- **nothing at all after a purchase**, because `holds` deliberately stays put
  while the money is in the thing (AC-39).

So every act that frees money — lowering the amount below what is held (AC-16),
cancelling (AC-15), keeping a bought meta with a new amount (AC-8) — handed
back figures that no month had ever paid.

The fourth symptom is the same seam read backwards: `fold` took the walk's
`released` **or** the cancellation's, never both, so a meta lowered and
cancelled in one month gave back only the pennies the lowering had left it
with.

## What closes it

The walk carries `funded`: what the months have actually put in, cumulative,
net of what has gone back, and net of what a purchase took out. Nothing is
released past it, and `_gave_back` is the one answer for a month that saw both
acts.

`complete` stopped being read off `released > 0` and got its own answer,
`overfilled`. The two come apart exactly where the mint was: a meta lowered
below a stated opening stops wanting more and hands back nothing, and it is
still finished.

## What it cost to find

Three rounds, each on a green suite:

| round | what it found |
|---|---|
| ceiling at creation | closed the front door and claimed to close the hole |
| independent verifier | the same mint one `PATCH` or one cancel away |
| independent verifier | the ledger was right but measured the wrong quantity — a purchase never left it — plus the give-back the same month was dropping |

**No suite saw any of it.** Mutation could not either: the code and the tests
agreed. What found each was an agent told to break the fix.
