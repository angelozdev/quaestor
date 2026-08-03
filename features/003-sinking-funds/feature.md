---
title: "Sinking funds: envelope funding rules + smoothed monthly available"
slug: sinking-funds
number: 003
status: ready
autonomy_level: medium
branch: sinking-funds
area: budget
owner: angelo
assignee: local
tracker_ref: local
roadmap_ref: sinking-funds
relevant_adrs: [0006, 0028]
created: 2026-07-28
promoted: 2026-08-02
intake: discuss
---

# Sinking funds: envelope funding rules + smoothed monthly available

## Outcome

The user sees a **smoothed monthly available** number computed from normalized
real data — monthly-equivalent income minus the sum of every fund's monthly
funding rule minus unbudgeted pending payments — so lumpy cash flows (the
$7.000.000 annual car insurance, the quarterly USD bonus) never distort a single
month. Envelopes and savings goals collapse into **one thing, the fund**: each
accumulates its monthly contribution via the existing rollover, so when the
annual payment arrives the fund already holds it.

## The core decision (2026-08-02)

**There is no separate goals feature. A goal is a fund with a target and a
date.** The `Goal` / `GoalContribution` tables, the goals screen and the
month-close contribution hook all go away.

Verified against the reference implementations before deciding:

- **YNAB** and **Actual Budget** — both envelope budgeters — have *no* goals
  feature at all. A goal is one target type among several on a category. YNAB:
  *Set Aside Each Month* / *Refill Up To* / *By Date*. Actual:
  `#template 10000 by 2025-12` sits in the same list as
  `#template average 3 months`. Neither involves an account. YNAB states the
  principle directly: organisation happens in categories, not accounts — the
  plan does not care where the money is stored, only that you have it.
- **Monarch** does tie goals to accounts and reads progress from real account
  balances — but Monarch is a net-worth tracker with a budget bolted on, not an
  envelope budgeter. It can afford the link because it already ingests bank
  balances.

Quaestor is architecturally an envelope budgeter (product ADR-002: envelopes +
rollover) carrying a Monarch-shaped goal. That mismatch is the defect, and
production proves it — see *Evidence* below.

## Scope

- **Four funding rules per fund.** `fixed` (a user amount) | `average` (spent
  over the last N months) | `from-recurring` (linked recurring item: annual ÷
  12, quarterly ÷ 3) | `target-by-date` (target amount ÷ months remaining —
  this is the former goal).
- **Rollover behaviour per fund**, orthogonal to the rule: *accumulates* (car
  insurance) or *resets each month* (restaurants). Matches YNAB's *Set Aside
  Each Month* vs *Refill Up To*. The current global gap-reset is an
  implementation artefact, not a semantic — replace it.
- **Normalized income**: non-monthly recurring income converted to its monthly
  equivalent (quarterly ÷ 3, annual ÷ 12) in the headline.
- **Reformulated headline**: normalized income − Σ funding rules − unbudgeted
  pending = smoothed monthly available. Replaces the due-date-based
  safe-to-spend formula outright.
