---
title: "Sinking funds: envelope funding rules + smoothed monthly available"
slug: sinking-funds
number: 003
status: parked
autonomy_level: null
branch: sinking-funds
area: budget
owner: angelo
assignee: local
tracker_ref: local
roadmap_ref: sinking-funds
relevant_adrs: [0006, 0028]
created: 2026-07-28
intake: discuss
---

# Sinking funds: envelope funding rules + smoothed monthly available

## Outcome

The user sees a **smoothed monthly available** number computed from normalized
real data — monthly-equivalent income minus the sum of every envelope's monthly
funding rule minus unbudgeted pending payments — so lumpy cash flows (annual
insurance, quarterly income) never distort a single month. Envelopes become
**sinking funds**: each accumulates its monthly contribution via the existing
rollover, so when the annual payment arrives the fund already holds it.

## Scope (draft — to be refined when unparked)

- **Funding rule per envelope** (configurable): `fixed` (user amount) |
  `average` (spent over last N months) | `prorated` (linked recurring item:
  annual ÷ 12, quarterly ÷ 3, etc.).
- **Normalized income**: non-monthly recurring income converted to its
  monthly equivalent (quarterly ÷ 3, annual ÷ 12) in the headline calc.
- **Reformulated headline**: normalized income − Σ funding rules −
  unbudgeted pending = smoothed monthly available. Replaces the current
  due-date-based safe-to-spend formula.
- **Fund health**: envelope balance vs. expected accumulation ("insurance
  fund: 400k of 1.2M — on track / behind").
- **Goals unification (candidate)**: savings goals become funds with a
  target amount + date (target ÷ remaining months = funding rule).

## Source links

- Replaces product decisions ADR-003 (STS = unassigned money) and ADR-004
  (forecast income) — formal supersede required at build time in
  `docs/decisions/product-decisions.md`.
- Builds on product ADR-002 (envelopes + rollover) and ADR-005 (rollover
  positive-only) — the rollover mechanism is the fund vehicle, unchanged.
- Technical: `docs/adr/0006-goals-and-budgets-write-api-with-mcp-parity.md`,
  `docs/adr/0028-bounded-query-read-path-for-monthly-aggregates.md`.
- Industry references: YNAB sinking funds / targets
  (https://www.ynab.com/blog/what-is-a-sinking-fund), Actual Budget goal
  templates — schedule + average based
  (https://actualbudget.org/docs/experimental/goal-templates/).

## Code co-locations

- Backend: `backend/src/quaestor/services/budgets.py` (headline + envelope
  status), `backend/src/quaestor/domain/rules.py` (`safe_to_spend_calc`),
  `backend/src/quaestor/services/month_aggregate.py` (bounded read path,
  ADR-0028), `backend/src/quaestor/services/goals.py`.
- Frontend: `frontend/app/(app)/budgets/page.tsx`, dashboard STS card in
  `frontend/app/(app)/page.tsx`.

## Notes

- Parked from discuss 2026-07-28 (portfolio review): user barely uses current
  envelopes and the safe-to-spend formula "no es lo que quería" — wanted
  smoothed, fund-based math instead of due-date spikes.
- **Too big for one feature** — expect decomposition when unparked (likely:
  funding rules, normalized income + headline, goals unification).
- Open questions for the next discuss session: fate of the current budgets
  page UI, migration of existing `Budget` rows, exact normalization formula
  for irregular intervals, whether goal-contribution-hooks survives.
- Consolidation impact (applied 2026-07-28): ATDD tasks for
  `budgets-safe-to-spend` and `goals` moved to the bottom of
  `.engineer/consolidation.md` — don't write acceptance tests for formulas
  this feature will replace.
- **User design decisions captured 2026-07-31** (discover-acs ran on 001 by
  mistake — the interview surfaced product answers that belong here):
  1. **Per-envelope rollover rule.** Two envelope kinds: accumulating funds
     ("tecnología: 100k every month — MUST accumulate") and monthly-limit
     envelopes ("restaurantes: reset each month"). Per-category rollover
     toggles are industry standard (Monarch, PocketGuard, Quicken). The
     current global gap-reset is an implementation artifact — adopt neither
     semantic globally; make it a per-envelope rule.
  2. **Month income.** User wants full product ADR-004 semantics: expected
     income from recurring, corrected to actual as incomes post (each income
     counted exactly once), and atypical posted income (bonus) joins the
     pool. Feed this into the normalized-income design.
  3. **Underfunded envelope.** The headline must tell "la verdad desde el
     inicio": when a known obligation exceeds its envelope's coverage
     (assigned + accumulated), the shortfall reduces the headline from day 1,
     never as a surprise on charge day. Prorated-recurring funding rules
     cover this naturally.
  4. **Independent fix (survives the redesign, do not wait for 003):**
     assigning budget to an archived or exclude_from_budget category must be
     rejected — today it is accepted, subtracts from the headline, and is
     invisible in the budgets list (phantom money).
