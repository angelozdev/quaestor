> ▶ Shipped pre-DAE; ATDD coverage paused at consolidation #15 | NEXT: unpause after the sinking-funds redesign (features/003) | BLOCKED: none

# Progress — 001 budgets-safe-to-spend

Shipped before DAE adoption (onboarding intake 2026-07-28). No `acs.md` and no
`spec.md`: acceptance coverage is consolidation task #15, deliberately paused
because the sinking-funds redesign (features/003) replaces these formulas and
writing acceptance tests for them now would be wasted work.

## Checkpoints

| CP | Stage | Status | Handoff |
|---|---|---|---|
| 2 | ACs | aborted | 2026-07-31T0939-discover-acs.md |

The 2026-07-31 discovery interview ran (four behavior decisions confirmed by
Angelo) but stopped before writing `acs.md` on finding the consolidation pause.
The decisions were routed to `features/003-sinking-funds`; one of them — reject
envelope assignment to archived or budget-excluded categories — was independent
of the redesign and became a fix.

## Fixes

| When | Fix | Result |
|---|---|---|
| 2026-07-31 | `2026-07-31-phantom-budget-assignment` | closed — `set_budget` now rejects archived and budget-excluded categories; pinned by three service-layer regression tests, bug-line gate passed, mutation 3/3. Production `budget` table was empty, so no real data was affected. Handoff: `.engineer/handoffs/2026-07-31-phantom-budget-assignment-close.md` |

## Open followups

- When #15 unpauses: land "archived and budget-excluded categories cannot hold
  an envelope" as an AC in `acs.md` and propagate to `spec.md` (gap:
  `missing_ac`). The rule is already enforced in code — only the paper trail is
  missing. Logged in `.engineer/consolidation.md` under task #15.