- **Fund health**: balance vs. expected accumulation ("insurance: $400k of
  $1.2M — on track / behind").
- **Goals migration**: fold the single existing goal into a fund; drop the
  goals surface.

## Decisions taken in the 2026-08-02 discuss

1. **Goals become funds.** One machine, four rules. The goals screen dies.
2. **The rule *is* the number — there is no monthly assign ritual.** YNAB and
   Actual both require a monthly button that distributes money into categories.
   Quaestor does not: the headline is computed from the rules themselves, so a
   configured fund costs zero clicks per month forever. This is load-bearing
   given the owner's history (see *Evidence*) — any design requiring a recurring
   manual action will end up empty again.
3. **The new headline replaces the old outright, and shows its work.** No
   coexistence period. Instead the number expands into its own breakdown
   (`income − rent − insurance ÷ 12 − …`), which gives the same confidence as a
   parallel run without keeping two formulas alive forever. The existing
   `committed_breakdown` is the pattern to follow.
4. **A fund that already holds money gets its opening balance typed in once**,
   at creation. Not read from an account — that would reintroduce the
   fund↔account coupling this feature exists to remove. The creation screen may
   *suggest* a savings account's balance as a starting figure, but the fund never
   tracks the account afterwards.
5. **The app starts empty; the user creates each fund.** Reversed from the
   recommendation on the table, which was to auto-propose a full set of funds
   from the recurring items and spending history. The owner's reason for the
   empty envelope history was not reluctance to configure but waiting for enough
   history to set a meaningful average — and that wait is now over (7 months,
   477 posted expenses). Auto-proposal stays available as a later addition if
   adoption stalls. **Note the boundary:** "starts empty" means no fund is
   auto-created. Once the user creates a fund and picks `average` or
   `from-recurring`, the rule still computes the amount — that is the rule
   working, not a proposal.
6. **`goal-contribution-hooks` dies.** The month-close hook that proposes one
   planned transfer per active goal has no purpose once a fund accumulates on
   its own. This resolves the caveat blocking consolidation task 4
   (`month-close-rollover`).
7. **Rule selection is not interchangeable — it is per-category correct.**
   Production shows why: for `🛡️ Auto Insurance` the 3-month average returns
   $149.100 (the annual SOAT charge smeared across the window it happened to
   land in) while `from-recurring` returns the correct $620.608 ($7.000.000 +
   $447.300, each ÷ 12). For `🍽️ Restaurants` the average is right and
   `from-recurring` does not apply. Default heuristic: category has a recurring
   item → `from-recurring`; otherwise → `average`.
8. **The average rule has a known feedback trap** — overspending raises the
   average, which raises the budget, which blesses the overspend. Actual's
   answer is the guidance to adopt: `average` for what you do not control
   (utilities, fuel), `fixed` for what you want to cap (restaurants,
   entertainment).

## Evidence from production (read-only, 2026-08-02)

The measurements that drove the decisions above:

- **Zero budget rows. Ever.** Not one envelope has been created in the app's
  history, so **there is nothing to migrate** — the migration risk that shaped
  the original park note does not exist.
- **One goal, zero contributions** — and it is broken in exactly the way the
  design predicts:

  ```
  Goal "Korea"        $0 of $10.000.000      0%    ← what the app shows
  Account 🇰🇷 Korea    $14.659.572                  ← what actually exists
  ```

  The goal has been surpassed by 46% and the app cannot tell, because progress
  counts `GoalContribution` rows rather than the balance of the account it
  *forced the user to link*. Three proposed transfers sit unconfirmed (one
  skipped 2026-06-30, two planned). The deadline is 2026-08-31. This is the
  worst of both models: Monarch's account requirement with none of Monarch's
  account-derived progress.
- **The owner genuinely does separate money in real life** — `🇰🇷 Korea`
  ($14.659.572) and `🆘 Emergency Fund` ($30.805.146) are real savings accounts
  with real balances. This confirms rather than contradicts the YNAB model:
  *where* the money sits and *what it is for* are orthogonal, and the app should
  track purpose without dictating location.
- **The lumpiness is real and large.** Annual expenses: Seguro del Carro
  $7.000.000, SOAT $447.300, DolarApp Premium US$69.99, Opal US$29.35 — a
  $620.608/month COP equivalent that today lands as a single $7.000.000 crater.
  Quarterly income: Ubidots Bonus US$2.847 → US$949/month normalized.
- **Seven months of history, 477 posted expenses** (Jan–Jul 2026) — the
  `average` rule is viable today. Sample 3-month averages (Apr–Jun, COP):
  Rideshare $331.816, Services $266.736, Courses $226.667, Home Maintenance
  $221.583, Restaurants $159.717, Entertainment $143.650, Flights $113.255.

## Dependencies

- **`008-mandatory-categories` lands first.** 10 of 14 active recurring items
  carry no category, which caps `from-recurring` at 3 derivable funds instead of
  8 and forces Internet to a polluted $149.585 average instead of its exact
  $85.000. Not a hard block, but building on uncategorised data wastes the
  feature's best rule.

## Source links

- Supersedes product ADR-003 (STS = unassigned money) and ADR-004 (forecast
  income) — formal supersede required at build time in
  `docs/decisions/product-decisions.md`. The goals-become-funds decision needs
  its own product ADR there too.
- Builds on product ADR-002 (envelopes + rollover) and ADR-005 (rollover
  positive-only) — the rollover mechanism is the fund vehicle, unchanged.
- Technical: `docs/adr/0006-goals-and-budgets-write-api-with-mcp-parity.md`
  (its goals half is superseded by this feature),
  `docs/adr/0028-bounded-query-read-path-for-monthly-aggregates.md`.
- Industry: [YNAB targets](https://support.ynab.com/en_us/getting-started-with-targets-ryAEP08xC),
  [YNAB categories vs accounts](https://support.ynab.com/en_us/category-balances-versus-account-balances-an-overview-ryvnKB_Ac),
  [Actual Budget goal templates](https://actualbudget.org/docs/experimental/goal-templates/),
  [Monarch goals](https://help.monarch.com/hc/en-us/articles/15000751305108-Using-Goals).

## Code co-locations

- Backend: `backend/src/quaestor/services/budgets.py` (headline + envelope
  status), `backend/src/quaestor/domain/rules.py` (`safe_to_spend_calc`,
  `envelope_status_calc`, `goal_progress_calc`),
  `backend/src/quaestor/services/month_aggregate.py` (bounded read path,
  ADR-0028), `backend/src/quaestor/services/goals.py` (removed),
  `backend/src/quaestor/services/month_close.py` (the goal proposal hook,
  removed).
- Frontend: `frontend/app/(app)/budgets/page.tsx`, the goals screen, the STS
  card in `frontend/app/(app)/page.tsx`.

## Notes

- Parked from discuss 2026-07-28 (portfolio review), promoted 2026-08-02.
- **Still too big for one pipeline run — expect phasing at `plan`.** The
  owner's position, stated 2026-08-02, is that the value only lands when the
  headline changes, so the split is into phases inside one feature rather than
  separate features. Likely phases: funding rules + per-fund rollover; goals
  fold-in and removal; normalized income + the new headline.
- **User design decisions captured 2026-07-31** (surfaced during a
  `discover-acs` run that landed on 001 by mistake):
  1. **Per-fund rollover rule** — accumulating funds ("tecnología: 100k every
     month — MUST accumulate") vs monthly-limit funds ("restaurantes: reset
     each month"). Per-category rollover toggles are industry standard
     (Monarch, PocketGuard, Quicken). Independently rederived on 2026-08-02 as
     exactly YNAB's *Set Aside Each Month* / *Refill Up To* pair.
  2. **Month income** — full product ADR-004 semantics: expected income from
     recurring, corrected to actual as incomes post (each counted exactly
     once), and atypical posted income (bonus) joins the pool. Feeds the
     normalized-income design.
  3. **Underfunded fund** — the headline must tell *"la verdad desde el
     inicio"*: when a known obligation exceeds its fund's coverage (assigned +
     accumulated), the shortfall reduces the headline from day 1, never as a
     surprise on charge day. `from-recurring` rules cover this naturally.
  4. **Independent fix (already closed):** assigning budget to an archived or
     `exclude_from_budget` category is rejected — shipped as fix
     `2026-07-31-phantom-budget-assignment`. Its AC/spec paper trail is still
     owed when consolidation task 15 unpauses.
- Consolidation impact: ATDD tasks for `budgets-safe-to-spend` and `goals` sit
  at the bottom of `.engineer/consolidation.md` and stay paused until this
  ships. Task 4 (`month-close-rollover`) is unblocked by decision 6 above.
- Open for `discover-acs`: the exact normalization formula for irregular
  intervals; what happens on the day a fund's obligation is actually charged
  (the fund empties, the headline must not move); the fate of the existing
  budgets page UI; whether `skipped` occurrences affect fund accumulation.
