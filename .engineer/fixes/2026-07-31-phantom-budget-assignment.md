---
slug: "2026-07-31-phantom-budget-assignment"
title: "Budget assignment to archived/excluded categories creates phantom money"
severity: medium
blocks_user: false
workaround: "re-assign 0 to that category x month (the assignment is an upsert) to neutralize the hidden line"
status: pinned-pending

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
