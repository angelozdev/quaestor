# Quaestor — Architecture Decision Records

**Date:** 2026-06-16
**Context:** product review session over `docs/superpowers/specs/2026-06-16-quaestor-general-design.md`. Each ADR records a decided case, its rejected alternative, and the consequence in the sub-specs. The P0–P7 specs were updated to reflect these decisions.

> Format: **Status · Context · Decision · Alternatives rejected · Consequences.** Stable numbering; decisions are not renumbered when new ones are added.

---

## ADR-001 — The driver is an owned backend + agent-native (not just the 3 pains)

**Status:** accepted

**Context.** Lunch Money already works. Building an entire single-user system is only justified if the engine is more than "three features that LM is missing."

**Decision.** The primary driver is **(B) ownership + agent-native**: an owned DB, an owned backend, talking to an agent about *my* schema without depending on a third party's API. The 3 pains (to-pay, goals, reports) are the **v1 proof of value**, not the justification for the system. The **budget** is the explicit product differentiator (see ADR-002).

**Alternatives rejected.** (A) Solving only the 3 pains with a script over the LM API → gives neither ownership nor independence from the provider.

**Consequences.** Justifies the full build (P0–P7). Prioritizes the MCP/services path over the UI (see ADR-008). The budget gets disproportionate design investment (P4).

---

## ADR-002 — Hybrid budget: envelopes with rollover + safe-to-spend

**Status:** accepted · **Supersedes** the flat budget from the original spec (§6, P4)

**Context.** The original spec modeled an LM-style budget: category×month, amount vs actual expense, % used. That is exactly what the user already has in LM; it doesn't differentiate.

**Decision.** A **hybrid** budget:
- **Per-category envelopes with rollover.** Each category has an envelope (a `Budget` per month); whatever is not spent **rolls over** into the next month's envelope.
- **Global safe-to-spend** (see ADR-003): a headline number that integrates recurring + planned + goals, something LM structurally doesn't do.

**Alternatives rejected.** Pure YNAB-style envelope/rollover (competes on ground where YNAB already wins, doesn't differentiate); the flat LM budget (doesn't differentiate).

