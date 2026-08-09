> ▶ CP5 Implement — 5/6 criteria met | NEXT: owner runs `just backup && just migrate`, then /engineer.refine on a fresh agent | BLOCKED: verification independence is unmet by construction — one agent wrote the plan, the code and its own handoff

# Progress — 009 named-goals

Metas: named savings goals beside the fund, not inside it. 45 ACs, 125
scenarios, all bound and green. Three migrations still outstanding and
human-owned. CP6/7/8 open and blocked on a fresh agent, not on the code.

## Checkpoints

| CP | Stage | Status | Handoff |
|---|---|---|---|
| 1.5 | Ready | done | (promoted from discuss 2026-08-05) |
| 2 | ACs | done | 2026-08-08T1215-discover-acs.md |
| 3 | Spec | done | 2026-08-08T1610-atdd-redraft.md |
| 4 | Plan | done | 2026-08-08T2000-plan.md |
| 5 | Implement | **open** | 2026-08-08T2130-implement.md |
| 6 | Refine | not started | — |
| 7 | Verify | not started | — |
| 8 | Harden | not started | — |

`dae_handoff.py --through 5` reports checkpoint 4 as the latest complete,
which is correct: CP5's independence criterion is asserted `met: false`
rather than papered over.

## Where the code stands

```
009        125 scenarios · unbound 0
010        unbound 0
backend    1010 passed
vitest     55 files · 397 passed
lint       clean
month load 14 bounded queries
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

## Outstanding

| What | Owner | How |
|---|---|---|
| Migrations 0014, 0015, 0016 | human (CHARTER §7) | `just backup && just migrate` |
| CP6 refine | fresh agent | Principle 7 — the implementer cannot refine its own code |
| CP7 crap-analyzer | fresh agent | |
| CP8 mutation | fresh agent | `domain/rules.py` and `services/metas.py` only, per plan.md |

Production is clear for 0015: `SELECT count(*) FROM fund` returned 0
read-only on 2026-08-08, so nothing uses the dated rule it drops. The
SQLite sandbox is not clear — it holds one dated fund and 0015 aborts
that container's startup, which is the guard working.

## Tracker sync

- 2026-08-08: tracker `local` — feature files are the tracker (no-op).
  Roadmap item `named-goals` in-progress. `withdraw-target-by-date`
  absorbed into this feature rather than following it. feature.md status
  → in-progress.
