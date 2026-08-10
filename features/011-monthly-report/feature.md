---
title: "El informe del mes, y el camino de lectura del que sale"
slug: monthly-report
number: 011
status: in-progress
autonomy_level: medium
branch: monthly-report
area: reports
owner: angelo
assignee: local
tracker_ref: local
roadmap_ref: atdd-consolidation
acceptance_stream: mixed
relevant_adrs: [0019, 0028, 0031, 0043, 0044, 0045]
created: 2026-08-10
intake: onboarding
validation_method: "The three streams (backend pytest, generated acceptance, vitest), plus one read of the real month against a restored copy of production — the report is the screen the owner opens once a month, and its figures are the ones he acts on"
---

# El informe del mes, y el camino de lectura del que sale

## Outcome

The owner opens one screen at the end of a month and it tells him, truthfully,
where his money went: what came in, what went out, what each category and each
group took, what every fund and every meta claimed, what each account holds now,
whether the month drifted from the one before it, how much of his spending was
in dollars, and what he still has not confirmed. The same answer reaches him
through the app, through the assistant and through the API, and it adds up
whichever way he asks for it.

## Scope

Consolidation task 5, taken as **one feature** because the two rows share a read
path — the backlog says so, and the code agrees: `monthly_report` folds the same
`MonthAggregate` that the money-available number folds, so covering one without
the other would pin the report's arithmetic against a loader nothing describes.

- **The report itself** — `services/reports.py` (234 lines) and the shape it
  answers with, `domain/report_types.py`: income, expense, net, the fund
  summary and its lines, the meta lines, what the two ask together, the
  by-category and by-group sections, account balances, month-over-month drift,
  the dollar share of spending, the unconfirmed-entry alerts, and the
  money-available closing line.
- **The bounded read path** — `services/month_aggregate.py` (323 lines), the
  loader ADR-0028 exists for. Its promise is a fixed number of queries per
  month regardless of how much history there is; CP7 of feature 009 measured 13
  and that budget is part of what this feature must pin.
- **The markdown rendering** — `domain/report_markdown.py`, which is what the
  assistant and the MCP tool actually hand back.
- **All four surfaces** — the service, `GET /api/reports`, the MCP
  `monthly_report` tool, and `frontend/app/(app)/reports/`. ADR-0006/0009
  require REST/MCP parity, and feature 009 shipped three separate defects where
  one surface disagreed with another, so parity is a thing to test rather than
  assume.
- **Out of scope:** changing what the report says. This is reverse-engineer
  coverage — a divergence between the code and what the ACs decide it should do
  is resolved explicitly as fix-or-accept, the method feature 007 fixed at
  intake and every consolidation row has reused since.

## Why this row and not task 4

Task 4, `month-close-rollover`, was next in the backlog and turned out to have
nothing to cover: `close_month` iterates an empty hook list, measured at 0 hooks
at runtime, with the only registrations being fakes inside its own tests. It is
parked as roadmap `id:month-close-does-nothing` pending a product decision.
Writing scenarios for it would have been a green suite over code that does
nothing.

## What is already true, measured at intake

- Four surfaces exist and all four are wired: service, REST router (mounted at
  `api/__init__.py:124`), MCP tool, and a screen with its own vitest file.
- Unit tests exist — `test_reports.py`, `test_month_aggregate.py`,
  `test_report_markdown.py`, `test_report_types.py` — and **not one acceptance
  scenario**. That is the gap this row closes.
- 009's CP7 measured `GET /reports` at 16 queries and `services/month.py` at
  100% line coverage. Feature 009 then found six user-facing defects in code at
  that coverage level, so the number is a floor, not a verdict.

## Charter signals

- **No migration, no new table.** This is coverage of shipped behaviour; if an
  AC forces a schema change it stops being this row and needs its own decision.
- **`report_types.py` carries prohibited trailing comments** on `MonthlyReport`
  and `CategorySection`. They predate 009 and belong to roadmap
  `id:strip-code-comments`; touching them here would widen the diff for no
  reason, so they are left alone and named so the next reader knows why.
- **Every new screen speaks English on refusal** until `id:error-contract`
  ships. Known, tracked, does not block.
