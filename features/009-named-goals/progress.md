> ▶ CP8 Harden — 5/6 criteria met | NEXT: merge `fix/meta-keeps-only-what-fits` into `main` (CHARTER §7) | BLOCKED: none

# Progress — 009 named-goals

Metas: named savings goals beside the fund, not inside it. 45 ACs, 146
scenarios. Merged to `main` on 2026-08-09. An independent review of the merged
code then found six more user-facing defects; those fixes, the scenarios that
catch them and a behaviour-preserving refactor merged on 2026-08-10 as
`ae5f0ae`. **Done.**

The green suite has been wrong six times in this feature, always the same way:
a behaviour reachable from Python and from no screen, or reachable from one
surface and not the other. 112 of the scenarios are `@backend`, bound at the
services layer.

Three independent verifiers traced all 45 ACs from a screen to a rule, each
against the code the previous round's fixes produced:

```
ronda 1   13 de 45 mal   3 cifras, 8 sin construir
ronda 2    9 de 45 mal   7 causados por arreglar los 13
ronda 3    6 de 45 mal   1 causado por arreglar los 9; los otros más viejos
```

Then a real-data lifecycle pass over HTTP found a seventh defect nobody had
looked for, and then an independent CP6 found six more. **That is the number
worth remembering: after three AC-tracing rounds and a real-data pass had all
closed, a fresh three-lens review of the merged code found six user-facing
defects.** AC tracing asks *does each criterion work*; refine asks *what is this
code actually doing*. Different questions, different bugs.

## Checkpoints

| CP | Stage | Status | Handoff |
|---|---|---|---|
| 1.5 | Ready | done | (promoted from discuss 2026-08-05) |
| 2 | ACs | done | 2026-08-08T1215-discover-acs.md |
| 3 | Spec | done | 2026-08-08T1610-atdd-redraft.md |
| 4 | Plan | done | 2026-08-08T2000-plan.md |
| 5 | Implement | done | 2026-08-08T2130-implement.md · three verify/close pairs |
| 6 | Refine | **done** | 2026-08-10T1100-refine-round2.md (superseding 2026-08-09T0758-refine.md) |
| 7 | Verify | **done** | 2026-08-10T1115-crap-analyzer-round2.md |
| 8 | Harden | **done** | 2026-08-10T1145-mutation-round2.md |

## The Principle 7 gate, and why it stays red

`dae_handoff.py --through 6` still reports the violation, and the report is
accurate about the file it names: `2026-08-09T0758-refine.md` carries
`agent_id: main-session`, the same agent that implemented CP5, because that day
main-session applied its own refine findings.

The round that supersedes it was written entirely by fresh agents —
`subagent-refine-cp6-{reuse,quality,efficiency}` reviewed;
`subagent-fix-cp6-bugs`, `subagent-refactor-cp6-{backend,dry,frontend}` and
`subagent-cp7-gaps` wrote every line. `main-session` dispatched, consolidated,
wrote the briefs, and independently reproduced each defect over HTTP before and
after. It wrote no code.

**The gate reads the first CP6 handoff, not the latest.** Rewriting that file
would turn the gate green by falsifying the record of what happened on
2026-08-09, so it was left alone. The substance is met and is measurable: the
independent lenses found six user-facing defects in code main-session had
written and shipped.

## Where the code stands

```
009           146 escenarios · unbound 0
backend      1126 passed        (era 1082 al mergear)
aceptación    493 passed        (eran 472)
vitest         56 archivos · 440 passed
lint          exit 0 · Contracts 2 kept, 0 broken
cobertura     backend unión 96,02% · frontend 84,1%
CRAP          0 hallazgos backend sobre 20; 3 frontend, los tres artefactos
mutación      297 mutantes · 287 muertos · 96,6% crudo · 99,7% ajustado
```

## What the independent CP6 found, after everything else had closed

Each reproduced over HTTP against today's production data restored into a
scratch database, before the fix and after it.

| Defect | What the owner would have seen |
|---|---|
| AC-45's warning compared the instalment in the meta's own currency against an income in pesos | A meta of US$20.000 costing $62.840.000 a month — 3,5× the income — warned about nothing |
| `plan_payment` wrote `meta_id` with no validation, while both sibling writers refused a cancelled meta | *Por pagar* accepted a payment pointed at a meta already called off (AC-25) |
| `complete` meant *bought, ever* | A meta raised after its purchase asked $70.000 this month **and** wore the *cumplida* badge; the button offered *Cerrar* instead of *Ponerle plata* |
| The preview's cache key omitted `stated_opening`, under a 30 s `staleTime` | AC-34's own example: the form kept saying $1.600.000 after the owner said he already had $3.000.000 of the $8.000.000 |
| The assistant's money-available card diverged from the screen three ways | Closed metas named at −0,00 in every month out to 2028; no mark on the cancelled ones; every give-back called a cancellation even when the amount had merely been lowered |
| The contributions endpoint returned the latest month's row | The toast reported a figure the owner never entered (API-only; the screen always sends the current month) |

