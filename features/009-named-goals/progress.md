> ▶ CP5 Implement — 8/10 criteria met | NEXT: the owner runs `just backup && just migrate` for 0015 and 0016 | BLOCKED: the CP5/CP6 shared agent_id keeps the Principle 7 gate red for every checkpoint after it

# Progress — 009 named-goals

Metas: named savings goals beside the fund, not inside it. 45 ACs, 125
scenarios, all bound and green. Three migrations still outstanding and
human-owned.

The green suite has now been wrong four times in this feature, and each time
the same way: a behaviour reachable from Python and from no screen, pinned by
an `@backend` scenario bound at the services layer. 112 of the 125 scenarios
are that shape. Refine found two bugs and left the acceptance stream red for
twelve hours behind two green ones. Mutation found 54 behaviours the suite
could not tell from the real thing. An independent verifier then traced all 45
ACs from a screen to a rule and found thirteen that could not be reached —
three of them wrong figures, eight of them unbuilt.

## Checkpoints

| CP | Stage | Status | Handoff |
|---|---|---|---|
| 1.5 | Ready | done | (promoted from discuss 2026-08-05) |
| 2 | ACs | done | 2026-08-08T1215-discover-acs.md |
| 3 | Spec | done | 2026-08-08T1610-atdd-redraft.md |
| 4 | Plan | done | 2026-08-08T2000-plan.md |
| 5 | Implement | **open** | 2026-08-08T2130-implement.md · 2026-08-09T1111-verify-implementation.md · 2026-08-09T1230-close-findings.md |
| 6 | Refine | **open** | 2026-08-09T0758-refine.md |
| 7 | Verify | **open** | 2026-08-09T0811-crap-analyzer.md |
| 8 | Harden | **open** | 2026-08-09T0901-mutation.md |

`dae_handoff.py --through 5` reports checkpoint 4 as the latest complete, and
fails on Principle 7. Both are correct and neither is worked around: the gate
takes the **first** CP5 handoff as the implementer's, so `main-session` stays
the recorded implementer and CP6 — also `main-session`, because the implementer
applied refine's findings — keeps sharing it. The verification handoff attests
CP5 independently; it does not launder CP6.

## Where the code stands

```
009        125 scenarios · unbound 0
010        unbound 0
acceptance 472 passed
backend    1063 passed
vitest     55 files · 417 passed
lint       exit 0 · Contracts 2 kept, 0 broken
knip       0 findings
dup        43 clones · 1.96%
month load 13 bounded queries
mutation   metas.py 96.5% · rules.py 98.4% · both 100% adjusted
```

## What the green suite did not catch

Four screens, then three figures, then eight behaviours — one shape.

| Gap | Found | Fixed in |
|---|---|---|
| A purchase could be linked from Python, from nowhere a browser could reach | QA | 8408f99 |
| The available breakdown never left the server; /reports showed a column that did not add up | QA | 577e2af |
| The savings split had a service, an endpoint and a client, and no screen | QA | e0c57b8 |
| The /metas buttons rendered with no `onClick` | QA | 25b0860 |
| Closing a bought meta erased it from every month, past ones included | verifier | 2eb1d13 |
| A meta went on asking after the thing was bought | verifier (behind the above) | 2eb1d13 |
| A contribution was trimmed against the stored amount, not the amended one | verifier | 2eb1d13 |
| A closed meta was listed as cancelled, with a button that charged the month | verifier | 2eb1d13 |
| Eight behaviours in Python and on no screen (AC-11, 16, 19, 26, 34, 36, 41, 42) | verifier | 13253a8 |
| `PATCH /metas/{id}` reached by no stream | crap-analyzer | 60aca13 |

## Handoff log

| When | Skill | Agent | Result |
|---|---|---|---|
| 2026-08-05T0933 | discuss | main | promoted; a meta is not a fund |
| 2026-08-08T1030 | prime-context | main | loaded |
| 2026-08-08T1215 | discover-acs | main | 38 → 45 ACs; the target month became mandatory |
| 2026-08-08T1340 | atdd | main | 87 scenarios; audited and returned NOT FIT |
| 2026-08-08T1610 | atdd (redraft) | main | 110 → 125 scenarios derived from the one rule |
| 2026-08-08T2000 | plan | main | ADR-0046 + product ADR-043 accepted; runbook created |
| 2026-08-08T2130 | implement | main | all streams green; independence NOT met |
| 2026-08-09T0758 | refine | main + 3 fresh reviewers | 12 findings, 2 bugs, 1 regression of its own |
| 2026-08-09T0811 | crap-analyzer | subagent-crap-cp7 | 0 backend findings over 20; 11 lines no stream reaches |
| 2026-08-09T0901 | mutation | subagent-mutation-cp8 | rules.py 96.9%, metas.py 56.3%; 54 real survivors |
| 2026-08-09T1005 | kill-mutants | main | `tests/services/test_metas.py` written; every real survivor dead |
| 2026-08-09T1111 | verify-implementation | subagent-verify-cp5 | 32 of 45 ACs reachable; 3 wrong figures reproduced, 8 unbuilt |
| 2026-08-09T1230 | close-findings | main | all 13 closed; product ADR-044 + ADR-0048 |

## Outstanding

| What | Owner | How |
|---|---|---|
| Migrations 0015, 0016 | human (CHARTER §7) | `just backup && just migrate` |
| Merge to `main` | human (CHARTER §7) | — |

Production is clear for 0015: `SELECT count(*) FROM fund` returned 0
read-only on 2026-08-08, so nothing uses the dated rule it drops. The
SQLite sandbox is not clear — it holds one dated fund and 0015 aborts
that container's startup, which is the guard working.

Closed since the last entry: `_Month.contributed` deleted (`2a3e2ee`); the
contributions history reversed from **delete** to **build**, because the owner
chose to close 009 only when all 45 ACs are reachable from the app; the CP5/CP6
independence question answered by dispatching a fresh verifier rather than
accepting it as documented.

Known and deliberately not 009's: a screen that hits `MissingRate` shows a
generic error rather than naming the TRM. That is app-wide and predates metas
(the settings screen is where the rate is set, and it does name it).

## Tracker sync

- 2026-08-08: tracker `local` — feature files are the tracker (no-op).
  Roadmap item `named-goals` in-progress. `withdraw-target-by-date`
  absorbed into this feature rather than following it. feature.md status
  → in-progress.
