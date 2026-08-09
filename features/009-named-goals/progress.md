> ▶ CP5 Implement — 7/9 criteria met | NEXT: the owner runs `just backup && just migrate` for 0015 and 0016, then the merge | BLOCKED: the CP5/CP6 shared agent_id keeps the Principle 7 gate red for every checkpoint after it

# Progress — 009 named-goals

Metas: named savings goals beside the fund, not inside it. 45 ACs, 125
scenarios, all bound and green. Three migrations still outstanding and
human-owned.

The green suite has been wrong five times in this feature, always the same
way: a behaviour reachable from Python and from no screen, pinned by an
`@backend` scenario bound at the services layer. 112 of the 125 scenarios are
that shape.

Refine found two bugs and left the acceptance stream red for twelve hours
behind two green ones. Mutation found 54 behaviours the suite could not tell
from the real thing. Three independent verifiers have now traced all 45 ACs from a screen to a rule,
each against the code the previous round's fixes produced:

```
ronda 1   13 de 45 mal   3 cifras, 8 sin construir
ronda 2    9 de 45 mal   7 causados por arreglar los 13
ronda 3    6 de 45 mal   1 causado por arreglar los 9; los otros más viejos
```

Round three's worst was the app **minting money**: cancelling a meta the owner
had contributed to handed that contribution back without ever having stopped
charging it. Four green streams saw every one of the twenty-eight.

## Checkpoints

| CP | Stage | Status | Handoff |
|---|---|---|---|
| 1.5 | Ready | done | (promoted from discuss 2026-08-05) |
| 2 | ACs | done | 2026-08-08T1215-discover-acs.md |
| 3 | Spec | done | 2026-08-08T1610-atdd-redraft.md |
| 4 | Plan | done | 2026-08-08T2000-plan.md |
| 5 | Implement | **open** | 2026-08-08T2130-implement.md · three verify/close pairs, the last `2026-08-09T1640-verify-round3.md` + `2026-08-09T1745-close-round3.md` |
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
009        137 scenarios · unbound 0
010        unbound 0
acceptance 484 passed
backend    1082 passed
vitest     55 files · 421 passed
lint       exit 0 · Contracts 2 kept, 0 broken
knip       0 findings
dup        43 clones · 1.96%
month load 13 bounded queries
mutation   metas.py 95.9% · rules.py 98.4% · both 100% adjusted
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
| A closed meta was charged by the month and named by nothing (AC-4, 31, 32, 36, 37, 38) | verifier 2 | 43a3fb7 |
| A meta kept on with a new amount or month moved no figure, and took contributions that vanished (AC-8) | verifier 2 | 43a3fb7 |
| A planned purchase stopped the meta, which AC-43 says it must not | verifier 2 | 43a3fb7 |
| A past month stopped naming a meta closed later (AC-27) | verifier 2 | 43a3fb7 |
| A dollar meta's instalment was summed as pesos in three columns (AC-26) | verifier 2 | 43a3fb7 |
| Cancelling a meta contributed to gave the contribution back twice (AC-15) | verifier 3 | eea63a1 |
| The report totalled $0 over a table listing $1.600.000 (AC-36) | verifier 3 | eea63a1 |
| A meta closed after being lowered never left the screen (AC-16, AC-29) | verifier 3 | eea63a1 |
| `POST /planned` dropped `meta_id` and the form had no selector (AC-43) | verifier 1 and 3 | eea63a1 |

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
| 2026-08-09T1400 | verify-implementation (round 2) | subagent-verify-cp5-round2 | 34 of 45 correct; 9 wrong, 7 of them ADR-0048's collateral |
| 2026-08-09T1510 | close-findings (round 2) | main | all 9 closed; ADR-0049 supersedes ADR-0048's implementation clauses |
| 2026-08-09T1640 | verify-implementation (round 3) | subagent-verify-cp5-round3 | 36 of 45 correct; 6 wrong, 3 partial, 1 report rebutted |
| 2026-08-09T1745 | close-findings (round 3) | main | 6 closed, 3 partials closed, 1 rebutted with its reproduction |

## Outstanding

| What | Owner | How |
|---|---|---|
| Whether a fourth verifier runs | human | 13, then 9, then 6 — decreasing, not yet zero |
| Migrations 0015, 0016 | human (CHARTER §7) | `just backup && just migrate` |
| Merge to `main` | human (CHARTER §7) | — |

**The acceptance suite saw none of the twenty-eight, and the reason is
structural.** No scenario closes a meta in a month where closing can move a
figure; AC-39's only close is in January over a December purchase. No scenario
cancels a meta that was contributed to. AC-43 asserts only *is running*. Twelve scenarios that catch them are in, approved by the owner, with
every figure run against the service rather than reasoned out. **Eleven of the
twelve go red against the code they were written to catch**; the twelfth is
AC-8's control arm and must pass on both sides. 009 goes from 125 scenarios to
137, the pipeline from 472 to 484.

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