**Consequences.** P4 is rewritten (it's the differentiator). `Budget` gains rollover semantics. New `safe_to_spend` service. P4 now **depends on P3** (it needs planned + recurring for "committed"). P5 and the dashboard show both numbers.

---

## ADR-003 — safe-to-spend = unassigned money

**Status:** accepted

**Context.** With two layers (envelopes + global number) there is a risk of **counting the same money twice**: the unspent money that rolls over in an envelope AND counts as "free." A single source of truth is needed.

**Decision.** An assignment cascade. Income flows down in layers:

```
forecast income for the month
  − committed (auto recurring + planned + proposed goal contributions)
  − assigned to discretionary envelopes (with rollover)
  = SAFE TO SPEND = money you have NOT assigned to any envelope
```

- **safe-to-spend** = unassigned money (analogous to "Ready to Assign").
- **envelopes** = already-assigned money (with memory/rollover).
- Once you assign to an envelope, it leaves the safe-to-spend → nothing is counted twice.

**Alternatives rejected.** safe-to-spend = "what's left after distributing everything" (cushion) → tends toward ~0, loses its value as a headline number.

**Consequences.** Defines the `safe_to_spend` formula in P4. Depends on ADR-004 (where income comes from) and ADR-014 (count once).

---

## ADR-004 — The safe-to-spend income is forecast (expected)

**Status:** accepted

**Context.** safe-to-spend depends on how much money there is. With variable income, a forecast lies until the money arrives; with cash-on-hand you can't plan the month until the paycheck lands.

**Decision.** **Forecast (expected).** The month's expected income comes **from the `income` recurring items that touch the month** (salary, fixed freelance), **without a typed override** (A2). It feeds the safe-to-spend from day 1 → lets you plan the month from the start. An atypical income (bonus, year-end bonus) is recorded as a standalone income and counts when posted; it is not anticipated.

**Alternatives rejected.** YNAB-style cash-on-hand (only money already received) → more honest but doesn't allow planning; revisit if income becomes very irregular. Typed per-month override (A2) → recurring manual friction, avoided.

**Consequences.** P4 reads the expected income from the month's `income`-type recurring items. The forecast is corrected to actual as transactions post, counting each income exactly once (ADR-014).

---

## ADR-005 — Envelope overdraft eats from safe-to-spend; rollover positive only

**Status:** accepted

**Context.** What happens when a category spends more than its envelope?

**Decision.** The excess **eats from safe-to-spend** (the unassigned pool). The **rollover carries only a positive balance**: an overdrawn envelope is absorbed into the global pool and **resets to 0** the following month (it does not carry a negative).

**Alternatives rejected.** Carrying the negative into the next month (strict YNAB-style) → punishes twice and complicates the reading for a single user.

**Consequences.** Defines `rollover_in = max(previous_balance, 0)` in P4. An implementation detail; the P4 tests pin it down.

---

## ADR-006 — Flexible goals (it proposes + you confirm), not forced saving

**Status:** accepted · **Changes** the stance of the original spec (§6, P4: auto-transferred contribution on rollover)

**Context.** The original spec had `close_month` auto-create the `GoalContribution` + transfer: the goal paid itself like a bill. Risk: a tight month sneaks in an automatic transfer that leaves you in the red.

**Decision.** **Flexible saving.** The rollover **proposes** the contribution as a `planned` obligation (it shows up in "to-pay"); you **confirm** it with the actual amount (or skip it if the month was lean). It doesn't move money on its own.

**Alternatives rejected.** Forced saving / auto-transfer (maximum discipline, but fights with irregular months and breaks the balance).

**Consequences.** P4: the rollover hook changes from `apply_goal_contributions` (auto-transfer) to `propose_goal_contributions` (creates `planned`). `GoalContribution` is recorded on **confirmation**, not on rollover. Reuses the `planned`/`confirm_payment` machinery from P3 (see ADR-007). P3 exposes a post-confirm seam so P4 records the contribution without P3 knowing about goals.

---

## ADR-007 — "to-pay" is the single confirmation queue

**Status:** accepted

**Context.** After ADR-006, three different things need confirmation: manual recurring items (electricity, water), standalone payments (I owe a friend), and goal contributions.

**Decision.** All three converge on **"to-pay"** as the single confirmation queue. They are all `planned` transactions that `confirm_payment` turns into `posted`.

**Alternatives rejected.** Separate flows per type → three different mental models for the same action ("confirm an obligation").

**Consequences.** `to_pay` (P3) lists all three sources. The minimal dashboard (ADR-008) centers on this widget. P4 links its proposed contributions to the P3 queue.

---

## ADR-008 — Minimal frontend v1 (MCP-first); full CRUD to backlog

**Status:** accepted · **Trims** the scope of the original spec (§8, P6: full UI in v1)

**Context.** The driver is agent-native (ADR-001). A full Next.js app (10 routes, CRUD for everything) in v1 is weeks of a different product that competes with the engine. Chat is bad at **reviewing** (dashboards, tables), good at **recording**.

**Decision.** **MCP-first.** Frontend v1 = **two read-first views**: a dashboard with the "to-pay" widget + the monthly report. The rest of the CRUD is operated by the agent; the other screens are **documented as backlog**, not deleted.

**Alternatives rejected.** Full UI in v1 (maximum time before using it); MCP-only with no UI (loses the two views that chat does badly).

**Consequences.** P6 is trimmed to minimal v1 + backlog. Frontend build order: dashboard/to-pay and report first; the rest when needed.

---

## ADR-009 — Clean cold start (no backfill for now)

**Status:** accepted

**Context.** Reports with MoM drift, USD share, and envelope rollover need history to be useful. Starting empty leaves them decorative for ~2-3 months.

**Decision.** **Clean start, no backfill for now.** Weak reports for the first few months are accepted. The **CSV importer stays in scope** (P5) in case backfilling LM history is decided later (export LM → map to the owned CSV → import once).

**Alternatives rejected.** Immediate backfill via CSV (instant history, but work now); a dedicated LM migrator (over-engineering for a one-off import, already rejected in the spec).

**Consequences.** P5 notes that the importer remains available for deferred backfill; the report degrades gracefully when there is no previous month.

---

## ADR-010 — Full COP+USD multi-currency

**Status:** accepted (confirms the spec's decision)

**Context.** The user has roughly half of their expenses in USD (it is not occasional metadata).

**Decision.** **Full multi-currency**, exactly as the spec designs it: `currency` + `fx_rate` + `to_base` **frozen** at recording time + an `FxRate` table. Historical aggregates stay stable even if the rate changes.

**Alternatives rejected.** Recording only the COP the card charged and leaving FX as metadata (valid only if USD were marginal); COP-only.

**Consequences.** No changes to the P0 FX model. Surfaces the problem of **where the rate comes from** (ADR-011).

---

## ADR-011 — FX rate: daily auto-fetch + manual override

**Status:** accepted · **Changes** the "manual" of the original spec (§5, P0)

**Context.** With USD at ~50% of the volume, keeping the rate by hand is constant, forgettable friction; a stale rate leaves `to_base` skewed.

**Decision.** A **daily job** on the VPS hits a free FX API and stores the rate in `FxRate`. `set_fx_rate` remains as a **manual override / fallback** if the API fails. The `to_base` is still frozen at recording time.

**Alternatives rejected.** Manual only (friction); having the agent fetch the rate when recording (less reproducible, depends on the MCP client).

**Consequences.** P7 adds the scheduled job (alongside the rollover). P0 exposes the rate-update hook that the job invokes. Historical consistency intact (to_base frozen).

---

## ADR-012 — Recurring: auto for fixed, manual for variable (intentional asymmetry)

**Status:** accepted (confirms the spec's decision)

**Context.** After ADR-006/007, goals and manual recurring items go through confirmation. The **auto** recurring items are the only thing that still posts on its own. Inconsistency?

**Decision.** It's on purpose: **you confirm where there is a real decision, you automate where there isn't.** Rent/Netflix = fixed amount, nothing to decide → auto-posts. Electricity/water = varies → manual, you confirm. The asymmetry is a feature.

**Alternatives rejected.** Everything through "to-pay" (forcing confirmation where there's no choice = friction, not control).

**Consequences.** No changes to P3 on this. Reinforces the ADR-014 guard (an auto-recurring item that posts must not move the safe-to-spend if it was already committed).

---

## ADR-013 — Auth: /mcp behind Tailscale; frontend public with a password

**Status:** accepted · **Hardens** the original spec (§4: everything public behind HTTPS with a static token)

**Context.** A static `APP_TOKEN` is the only thing between the internet and full read/write access to the financial history. It neither expires nor rotates. The user operates the MCP from their own machines.

**Decision.** The sensitive `/mcp` endpoint is kept **off the public internet**, behind **Tailscale** (a private network); the user reaches it from their devices. The **frontend stays public** behind a password + HTTPS. The static `APP_TOKEN` is kept (no longer exposed at the critical point).

**Alternatives rejected.** A public static token as-is (one leak = full access, no panic button) — valid only if cloud MCP clients were needed; rotatable tokens + expiration (overkill for one person).

**Consequences.** P7 adds Tailscale for `/mcp`; Caddy stays public for the frontend. P2 documents that the transport lives on the private network. **Trade-off:** cloud MCP clients (claude.ai web) can't reach `/mcp`; if needed, revisit.

---

## ADR-014 — safe-to-spend counts each obligation exactly once

**Status:** accepted · **Critical guard**

**Context.** An obligation exists first as expected/`planned` and later as `posted`. If safe-to-spend subtracts it in both states, the number lies and trust is lost.

**Decision.** safe-to-spend counts each obligation **exactly once**, whether it is `planned` or already `posted`. When an auto-recurring item posts or a `planned` is confirmed, the money moves from "expected" to "real" but safe-to-spend **does not move** — it was already deducted.

**Alternatives rejected.** Summing planned + posted separately (double-count).

**Consequences.** P4 defines "committed" as the union (without double counting) of the month's obligations in any state. The P4 tests verify it explicitly.

---

## ADR-015 — Source account for goal contributions: global (Settings)

**Status:** accepted (case A3)

**Context.** A goal contribution is an internal transfer: the goal defines the **destination** account (savings), but the **source** account the money comes from was still undefined.

**Decision.** **A single global source account** in `Settings` (`default_source_account_id`). All goal contributions come out of there. The specific account doesn't matter; simplicity is preferred.

**Alternatives rejected.** A source account per goal (`Goal.source_account_id`) → extra config per goal; choosing on confirmation in "to-pay" → flexible but unnecessary for this user.

**Consequences.** `Settings` gains `default_source_account_id` (FK Account). `propose_goal_contributions` creates the `planned` proposal with that account as the source; on confirmation, the transfer comes out of there. If a per-goal setting is wanted later, it can be added without breaking anything.

---

## ADR-016 — Optional envelopes (not "every dollar a job")

**Status:** accepted (case A4)

**Context.** Should every category with spending have an envelope (YNAB "every dollar a job"), or only some?

**Decision.** **Optional envelopes.** Only the categories the user wants to discipline get a `Budget`; the rest spends **directly from safe-to-spend**. This is what keeps safe-to-spend a meaningful headline number: if everything were assigned, it would tend toward 0 (the very point ADR-002/003 sought would be lost).

**Alternatives rejected.** "Every dollar a job" (all categories with an envelope) → safe-to-spend ≈ 0, and it forces budgeting everything every month (heavy).

**Consequences — corrects the safe-to-spend formula.** Spending in categories **without an envelope** must be subtracted from the pool (otherwise the number overstates free money). Full formula (ADR-003/005/014/016):
```
safe_to_spend = forecast_income
              − committed                              # obligations, counted once (ADR-014)
              − Σ amount_assigned (categories with an envelope, this month)
              − Σ unbudgeted_spending                   # posted spending in categories WITHOUT an envelope
              − Σ overdraft                             # per envelope: max(spent − (assigned + rollover_in), 0)
```
- The `rollover_in` (money from previous months carried into the envelope) does **not** add to this month's safe-to-spend (it's already in the envelope) and **protects** against counting false overdraft.
- The rollover × overdraft × unbudgeted interactions are **pinned by the P4 tests**.

---

## ADR-017 — `close_month` fires automatically (daily scheduler, idempotent)

**Status:** accepted (case A5)

**Context.** The rollover (`close_month`) materializes the month: it posts `auto` recurring items, sends manual ones + goal contributions to "to-pay." If it depends on the user running it by hand and they forget, "to-pay" stays empty → breaks pain #1 ("what do I still have to pay?").

**Decision.** **Automatic, with no relevant manual trigger.** The `scheduler` (which already runs daily for FX, ADR-011) **ensures every day that the current month is closed**: on day 1 it materializes the month; the other days are a no-op (idempotency, P3); a missed day 1 **self-heals** on the next run. It's not a fragile monthly cron but a daily "ensure."

**Alternatives rejected.** Manual ("close June") → fragile, depends on memory. Hybrid auto + manual → the user chose pure auto; the manual trigger isn't needed (and idempotency already covers re-running if it were ever required).

**Consequences.** P7: the `scheduler` runs, daily, FX + `ensure_month_closed(current_month)`. `close_month` remains the service it invokes (P3); it stops being a user-facing MCP tool (it operates on its own). P3's idempotency is now a **robustness requirement**, not just a correctness one.

---

## ADR-018 — Mechanism for the flexible goal contribution (reviewed and accepted)

**Status:** accepted (cases B1, B2 — mechanisms proposed by the assistant and validated by the user)

**Context.** The flexible contribution (ADR-006) requires: proposing as `planned`, confirming by moving real money (a transfer to savings), and recording the contribution — without P3 (owner of "to-pay"/confirm) knowing what a goal is. The concrete mechanism wasn't decided by the user; the assistant proposed it and it was reviewed.

**Decision.**
- **B1 — recording the contribution (two records):** keep `goal_id` FK in `Transaction` + a **post-confirm hook** in P3 that writes the `GoalContribution` row on confirmation. "Deriving contributions from tagged transfers" (a single source of truth) was rejected — the user preferred explicit recording.
- **B2 — moving money (a single confirm):** P3's `confirm_payment` **materializes planned transfers** (a real pair via `transfer`) as a **generic** capability — not goal-specific. A single confirmation verb for everything (a one-account payment or a two-account transfer). A `confirm_contribution` of P4's own (two confirmation paths) was rejected.

**Alternatives rejected.** B1: contributions derived from transfers with `goal_id` (less machinery, but the user chose explicit recording). B2: P4 owning its confirmation (P3 intact, but two paths).

**Consequences.** No changes relative to what's already written in P3/P4 (the mechanism described there is confirmed). `confirm_payment` that materializes planned transfers stays as a reusable capability beyond goals.

---

## ADR-019 — Retrospective monthly report (headline = net + envelope performance; safe-to-spend at the bottom)

**Status:** accepted (case C1) · **Changes** the role of safe-to-spend in the report (§9, P5: it was the "headline number")

**Context.** Two surfaces show the month's numbers: the **dashboard** (live, current month, headline = safe-to-spend "how much I have left") and the **report** (`/reports`, month selector). The original spec put **safe-to-spend as the report's headline number**. But safe-to-spend is *forward-looking* ("what I have left to spend"): in an already-closed month it's just the leftover, an odd headline. Risk: report ≈ dashboard with a date-picker → redundant.

**Decision.** The monthly report is **purely retrospective** and answers *"how did I do?"*. Its **headline is the month's net + envelope performance** (how many in the green/red, how much rollover you generated for the next month) — exactly what LM doesn't tell. The **safe-to-spend drops to a closing figure at the bottom** ("you closed with $X free"), it is not the headline. The dashboard remains owner of the live safe-to-spend. Separate roles, zero redundancy.

**Alternatives rejected.** (B) Frozen safe-to-spend as the report's headline → report ≈ historical dashboard, little extra value and a meaningless headline in closed months. (C) No headline, all sections flat (LM-style) → loses the "at a glance."

**Consequences.** P5: the `safe_to_spend` of the `MonthlyReport` goes from "headline number" to **closing figure at the bottom**; the headline is built from `net` + an **envelope-performance summary** (green/red + total rollover generated). The markdown renderer orders: net → envelopes → goals → … → safe-to-spend at close. The dashboard (P6) doesn't change (it still shows safe-to-spend at the top, live).

---

## ADR-020 — Generic recurrence engine (every-N interval) + daily due-driven materialization

**Status:** accepted (case C2) · **Supersedes** the `frequency` enum + `due_day` and the `(recurring_id, period)` key of the original spec (§5, P3)

**Context.** The spec modeled `frequency ∈ {monthly, weekly, biweekly, yearly}` with a `due_day` (day-of-month) and an occurrence with a unique key `(recurring_id, period=YYYY-MM)` → **a single occurrence per recurring item per month**. That clashes with any sub-monthly frequency: a weekly recurring item falls ~4 times/month, a biweekly one 2. As it stood, weekly/biweekly fired only once. Moreover the user asked for **real variety**: monthly, every 3 and 4 months, semiannual, annual, weekly, every 2 weeks, etc.

**Decision.** A **generic every-N engine**, anchored to a date:
- `RecurringItem` replaces `frequency` + `due_day` with **`interval_unit ∈ {day, week, month, year}` + `interval_count` (≥1)**, anchored to `start_date`. Each due date = `start_date + k × interval`; end-of-month clamp for `month`/`year` units (day 31 → 30/28). Covers everything: monthly=`1 month`, quarterly=`3 month`, every-4-months=`4 month`, semiannual=`6 month`, annual=`12 month`, weekly=`1 week`, biweekly/every-2-weeks=`2 week`.
- The occurrence is keyed by **`(recurring_id, due_date)`** (not by `period`). More precise and still idempotent.
- **Due-driven materialization (not eager):** the daily `scheduler` (ADR-011/017) materializes each day the occurrences with `due_date ≤ today` not yet created. An **auto** posts on its real date (not the whole month in advance → the balance doesn't pull expenses forward); a **manual** is generated `planned` for the current month, visible in "to-pay." Missed days self-heal.

**Alternatives rejected.** (A) Only monthly/annual (biweekly = 2 separate recurring items) → simple but it splits items and doesn't give the requested variety. **Eager** materialization (the whole month at once on close) → today's balance pulls future expenses forward, exactly what a "how much do I have left?" system should avoid.

**Consequences.** P3 is redesigned: `RecurringItem` with an every-N interval; occurrence by `due_date`; the **daily materialization of recurring items** (due-driven, any interval) is **separated** from the **monthly close** (envelope rollover + goal-contribution proposal, which remain by calendar `period`, ADR-022). `domain/rules.py` changes `touches_period`/`due_date` to a per-interval date generator. P7: the daily scheduler runs FX + materialize-due(today) + ensure monthly close. Idempotency now by `(recurring_id, due_date)`.

---

## ADR-021 — Credit card on an accrual basis (expense at purchase; statement payment = transfer)

**Status:** accepted (case C3)

**Context.** `Account.type` already includes `credit`. With debit/cash the money leaves instantly; with a **credit card** you buy today and the money leaves the bank weeks later (when you pay the statement). It was still undecided when that expense hits the budget and safe-to-spend.

**Decision.** **Accrual basis (YNAB-style).** A card expense counts **on the day of purchase** against its category's envelope and lowers safe-to-spend at that moment. Two firm rules hold it up:
1. The **statement payment is a transfer** (debit account → card account), **never an expense** — otherwise it would be counted twice.
2. safe-to-spend and the envelopes count the expenses from **all accounts, including the card**, on the purchase date.

The card account stays a normal account with a **negative balance = debt**; the payment raises it toward zero without touching the budget again.

**Alternatives rejected.** Cash basis (the card expense doesn't touch the budget until the statement is paid) → safe-to-spend inflates during the month and crashes all at once on payment; dishonest for a system whose north star is "how much do I have left?".

**Consequences.** The **current model already supports this with no structural changes**. The two firm rules are documented in P0 (semantics of the `credit` account), §5/§6 of the general spec, and P4 (the safe-to-spend's `spent`/`unbudgeted_spending` aggregate **all accounts**; the statement payment, being a `transfer`, is already excluded from spending).

---

## ADR-022 — Budget period = calendar month

**Status:** accepted (case C4) · confirms the engine's assumption

**Context.** The whole system is wired to `YYYY-MM`: monthly close, envelopes, rollover, safe-to-spend. The alternative was budgeting by **pay cycle** (e.g. the 15th to the 14th, anchored to when the salary arrives), useful for someone living "paycheck to paycheck."

**Decision.** **Calendar month** (1 → end of month). The budget, the envelopes, and safe-to-spend reset on day 1. It's how most people reason and how the entire engine is already built.

**Alternatives rejected.** A configurable pay cycle (15 → 14) → breaks the `YYYY-MM` assumption that runs through P3/P4/P5; close, rollover, and reports would have to be re-keyed to arbitrary ranges. Expensive, and the **envelope rollover already covers** the case (whatever's left from the first half of the month stays available for the second half within the same calendar month).

**Consequences.** None to the model (confirms what exists). Note: the **materialization of recurring items** is by date (due-driven, ADR-020), but the **budget close/rollover and the contribution proposal** remain by calendar month.

---

## ADR-023 — Category group as its own entity

**Status:** accepted (case C5) · **Changes** `Category.group_name` (string) of the original spec (§5, P0)

**Context.** The category was always an entity (the `Category` table) and the per-category report already exists. The "group" (a container that bundles categories: "Essentials" → Groceries, Rent) was **free text** (`group_name`). The user wants structure and reports by category **and by group**.

**Decision.** The group becomes **its own entity `CategoryGroup`**; each `Category` points to a group by **FK (`group_id?`)**. We gain: renaming the group in a single place, fixed ordering (and color in the future), zero typos/phantom duplicates, and clean per-group report rollups.

**Alternatives rejected.** Group as free text → allows grouping in reports, but renaming forces touching every category, typos create duplicate groups, and there's no ordering/color. For a user who wants per-group reports, the entity is worth its minimal CRUD.

**Consequences.** P0: new entity `CategoryGroup` (`name`, `sort_order`, `archived`) + `create_group`/`list_groups` services; `Category.group_name` → `group_id?` (FK); `create_category` receives `group_id`. §5 of the general spec adds the `CategoryGroup` row and changes `Category`. P5: `CategorySection` resolves the group name by FK and enables per-group rollup. P6: `/categories` and `/category-groups` (backlog) manage both.

---

## ADR-024 — Masters and v1 scope: optional category, minimal settings, importer with no UI (confirmations)

**Status:** accepted (case C5, minor closures) · confirms the spec's assumptions

**Context.** A final sweep of masters/scope: three points the spec already assumed but that weren't recorded as a decision.

**Decision.**
- **Optional category when recording.** `Transaction.category_id` stays nullable: you can record "I spent 30 thousand" with no category. The expense without an envelope falls into the safe-to-spend's `unbudgeted_spending` (ADR-016). Low friction with the agent; the report shows how much was left uncategorized.
- **Minimal settings.** Only `base_currency=COP` (fixed) and `default_source_account_id` (ADR-015). No knobs are added for a single user; a real future preference = one more row, not a panel.
- **Importer as a service, no UI in v1.** `import_csv` (owned format) stays in P5 as a tested contract, but it starts clean (ADR-009) and the frontend v1 does **not** ship an `/import` screen (ADR-008). Usable via MCP/endpoint if needed occasionally.

**Alternatives rejected.** Forcing a category always (friction); a configurable settings panel (config no one will touch); an `/import` screen in v1 (UI for something not used on a clean start).

**Consequences.** None structural — confirms what exists. P5 keeps the importer available (deferred backfill); P6 leaves `/import` and the bulk of `/settings` in backlog.

---

## ADR-025 — Graduate the backlog frontend CRUD to a built UI, in two phases

**Status:** accepted · **Extends** ADR-008 (does not supersede it: the backlog screens were always the documented target, "built feature by feature when needed")

**Context.** ADR-008 shipped a minimal MCP-first frontend (dashboard + report) and deferred all CRUD to backlog, operated through the agent. Before P7 (deployment), the user wants the **full day-to-day workflow doable from the frontend**, not only through the agent. But the frontend is a thin client (P6: zero business logic), so it can only build CRUD for endpoints the API already exposes — and a sweep shows the differentiators (goals, budgets) and `recurring` edit/delete have only **read** (or partial) endpoints today; building their management would mean backend work in P4/P3 territory.

**Decision.** Graduate the backlog to a built UI in **two phases**:

- **Phase 1 (before P7):** frontend CRUD for **every entity the API already exposes** — `/transactions` (full CRUD + transfer + filters), `/to-pay` (confirm/skip/plan one-off), `/recurring` (create + list + skip), the four masters (`/accounts`, `/categories`, `/category-groups`, `/tags`), thin `/settings` (default source account + manual FX override), and **read-only** `/goals` and `/budgets`. Navigation moves to a grouped sidebar. The frontend stays a **thin client**: no business arithmetic in the client.
- **Phase 2 (later sub-project, possibly post-P7):** add the missing backend endpoints (goals CRUD + contribute, budgets assign/status, recurring edit/delete) and their management UI; enable re-activating archived masters.

**`/import` stays out of the UI** (reaffirms ADR-024): usable through the endpoint/MCP if ever needed.

**Build approach:** tiered — a generic schema-driven CRUD modal (`EntityFormDialog`) for the four uniform masters only; bespoke pages for the entities with their own shape (transactions, to-pay, recurring) and for the read-only planning views.

**Alternatives rejected.** (A) **Full-stack now** — also add the missing P3/P4 endpoints in this push so the differentiators are manageable from the UI: most complete, but balloons the scope back into P4 backend territory right before deployment. (B) **Stay MCP-only** for CRUD (status quo of ADR-008): keeps the frontend minimal but leaves the day-to-day workflow agent-only, which the user explicitly wants to change. (C) Build the CRUD without recording it: a real posture shift from "minimal v1" should be governed by a decision.

**Consequences.** New sub-project spec `docs/superpowers/specs/2026-06-20-P6-frontend-crud-design.md` (Phase 1). P6 grows from 2 views to 12 routes; `ui/` gains form primitives (dialog, select, checkbox, textarea, dropdown-menu) under the ADR-0002 boundary; `lib/api.ts` grows to ~35 methods + a `lib/query.ts` invalidation map. The agent (MCP, P2) remains a **co-equal write path** — the UI does not replace it. Phase 2 becomes the trigger for exposing the goals/budgets/recurring write endpoints in P4/P3. The thin-client rule (no business logic in the frontend) is preserved across both phases.