Three further reports were triaged **out** after reading the code: a full meta
reading `complete=False` (deliberate — AC-17, a full meta waits for the
purchase), closing a running meta returning 422 (correct — AC-39, a running
meta is cancelled not closed), and `/metas/archived` omitting closed metas
(documented in `list_archived`).

## What CP7 exposed that no round had looked at

009 shipped **four migrations and no migration test** — the first feature in the
repo to break that pattern, on the only code it added that touches real data
irreversibly. The 329 lines were not even in the coverage denominator:
`migrations/versions/` has no `__init__.py`, so coverage.py never discovers it.
`0015`'s guard against withdrawing the dated fund rule while a fund still uses
it had never fired in a test, having only ever run against an empty database.

Also: `frontend/lib/api/metas.ts` had an lcov record of `FNF:12 / FNH:0` —
twelve functions, none executed, because every screen test mocks the module. A
covered screen and a covered router, joined by twelve URLs and verbs that
nothing asserted.

All closed: four migration tests, a client-contract test, two to-pay tests and
three not-found tests. The residue fell from eleven lines to none.

## Outstanding

| What | Owner | How |
|---|---|---|
| ~~The SQLite sandbox crash-loops~~ | — | **Closed 2026-08-10.** The sandbox held one fund on the withdrawn dated rule, so 0015 refused and the container never finished booting — the guard working, not a bug. Its intent was preserved rather than deleted: the fund became a meta wanting the same $10.000.000 by 2026-09. Backup at `.dev-data/quaestor.pre-0016.db` |

## Found here, not 009's, filed rather than fixed

- **`just lint` breaks whenever anyone generates frontend coverage.** Biome does
  not honour `.gitignore` here, so `frontend/coverage/` — 4 MB of generated HTML
  — produced 623 errors and a red gate.
- **`tests/test_scheduler.py::TestRunOnce::test_run_once_success` is not
  hermetic.** It builds its engine from `QUAESTOR_DB` rather than the in-memory
  test engine, so it passes only because direnv loads the gitignored
  `backend/.env.local.sqlite`. Pointed at a fresh path it fails in 0.07s with
  `no such table: recurring_item`. **`1126 passed` is a statement about this
  machine, not about the repository.**
- **The plan dialog's *Cuenta* and *Monto* labels carry no `htmlFor`** and their
  controls no `id`, so neither is reachable by label — unlike every other field
  in that dialog.

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
| 2026-08-09T1005 | kill-mutants | main | every real survivor dead |
| 2026-08-09T1111 | verify-implementation | subagent-verify-cp5 | 32 of 45 ACs reachable; 3 wrong figures, 8 unbuilt |
| 2026-08-09T1230 | close-findings | main | all 13 closed; product ADR-044 + ADR-0048 |
| 2026-08-09T1400 | verify (round 2) | subagent-verify-cp5-round2 | 34 of 45 correct; 9 wrong |
| 2026-08-09T1510 | close-findings (round 2) | main | all 9 closed; ADR-0049 |
| 2026-08-09T1640 | verify (round 3) | subagent-verify-cp5-round3 | 36 of 45 correct; 6 wrong, 3 partial, 1 rebutted |
| 2026-08-09T1745 | close-findings (round 3) | main | 6 closed, 3 partials closed, 1 rebutted |
| 2026-08-09T2020 | real-data lifecycle | main | a 7th defect: two single-field edits reverted each other |
| 2026-08-10T1100 | refine (round 2) | 3 lenses + 4 appliers, all fresh | 39 findings; 6 user-facing defects; 7 refactor items byte-identical |
| 2026-08-10T1115 | crap-analyzer (round 2) | subagent-crap-cp7-round2 | 96,02% union; residue 11 → 3 lines, then 0 |
| 2026-08-10T1145 | mutation (round 2) | subagent-mutation-cp8-round2 | 99,7% adjusted; 9 equivalent survivors, 1 real gap left open for an AC |
| 2026-08-10T1230 | atdd (defect scenarios) | subagent-atdd-cp3-defects | 139 → 145 scenarios, additions only; 5 proven red at 46af2da, 1 control arm green on both sides |
| 2026-08-10T1400 | atdd (AC-39 clause) | subagent-atdd-ac39-close-before-start | product ADR-045; CP8's last real survivor killed at stage 2 |

## Tracker sync

- 2026-08-10: tracker `local` — feature files are the tracker (no-op). 009
  stays `in-progress` until `cp6-independent-review` merges. Roadmap items
  `named-goals` and `withdraw-target-by-date` still in-progress for the same
  reason.

## Fix applied — 2026-08-13-a-meta-swallows-what-it-cannot-take
- Severity: high; user-blocking: no
- Followups: 3 advisory, 0 blocker applied inline
- See `.engineer/fixes/2026-08-13-a-meta-swallows-what-it-cannot-take.md`

Two money defects were found in the merged code on 2026-08-12 by a browser QA
sweep and by the independent verifier of the fix that followed. Both were the
same sentence — nothing tied what a meta took of a hand contribution to what
the month was charged for it — and neither could be seen by mutation, because
the code and the tests agreed.
