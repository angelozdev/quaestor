---
skill: atdd-mutate
agent_id: subagent-mutation-cp8-round2
feature: 009-named-goals
started: 2026-08-10T1030
ended: 2026-08-10T1145
checkpoint: 8
artifacts:
  - features/009-named-goals/handoffs/2026-08-10T1145-mutation-round2.md
exit_criteria:
  - criterion: The checkpoint's entry gate is clean
    verified_by: tool
    met: false
    evidence: "`dae_handoff.py features/009-named-goals --through 7` fails for the same reason CP7's did: the gate reads the FIRST CP6 handoff, `2026-08-09T0758-refine.md`, which records `agent_id: main-session` and correctly says main-session applied its own findings. NOT MET AND NOT CLAIMED. The superseding `2026-08-10T1100-refine-round2.md` was written entirely by fresh agents; the old handoff was left as the audit trail of what happened that day rather than rewritten to turn the gate green."
  - criterion: Verification independence for THIS checkpoint (Principle 7)
    verified_by: judgment
    met: true
    evidence: "`agent_id: subagent-mutation-cp8-round2`, a fresh agent, distinct from the CP5 implementer (`main-session`), from every CP6 applying agent, from CP7's `subagent-crap-cp7-round2`, and from the previous CP8 (`subagent-mutation-cp8`)."
  - criterion: Mutation ran in isolation, not in the shared checkout
    verified_by: tool
    met: true
    evidence: "Ran in its own git worktree at `.claude/worktrees/agent-adff0f922b45c7e7e`, reset to `cf81348`. This is the direct remedy for the previous CP8, which swept the shared checkout and left `services/metas.py` as an AST round-trip of itself with `# noqa: E712` stripped — `ruff check` reported 18 errors, which would have stopped `run-acceptance-tests.sh` at the lint gate before a single test ran. Worktree removed by main-session after the report (`git worktree remove --force`, `git worktree prune`, branch deleted); `git worktree list` now shows only the main checkout."
  - criterion: Every stage was green-gated against untouched source before the sweep
    verified_by: tool
    met: true
    evidence: "Six `[baseline] … pass` lines, one per stage per target, in `scratchpad/mutation-cp8.progress.log`, all against `ast.unparse`-round-tripped source. Ladder, cheapest first: (1) 146 focused tests over `test_rules.py`, `test_fund_rules.py`, `test_metas.py`, `test_metas.py` (api), `test_month_aggregate.py`, ~6s; (2) the eight generated acceptance dirs, 486 tests, ~29s; (3) the full backend suite, 1125 tests, ~60s. The acceptance stream is cheaper than the full unit suite here, so it sits second."
  - criterion: The scope is what plan.md opted in
    verified_by: tool
    met: true
    evidence: "`backend/src/quaestor/services/metas.py` and `backend/src/quaestor/domain/rules.py`, exactly the two modules feature 009's plan.md Test strategy names. Zero mutants skipped."
  - criterion: Every survivor was read and judged, not counted
    verified_by: judgment
    met: true
    evidence: "Ten survivors, each with a verdict and a reason below. Nine equivalent, one a real gap — and the real one was NOT killed, because no acceptance criterion says what the behaviour should be and pinning the current value would have invented the rule from the code. That refusal is the finding."
