---
slug: "2026-08-13-a-stated-opening-above-the-amount-mints-money"
title: "Saying a meta already held more than it costs hands the month money that never existed"
severity: high
blocks_user: false
workaround: "raise the meta's amount to at least what was stated, or cancel it and open it again with the right figure — `stated_opening` cannot be edited"
status: investigating

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

fix_commits: []

harden_results:
  mutation_score: null
  arch_check: null
  bug_line_mutation_confirmed: false

gap_analysis: []

followups: []
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
