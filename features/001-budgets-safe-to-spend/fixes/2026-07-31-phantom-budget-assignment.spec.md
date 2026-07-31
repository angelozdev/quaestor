# Regression spec for fix: 2026-07-31-phantom-budget-assignment
# Feature: features/001-budgets-safe-to-spend
# Written: 2026-07-31
# Status on current code (pre-fix): RED — confirmed 2026-07-31

Feature: Hybrid budget — envelopes with rollover + safe-to-spend

  # These scenarios pin the defect: an envelope can be assigned to a category
  # that the budget never shows and whose spending is never aggregated, so the
  # amount is subtracted from safe-to-spend with no visible trace.
  #
  # Feature 001 has no acceptance pipeline yet (paused at consolidation task
  # #15, pending the sinking-funds redesign), so these scenarios are pinned as
  # service-layer tests in backend/tests/services/test_budgets.py rather than
  # generated from a spec.md.

  Scenario: An archived category cannot hold an envelope
    Given a category that has been archived
    When  the user assigns 300000 to that category for 2026-06
    Then  the assignment is rejected with a clear validation error
    And   the month's safe-to-spend is unchanged

  Scenario: A budget-excluded category cannot hold an envelope
    Given a category marked as excluded from the budget
    When  the user assigns 300000 to that category for 2026-06
    Then  the assignment is rejected with a clear validation error
    And   the month's safe-to-spend is unchanged

  Scenario: Archiving a category after it holds an envelope is out of scope
    Given a category with 300000 already assigned for 2026-06
    When  the category is archived afterwards
    Then  the existing envelope is left alone
    # Documented as deliberately unpinned: the 2026-07-31 decision covers the
    # assignment path only. Retroactive cleanup belongs to the sinking-funds
    # redesign (features/003), which replaces these formulas.
