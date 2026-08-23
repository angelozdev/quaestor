---
slug: monthly-expense-trend
checkpoint: 4
plan_status: confirmed
created: 2026-08-22
---

## Architecture

**Backend — extends three existing files, no new endpoint, no new query.**

- `month_aggregate.py`: `MonthAggregate` gains one method,
  `category_month_totals(months: list[str]) -> dict[tuple[int | None, str], int]`.
  It starts from `_spent_by_cat_month` for the requested months and folds
  back in what that dict deliberately excludes: settled charges that have
  their own fund (ADR-0057). `_spent_by_cat_month` is built for the fund's
  own fold (`spent_in`'s docstring: "Only the *plan* reads this... What was
  actually spent is read from the movements themselves") and diverts
  fund-per-charge amounts into `_settled_by_charge_month` instead, so a
  category with such a charge would read low for any month outside the
  current/previous pair if nothing corrected it. The correction:
  `{f.recurring_id: f.category_id for f in self.funds if f.recurring_id is not None}`
  (`funds` is already loaded with no active/date filter) maps each settled
  charge back to its category, and its `_settled_by_charge_month` amount
  (native currency) is converted at `self.trm` and added to that category's
  month total. Zero new queries — both source dicts are already in memory.
- `report_types.py`: three new frozen dataclasses — `TrendMonth` (`month`,
  `total`, `by_group: dict[str, int]`), `TrendCategoryRow` (`category`,
  `group`, `total` across the window, `by_month: dict[str, int]`), `Trend`
  (`window_start`, `window_end`, `months: list[TrendMonth]`,
  `categories: list[TrendCategoryRow]`). `MonthlyReport` gains `trend: Trend`.
- `reports.py`: a new private `_trend(agg, today)`, same shape as the
  existing `_category_sections`/`_group_sections`/`_drift` — bucket, sort,
  return. The 12-month window is
  `[shift_year_month(year_month_of(today), -i) for i in range(11, -1, -1)]`
  (`shift_year_month` already exists in `domain/rules.py` — no new date
  arithmetic), anchored on `today`, **not** on the `month` the rest of the
  report was asked for (AC-1's "independiente del selector de mes"). Rows
  with zero total across the whole window are dropped (AC-6); a category
  archived mid-window still appears because `agg.categories` is loaded with
  no `archived` filter (AC-7, free — archiving is soft-delete, ADR-0005).
  Grouping with no `group_id` buckets under `"Sin grupo"` (Spanish — new
  code, ADR-0001's UI-copy carve-out; the sibling `_group_sections` keeps its
  existing `"Ungrouped"` unchanged, since respecting an accepted decision
  means not touching code this feature doesn't need to touch).
- `monthly_report(session, month, *, today: Date | None = None)`: the
  `today` parameter already exists and is accepted-but-unused today (its own
  docstring says so). It becomes `today = today if today is not None else
  Date.today()`, used only to anchor `_trend`'s window. Neither REST caller
  (`api/routers/reports.py`) nor the MCP tool (`mcp/tools/reports.py`)
  passes `today` today — after this change neither has to; both start
  getting a correct trend for free. The acceptance step handlers (CP3) already
  pass `today=world.today` explicitly, for determinism.
- `render_markdown()` is **not touched**. This is how the screen-only scope
  decision (discover-acs, 2026-08-22) is implemented: the MCP text surface
  simply never reads `report.trend`, so there is no branch, no surface flag,
  no special case — the field exists on the shared dataclass (MCP's own
  `monthly_report()` call gets it too, at no cost) but nothing points the
  chat's renderer at it.

**Frontend:**

- `lib/api/types.ts`: `Trend`/`TrendMonth`/`TrendCategoryRow` interfaces,
  mirroring the backend field names (existing convention — `by_category`/
  `by_group` are already un-translated snake_case in this file).
- `reports/page.tsx`: wrapped in `ui/components/tabs.tsx` (already exists,
  unused on this screen today) — "Mes" becomes a tab holding today's content
  unchanged, "Evolución" is the new one.
- `reports/evolucion-tab.tsx` (new): Recharts `BarChart`/`Bar`, one stacked
  series per group, reading `report.trend.months`; series fill colors
  `var(--chart-1)` through `var(--chart-10)`. The matrix table reuses
  `ui/components/table.tsx`; rows come from `report.trend.categories`,
  already sorted server-side (AC-5) — no client-side sort.
- `app/globals.css` + `ui/styles/tokens.css`: extend `--chart-1..5` to
  `--chart-1..10` (light + dark), same `oklch(...)` pattern already there,
  plus the matching `--color-chart-6..10` mappings in `tokens.css`. Decided
  with the owner in CP4: repeating the 5 existing tokens would let two
  different groups share a color in the stacked bar; the table below doesn't
  depend on color, but the chart itself does.

**Key decision — where the fund-per-charge fold lives.** On `MonthAggregate`,
not in `reports.py`. The private dicts it corrects
(`_spent_by_cat_month`, `_settled_by_charge_month`) are the aggregate's own,
and `spent_in`'s existing docstring already carries the reasoning for why
they're split the way they are — the trend's correction belongs next to that
reasoning, not reaching into underscore-prefixed attributes from a different
module. Matches ADR-0044's precedent directly ("el fold vive en el
aggregate").

**Alternative rejected — a new `services/trend.py` module.** Considered,
because the fold is non-trivial. Rejected because `reports.py` already holds
one private builder function per report section in one file
(`_category_sections`, `_group_sections`, `_drift`, `_fund_lines`,
`_meta_lines`, `_pending_lines`) — a dedicated module for just this one
section would break that existing convention for no coupling benefit (the
new `_trend` function is the same size and shape as its siblings already in
the file).

**Confirmed with the owner** (including the fund-per-charge fix, the extra
`spec.md` scenario for it, and the 10-color palette) before drafting the
rest of this plan.

## Charter Check

| Charter rule | Status | Note |
|---|---|---|
| §1 Methodology — ADR for architecturally-significant decisions | ✅ | ADR-0061 (Recharts) written and accepted 2026-08-22, during this same checkpoint. No other architecturally-significant decision here — the `MonthAggregate` method and the three dataclasses extend an existing, already-decided module shape (ADR-0028/0044), not a new one. |
| §2 Architecture — layering (`api` → `services` → `domain`) | ✅ | No new router, no new MCP tool, no schema crossing the API boundary beyond one new nested field on the existing `GET /api/reports` response. |
| §2 — MCP surface REST parity (ADR-0006/0009) | ✅ N/A, not a deviation | Re-read both ADRs during this checkpoint: ADR-0006's mandate is "every new HTTP **write** ships a sibling MCP tool" (co-equal write path, ADR-0008/0025) — trend is a read-only addition to an existing `GET`, not a write. `monthly_report()` returns the same `Trend`-carrying object to MCP as to REST (no data withheld); the screen-only decision is implemented by `render_markdown()` never reading `report.trend`, not by hiding it from MCP's code path. No amendment ADR needed — flagging this reasoning explicitly here rather than deciding it unilaterally, since the owner is the one who resolved the underlying scope question at discover-acs. |
| §3 Conventions — English identifiers, pnpm, vitest colocated | ✅ | All new identifiers (`Trend`, `TrendMonth`, `TrendCategoryRow`, `category_month_totals`) are English; `"Sin grupo"` is a Spanish **string value** (UI copy), not an identifier — same category as existing Spanish copy elsewhere, not a violation of ADR-0001. |
| §6 Quality stance — a converted figure is tested in another currency (2026-08-13 amendment) | ✅ | AC-11's `spec.md` scenario (already written, already red for the right reason at CP3) seeds USD spend inside the window and asserts the COP conversion. |
| §6 — green is not verified, browser pass required | ⚠️ → planned | See Test strategy: `feature.md`'s `validation_method` already specifies the exact browser pass (3+ months, 2+ groups, bars and table checked against seeded data) before CP8 closes. |
| §7 Autonomy — medium, data gates | ✅ | No migration, no `.dev-data/` touch, no schema change — nothing here requires escalation past medium. |
| Verification independence (Principle 7) | ✅ | CP6 refine's reviewer and CP7's verifier are distinct agents from the CP5 implementer, per the standard checkpoint contract. |
| Mutation policy (`manifest.mutation`: `default_per_feature: opt_in`) | **Opt in** | The fund-per-charge fold is exactly the kind of subtle branch (a dict lookup that either fires or silently returns 0) that a passing acceptance suite can still leave unguarded against a future regression. Scope: changed lines in `month_aggregate.py`, `report_types.py`, `reports.py`. |

**Amendments:** none. The one ⚠️ row (browser pass) is closed by a planned
step in Test strategy, not a charter exception; the MCP-parity row is
resolved as not-applicable by re-reading the ADRs' actual scope, not by an
amendment.

## Phasing

**Three slices — the fund-per-charge fold first (the one real behavior
correction), the rest of the trend build second, frontend third —** matching
dependency order: nothing else can be verified as *correct* (vs. merely
*present*) until the fold exists, and the frontend has nothing to render
until the backend field exists.

1. **`month_aggregate.py`** — `category_month_totals`, with the
   fund-per-charge fold. Closes the new `spec.md` scenario under "Sobre
   AC-2" first, in isolation, since it's the one correction this plan itself
   surfaced (not originally in `acs.md`).
2. **`report_types.py` + `reports.py`** — `Trend`/`TrendMonth`/
   `TrendCategoryRow`, `MonthlyReport.trend`, `_trend()`, the `today`
   default. Closes the remaining 10 `@backend` scenarios (AC-1, AC-2, AC-3,
   AC-5 through AC-9, AC-11, AC-12 — AC-12 is already green, unaffected).
3. **`lib/api/types.ts`, `globals.css`/`tokens.css` (10-color palette),
   `reports/page.tsx` (Tabs), `reports/evolucion-tab.tsx`** — the two
   untagged scenarios (AC-4, AC-10), bound to new `evolucion-tab.test.tsx`
   titles matching `spec.md` verbatim (ADR-0045).
4. Full suite re-run: pytest (13 `@backend`/generated scenarios), vitest,
   `spec_coverage.py` (13/13 bound), CHARTER §6 browser pass.

## Performance budgets

Negligible. Zero new SQL queries — `category_month_totals` folds two dicts
already loaded by `load_month_aggregate` for every report, trend or not. The
in-memory fold is O(months × categories already in the aggregate), bounded
by real data volume (a handful of categories × 12 months). One new nested
field in the REST JSON response body — no new round-trip, no new N+1.

## Collaboration schedule

Solo — CP5 implementer runs the three slices directly (well-scoped,
sequential, no cross-team handoff needed). CP6 refine and CP7 verify run as
independent passes per the standard checkpoint contract.

## Execution modes

Local subagent for CP5 implement (auto-dispatched, autonomy `medium`); CP6
refine's review subagent(s) and CP7's independent verifier are also local
subagents. No cloud dispatch (`remote.ready: false`).

## Test strategy

`acceptance_stream: mixed` (`feature.md`): 11 `@backend` scenarios (10 from
the original 12 ACs + 1 added in this checkpoint for the fund-per-charge
correction, under AC-2) bind to pytest via the existing generator; 2 untagged
scenarios (AC-4, AC-10) bind to vitest by exact scenario-title match
(ADR-0045). All 11 `@backend` scenarios were confirmed at CP3 to fail for
the right reason (`AttributeError: 'MonthlyReport' object has no attribute
'trend'`), except AC-12 which is already green (inherited, pre-existing
behavior — see `spec.md`'s note on it).

**Mutation:** opt in, scoped to the changed lines in `month_aggregate.py`,
`report_types.py`, `reports.py` — closing exactly the class of bug this plan
found by reading the code (a silent, branch-shaped undercount), the same
justification pattern as ADR-041/019's mutation opt-in.

**`validation_method` (from `feature.md`):** "sembrar gasto en al menos 3
meses distintos repartido en al menos 2 grupos, abrir la pestaña Evolución y
confirmar que las barras apiladas y la tabla categoría x mes coinciden con
lo sembrado, mes por mes y categoría por categoría" — run against the local
sandbox before CP8 closes, per CHARTER §6 ("green is not verified"). This
browser pass is the only place AC-4 and AC-10's visual claims (total above
the bar, empty-state parity) get a human's eyes on them beyond the vitest
title-match; everything with real arithmetic (AC-1/2/3/5–9/11/12, plus the
fund-per-charge scenario) is proven by the acceptance suite and mutation.
