---
slug: "2026-08-13-a-stated-opening-above-the-amount-mints-money"
title: "Saying a meta already held more than it costs hands the month money that never existed"
severity: high
blocks_user: false
workaround: "raise the meta's amount to at least what was stated, or cancel it and open it again with the right figure — `stated_opening` cannot be edited"
status: closed

source:
  kind: internal
  ref: "found by the CP7 verifier of fix 2026-08-13-a-meta-swallows-what-it-cannot-take"

repro: |
  1. Open a meta "Celular" for 5.000.000 COP by 2026-12, starting 2026-10,
     stating the owner already held 8.000.000 COP.
  2. Read 2026-10, on an income of 5.000.000 COP.

expected: "The app refuses it: the owner already has more than the thing costs (the owner's decision, 2026-08-13)."
actual: |
    the meta holds     5.000.000,00
    the meta released  3.000.000,00
    money available    8.000.000,00   ← on an income of 5.000.000,00

  The month is handed 3.000.000,00 that never entered it.

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
        command: "./run-acceptance-tests.sh features/009-named-goals"
        output: |
          The ceiling:
          FAILED test_a_meta_cannot_be_told_it_already_holds_more_than_the_thing_costs
                 the meta was accepted, expected a refusal
          2 failed, 141 passed in 7.47s

          The floor and the give-back, pinned after an independent verifier showed
          the ceiling alone did not close the mint — metas.py reverted to HEAD and
          the pipeline re-run:
          FAILED test_cancelling_gives_back_only_what_the_months_put_in
          FAILED test_lowering_below_a_stated_opening_gives_back_only_what_the_months_put_in
          FAILED test_a_meta_cannot_be_told_it_already_holds_less_than_nothing
          FAILED test_the_form_refuses_a_statement_the_creation_would_refuse
          4 failed, 143 passed in 7.84s

fix_commits:
  - "32bcc7f fix(009): the app stops taking money it cannot put anywhere"
  - "d4ef558 fix(009): a meta gives back only what the months put in"

harden_results:
  mutation_score: 0.957
  arch_check: "pass — cd backend && uv run lint-imports: Contracts: 2 kept, 0 broken"
  bug_line_mutation_confirmed: true

handoff_path: .engineer/handoffs/2026-08-13-metas-refuse-what-cannot-land-close.md

gap_analysis:
  - category: missing_ac
    phase: discover-acs
    finding: "AC-34 let the owner state what a meta already held and put no bounds on it at all — neither a ceiling at the amount nor a floor at zero. A negative statement made a 5.000.000 meta ask 10.000.000 over three months."
    followup_kind: amend_ac
  - category: incomplete_spec
    phase: atdd
    finding: "The ceiling alone does not close the mint, and the first fix claimed it did. AC-15 already said in words that releasing more than was ever taken would mint money, but no scenario put a stated opening in front of a give-back, so lowering the amount afterwards or cancelling reached the same money untouched. An independent verifier found it; the suites were green."
    followup_kind: extend_spec

followups:
  - category: missing_ac
    action: "AC-34 carries a ceiling and a floor; scenarios for both refusals, for stating exactly the amount, and for stating exactly zero — which is what the frontend actually sends"
    status: applied
  - category: incomplete_spec
    action: "The walk carries `funded`; scenarios under AC-15 and AC-16 for cancelling and for lowering below a stated opening"
    status: applied
---

# A stated opening above the amount mints money

## The two rules that meet in the wrong place

`create_meta` validates the name, the amount and the target month.
`stated_opening` is not among them (`_validate_spec` never sees it).

`_month_of` then meets it on the give-back branch:

```python
if opening > amount:
    return _Month(opening=opening, ask=0, holds=amount, released=opening - amount)
```

That branch is AC-16's: the owner lowered the amount below what the meta had
**already taken from months it charged**, so the excess goes back to the month
it came out of. A stated opening never came out of any month — AC-34 says it
*"costs no month"* — so handing 3.000.000 back mints it. Product ADR-014 names
exactly this: releasing more than was ever taken would mint money.

## What the owner decided

**Refuse it at creation** (2026-08-13). The alternative offered was accepting
only up to the amount and letting the meta be born complete; it was declined.

## Note for the pin

The refusal belongs in `_validate_spec` so `create_meta` and any later caller
get it from one place. The regression must also keep AC-34's own case green: a
stated opening *equal to or below* the amount still costs the month nothing.
