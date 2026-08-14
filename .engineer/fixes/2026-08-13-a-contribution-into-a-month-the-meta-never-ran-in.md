---
slug: "2026-08-13-a-contribution-into-a-month-the-meta-never-ran-in"
title: "A contribution into a month before the meta existed is accepted and reaches nothing"
severity: medium
blocks_user: false
workaround: "remove it from the meta's history and make it again in a month the meta ran in"
status: closed

source:
  kind: internal
  ref: "found by the CP7 verifier of fix 2026-08-13-a-meta-swallows-what-it-cannot-take"

repro: |
  1. Open a meta "Celular" for 8.000.000 COP by 2026-12, starting 2026-10.
  2. Contribute 1.000.000 COP into 2026-08 — two months before the meta existed.
  3. The app accepts it and lists it in the meta's history.
  4. Read 2026-08, 2026-10 and 2026-12.

expected: "The app refuses it: that meta did not exist in August (the owner's decision, 2026-08-13)."
actual: |
  Accepted and stored. It reaches no month and no meta:

    2026-08   holds          0,00   contributed 0,00   free          0,00
    2026-10   holds  2.666.666,67   contributed 0,00   free  2.333.333,33
    2026-12   holds  8.000.000,00   contributed 0,00   free -2.666.666,66
    the meta's own history still lists it at 1.000.000,00

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
          FAILED test_a_contribution_into_a_month_the_meta_never_ran_in_is_refused
                 the contribution was accepted, expected a refusal
          2 failed, 141 passed in 7.47s

          Its boundary scenario — a past month the meta DID run in still takes a
          contribution — was green before and after, so the refusal is pinned in
          both directions.

fix_commits:
  - "32bcc7f fix(009): the app stops taking money it cannot put anywhere"

harden_results:
  mutation_score: 0.957
  arch_check: "pass — cd backend && uv run lint-imports: Contracts: 2 kept, 0 broken"
  bug_line_mutation_confirmed: true

handoff_path: .engineer/handoffs/2026-08-13-metas-refuse-what-cannot-land-close.md

gap_analysis:
  - category: missing_ac
    phase: discover-acs
    finding: "AC-10 said `Aportar` adds money 'on any month' and nothing ever asked which months a meta has. The write path trimmed to what fitted and the read path started at `start_month`, so the two disagreed about a month neither had been told about."
    followup_kind: amend_ac

followups:
  - category: missing_ac
    action: "AC-10 now says any month the meta has RUN in, with a scenario for the refusal and one holding down that a past month it did run in still takes a contribution"
    status: applied
---

# A contribution into a month the meta never ran in

## Where the write path stops looking

`contribute()` trims to `_room_left`, and `_room_left` asks the walk:

```python
def _room_left(session, meta, year_month):
    agg = load_month(session, year_month)
    if _finished_before(agg, meta, year_month):
        return 0
    wanted, _ = _wanted_in(agg, meta, year_month)
    return wanted - _walk(agg, meta).month.holds
```

`_walk` answers `holds = 0` for a month before `meta.start_month`, so the room
comes out as the whole amount and the write is accepted. The same `_walk` then
never calls `_month_of` for that month at all, so nothing ever reads the row.

## What the owner decided

**Refuse it** (2026-08-13). The alternative offered was moving the contribution
to the meta's first month; it was declined.

Before the fix this row also stole money — the month was charged for it while
the meta held nothing. `2026-08-13-a-meta-swallows-what-it-cannot-take` closed
that half, which is what turned a theft into a silent no-op. Both halves came
from the same place: nothing tied what the owner offered to what the meta could
take.

## Note for the pin

The regression has to assert the refusal **and** that the meta's history no
longer lists a row that does nothing (AC-42 lists contributions at face value).