findings_summary: "COMBINED 297 MUTANTS, 287 KILLED, 10 ALIVE — 96.6% RAW, 99.7% ADJUSTED. `services/metas.py` 169/161/8 = 95.3% raw, 99.4% adjusted; `domain/rules.py` 128/126/2 = 98.4% raw, 100% adjusted. `rules.py` improved from the previous round's 96.9%. THE NINE EQUIVALENT SURVIVORS. Four are `frozen=True` → `frozen=False` on `MetaPreview`, `_Month`, `_Walked` and `MetaFold` — each built once and only read, no field assignment, no `dataclasses.replace`, no hashing anywhere in src, tests or acceptance; `frozen` is a design constraint with no observable behaviour. One is `metas.py:182` `opening > amount` → `>=`, where the arms coincide exactly at equality: the mutant returns holds=amount, released=0, and the fall-through computes ask=0 and contributed=0 for the same holds=amount, released=0 — verified including a pending contribution, and AC-16's 'strictly below completes' is safe either way because completion is read off `released > 0`. Two are `metas.py:243` `… if amount else 0` → `else 1` / `else 2`, an arm no reachable state enters: `create_meta` with 0 and with −1, and `set_meta` with 0, are all refused with 'a meta needs an amount above zero'. One is `rules.py:133` `missing <= 0` → `< 0`, identical at zero, verified for months_left in {−3, 0, 1, 3, 12}. One is `rules.py:150`'s floor `max(months_between(…) + 1, 1)` → `max(…, 0)`, masked because both callers feed the result into `fund_ask_calc`, which applies its own `max(months_left, 1)` — the floor in `months_to_meta` is dead code duplicating a floor downstream. Its sibling on the same line, `+ 1` → `+ 0`, which IS AC-2/AC-18's 'the named month is a month that saves', died at stage 1. THE ONE REAL GAP, AND WHY IT WAS LEFT OPEN: `metas.py:210`, `_walk`'s branch for a month before the meta's `start_month`, `finished=False` → `finished=True`. Its only reader that sees the value is `close_meta`. Reproduced over HTTP against a copy of production by main-session: closing a meta that starts 2026-08 as of 2026-07, 2026-06 or 2025-01 is refused today with 'the meta is still running, so it is cancelled rather than closed'; under the mutant it succeeds and archives the meta. Reachable, because `POST /metas/{id}/close?month=…` takes the month as a caller-supplied query parameter. NOTHING IN acs.md SAYS WHAT CLOSING A META AS OF A MONTH BEFORE IT EXISTED SHOULD DO. AC-39 governs closing after the purchase. The current refusal is a defensible reading of AC-27 — every figure derives from the month being read, and in July the meta had not finished — but that is the code's choice, not the spec's, so no test was written to pin it."
human_action_needed: yes
human_action_kind: decision
recommended_next: "One decision: what should `POST /metas/{id}/close?month=M` do when M is before the meta's start month? The screen never sends such a month (`metas/page.tsx` always sends the current one), so this is an API-surface question. If the refusal is right, it wants an acceptance criterion and a scenario, and the survivor dies with it. Then the owner merges `cp6-independent-review` into `main` (CHARTER §7)."
tracker_update: "local — 009 at checkpoint 8 complete, status in-progress. Mutation 297 mutants, 287 killed, 99.7% adjusted across the two opted-in modules. Nine survivors equivalent with reasons; one real gap left open pending an AC. Ran in an isolated worktree, since removed. CP8 closed."
status: complete
---

# atdd-mutate (round 2) — handoff summary

## What the score does not prove, in the agent's own accounting

- **The frontend was not mutated and its stream did not run here.** `pnpm` aborts
  in a fresh worktree with `ERR_PNPM_IGNORED_BUILDS: esbuild`. Stage 2 invoked
  pytest over the generated dirs directly, so vitest gated nothing. Any 009
  behaviour bound only to a vitest scenario — AC-5's progress figure, AC-44's
  ordering — is reached in stage 1 only through `tests/services/test_metas.py`.
- **The mutator rewrites operators, boolean constants, small integer constants
  and six builtin names.** It never deletes a statement, reorders arguments or
  swaps one variable for another, so a term left out of a sum, or the wrong
  meta's row read, is outside what 99.7% speaks to.

## The finding that is not about 009

`tests/test_scheduler.py::TestRunOnce::test_run_once_success` had to be
deselected from stage 3: it is red in a fresh worktree before any mutation,
because `jobs.daily.main()` builds its engine from `QUAESTOR_DB` — default
`sqlite:///quaestor.db` — rather than the in-memory test engine. In this
checkout direnv loads the gitignored `backend/.env.local.sqlite`, which points at
a migrated file, so it passes here.

Main-session reproduced it independently: pointing `QUAESTOR_DB` at a fresh
sqlite path makes it fail with `no such table: recurring_item` in 0.07s.

**So `1126 passed` is a statement about this machine, not about the repository.**
On a clean clone, or in CI, that test is red. It is outside 009's blast radius
and was not fixed here.
