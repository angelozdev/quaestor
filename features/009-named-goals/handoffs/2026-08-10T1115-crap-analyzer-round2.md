---
skill: crap-analyzer
agent_id: subagent-crap-cp7-round2
feature: 009-named-goals
started: 2026-08-10T1020
ended: 2026-08-10T1115
checkpoint: 7
artifacts:
  - features/009-named-goals/handoffs/2026-08-10T1115-crap-analyzer-round2.md
exit_criteria:
  - criterion: The checkpoint's entry gate is clean
    verified_by: tool
    met: false
    evidence: "`dae_handoff.py features/009-named-goals --through 6` → `verifier-independence violated: CP6 handoff 2026-08-09T0758-refine.md shares agent_id main-session with the CP5 implement handoff`, exit 1. NOT MET AND NOT CLAIMED. The gate reads the FIRST CP6 handoff, which is the 2026-08-09 one and correctly records that main-session applied its own findings. The superseding round — `2026-08-10T1100-refine-round2.md` — was written entirely by fresh agents and asserts independence met, but the old handoff is the audit trail of what happened that day and was not rewritten to turn the gate green."
  - criterion: Verification independence for THIS checkpoint (Principle 7)
    verified_by: judgment
    met: true
    evidence: "`agent_id: subagent-crap-cp7-round2`, a fresh agent that wrote none of the code under measurement and is distinct from the CP5 implementer (`main-session`), from every CP6 applying agent, and from the previous CP7 (`subagent-crap-cp7`)."
  - criterion: Real coverage was generated for every stream, not assumed
    verified_by: tool
    met: true
    evidence: "Backend unit — `TOTAL 5171 227 96%` and `1096 passed, 1 warning in 87.66s`. Backend acceptance, the eight generated dirs re-run under coverage — `TOTAL 5171 1385 73%` and `486 passed, 1 warning in 52.10s`. Union of the two: 4965/5171 = 96.02%, missing 206. Frontend — `Test Files 55 passed (55) / Tests 424 passed (424)`, `Statements 84.1% (7093/8434) / Branches 86.58% (1278/1476) / Functions 60.49% (513/848)`. `pytest-cov` is not in the backend venv; `uv run --with pytest-cov` supplied it per invocation and installed nothing."
  - criterion: CRAP computed over the feature's changed code, both languages
    verified_by: tool
    met: true
    evidence: "Diff base `4c3b3062c1e526c8761f80a67cd5dc29c27b678b` — main immediately before 009 merged. Backend, union coverage, threshold 20: no findings. Highest scorer in the whole blast radius is `services/month_aggregate.py load_month_aggregate` at 17.0 with 100% coverage. Frontend, threshold 20: three findings — `to-pay/page.tsx ToPayPage` 102.45, `transaction-create-dialog.tsx` 40.45, `categories/page.tsx CategoriesPage` 25.2."
  - criterion: Every finding above threshold was read before being judged
    verified_by: judgment
    met: true
    evidence: "All three frontend findings read in full and attributed line by line against 009's diff. All three are artefacts of one measurement error, named precisely: the analyzer scores the whole enclosing function, and a Next.js page component's body is the entire file — 410 lines for `ToPayPage`. Of `transaction-create-dialog`'s 69 uncovered lines, zero belong to 009 (they are the pre-existing transfer tab and its mutation body); of `CategoriesPage`'s 13, zero (009 added one checkbox in 8 covered lines); of `ToPayPage`'s 159, exactly one — line 138 — and that one was a real hole, since closed."
  - criterion: Report only — no refactor applied, no test written
    verified_by: tool
    met: true
    evidence: "`git status --short` at exit returned the same two entries as at entry (` M .engineer/roadmap.md`, `?? .claude/skills/record-movements/`), neither this agent's. `backend/.coverage` appeared during the runs and was deleted. All reports live in the session scratchpad."
findings_summary: "THE RESIDUE FELL FROM ELEVEN LINES TO THREE, AND THE THREE THAT REMAIN HAVE NO CRITERION BEHIND THEM. Union backend coverage 96.02%; zero backend CRAP findings above 20, for the second round running. Four of the five gaps the previous CP7 named are now closed by CP6's tests: `PATCH /metas/{id}`'s adapter body, `_amend`'s replace-this-month branch (whose docstring had promised a behaviour nothing verified), `_to_meta_currency`'s non-COP branch, and the create form's submit handler, now asserted rather than merely primed. What is left is three `NotFound` raises with no acceptance criterion — since closed anyway, on the argument that the repo already pins that shape for accounts, transactions, tags and funds. THREE THINGS THE PERCENTAGES CONCEALED, ALL SINCE CLOSED. (1) `frontend/lib/api/metas.ts` had an lcov record of FNF:12 / FNH:0 — twelve functions, none executed by any test, because every screen test mocks the module. The covered screen and the covered router were joined by twelve URLs and verbs that nothing asserted; a `post` where a `patch` belongs would have left every test green. (2) `to-pay/page.tsx:138` — `meta_id: values.metaId` inside the plan-payment mutation body, on the screen that produced two of CP6's six defects. `planPayment` was not even mocked. (3) THE BIGGEST: 009's four migrations are absent from the coverage denominator entirely, because `migrations/versions/` has no `__init__.py` and coverage.py's source discovery skips it — 329 lines, the only code in the feature that touches the owner's real data irreversibly, contributing nothing to the 96.02% and unable to appear in any residue list. Features 006, 007, 011 and 012 each have a `tests/db/test_migration_NNNN.py`; 009 was the first to ship migrations without one. `0015`'s guard against withdrawing the dated fund rule while a fund still saves toward a date had never fired in a test, having only ever run against an empty database. WHAT THE NUMBERS DO NOT PROVE: line coverage is not oracle coverage. `services/metas.py` at 99% means the fold's lines ran, not that the amounts they produced are right for a month no test names — and CP6 found six user-facing defects in exactly that code."
human_action_needed: no
recommended_next: "CP8 mutation on `domain/rules.py` and `services/metas.py` per plan.md's Test strategy, on a fresh agent in its own git worktree — the previous CP8 ran in the shared checkout and left `metas.py` as an AST round-trip of itself with `# noqa` stripped, which would have stopped the acceptance pipeline at the lint gate. Then the owner merges `cp6-independent-review`."
tracker_update: "local — 009 at checkpoint 7 complete, status in-progress. Union backend coverage 96.02%, 0 CRAP findings above 20; 3 frontend findings above 20, all attributed as whole-file measurement artefacts. Residue 11 lines -> 3, then 0. Four migration tests, a client-contract test and two to-pay tests added to close what the measurement exposed. CP8 open."
status: complete
---

# crap-analyzer (round 2) — handoff summary

## What I did

Generated real coverage for all three streams against `cp6-independent-review`
at `397c21f`, merged the two backend ones, ran `compute_crap.py` over 009's full
blast radius for both languages, read every finding above threshold, and listed
every line no stream executes. No refactor applied, no test written.

## The one number worth remembering

CRAP found nothing on the backend for the second round running, and the useful
signal was never a CRAP score. It was the residue — and behind the residue, the
329 lines an accident of packaging kept out of the measurement altogether.
