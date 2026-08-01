---
slug: "2026-07-31-phantom-budget-assignment"
title: "Budget assignment to archived/excluded categories creates phantom money"
severity: medium
blocks_user: false
workaround: "re-assign 0 to that category x month (the assignment is an upsert) to neutralize the hidden line"
status: closed

source:
  kind: internal
  ref: "features/001-budgets-safe-to-spend/handoffs/2026-07-31T0939-discover-acs.md"

repro: |
  1. Create a category and archive it (or set exclude_from_budget on it).
  2. Assign a budget amount to that category for the current month
     (the assignment is accepted through UI, API and agent alike).
  3. Read the month's budgets list and the safe-to-spend headline.

expected: "The assignment is rejected with a clear validation error — archived or budget-excluded categories cannot hold an envelope (user decision 2026-07-31)."
actual: "The assignment is accepted; the amount is subtracted from the safe-to-spend headline (assigned envelopes) but the category never appears in the budgets list — money invisibly claimed."

feature_refs:
  - "features/001-budgets-safe-to-spend"

investigation:
  match_mode: auto
  candidates_considered: 1

pin_confirmation:
  feature_refs:
    - feature: "features/001-budgets-safe-to-spend"
      spec_path: "features/001-budgets-safe-to-spend/fixes/2026-07-31-phantom-budget-assignment.spec.md"
      red_run:
        result: red
        command: "uv run --project backend pytest backend/tests/services/test_budgets.py -q -k 'archived_category or excluded_category or rejected_assignment'"
        output: |
          FAILED test_set_budget_rejects_an_archived_category — Failed: DID NOT RAISE ValidationError
          FAILED test_set_budget_rejects_a_budget_excluded_category — Failed: DID NOT RAISE ValidationError
          FAILED test_rejected_assignment_leaves_safe_to_spend_untouched — Failed: DID NOT RAISE ValidationError
          3 failed, 20 deselected in 0.11s
      note: "Feature 001 has no acceptance pipeline (paused at consolidation #15 pending the sinking-funds redesign), so the GWT spec is pinned as service-layer tests instead of generated scenarios."

fix_commits:
  - "e2f1fba fix(budgets): reject envelope assignment to hidden categories"
  - "e186792 chore(dae): feature 002 artifacts through CP6 (carried the fix artifact)"
  - "Ships inside feature 002's PR. Decision (Angelo, 2026-07-31): leave it on the transactions-crud branch rather than split it. Splitting was cheaper than the CP6 handoff implied — the branch was never pushed, so rewriting it carried none of the usual risk — but the fix is small, already verified, and merges with 002 anyway. Trade accepted: this fix cannot merge independently of 002."

harden_results:
  mutation_score: 1.0
  arch_check: "pass — the guard stays in services/ and reads domain/models.Category; no new dependency, no layer crossed"
  bug_line_mutation_confirmed: true
  notes: |
    Bug-line gate: both raises reverted to `if False:` → the three regression
    tests returned to RED (DID NOT RAISE ValidationError). Fix restored, suite
    back to 744 passed.
    Targeted mutation over the new guard, 3/3 killed: negate `archived`,
    negate `exclude_from_budget`, swap `archived` for `exclude_from_budget`.
    Scope deviation: a hand-run mutation set over the 4 changed lines instead
    of a full `atdd:mutate` pass over budgets.py, and no three-subagent refine
    in Step 5 — disproportionate for a 10-line guard. Flagged to the user, who
    accepted.
    Coverage of services/budgets.py: 97% (4 uncovered lines all pre-existing:
    91, 101, 118, 183).

gap_analysis:
  - category: missing_ac
    phase: discover-acs
    finding: "The rule 'only a category the budget can show may hold an envelope' was never an acceptance criterion. Feature 001 predates DAE (onboarding intake 2026-07-28) and its AC discovery is paused at consolidation task #15 pending the sinking-funds redesign. The methodology did surface the defect — it came out of the 2026-07-31 discovery interview, the one aborted on finding the pause — but nothing pinned it as a test."
    followup_kind: amend_ac
  - category: inadequate_verification
    phase: verify
    finding: "The pre-existing unit test test_budget_status_respects_exclude_flags called set_budget on a budget-excluded category in its setup, treating the invalid assignment as legitimate; no test in the suite asserted it should be rejected. A test quietly ratifying the defect it should have caught."
    followup_kind: add_verification

followups:
  - category: missing_ac
    action: "When feature 001 unpauses (after the sinking-funds redesign), land 'archived and budget-excluded categories cannot hold an envelope' as an AC in acs.md and propagate to spec.md"
    status: open
  - category: inadequate_verification
    action: "Add regression tests asserting set_budget rejects archived and budget-excluded categories, and drop the invalid set_budget setup line from test_budget_status_respects_exclude_flags"
    status: applied

handoff_path: .engineer/handoffs/2026-07-31-phantom-budget-assignment-close.md
---

# Phantom budget assignment — notes

Found during the 2026-07-31 discovery interview on 001 (aborted before
acs.md; see source handoff). The envelope assignment validates only that the
category exists — not that it is active and budget-eligible. The budgets
list filters archived and excluded categories, and their spending is never
aggregated, so an assignment there is subtracted from the headline with no
visible trace.

Behavior decision (Angelo, 2026-07-31): reject the assignment. This rule is
independent of the sinking-funds redesign (features/003) and survives it —
also recorded in 003's notes as item 4.

Resume at Step 3 (Pin): write the regression spec, confirm RED on current
code, then fix in the assignment validation.
