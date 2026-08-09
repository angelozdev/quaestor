> ▶ CP8 Harden — 6/7 criteria met | NEXT: the owner decides the CP5 independence question and runs `just backup && just migrate` | BLOCKED: the CP5/CP6 shared agent_id keeps the Principle 7 gate red for every checkpoint after it

# Progress — 009 named-goals

Metas: named savings goals beside the fund, not inside it. 45 ACs, 125
scenarios, all bound and green. Three migrations still outstanding and
human-owned. Refine has run — twelve findings, two real bugs, and one
regression of its own that left the acceptance stream red for twelve hours
while the other two streams reported green. Mutation then found 54 more
behaviours the suite could not tell from the real thing; the service now has
the unit test file it never had, and every real survivor is dead.

## Checkpoints

| CP | Stage | Status | Handoff |
|---|---|---|---|
| 1.5 | Ready | done | (promoted from discuss 2026-08-05) |
| 2 | ACs | done | 2026-08-08T1215-discover-acs.md |
| 3 | Spec | done | 2026-08-08T1610-atdd-redraft.md |
| 4 | Plan | done | 2026-08-08T2000-plan.md |
| 5 | Implement | **open** | 2026-08-08T2130-implement.md |
| 6 | Refine | **open** | 2026-08-09T0758-refine.md |
| 7 | Verify | **open** | 2026-08-09T0811-crap-analyzer.md |
| 8 | Harden | **open** | 2026-08-09T0901-mutation.md |

`dae_handoff.py --through 5` reports checkpoint 4 as the latest complete,
which is correct: CP5's independence criterion is asserted `met: false`
rather than papered over.

## Where the code stands

```
009        125 scenarios · unbound 0
010        unbound 0
acceptance 472 passed
backend    1042 passed
vitest     55 files · 397 passed
lint       exit 0
month load 13 bounded queries
mutation   metas.py 93.3% · rules.py 98.4% · 100% adjusted
```

## What the green suite did not catch

Four gaps, all the same shape — the service and the REST surface carried
a behaviour and no screen reached it, while the scenario pinning that
behaviour was `@backend` and bound at the services layer. All four were
found by driving the app in Chrome against a real server.

| Gap | Found | Fixed in |
|---|---|---|
| A purchase could be linked from Python, from nowhere a browser could reach | QA | 8408f99 |
| The available breakdown never left the server; /reports showed a column that did not add up | QA | 577e2af |
| The savings split had a service, an endpoint and a client, and no screen | QA | e0c57b8 |
| The /metas buttons rendered with no `onClick`; cancel, restore and contribute had no way in | QA | 25b0860 |

The lesson is specific and belongs to CP6/CP7: a feature whose screen
scenarios are thin and whose behaviour scenarios are all `@backend` will
report green over an app the owner cannot use.

## Handoff log

| When | Skill | Agent | Result |
|---|---|---|---|
| 2026-08-05T0933 | discuss | main | promoted; a meta is not a fund |
| 2026-08-08T1030 | prime-context | main | loaded |
| 2026-08-08T1215 | discover-acs | main | 38 → 45 ACs; the target month became mandatory |
| 2026-08-08T1340 | atdd | main | 87 scenarios; audited and returned NOT FIT |
| 2026-08-08T1610 | atdd (redraft) | main | 110 → 125 scenarios derived from the one rule, not transcribed |
| 2026-08-08T2000 | plan | main | ADR-0046 + product ADR-043 accepted; runbook created |
| 2026-08-08T2130 | implement | main | all streams green; independence NOT met |
| 2026-08-09T0758 | refine | main + 3 fresh reviewers | 12 findings applied, 2 bugs, 1 regression of its own; independence partial |
| 2026-08-09T0811 | crap-analyzer | subagent-crap-cp7 | 0 backend findings over 20; 11 lines no stream reaches, 4 of them 009's |
| 2026-08-09T0901 | mutation | subagent-mutation-cp8 | rules.py 96.9% strong, metas.py 56.3% weak; 54 real survivors |
| 2026-08-09T1005 | kill-mutants | main | `tests/services/test_metas.py` written; metas 93.3%, rules 98.4%; every real survivor dead |

## Outstanding

| What | Owner | How |
|---|---|---|
| Migrations 0014, 0015, 0016 | human (CHARTER §7) | `just backup && just migrate` |
| Decide how CP5/CP6 independence is closed | human | accept as documented, or send a fresh agent to verify CP5 against the 45 ACs |
| `PATCH /metas/{meta_id}`, reached by no stream | open | both ends are tested and the middle is not; a wrong query param stays green |
| `_Month.contributed` is written in three places and read in none | open | dead field CP8 surfaced; removing it is a refactor, not a test |

Production is clear for 0015: `SELECT count(*) FROM fund` returned 0
read-only on 2026-08-08, so nothing uses the dated rule it drops. The
SQLite sandbox is not clear — it holds one dated fund and 0015 aborts
that container's startup, which is the guard working.

## Tracker sync

- 2026-08-08: tracker `local` — feature files are the tracker (no-op).
  Roadmap item `named-goals` in-progress. `withdraw-target-by-date`
  absorbed into this feature rather than following it. feature.md status
  → in-progress.
