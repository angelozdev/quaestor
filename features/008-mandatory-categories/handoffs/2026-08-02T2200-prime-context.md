---
skill: prime-context
agent_id: main
started: 2026-08-02T2155
ended: 2026-08-02T2200
checkpoint: null
artifacts: []
findings_summary: "Primed 008-mandatory-categories. The write paths already validate a category when one is given — every one of them treats it as optional (`category_id: int | None = None`). The change is turning optional into required for expense/income, forbidden for transfer, in four service entry points plus the migration."
human_action_needed: no
human_action_kind: none
recommended_next: "/engineer.discover-acs"
tracker_update: none
status: complete
---

# prime-context — handoff summary

## What was loaded

- `features/008-mandatory-categories/feature.md`
- `CHARTER.md`, `.engineer/manifest.yml`
- `features/008-mandatory-categories/handoffs/2026-08-02T2100-feature-init.md`
- `features/003-sinking-funds/feature.md` + its `2026-08-02T2100-discuss.md`
  (the originating session)
- Code pointers: `domain/models.py` (`Category`, `Transaction`,
  `RecurringItem`), `services/transactions.py` (`_record`, `record_expense`,
  `record_income`, `transfer`, `update_transaction`), `services/recurring.py`
  (`create_recurring`, `update_recurring`), `services/planned.py`
  (`plan_payment`)

## Orientation

**The shape of the change is smaller than it looks.** Every write path already
resolves and validates a category — `_record`, `plan_payment` and
`create_recurring` each run the same three lines: fetch, reject if missing,
reject if archived. All three guard that block behind `if category_id is not
None`, and all three declare the parameter `category_id: int | None = None`.
The feature is the removal of that guard on `expense`/`income`, an explicit
rejection on `transfer`, and the migration that pins it.

**Four service entry points** carry the rule: `transactions._record` (feeds
`record_expense` + `record_income`), `transactions.update_transaction` (which
today accepts `category_id=None` explicitly via its `_UNSET` sentinel — that
path can currently *strip* a category off a posted row), `planned.plan_payment`,
and `recurring.create_recurring` / `update_recurring`.

**`transactions.transfer` never accepts a category at all** — the transfer rule
is already satisfied structurally, not by validation. Worth confirming at AC
time that this stays true through `planned._materialize_planned_transfer`.

**Two model details that will shape the ACs:** `Category.is_income` exists, so
"has a category" and "has a category of the right polarity" are two different
rules — the feature currently claims only the first. And
`Category.exclude_from_budget` / `archived` interact with the backfill: the
28 uncategorised posted expenses need a destination category that is neither
archived nor excluded, or they stay invisible to reports anyway.

## New pointers added to feature.md

None.

## Recommended next step

`/engineer.discover-acs`. Open questions carried in: inline category creation
vs. a trip to the categories screen; whether `skipped` rows are backfilled or
exempted; and now also whether `is_income` polarity is enforced.
