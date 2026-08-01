---
skill: fix
agent_id: main
started: 2026-07-31T1330
ended: 2026-07-31T1350
checkpoint: null
fix_slug: "2026-07-31-phantom-budget-assignment"
artifacts:
  - .engineer/fixes/2026-07-31-phantom-budget-assignment.md
  - features/001-budgets-safe-to-spend/fixes/2026-07-31-phantom-budget-assignment.spec.md
  - backend/src/quaestor/services/budgets.py
  - backend/tests/services/test_budgets.py
  - .engineer/consolidation.md
exit_criteria:
  - criterion: "Regression spec confirmed RED on unfixed code"
    verified_by: tool
    met: true
    evidence: "3 failed, 20 deselected — all three with 'Failed: DID NOT RAISE ValidationError'"
  - criterion: "Regression spec GREEN after the fix; no suite regression"
    verified_by: tool
    met: true
    evidence: "uv run pytest -q → '744 passed, 1 warning in 14.88s' (baseline 741 + 3 regression tests); ./run-acceptance-tests.sh → '64 passed'"
  - criterion: "Bug-line mutation gate passed"
    verified_by: tool
    met: true
    evidence: "Both raises reverted to `if False:` → the three regression tests returned to RED; fix restored and suite re-run green. git diff confirms no mutant residue."
  - criterion: "Mutation over the changed lines"
    verified_by: tool
    met: true
    evidence: "3/3 killed — negate archived, negate exclude_from_budget, swap archived for exclude_from_budget"
  - criterion: "gap_analysis non-empty, no unresolved blockers"
    verified_by: judgment
    met: true
    evidence: "Two findings (missing_ac, inadequate_verification), both advisory: blocks_user is false and no architecture_violation. User approved both before writing."
findings_summary: "set_budget validated only that the category existed, while _budget_lines filters archived and budget-excluded categories out of the list and never aggregates their spending — so an envelope assigned there was subtracted from safe-to-spend with no visible trace. Fixed by rejecting both cases in the service layer, mirroring how record_expense already rejects archived categories, so app, REST and MCP are covered by one guard. Production check (read-only): the budget table is empty, so the defect never touched real data — the fix is preventive."
human_action_needed: yes
human_action_kind: decision
recommended_next: "Decide the branch question below, then resume 002 at CP7 verify."
status: complete
---

# fix — close summary: phantom budget assignment

## What broke and why it was invisible

`services/budgets.set_budget` accepted any existing category. `_budget_lines`
renders only `not c.archived and not c.exclude_from_budget`, and unbudgeted
spending in those categories is never aggregated. The assignment therefore
reached `assigned_envelopes` — lowering safe-to-spend — while the category it
belonged to never appeared anywhere. Money claimed with no trace.

Behavior decision (Angelo, 2026-07-31): reject the assignment. Independent of
the sinking-funds redesign and survives it.

## Real-data impact: none

Read-only query against the local production Postgres: `budget` has **0 rows**.
The budget feature has never been used there, so no phantom envelope exists.
The fix is preventive.

## Gap analysis (both advisory, both approved)

1. **`missing_ac`** (phase: discover-acs) — the rule was never an AC. Feature
   001 predates DAE and its AC discovery is paused at consolidation #15. Worth
   noting the methodology *did* surface the defect — it came out of the aborted
   2026-07-31 discovery interview; what was missing was a test pinning it.
   Followup logged in `.engineer/consolidation.md` under task #15.
2. **`inadequate_verification`** (phase: verify) — the pre-existing test
   `test_budget_status_respects_exclude_flags` called `set_budget` on an
   excluded category in its setup, treating the invalid assignment as
   legitimate. Its real assertion (`spent == 0`) was left untouched; only the
   invalid setup line was removed. Followup applied.

## Open — needs your decision

**The fix landed on `transactions-crud`, not on its own branch.** The intent was
a branch off `main`, but the fix artifact was already committed there (it rode
along in `e186792 chore(dae)`), so `git checkout -b … main` aborted rather than
clobber the local edits. Splitting now requires rewriting history on the 002
branch (cherry-pick + `reset --hard`), which was not done unprompted.

Consequences as it stands: the 002 PR will carry a small budgets fix, and this
fix cannot merge independently of 002. Either accept that, or do the split
after 002 merges.

Nothing here is committed yet.

## Post-merge cleanup

```
After the PR merges:
  git checkout main && git pull --ff-only && git branch -d transactions-crud
```
