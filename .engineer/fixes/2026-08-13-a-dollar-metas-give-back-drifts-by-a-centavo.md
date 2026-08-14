---
slug: "2026-08-13-a-dollar-metas-give-back-drifts-by-a-centavo"
title: "A dollar meta's give-back can exceed what its months put in, by a centavo"
severity: low
blocks_user: false
workaround: "none needed — the drift is sub-peso and never reaches a figure the owner reads"
status: investigating

source:
  kind: internal
  ref: "split out of 2026-08-13-restoring-a-meta-revives-a-contribution-it-promised-to-forget, where it was prose in the body and was nearly closed by accident"

repro: |
  A meta held in USD, at a TRM whose thirds do not divide — measured at
  3333,33 and at 4123,77. Let it run several months, then cancel it and read
  what the month released against the sum of what the months charged.

expected: |
  `released` never exceeds what the months put in. AC-15: "What comes back is
  what the months put in, and never more" — releasing more than was ever taken
  would mint money, which is what product ADR-014 exists to prevent.
actual: |
  Reproduced 2026-08-13. A USD meta opened 2026-01 for 2026-12 and cancelled in
  2026-07, comparing the sum of what each month charged (converted per month,
  the way the fold does it) against what the cancellation released:

      TRM  3333.33   US$ 2,000.00   charged 3,888,962.77   gave back 3,888,962.78   +0.01
      TRM  4123.77   US$ 2,000.00   charged 4,811,161.25   gave back 4,811,161.22   −0.03
      TRM  3899.11   US$ 2,000.00   charged 4,549,052.62   gave back 4,549,052.65   +0.03
      TRM  4123.77   US$   700.00   charged 1,683,941.46   gave back 1,683,941.48   +0.02

  So the range is **±3 centavos, not ±1** — the original note understated it.
  It grows with the number of months, since it is an accumulation of rounding.

  `_gave_back` compares meta-currency ints and converts the total ONCE, while
  each month's ask was converted on its own by the fold. `Σ round(xᵢ)` is not
  `round(Σ xᵢ)`.

  IT NEVER REACHES A FIGURE THE OWNER READS. Peso amounts are rendered without
  cents (`$ 5.000.000`), and no screen shows a meta's lifetime charge next to
  its release — only per-month figures, each of which is exact. It is the
  invariant that drifts, not an answer.

feature_refs:
  - "features/009-named-goals"

investigation:
  match_mode: auto
  candidates_considered: 1
  note: |
    Investigated 2026-08-13 and DELIBERATELY NOT FIXED. Reproduced, quantified,
    and the shape of the fix established; the trade was judged bad today.

    It is not a one-liner. `_gave_back` computes
    `freed = released + min(holds, funded)` — a comparison in the META's
    currency whose result must then be expressed in COP. Carrying a `funded_cop`
    alongside `funded` is not enough, because when the `min` binds, the COP
    figure has to be apportioned rather than substituted. Making `funded` itself
    COP breaks the comparison against `holds`.

    So the fix threads a second accumulator through `_saved_in`, `_month_of` and
    `_walk` — the core of the module that took FIVE money fixes and three
    verification rounds on 2026-08-13, and where every defect found that day was
    invisible to a green suite. Opening it again, at the end of that day, to
    move three centavos nobody can see, is the wrong trade. Recorded as the
    owner's call rather than made silently.

fix_commits: []

harden_results:
  mutation_score: null
  arch_check: null
  bug_line_mutation_confirmed: false

gap_analysis: []

followups: []
---

# A dollar meta's give-back drifts by a centavo

## Why it is filed rather than fixed

It is one cent, below the peso, on a screen that shows no cents. Nothing the
owner reads changes. Every other money defect closed today moved millions.

## Why it is filed at all

Because it is the **cap** that drifts. Five fixes on 2026-08-13 exist to make
one sentence true — *nothing may be given back that no month ever put in* — and
this is the one input for which that sentence is false. A rule with a known
exception is a rule someone will later find a bigger hole in.

## The shape

```
the fold      →  converts each month's ask on its own, N times
_gave_back    →  compares meta-currency ints, converts the total once
```

`Σ round(xᵢ)` and `round(Σ xᵢ)` are not the same number. At TRM 3333,33 and
4123,77 they come apart by a cent.
