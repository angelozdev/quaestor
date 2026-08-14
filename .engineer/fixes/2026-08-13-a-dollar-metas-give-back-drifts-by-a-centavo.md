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
  They differ by ±1 cent in COP over the meta's life. `_gave_back` compares
  meta-currency ints and converts the total ONCE, while each month's ask was
  converted on its own by the fold. Summing N rounded conversions is not the
  same as rounding one sum.

  Sub-peso, so it never reaches a figure the owner reads. But it is the only
  known case where the give-back cap — the thing five money fixes were written
  to install — can be crossed at all.

feature_refs:
  - "features/009-named-goals"

investigation:
  match_mode: auto
  candidates_considered: 1
  note: |
    Not yet investigated. The question to settle first is whether the fix
    belongs in `_gave_back` (convert per month, like the fold does) or in the
    fold (carry the COP figure alongside the meta-currency one). ADR-0031's
    single scalar TRM means both are available; which is right depends on
    whether the cap is a statement about the meta's currency or about pesos.

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
