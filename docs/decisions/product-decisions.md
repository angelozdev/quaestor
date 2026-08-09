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

**Status:** accepted, **amended by ADR-037** (feature 003, 2026-08-04) — the envelope becomes the *fund* and the rollover becomes per-fund rather than global; the hybrid stance survives, the two mechanisms become one · **Supersedes** the flat budget from the original spec (§6, P4)

**Context.** The original spec modeled an LM-style budget: category×month, amount vs actual expense, % used. That is exactly what the user already has in LM; it doesn't differentiate.

**Decision.** A **hybrid** budget:
- **Per-category envelopes with rollover.** Each category has an envelope (a `Budget` per month); whatever is not spent **rolls over** into the next month's envelope.
- **Global safe-to-spend** (see ADR-003): a headline number that integrates recurring + planned + goals, something LM structurally doesn't do.

**Alternatives rejected.** Pure YNAB-style envelope/rollover (competes on ground where YNAB already wins, doesn't differentiate); the flat LM budget (doesn't differentiate).

**Consequences.** P4 is rewritten (it's the differentiator). `Budget` gains rollover semantics. New `safe_to_spend` service. P4 now **depends on P3** (it needs planned + recurring for "committed"). P5 and the dashboard show both numbers.

---

## ADR-003 — safe-to-spend = unassigned money

**Status:** **superseded by ADR-037** (feature 003, 2026-08-04) — "unassigned money" required a monthly assignment ritual that was never performed once in the app's history; the headline is now income minus what every fund's rule asks

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

**Status:** accepted, **split and finally built by ADR-037** (feature 003, 2026-08-04) — **not** superseded. Its forecast clause is split across two numbers (the money available counts income only in the month it is due; the earning rate smooths it), and its reconciliation clause — *"corrected to actual as transactions post, counting each income exactly once"* — is implemented for the first time, seven months after acceptance (consolidation C17)

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

**Status:** **superseded by ADR-037** (feature 003, 2026-08-04) — goals disappear as a concept; a goal is a fund with a target and a date, and it names no account · **Changes** the stance of the original spec (§6, P4: auto-transferred contribution on rollover)

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

**Note (2026-08-04):** moot under ADR-037 — the goal transfers this setting existed for are gone. The setting itself stays: manual transfers still use it.

**Status:** accepted (case A3)

**Context.** A goal contribution is an internal transfer: the goal defines the **destination** account (savings), but the **source** account the money comes from was still undefined.

**Decision.** **A single global source account** in `Settings` (`default_source_account_id`). All goal contributions come out of there. The specific account doesn't matter; simplicity is preferred.

**Alternatives rejected.** A source account per goal (`Goal.source_account_id`) → extra config per goal; choosing on confirmation in "to-pay" → flexible but unnecessary for this user.

**Consequences.** `Settings` gains `default_source_account_id` (FK Account). `propose_goal_contributions` creates the `planned` proposal with that account as the source; on confirmation, the transfer comes out of there. If a per-goal setting is wanted later, it can be added without breaking anything.

---

## ADR-016 — Optional envelopes (not "every dollar a job")

**Status:** accepted (case A4), **amended by ADR-037** (feature 003, 2026-08-04) — "optional envelopes" becomes "optional funds" and `unbudgeted_spending` becomes *spending in categories no fund covers*. The principle is unchanged and is why the headline stays meaningful instead of tending to zero

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

**Status:** accepted (case C2) · **Supersedes** the `frequency` enum + `due_day` and the `(recurring_id, period)` key of the original spec (§5, P3) · **partially superseded by ADR-026** — the every-N engine, the `(recurring_id, due_date)` key and due-driven materialization all stand; the silent creation of past dates and the batch rollback do not

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

**Status:** accepted (case C5, minor closures) · confirms the spec's assumptions · **the "optional category" clause is superseded by ADR-036** (feature 008, 2026-08-03); the settings and importer clauses stand

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

- 2026-07-03 — Personal-finance data is now backed up daily on the VPS via `pg_dump` (ADR-0024). Up to 24h of unsynced changes may be lost in a VPS failure.

---

## ADR-026 — The engine never charges a date the user did not agree to, and one broken obligation costs only itself

**Status:** accepted (feature 007, 2026-08-02) · **Partially supersedes** ADR-020 · Technical detail in `docs/adr/0035` and `docs/adr/0036`

**Context.** ADR-020 fixed the shape of the engine — every-N interval, occurrence keyed by `(recurring_id, due_date)`, due-driven daily materialization — and two of its consequences turned out to be product decisions, not implementation detail. First, "the daily scheduler materializes each day the occurrences with `due_date ≤ today` not yet created" makes no distinction between a date missed because the machine was off and a date that was already in the past when the obligation was declared: declaring Netflix at 25.900 on 2 August with a start date of 5 January takes 181.300 out of the balance on the next run, unannounced. Second, the batch is one transaction, so a single obligation pointing at an archived account costs every other obligation its day, silently, every day until someone notices. The engine is the only surface in Quaestor that moves a balance with no user action, which is what makes both of these expensive.

**Decision.** Two rules, both scoped to what the user experiences:

- **Dates already passed when the obligation was declared are offered, never imposed.** They are presented one by one to accept or decline, and nothing is created until the user answers. A declined date is permanent: never charged, never offered again, never recreated by a later run. Declining every date is allowed and leaves the obligation live from its next future date. **Catch-up after downtime is unchanged** — an obligation that already existed was approved when it was declared, so the engine charges its missed dates unattended (this is the AC-9 / AC-12 line). The one place a missed date is *not* charged unattended is when the obligation was switched off and back on in the meantime: resuming cannot tell an outage's dates from the pause's, so it offers them too rather than deciding either way (ADR-0037, amended).
- **A failure on one obligation does not stop the others.** The rest of the day's charges still land, and the failure is reported naming which obligation and why. Each charge stays all-or-nothing on its own: its movement and its balance change together, or neither.

**Alternatives rejected.** (A) **Refuse a start date in the past outright**, as Firefly III does and as Actual Budget and YNAB effectively do by keeping schedules forward-only: simplest and the majority precedent, but it removes a capability the user asked for — declaring an obligation you have been paying for months and pulling that history in — and the workaround is entering months of movements by hand. GnuCash is the precedent for the chosen option, through its *Since Last Run* assistant, which lists every missed date and lets the user mark each Create / Postpone / Ignore. (B) **Keep the batch atomic and add a validation pass** before materializing: catches the predictable failures only, and duplicates the write path's rules in a second place that can drift.

**Consequences.** The every-N engine, the `(recurring_id, due_date)` key and due-driven daily materialization all stand exactly as ADR-020 states them. What changes is that a due date now has a fourth outcome — offered, awaiting the user's answer — and that the daily run reports per-obligation failures instead of failing whole. Feature 007's AC-12, AC-22 and AC-24 are the executable form of this decision.

---

## ADR-027 — The outstanding queue holds debt only, and expected money in is not planned

**Status:** accepted (feature 006, 2026-08-01)

**Context.** The queue that answers "what do I still owe" was populated by every pending transaction, income included. A manually-repeating salary materialized a pending income that landed among the bills: a planned salary of 5.000.000 beside an 85.000 phone bill rendered **"Por pagar 5.085.000"** — a number that is neither what is owed nor anything else, and one that hides the 85.000 bill behind the salary. Removing incomes then raises its own question: should the user be able to plan a *one-off* income — money expected but not yet received?

**Decision.** Two halves of one rule.

- **The queue carries obligations only** — expenses and transfers. Expected incoming money never appears there and never inflates the amount owed. The same example now shows one item and 85.000 owed.
- **Planning a one-off income stays out of scope.** Money coming in is recorded when it arrives; money that repeats is already covered by a recurring item. Forecasting individual inflows is a separate conversation, not a gap to patch here.

**Alternatives rejected.** (A) **Keep incomes in the queue but subtract them from the total** — turns "what I owe" into a net position, a different and less useful number, and still buries the 85.000 bill under the salary. (B) **A second queue for incoming money** in the same screen — a real shape, but the product had no confirmed need for planned one-off inflows; building the screen first and discovering the need later is the wrong order.

**Consequences.** `to_pay` filters to expenses and transfers. A repeating income can no longer usefully wait for confirmation, which forces ADR-031. The gap this leaves is real and deliberate: a repeating income whose money has not been recorded has **no screen** that can resolve it, and is currently reachable only through the agent. A **"Por cobrar"** view is the parked follow-up that would close it.

---

## ADR-028 — Skipping is reversible

**Status:** accepted (feature 006, 2026-08-01) · Technical detail in `docs/adr/0034`

**Context.** Skipping a pending payment was terminal. An 85.000 phone bill skipped by accident could not be brought back: the only recovery was to plan it again by hand, retyping payee, amount, due date and account, producing a new item with no memory of the old one. This is a one-click action used dozens of times a month.

**Decision.** A skipped payment can be returned to the queue with its payee, amount, due date and account intact, and can then be confirmed or skipped again like any other. **Undoing a skip moves no money on its own** — it restores the obligation, not a balance.

**Alternatives rejected.** (A) **Leave skipping terminal** and tell the user to re-plan: cheap, but it makes a high-frequency one-click action unforgiving. (B) **A confirmation dialog before skipping**: adds friction to the common correct case in order to protect against the rare mistake, and the mistake is cheap to undo once undo exists.

**Consequences.** `skipped → planned` becomes a legal transition, and the engine's record of that due date follows the movement rather than diverging from it.

---

## ADR-029 — Resolving something twice is refused, not silently absorbed

**Status:** accepted (feature 006, 2026-08-01)

**Context.** Two surfaces can resolve the same payment — the screen and the agent — and a screen can be stale. Confirming an already-confirmed 85.000 bill has two wrong answers: applying it moves the balance 85.000 twice, and silently succeeding leaves the user believing they just did something they did not.

**Decision.** Confirming or skipping something already confirmed, already skipped, or never owed in the first place is **refused with a message saying it is no longer pending**. The balance never moves a second time. The refusal *is* the feedback — it is how the user learns their screen was out of date.

**Alternatives rejected.** (A) **Idempotent absorb** (silently succeed, change nothing): protects the balance but withholds the one fact the user needs. (B) **Apply it again**: the defect itself.

**Consequences.** Every resolve path validates current status before acting. REST and MCP surface the same refusal, so the agent and the screen tell the user the same thing.

---

## ADR-030 — Without an exchange rate the app refuses to guess, even when it could

**Status:** accepted (feature 006, 2026-08-01) · **Upholds** feature 005's AC-9; does not supersede it · **generalised to every read path by ADR-038** (feature 003, 2026-08-04)

**Context.** Quaestor holds money in COP and USD. Feature 005 decided the app never assumes a rate: a report with no rate fails loudly rather than showing a wrong total. Feature 006 had to decide whether the outstanding queue inherits that rule or earns an exception, since a queue whose items happen to be all in pesos does not strictly need a rate to be correct.

**Decision.** Reading the outstanding queue with no rate ever set **fails with a clear message telling the user to set one — even when everything owed is already in pesos**. Planning and skipping keep working without a rate, so a user who has not set one is not locked out of recording.

**Alternatives rejected.** (A) **Require the rate only when a non-COP item is present**: correct in the moment, but it makes the rule conditional on today's data, so the user meets it only when it bites — adding a single USD item silently changes how the app behaves. (B) **Fall back to a stale or default rate**: exactly what feature 005 ruled out.

**Consequences.** One rule to remember instead of two. The rate is a genuine prerequisite of the reading surfaces and a non-issue for the writing ones.

---

## ADR-031 — Repeating income is always automatic

**Status:** accepted (feature 007, 2026-08-02) · **Consequence of** ADR-027 · Technical detail in `docs/adr/0039`

**Context.** A repeating item could be declared *manual*, meaning the engine created it as pending and waited for the user to confirm. For an expense that works — it lands in the outstanding queue and is resolved there. For an income it does not, because ADR-027 took incomes out of that queue. A manual repeating salary therefore produced a pending movement that **no screen could resolve**, accumulating one invisible row per month.

**Decision.** A repeating income is **always automatic**. On its due date it is recorded and the balance rises. A salary of 4.500.000 on the 30th adds 4.500.000 on the 30th; **if the real deposit was 4.480.000 the user corrects that movement**. Declaring an income that waits for confirmation is refused at the moment of declaring, with the reason.

**Alternatives rejected.** (A) **Build the "Por cobrar" screen** so manual income becomes resolvable: the complete answer, and still the right long-term shape, but it is a feature of its own, and 007's job was to stop the engine producing state nobody can act on. (B) **Accept the manual flag and quietly treat it as automatic**: the behaviour would be right and the record would lie.

**Consequences.** Existing manual repeating incomes were converted by a data migration. **The movements those items had already produced were deliberately not converted**: registering them would move balances the user never confirmed, and cancelling them would erase the record that the money was expected. Which one applies changes row by row, so it is a human decision, not a migration's. Until a "Por cobrar" view exists, the agent is the only surface that can resolve them. The month's forecast is unaffected either way — the recurring item is what tells safe-to-spend the money is coming, whatever state a past movement is in.

---

## ADR-032 — An obligation that reaches its end date switches itself off

**Status:** accepted (feature 007, 2026-08-02) · Technical detail in `docs/adr/0037`

**Context.** An obligation with an end date stayed listed as live forever after that date, producing nothing. The list of active obligations therefore mixed what is still going to be charged with what has already finished, and the only way to tell them apart was to open each one and read its end date.

**Decision.** Once the last due date on or before the end date has passed, the obligation **stops being live**: it leaves the active list and joins the switched-off ones, so that list only ever holds what is still going to be charged. **Extending the end date brings it back**, with no separate reactivation step.

**Alternatives rejected.** (A) **Keep it listed with a badge**: the list stays something to read rather than something to trust. (B) **Delete it at the end date**: destroys history the user may want to consult or extend.

**Consequences.** Being live is *derived* from the end date rather than stored, so there is no second piece of state that can drift out of agreement with the dates. Extending is an ordinary edit.

---

## ADR-033 — Resuming a paused obligation never charges the pause unattended

**Status:** accepted (feature 007, 2026-08-02) · Technical detail in `docs/adr/0037` (amended)

**Context.** A gym at 120.000 paused in March and resumed in August: the shipped engine charged all four paused dates at once on the first run after the resume — **480.000 in one go** — which turns pausing into deferring. The obvious opposite, discarding those four dates, is also wrong in a case the engine cannot distinguish: switching an obligation off and on again is *exactly* what a machine outage plus a manual restart looks like, and in that case the four dates are real money owed.

**Decision.** Resuming **never charges the paused stretch unattended**. The obligation charges next on its next due date from today. The dates that fell inside the pause are **offered** — presented for the user to accept or decline, one by one — because only the user knows whether those months were a deliberate pause or an interruption. Accepting none is the normal case and leaves the obligation live from its next future date.

**Alternatives rejected.** (A) **Charge the whole stretch** (the shipped behaviour): 480.000 unannounced. (B) **Discard the stretch silently**, which is what feature 007's AC-17 originally asked for: correct whenever the pause was deliberate, wrong and unrecoverable whenever it was an outage, and the user is never told which case they were in. Raised during independent review as defect D1 and decided by the user in favour of offering.

**Consequences.** Pausing keeps a predictable cost of exactly zero. Resuming may present a list of dates to decide, which is the same surface ADR-026 introduced for dates already in the past at declaration time — one mechanism, two entry points.

---

## ADR-034 — A charged date is not un-charged by skipping; deleting the movement is the correction

**Status:** accepted (feature 007, 2026-08-02) · Technical detail in `docs/adr/0038`

**Context.** Two halves of the same hole. Skipping a date whose money had already moved marked the date *skipped* while leaving the money out of the account: Netflix at 25.900 charged on 5 August and then skipped left the balance 25.900 lower while the record claimed nothing had happened — the obligation said unpaid, the account said paid. And deleting the movement the engine created returned the money but left the date recorded as charged, pointing at a movement that no longer existed, **consuming that date forever**: no run brought it back and no screen showed anything was wrong.

**Decision.** One correction path, in two parts.

- **Skipping a date whose money already moved is refused**, with a message saying it was already charged and pointing at the movement itself. Nothing changes. Skipping exists for what has not happened yet.
- **Deleting the movement the engine created returns the money *and* closes that due date**: it counts as skipped from then on and no later run charges it again. Deleting the 25.900 Netflix charge of 5 August puts 25.900 back in the account and leaves 5 August settled for good; 5 September arrives normally.

**Alternatives rejected.** (A) **Allow the skip and reverse the balance as a side effect**: a skip that silently moves money is a different action wearing the wrong name. (B) **Refuse the skip and stop there**: leaves the user holding a charge they want undone with no route out — the deletion path is what makes the refusal actionable rather than merely obstructive.

**Consequences.** The obligation and the account always agree. Deleting the movement becomes the single documented way to correct an engine charge made in error, and the refusal message names it.

---

## ADR-035 — Every engine charge is recognisable as one, without opening it

**Status:** accepted (feature 007, 2026-08-02) · Technical detail in `docs/adr/0038`

**Context.** The engine is the only surface in Quaestor that moves a balance with no user action. A movement it created recorded its origin internally but presented itself as hand-entered: nothing in the list of movements distinguished a 25.900 Netflix charge the engine posted overnight from one the user typed. Reconciling a balance that moved while the user was not looking meant guessing.

**Decision.** A movement created by the engine is **recognisable as such in the list of movements, without opening anything**, and identifies which obligation produced it.

**Alternatives rejected.** (A) **Show the origin only in the detail view**: the question "why did this move?" is asked while scanning a list, not while reading one row. (B) **Infer it from the payee matching the obligation's name**: breaks the moment the user renames either one.

**Consequences.** Origin becomes a displayed property, not merely a stored one. Charges made by the engine, by import, by the agent and by hand are told apart at a glance — which is also what makes ADR-034's deletion path safe to reach for.

---

## ADR-036 — Every peso that moves in or out says what it was for

**Status:** accepted (feature 008, 2026-08-03) · **Supersedes** ADR-024's "optional category when recording" clause · Technical detail in `docs/adr/0041` and `docs/adr/0042`

**Context.** ADR-024 kept the category optional on purpose: "you can record *I spent 30 thousand* with no category… Forcing a category always (friction)". Low friction with the agent, and the report would show how much was left uncategorised.

Measured against production on 2026-08-02, that is what it cost:

| | Rows | Uncategorised |
|---|---|---|
| expense (posted) | 477 | 28 |
| expense (planned / skipped) | 71 | 68 |
| income (posted) | 22 | 7 |
| income (skipped) | 28 | 28 |
| recurring items | 14 | **10** |

Money invisible to every report, posted and confirmed: **$2.072.854 COP + US$7.486,68 in expenses, $7.003.101 COP + US$10.495,55 in income.** Ten of the fourteen recurring obligations carried no category — including all three salaries, despite 💼 Salary existing — and those ten alone had produced 101 of the 131 uncategorised movements.

"The report shows how much was left uncategorised" turned out to be true and useless: seeing the number does not tell you which restaurant meal it was. The gap surfaced when feature 003's funding-rule proposal could derive only 3 envelopes from recurring items instead of 8, and Internet resolved to a $149.585 three-month average — inflated by uncategorised rows — instead of its exact $85.000.

**Decision.** **A category is mandatory on every expense and every income.** The app refuses to record one without it, and so do the records themselves.

- **Transfers carry none, by rule.** Moving money between the owner's own accounts is not spending: net worth does not change. Categorising a transfer counts the same money twice — once moving into the emergency fund, again when it is finally spent out of it. All 39 existing transfers are correctly uncategorised and stay that way.
- **A category belongs to one direction.** Recording money coming in offers only income categories, money going out only expense categories. A salary cannot be filed under 🍽️ Restaurantes because 🍽️ Restaurantes is not among the options.
- **The friction ADR-024 feared is answered, not accepted.** When nothing fits, the category is created from the same screen where the movement is being recorded, in one action, without losing what was typed. The case that forced it: four `4x1000` charges (Colombia's financial transaction tax) matched none of the owner's 34 categories.
- **Skipped charges carry a category too.** Owner's position: *"cualquier cosa que yo haga debe entrar en una categoría, debe."*
- **A recurring item's category is copied onto each charge at birth, not linked.** Re-classifying an obligation applies forward; closed months never rewrite themselves.

**Alternatives rejected.** (A) **Keep it optional and add an in-app "to fix" queue**: postpones the same decision to a screen the owner would visit as rarely as the categories screen — the 131 rows accumulated over months of exactly that. (B) **Force a category but leave it untyped**: closes the hole and leaves a salary filable as a restaurant meal, which is the specific failure feature 003 cannot survive. (C) **Give transfers a category too** (Monarch and Lunch Money both do, and the owner improvised `🔄 Payment / Transfer` by hand): a real design question, deliberately **parked as a separate discuss** rather than absorbed here.

**Consequences.**

- Uncategorised is no longer a state the data can reach, so per-category reports, monthly averages and any future envelope see every peso. `unbudgeted_spending` (ADR-016) is untouched and keeps its meaning — a category **without an envelope** is still unbudgeted; what disappears is money with **no category at all**. The two were never the same thing.
- The historical 131 rows were resolved by hand before the rule turned on, after a fresh backup (`quaestor-local-2026-08-02.dump`, ADR-0030): 101 by setting the 10 recurring items that lacked a category, 30 individually, with seven new categories created (🎁 Bonos, 💰 Rendimientos, 💳 Cashback, 🏦 Comisiones bancarias, 💸 Impuestos, 🔧 Mantenimiento Carro, 🧽 Lavado Carro).
- **Out of scope, and stated so it is not mistaken for an oversight:** re-categorising movements that already carry a category. Notably the 24 rows in `🔄 Payment / Transfer` that are typed as expenses but are not spending (`Ubidots (salario) -$6.223.101`, `Tyba -$29.084.436`, loans, Bitcoin) — the owner's workaround for the missing transfer category, which alternative (C) will decide.

---

## ADR-037 — Envelopes and goals collapse into one thing, the fund; and the month shows two numbers, not one

**Status:** accepted (feature 003, 2026-08-04), **amended by ADR-042** (feature 010, 2026-08-07) — vocabulary only: the fund that does not accumulate is named *presupuesto*, and every mechanism below stands unchanged, **and partly superseded by ADR-043** (feature 009, 2026-08-08) — the *"no separate goals feature"* clause and the four-rule list are replaced; everything else below stands · **Supersedes** ADR-003 (safe-to-spend = unassigned money) and ADR-006 (flexible goals) · **Amends** ADR-002 and ADR-016 · Technical detail in `docs/adr/0043` and `docs/adr/0044`

**Context.** ADR-002 gave Quaestor two layers: per-category envelopes with rollover, and a global safe-to-spend on top. ADR-006 added a third mechanism, the goal, with its own table, its own screen and a savings account it forced the user to link.

Measured against production on 2026-08-02:

- **Zero envelopes have ever been created.** Not one `Budget` row in the app's history. The differentiator ADR-002 named has no users.
- **One goal, zero contributions**, and it is broken in the exact way the design predicts:

  ```
  Goal "Korea"        $0 of $10.000.000      0%    ← what the app shows
  Account 🇰🇷 Korea    $14.659.572                  ← what actually exists
  ```

  Progress counts `GoalContribution` rows instead of the balance of the account the goal demanded. Three proposed transfers sit unconfirmed. The owner's correction during AC discovery is the whole point: *"olvida la cuenta"* — the $10.000.000 exist and have simply never been registered, and they are waiting for this feature.
- **The lumpiness is real and large.** $7.000.000 car insurance and $447.300 SOAT, both annual, land as a single crater; a US$2.847 quarterly bonus lands as a spike.

The reason the envelope stayed empty is not reluctance to configure. YNAB and Actual both require a **monthly ritual** — a button that distributes money into categories — and Quaestor copied the shape without asking whether a single user would press it every month for years. The answer, in seven months of data, is no.

**Decision.** **One noun: the fund.** A fund lives on one expense category, carries a **funding rule** and a start month, and *asks* for an amount each month. That ask is subtracted from the money available. A goal is a fund with a target and a date; an envelope is a fund with a fixed amount. There is no separate goals feature and no separate envelope.

- **The rule is the number — there is no monthly ritual.** Once configured, a fund costs zero clicks per month forever. This is the load-bearing decision: any design needing a recurring manual action ends up empty again.
- **Four rules.** `fixed` (an amount the owner names) · `average` (what the category actually cost, over a window the owner chooses) · `from-recurring` (every obligation filed under the category, added up) · `target-by-date` (an amount by a date — the former goal).
- **The fund never names an account.** Where the money sits and what it is for are orthogonal. A fund that already holds money is told so once, at creation, and never re-reads anything afterwards.
- **The fund is whole the month *before* the charge.** The SOAT charging 2027-05-02 from a November start asks $74.550 over six months, not $63.900 over seven — otherwise the money is still short on the morning it is taken.
- **A dated obligation divides by the months that remain, and recomputes.** Not a fixed ÷12. Putting in more one month lowers the next; a fund that gets drained raises its ask so the charge is still met.
- **Rollover is per fund.** 🍽️ Restaurantes resets each month; 💻 Tecnología accumulates. The choice is offered only where both make sense — a fund saving toward a date always accumulates, and is not asked.

**And the month shows two numbers, never merged:**

| | answers | smoothed? |
|---|---|---|
| **the money available this month** | *how much can I spend* — a balance | **no** |
| **earning rate / cost rate / margin** | *does my life fit my income* — rates | **yes** |

```
money available = income this month − Σ what every fund asks − what no fund covers
```

Income counts in the month it is **due**, and never before: the quarterly bonus contributes nothing to August and all of itself to September. Once real money lands in an income category, the guess for that category is dropped and only what arrived counts — **which is ADR-004's reconciliation clause, accepted seven months ago and never built.**

The rates are the other question, and there smoothing is correct: the quarterly bonus contributes a third of itself to each of three months. YNAB ships the same split — *Cost to Be Me* against *Ready to Assign* — and puts expected income in the first, never the second.

**Alternatives rejected.**

- **(A) Keep envelopes and add funds beside them.** Two ways to depress the same headline, which is already a live defect: an envelope can be assigned to an income category today and depresses safe-to-spend permanently with no way to clear it. A `fixed` accumulating fund *is* an envelope; keeping both is keeping the bug.
- **(B) Smooth the income into the money available too** — the owner's first choice, reopened after `acs.md` was written and argued in full. It was not rejected but **moved**. Smoothing an expense forward errs safe (money held that may not be needed); smoothing income forward errs unrecoverably (money spent that never arrived). The question the owner actually wanted answered — *"cuánto estoy ganando mes a mes"* — is a rate, and it now has its own number where smoothing is right.
- **(C) Auto-propose a full set of funds** from the recurring items and spending history. Reversed by the owner: the app starts empty and every fund exists because the owner made it. Once created, the rule still computes its own amount — that is the rule working, not a proposal. Auto-proposal stays available if adoption stalls.
- **(D) A configurable average** (divide by months-with-data vs months-in-window). Two reasons a month can be empty were separated instead: a month the app has **no data for** is excluded from the division; a month that existed with nothing spent is a real zero and counts. With that separated, the remaining "choice" was two different questions, and the other one is already reachable — it is the `fixed` rule.

**Consequences.**

- **ADR-003 is replaced.** Safe-to-spend as *unassigned money* required the assignment ritual to mean anything. The money available is now income minus what the rules ask, and it **shows its work**: the number opens into the income it counted, each fund by name and amount, and the uncovered spending. Nothing in it is unattributable.
- **ADR-006 is removed entirely.** The goals screen, the goal records and the month-end routine that proposed one transfer per goal all go. Nothing in the app afterwards requires a savings account to express an intention. The three unconfirmed Korea proposals are deleted with them — they were proposals from a routine that no longer exists and never moved money.
- **ADR-002 is amended:** the envelope becomes the fund and the rollover becomes per-fund rather than global. The hybrid stance survives; the two mechanisms become one.
- **ADR-016 is amended:** "optional envelopes" becomes "optional funds", and `unbudgeted_spending` becomes *spending in categories no fund covers*. The principle is unchanged and is why the headline stays meaningful instead of tending to zero.
- **ADR-004 is NOT superseded.** Its forecast clause is split across the two numbers, and its reconciliation clause is finally built.
- **ADR-005 survives unchanged** and is relied on directly: spending past a fund takes only the excess from the money available, and a fund never carries a negative balance into the next month.
- **ADR-015** (global source account for goal contributions) becomes moot with the goal transfers it existed for.
- **Nothing is frozen.** Asking for August's available money after switching off an income in October gives August's figure *without* that income. This is where Quaestor departs from both YNAB and Actual, where an assignment is a stored fact. The cost, chosen knowingly: a screenshot of August's number will not always match the app later.
- **A destructive migration on real data** — three tables and one column dropped, three unconfirmed proposals deleted. It runs behind a fresh backup and explicit human authorisation (charter §7, ADR-0030).

---

## ADR-038 — The rate is asked for on the way in, not when a dollar shows up

**Status:** accepted (feature 003, 2026-08-04) · **Upholds** ADR-030 and feature 005's AC-9; **withdraws** the amendment `docs/adr/0044` had proposed to technical ADR-0031 · **Expires** with the daily-TRM job on the roadmap

**Context.** Quaestor holds money in COP and USD, and every COP figure it shows is computed at read time from one USD→COP rate (the TRM). ADR-030 already settled the general rule for feature 006: without a rate the app refuses to guess, **even when everything owed is already in pesos**.

Feature 003 reopened it from the other side. Its new reading surfaces — the money available, the earning and cost rates, each fund's status — were built to fetch the rate **only on contact with a non-COP amount**, so a month recorded entirely in pesos would read without one. The argument was a measurement: 85 of the 92 approved scenarios of feature 003 never mention a rate.

**Decision.** **The rate is demanded on entry to every read path, always, and a rate must always be set.** The owner: *"La tasa se aplica al entrar en la app. Siempre debe estar (mientras creamos un feature que obtenga la TRM por debajo día a día)."*

Recording keeps working without a rate — an expense in dollars is registered whether or not a rate exists (feature 005's AC-1). It is *reading a COP figure* that requires one.

The friction is accepted because it **names its own expiry**: a job that fetches the TRM day by day is on the roadmap, and once it runs the rate is never missing in practice. Until then, setting it is a one-time act on a fresh install, not a daily chore.

**Alternatives rejected.** (A) **Ask for the rate only when a foreign amount is actually met** — the proposal this decision withdraws. It is correct in the moment and wrong as a rule: the app's behaviour would depend on today's data, so the user meets the requirement only when it bites, and adding one US$30 gym membership silently changes what the app will show. Exactly the alternative ADR-030 rejected for the outstanding queue, arriving again under a different name. (B) **Fall back to a default or stale rate** — what feature 005 ruled out; a wrong total is worse than no total.

**Consequences.**

- **One rule, no exceptions.** Technical ADR-0031's "reads fail loud" stays uniform, and ADR-030 stays the whole story rather than one case of two.
- **The accepted cost:** a month recorded entirely in pesos cannot be read until a rate is set. The owner knows this and chose it.
- **The 92 approved scenarios stand untouched.** They were silent about the rate, not dependent on its absence — every scenario whose subject *is* the missing rate says so explicitly. The acceptance suite seeds a rate as background state, exactly as a running app carries one.
- **The expiry is a roadmap item**, not a promise in prose: `daily-trm-fetch`. When it ships, this decision's friction disappears without the rule changing.

---

## ADR-039 — A bill that arrives for a different amount costs what it really cost

**Status:** accepted (feature 003, 2026-08-04) · **Mirrors** ADR-004's reconciliation clause onto the expense side · Technical detail in `docs/adr/0044`

**Context.** Feature 003 made the month's income stop guessing the moment money lands: a salary expecting $5.000.000 where $4.200.000 arrived counts $4.200.000, not both. The expense side was never given the same rule, and nobody noticed until Checkpoint 7.

Recurring expenses declare an amount. Real bills do not honour it — the electricity bill declared at $200.000 arrives at $250.000. The app was subtracting the **declared** figure from the money available and skipping the posted movement entirely, on the assumption that the declaration already accounted for it.

Two ways that loses money, both **upward**, which is the direction that gets spent before it can be corrected:

- the bill posts at $250.000 → the headline is $50.000 too high;
- the owner switches the obligation off after paying → the whole $200.000 disappears from the month, and `uncovered` reports $0,00 for a month that really spent $200.000.

**Decision.** **A turn that has posted is counted at what actually left the account; a turn still ahead is counted at what its obligation declared.** Every posted expense counts exactly once, at its real figure.

The owner, choosing between three framings put to him with numbers: *"Option 2"* — what really happened.

The match is **per turn**, not per obligation or per category: a posted expense carries the `recurring_id` of the turn that produced it, so each posted charge replaces exactly one promise. A weekly obligation with one charge posted and three ahead counts one real amount plus three declared ones. Income cannot do this — a posted income carries no link back to the obligation that expected it — which is why its boundary stays per category.

**Alternatives rejected.** (A) **Always the declared amount** — what the defect did. Stable, predictable, and wrong every time reality differs. (B) **The greater of declared and posted** — never overstates, but hides money from the owner in every month a bill comes in cheap: pay $150.000 against a $200.000 declaration and the app keeps $50.000 you actually have. It also needs two rules where one now serves, since the income side already reconciles to actual.

**Consequences.**

- **One rule for money in and money out.** *What really happened if it happened; what was expected if not.* The two sides of the headline now read the same way, which is one thing to remember instead of two.
- **The number moves when you register.** Confirming a bill at its real amount changes the money available on the spot. That is the point — the figure tracks reality rather than a declaration.
- **A fund absorbs this before it reaches the headline.** In a category *with* a fund, only spending past what the fund had set aside reaches the money available (AC-13), so this rule bites hardest on categories with no fund — which is every category until the owner creates one.
- **Pinned by the contract, not only by unit tests.** Six unit tests plus **AC-29**, three scenarios the owner authorised adding to the approved `spec.md`. They were run against the code they replaced and all three fail there, so they can actually catch a regression — the check AC-7 never had, and the reason that AC is filed as a defect.

## ADR-040 — A fund is behind when the month left it worse than not touching it would

**Status:** accepted (feature 003, 2026-08-04) · **Completes** ADR-037's fund status · Closes consolidation defect C19

**Context.** The funds table shows a badge per fund: *En camino* in green, *Atrasado* in red. Nothing ever decided what it means. It was a scope bullet in `feature.md` that Checkpoint 2 never turned into an acceptance criterion, so the implementer had to invent a threshold, and the one it invented can barely fire.

The badge asked one question: *did this month's spending push up what the fund must ask?* That reading is real and the contract already pins it — vacía un fondo de $3.600.000 de seguro y la cuota sube de $600.000 a $1.200.000, so it is behind. But it is the only question asked, and two of the four funding rules cannot answer it:

- **A fixed fund asks the same however much is spent.** $300.000 a month whether the category spent nothing or $900.000. Both sides of the comparison are equal, so the badge is green — including the month the fund empties out and spills over.
- **An averaged fund is the same**, its ask coming from completed months only.
- **Any fund opening at zero is the same**, because a fund holding nothing cannot hold less. That is every fund's first month, every month of a fund that resets, and every month after one is drained.

Seen live: a fund overdrawn by 350% with the green badge on, and the report's counter reading *cero atrasados*.

**Decision.** **A fund is behind when the month left it worse than not touching that category would have.** A fund can lose ground two ways, and both count:

1. the spending pushed up what the fund must ask, or
2. the spending went past everything the fund had — what it opened with plus what it asks.

Green means neither happened. The second reading is the same figure the money available already uses for the overspill (AC-13), so **the badge turns red exactly when the fund starts costing the month money** — the badge and the headline number can no longer disagree.

**Alternatives rejected.** (A) **Replace the ask-rise reading with the overspill one.** Simpler and uniform, but it contradicts an approved scenario: raiding a $3.600.000 insurance fund spills nothing (the money was there) yet doubles the cuota, and the owner's contract already calls that behind. Tried, and the acceptance suite refused it. (B) **Ritmo — compare what the fund holds against what it should hold by now.** The sharpest reading for a dated goal, but undated funds have no target to fall behind of, so half the funds would need the badge hidden and the owner would have two meanings to hold. Kept on the table for the *metas* feature, where every fund has a date by construction. (C) **Drop the badge.** Honest, and rejected: the case that hurts — spending more than the sobre had — is exactly what the owner wants flagged.

**Consequences.**

- **The badge can now be red for every rule.** Fixed and averaged funds get their first way to fail.
- **The counter is trustworthy.** *Atrasados* on the report counts the funds that actually cost the month money.
- **Not a pace warning.** A goal quietly slipping behind schedule while never overspending still shows green. That is the trade named in alternative (B) and is deliberate — the fix belongs to *metas*.
- **No new reading of the database.** The overspill was already computed for the money available; the fund's fold now hands the same figure to both, so the badge costs nothing and the two can never drift.
- **Pinned by the contract, not only by unit tests.** Five unit tests plus **AC-30**, three scenarios the owner authorised adding to the approved `spec.md`. Two of the three were run against the code they replaced and fail there; the third is the boundary and passes both ways, which is what a boundary is for. This closes the amendment in ADR-0043 that recorded the green badge as a known hole — and closes it *late*, since that amendment asked for the scenario **before** the code and got it after.

## ADR-041 — What a fund already holds is always said for a month, and never for a past one

**Status:** accepted (2026-08-05) · **Decides** ADR-0043's anchor-month amendment · **Not yet implemented** — see Confirmation

**Context.** A fund's balance is derived, never stored (ADR-0043). The one exception is the owner's own statement — *"this fund already holds $500.000"* — which is an input, not a reading. The app records the figure but not the month it was said for, and reads it as *"stated for whichever month is being looked at"*.

That makes the figure follow the owner around. A fund told in January it holds $500.000, asking $200.000 a month:

| Month opened | True | What the app says |
|---|---|---|
| December | $0 — nothing had been declared yet | $500.000 |
| January | $500.000 | $500.000 |
| February | $700.000 | $500.000 |
| March | $900.000 | $500.000 |

Right only in the month it was written, and in December it invents money in the past.

**Two things were found while deciding this, and both changed the answer.**

*The screen cannot say it at all.* The fund form offers category, rule, amount, window, target, target month, start month and accumulate — and no opening balance. The table offers only delete. The API supports it on both create and update; only the assistant ever writes it. So the undated path is not one of two ways to state a balance, it is the **only** way a person has.

*Neither reference system has an undated balance — the concept does not exist.* In YNAB and Actual Budget the budget **is** month-by-month: money is assigned into a month's column, and a category's balance is that month's assignment minus its spending plus what rolled over. There is nothing to date because nothing floats. YNAB also refuses retroactive resets outright — a Fresh Start begins today, with no way to create one from a point in the past; reflecting history means entering the movements.

**Decision.** **A stated balance always carries the month it was said for, and that month is never chosen freely.**

- **Said while creating the fund** — it carries the fund's **start month**, which the owner has just picked on the same screen. The form gains the field it never had, so *"it starts in August and by then it already held $500.000"* is one sentence in one place.
- **Said afterwards, through the assistant** — it carries the **current month**. The assistant has no idea which month is on screen, but it does know what day it is.
- **Never backdated.** Following YNAB: to reflect the past, record the movements.

The owner chose this over leaving the figure undated, after the behaviour was put to him month by month with the numbers above.

**Alternatives rejected.** (A) **Leave it undated.** What ships today. Correct for the month it is written and progressively wrong in every other, and it is the December row — money asserted before it was ever declared — that decides it. (B) **Let the owner pick any month for the statement.** Maximum flexibility, and it re-opens exactly what YNAB closed: a balance asserted for a month whose movements say otherwise, with no way to reconcile the two. The start month is a date the owner picked for a reason; a second free date is a second thing to get wrong.

**Consequences.**

- **A fund's opening becomes reachable from the app.** Today it is assistant-only, which is a gap the acceptance contract never caught because it allows an AC to be observed at *either* surface.
- **Rolling works from the statement forward.** February shows $700.000 because January's ask rolled in, which is the whole point of an accumulating fund.
- **Months before the statement read zero,** which is what they were.
- **The untested branch gets a behaviour to test.** Mutation left three survivors on the anchor branch — `stated_for > year_month` inverted, and its two return values — because no scenario dates an anchor at all. They stop being a hole once there is a decided behaviour to pin.

**Confirmation.** **Decided, not built.** Live today: `anchor_month` is nullable and `create_fund(opening_balance=…)` already dates its anchor at the start month. Pending: the form field, and dating what `set_fund(balance=…)` receives at the current month. Tracked as roadmap `id:fund-opening-balance`. Until it ships, the December row above is still what the app does.

---

## ADR-042 — A ceiling and a pot get two names; the mechanism stays one

**Status:** accepted (feature 010, 2026-08-07) · **Amends** ADR-037 in vocabulary only — its collapse of mechanisms stands unchanged

**Context.** ADR-037 collapsed envelopes and goals into one noun, the **fund**, and was right to: three tables, a goals screen and a monthly assignment ritual became one record with a rule that computes its own number. The collapse was about mechanisms.

It also produced one word for two behaviours that differ in the only way the owner cares about. A fund carries a rollover flag:

| | spend $60.000 of $100.000 in August | September opens at |
|---|---|---|
| does not accumulate | the $40.000 are not kept | $100.000 |
| accumulates | the $40.000 are kept | $140.000 |

On the screen that choice is a bare checkbox — *"Acumula lo que sobra cada mes"* — with no statement of what it changes next month, and it is unnamed to a screen reader.

On 2026-08-05 the owner asked for a monthly spending ceiling, a savings pot for irregular costs, and month-by-month saving toward an annual subscription. **All three were already built, tested and in production**, and he had commissioned all three. Asking for the first, he produced the missing word himself, unprompted and correctly: *"esos no son fondos sino presupuestos"*.

**Decision.** **Two nouns.**

- A **presupuesto** is a monthly ceiling. What is not spent is not kept.
- A **fondo** carries its leftover money into the next month.

The screen shows them as two labelled groups, creating one starts from which of the two the owner is making, and the rollover checkbox disappears — the entry point decides it. The navigation reads `Fondos y presupuestos`, because the menu is the only place a word is visible without a click.

**Every combination reachable before stays reachable.** The two rules that offer the choice reach both nouns; the two that must carry money forward — reading the owner's recurring charges, and saving toward a date — reach only the fondo.

**ADR-037 is amended, not weakened.** After this there is still one record shape, one screen, one create form, one rule that *is* the monthly number, and zero monthly ritual. What splits is what the owner is told he is making. The failure ADR-037 diagnosed was a ritual nobody performed; the failure this one diagnoses is a capability nobody could find.

**Alternatives rejected.**

- **(A) One noun with the mode written out.** Every entry stays a *fondo* and says in words whether it accumulates and what that means in September. Strictly truthful, strictly cheaper, and it keeps ADR-037's letter as well as its spirit. Rejected because the word the owner reached for is the word that would never appear: he would search the app for *presupuesto* and find nothing, which is the exact failure being fixed.
- **(B) Leave the checkbox and explain it better.** A longer label under the control. Rejected on Nielsen Norman's rule, which the audit applied directly: content whose absence stops the user completing the task must be a label, not help text — and the accumulate choice determines whether the owner picks right or wrong. Explaining a control well does not make it findable by someone who does not know it exists.

**Consequences.**

- **No migration, no schema change, no arithmetic change.** Nothing already created is edited or asked about; each existing entry simply appears under the heading matching what it already does. Feature 010's AC-18 states this and 003's acceptance suite is what proves it.
- **The rollover checkbox and its accessibility defect both disappear** rather than being fixed. The audit's D15 — the control announcing itself as an unnamed checkbox at the most important decision in the form — has no control left to be unnamed.
- **The assistant does not learn the word.** It was excluded from the audit by the owner, so after this the screens say *presupuesto* and the assistant does not know it. Named as a gap, filed for the roadmap, not fixed here.
- **The vocabulary is now load-bearing for anything new.** Feature 009 (named goals) was deliberately sequenced behind this one so it would inherit settled words instead of adding a fourth invisible surface.

**Confirmation.** Decided at feature 010's Checkpoint 2 on 2026-08-07, after the two shapes were put to the owner as behaviour with the September figures above. Not built: it ships with 010.

---

## ADR-043 — There is a second noun after all, and the fund gives up its fourth rule

**Status:** accepted (feature 009, 2026-08-08) · **Supersedes** two clauses of ADR-037: *"there is no separate goals feature"* and its four-rule list · Technical detail in `docs/adr/0046`

**Context.** ADR-037 collapsed envelopes and goals into one noun four days ago, on evidence that was overwhelming: zero envelopes had ever been created, and the one goal in the app read `$0 of $10.000.000` while the account it demanded held `$14.659.572`. Its decision sentence is *"One noun: the fund … A goal is a fund with a target and a date … There is no separate goals feature and no separate envelope."*

Feature 009 was promoted on 2026-08-05 to let the owner save for named things — a phone, a television — several at a time. Its `feature.md` claimed this was compatible with ADR-037 because the rejected alternative (A), *"keep envelopes and add funds beside them"*, concerned two mechanisms **on the same category**, and a meta belongs to none.

**That defence does not survive.** An adversarial review at Checkpoint 3 showed why: ADR-037's *"the same headline"* is the money available, not a per-category figure, and the duplication (A) named is of *mechanism*, not of category. A `target-by-date` fund and a meta are both an amount by a month, asked monthly, subtracted from the same number. Writing that the distinction holds would have been convenient and false.

**Decision.** **Two nouns, and only two.**

- **The fund** is what a category costs: a fixed amount, the average of what it has cost, or what its obligations add up to. Three rules, not four.
- **The meta** is a named thing with an end, belonging to no category: an amount, a month, and a purchase that closes it.

**And saving toward a date is said one way.** The fund's `target-by-date` rule is withdrawn in the same feature that introduces the meta.

Two things decided that, and the second is the one that matters:

1. **The label was already the meta's own words.** The dated rule ships as *"Junto una cantidad para una fecha"*, explained as *"Por ejemplo: $600.000 para febrero. Reparto lo que falta entre los meses que quedan."* It is only visible after pressing `+ Nuevo fondo` — the owner must commit to the noun *fondo* before the evidence appears that he may have wanted the other one. That is the exact failure feature 010 existed to fix, and ADR-042 had just spent a feature making two nouns tellable apart.
2. **The rule has no users and no case left.** Read from production on 2026-08-08, read-only, with the owner's permission: `SELECT rule, COUNT(*) FROM fund` returns **zero rows**. And his only two dated charges — `Seguro del Carro` at $7.000.000 a year and `SOAT carro` at $447.300 a year — are already recurring obligations, which the `from-recurring` rule covers **and renews by itself each cycle**, which `target-by-date` never did.

**What did not change, and is the reason this is not ADR-006 returning.** No savings account, anywhere (product ADR-015 stays dead, Firefly III's coupling stays refused). No monthly ritual: a meta fills itself, and not opening the app for a month still advances it. No proposal to confirm. What the old goal needed a month-end routine and a forced transfer to express, the owner now says once, on the day he buys the thing, by pointing the expense at the meta.

**Alternatives rejected.**

- **(A) Keep both and explain the difference in a panel.** The owner's own first choice, reversed at CP3 when the label above was put in front of him. It is 010's diagnosis — capability built and never announced — applied to a distinction rather than a feature, and there is no evidence a panel fixes what a four-option dropdown breaks.
- **(B) Withdraw `target-by-date` as a later feature.** Also the owner's first sequencing, and defensible while the migration looked expensive. The zero-row count removed the cost, and shipping both for even one release is what makes it a reversal rather than a replacement.
- **(C) Drop the meta and keep the dated fund.** Rejected on the constraint the roadmap item recorded from the start: one fund per category means one dated saving per category, which is YNAB's limit and the reason its users create a category per goal.

**Consequences.**

- **ADR-037's collapse stands where it was right.** One record shape for what a category costs, one screen for it, one form, zero monthly ritual. What is added is a second *kind of thing*, not a second way to do the same thing — which is precisely why the fourth rule cannot survive alongside it.
- **A third word enters the app**, after ADR-042 settled two. *Presupuesto* is a ceiling that resets, *fondo* carries its leftover forward, *meta* is a named thing with an end and no category. The metas screen must say all three (009's AC-30).
- **The month splits into consumo, ahorro and libre.** A presupuesto is consumo, a fondo that accumulates is ahorro, a meta is always ahorro — and a category may be marked as one where spending is saving, because production shows US$2.000 at a time going to `📈 Inversión` and the split would otherwise have reported near-zero saved in the months the owner saves most.
- **A destructive migration on real data**, though nothing is converted. Behind a fresh backup and explicit human authorisation (charter §7, ADR-0030).
- **The assistant reads metas and cannot manage them.** A stated deviation from CHARTER §4 and ADR-001, recorded in `docs/adr/0046` rather than left in a feature folder.


---

## ADR-044 — A meta stops the month after its purchase, and closing it moves no figure

**Status:** accepted (feature 009, 2026-08-09) · Extends ADR-043 and 009's AC-39 · Technical detail in `docs/adr/0046`

**Context.** A fresh agent verified feature 009 against its 45 acceptance criteria and reproduced three wrong figures. One of them was the button the owner presses most often on a meta that worked: `Cerrar`.

Closing archived the meta with no cancellation month, and the month's read path kept an archived meta visible only through that month. So a closed meta vanished from **every** month, past ones included:

```
A. meta abierta, $6.400.000 guardados        disponible 4.680.000   sin cubrir 0
B. celular de $8.000.000 comprado en agosto  disponible 3.400.000   sin cubrir 1.280.000
C. el dueño oprime "Cerrar Celular"          disponible 5.000.000   sin cubrir 0
```

August read as though nothing had happened. That is the exact failure AC-39's own text says it exists to prevent: *"una compra real desaparecería del mes y su plata reaparecería"*. It also emptied the past — a September that reported `lleva 3.200.000 · pide 1.600.000` reported nothing once the meta was closed in December, contradicting AC-27.

**And behind it sat a larger one.** A meta went on asking for its instalment every month after the thing was bought. A $8.000.000 phone bought in October against a meta holding $4.800.000 kept asking $1.600.000 in November and December — saving toward a phone already in the owner's pocket. Closing was the only way to stop it, and closing was what erased the past. The two defects were holding each other up.

**Decision.** **Buying stops the meta; closing only takes it off the screen.**

- A meta **asks nothing from the month after its purchase**, and keeps what it had. The purchase month itself still asks, because what it asks that month is part of what covered the purchase (AC-12).
- **Closing releases nothing and moves no figure.** The meta leaves the metas screen; the month it was bought in goes on reporting the gap the purchase left, forever.
- A closed meta is **not listed among the cancelled ones** and cannot be brought back. Cancelling hands money back and is reversible; closing hands nothing back and is not.

**Alternatives rejected.**

- **(A) Record the month a meta was closed and stop it from there.** The obvious fix, and it needs a new column and a fourth migration on real data while three are already outstanding. It also leaves the underlying defect alive: a meta the owner forgets to close still saves for a thing he owns. Rejected on both counts.
- **(B) Leave a closed meta on the screen forever.** Keeping it inside the arithmetic and inside the list are separate questions, and AC-29 already answers the second: an archived meta is out of the list. The screen's own copy was built for this — a closed meta renders with no badge and no actions.

**Consequences.**

- **No migration.** The behaviour falls out of the purchase the owner already recorded; nothing new is stored.
- **The `Cerrar` button becomes honest.** It says the meta is finished, and finishing changes no number — which is the only reading of AC-39 that does not contradict AC-27.
- **A meta bought before it filled stops asking anyway**, whether or not the owner closes it. The gap between what it held and what the thing cost is charged once, in the month of the purchase, and never again.
