# Quaestor — P4 Budgets + Goals (sub-project)

**Date:** 2026-06-16
**Depends on:** **P0** (domain/money/FX, db, `transfer`, transactions) and **P3** (rollover and post-confirm seams of `close_month`/`confirm_payment`; `to_pay` for the safe-to-spend "committed" amount).
**Exposed via:** **P1** (REST routers) and **P2** (MCP tools) — those sub-projects wire up the services defined here.
**Part of:** `2026-06-16-quaestor-general-design.md` (general design). Inherits its conventions (see §5 model, §6 goals/budget, §11).

---

## Objective

Give Quaestor the planning capabilities that are **the product differentiator** versus Lunch Money (ADR-001/002):

1. **Hybrid budget** (ADR-002/003): **per-category envelopes with rollover** (what you don't spend carries over) + a global **safe-to-spend** = money you haven't yet assigned to any envelope. The safe-to-spend integrates recurring items + planned + goals — something LM structurally doesn't do.
2. **Savings goals** with a **fixed monthly amount**, in two flavors: **defined** (with `target`+`deadline` → ETA and on-track/behind) and **open-ended** (just accumulates). **Flexible** contribution (ADR-006): the rollover **proposes** it, you confirm it in "To pay".

The budget is **read/compute logic** over real transactions; it doesn't invent money. Goal contributions are internal transfers into the savings account, **triggered by confirmation** (not automatic): P4 proposes them via P3's rollover hook and records them via P3's post-confirm hook.

---

## Scope

**In:**
- `Budget` model (with rollover semantics), `Goal`, `GoalContribution` (+ migration). Migration that adds `goal_id?` to `Transaction`.
- Budget services: `set_budget`, `budget_status` (envelope status with rollover), **`safe_to_spend`** (global number).
- Goal services: `create_goal`, `goal_contribution` (standalone manual contribution), `goals_progress`.
- **Defined** goal computation (monthly required, on-track/behind, ETA) and **open-ended** (accumulated total only).
- The rollover hook **`propose_goal_contributions(period)`** (creates `planned` contributions, doesn't transfer) and the **post-confirm** hook that records the `GoalContribution` on confirmation — both registered in P3's seams.

**Out:**
- Goals as a % of income (out of v1, see general §1).
- Recurring items and `planned`/To-pay (that's P3; P4 **consumes** them for "committed" and proposes contributions on top of that queue).
- Reports and their markdown (P5 consumes `budget_status`, `safe_to_spend`, and `goals_progress`).
- Concrete endpoints/tools: P4 defines the signatures; P1/P2 expose them.

---

## Contribution to the data model

P4 adds three entities (the rest already exist in P0/P3). Its own migration; it doesn't redefine anything external.

| Entity | Key fields |
|---|---|
| **Budget** (envelope) | `category_id` (FK Category), `year_month` (TEXT `YYYY-MM`), `amount_assigned` (COP cents, int ≥ 0 — what you assign to the envelope that month). Unique per `(category_id, year_month)`. **rollover_in is derived** (positive balance of the previous month), not stored; optionally `close_month` snapshots it for performance. |
| **Goal** | `name`, `target_amount?` (COP cents, nullable), `deadline?` (date, nullable), `monthly_amount` (COP cents, int > 0, **fixed**), `savings_account_id` (FK Account, `type=savings`), `status` ∈ `active`/`reached`/`paused`. |
| **GoalContribution** | `goal_id` (FK Goal), `date`, `amount` (COP cents), `source` ∈ `confirmed`/`manual` (`confirmed` = contribution proposed by rollover and confirmed in To-pay; `manual` = standalone contribution), `transaction_id?` (FK Transaction — the transfer that backs the contribution; nullable only for historical contributions without a tx). |
| **Transaction.goal_id?** | column that **P4 adds by migration** to P0's `Transaction` table: links a `planned` tx (proposed contribution) to its `Goal`. On confirmation, P3's post-confirm hook reads `goal_id` and creates the `GoalContribution`. |

**Invariants:**
- A `Goal` is **defined** iff it has `target_amount` **and** `deadline`; it is **open-ended** iff it has neither. Having only one → `ValidationError` on creation.
- `monthly_amount > 0` always (both types).
- `savings_account_id` must point to an `Account` with `type=savings` and not `archived`.
- Amounts in COP cents (contributions are already base currency; goals don't handle FX).

---

## Components

- `domain/rules.py` (extends): **pure** computation functions — `envelope_status_calc(...)` (assigned + rollover_in − spent), `safe_to_spend_calc(...)` (cascade), `goal_progress_calc(...)`. They receive already-queried data, don't touch the DB. This is where the math lives for rollover, % used, monthly required, ETA, on-track, and the safe-to-spend cascade.
- `services/budgets.py`: `set_budget`, `budget_status` (envelope status with rollover), **`safe_to_spend`** (queries income forecast + committed via P3 + assignments, delegates the cascade to `rules`).
- `services/goals.py`: `create_goal`, `goal_contribution` (standalone), `goals_progress`, the rollover hook **`propose_goal_contributions`** and the **post-confirm** hook `record_confirmed_contribution`.
- `domain/models.py` (extends): `Budget`, `Goal`, `GoalContribution` + the `goal_id?` column on `Transaction`.
- Migration: creates the three tables + indexes (`Budget(category_id, year_month)` unique; `GoalContribution(goal_id, date)`) and **adds `goal_id?` to `Transaction`**.
- **Seam registration** (in P4's bootstrap): `register_rollover_hook(propose_goal_contributions)` and `register_post_confirm_hook(record_confirmed_contribution)`.

`propose_goal_contributions` **creates `planned` txs** (with `goal_id`), doesn't transfer. `record_confirmed_contribution` fires when that tx is confirmed (already `posted`, internal transfer done by `confirm_payment`) and only **records the `GoalContribution`**. No step writes transfer transactions by hand outside P0/P3's `confirm_payment`/`transfer`.

---

## Public interface

`services` signatures (what P1/P2/P5 consume). Amounts in COP cents.

```python
# budgets.py
def set_budget(session, category_id: int, year_month: str, amount_assigned: int) -> Budget:
    """Assigns (upserts) a category's envelope for a month."""

def budget_status(session, category_id: int, year_month: str) -> BudgetStatus:
    """Envelope status with rollover: assigned, rollover_in, spent, available, pct_used, status."""

def safe_to_spend(session, year_month: str) -> SafeToSpend:
    """Headline number (cascade) + breakdown: income forecast, committed, assigned, free."""

# goals.py
def create_goal(session, name: str, monthly_amount: int, savings_account_id: int,
                target_amount: int | None = None, deadline: date | None = None) -> Goal:
    """Defined if target+deadline; open-ended if neither; error if only one."""

def goal_contribution(session, goal_id: int, amount: int, date: date) -> GoalContribution:
    """Standalone manual contribution (source=manual) + internal transfer to the savings account. Atomic."""

def goals_progress(session, goal_ids: list[int] | None = None) -> list[GoalProgress]:
    """Status of each goal (all active ones if goal_ids=None)."""

# hooks registered in P3's seams (not called directly from P1/P2):
def propose_goal_contributions(period: str, session) -> list[Transaction]:
    """Rollover hook: for each active Goal creates a `planned` tx (proposed contribution). Idempotent."""

def record_confirmed_contribution(tx, session) -> GoalContribution | None:
    """Post-confirm hook: if tx.goal_id, records GoalContribution(source=confirmed). Otherwise no-op."""
```

**Output DTOs** (dataclasses/Pydantic, not DB models):

```python
BudgetStatus  = {category_id, year_month, assigned, rollover_in, spent, available, pct_used, status}
SafeToSpend   = {year_month, income_forecast, committed, assigned_envelopes, free, committed_breakdown[]}
GoalProgress  = {goal_id, name, type("defined"|"open-ended"), monthly_amount, saved,
                 # defined only:
                 target_amount?, deadline?, monthly_required?, on_track?, eta?, remaining?}
```

---

## Key logic and rules

### Hybrid budget (ADR-002/003/005)

**Per-category envelope (with rollover).**
- `spent = Σ to_base(tx)` over transactions with `type=expense`, `status=posted`, the given `category_id`, `date` within `year_month`, across **all accounts including the credit card** (on an accrual basis, on the purchase date — ADR-021). The statement payment is `type=transfer`, already excluded from spending, so it isn't counted twice.
- **Respects Category flags:** if the category has `exclude_from_budget` **or** `exclude_from_totals`, its spending is **not** aggregated → it isn't budgeted (informational, not blocked).
- `rollover_in(cat, month) = max(available(cat, month−1), 0)` — what wasn't spent last month carries over; an overspent envelope is absorbed into the global pool and **resets to 0** (ADR-005), it doesn't carry a negative.
- `available = rollover_in + amount_assigned − spent`.
- `pct_used = round(spent / (rollover_in + amount_assigned) * 100)` (0 if the denominator is 0).
- `status = "over"` if `spent > rollover_in + amount_assigned`, otherwise `"under"`.
- Always in `to_base` (COP), never the original currency.

**Global safe-to-spend (cascade, ADR-003/005/014/016).** Envelopes are **optional** (A4): only some categories carry an envelope; the rest spend directly from the pool.
```
safe_to_spend(month) = income_forecast(month)
                     − committed(month)
                     − Σ amount_assigned(month)        # categories WITH an envelope
                     − Σ unbudgeted_spending(month)     # posted spending in categories WITHOUT an envelope
                     − Σ overspend(month)               # per envelope: max(spent − (assigned + rollover_in), 0)
```
- `income_forecast(month)` = sum of the `RecurringItem`s of `type=income` whose due dates **fall in the month** (ADR-004/A2); **no typed override**. Atypical income (a bonus) is recorded standalone and counts when posted.
- `committed(month)` = the month's obligations **counted exactly once** (ADR-014): recurring items that **come due in the month** + the month's `planned` txs (standalone payments, proposed goal contributions). **Projected, not read from materialized occurrences (ADR-020):** since recurring items are materialized **due-driven** (only those due as of today exist as an occurrence), `committed` projects the full month's calendar via P3's `due_dates` → the safe-to-spend is **stable all month long**, it doesn't rise each day just because what's left hasn't yet been materialized. An obligation is counted once regardless of its state (not materialized / `planned` / `posted`): when it materializes or posts, the safe-to-spend **doesn't move**.
- `Σ amount_assigned` = what's assigned to envelopes this month (the money is already "claimed" whether spending exists or not).
- `Σ unbudgeted_spending` = `posted` spending in categories **without an envelope** (from **all accounts incl. the card**, discounting transfers and `exclude_*`). Without this, the pool would overstate the free money (A4).
- `Σ overspend` = what was overspent in an envelope above `assigned + rollover_in` (ADR-005). The `rollover_in` (money from previous months) **doesn't** add to this month's pool and **protects** against false overspend.
- The rollover × overspend × unbudgeted interactions are **pinned by the tests** (below).

### Goals (fixed amount)
- **Open-ended:** `saved = Σ GoalContribution.amount`. No `monthly_required`, no `eta`, no `on_track`. Accumulated total only.
- **Defined:**
  - `remaining = max(target_amount − saved, 0)`.
  - `months_left = # of calendar months from the current month to the deadline month` (≥ 1; if the deadline has already passed → 1 to avoid dividing by zero).
  - `monthly_required = ceil(remaining / months_left)`.
  - `on_track = (monthly_amount >= monthly_required)`. If `False` → "behind".
  - `eta` = at the current pace (`monthly_amount`): `ceil(remaining / monthly_amount)` months → projected date; if `remaining=0` the goal is reached (ETA = today).
  - If `saved >= target_amount` → the goal moves to `status=reached` (it's marked in `goals_progress`; the persistent status change happens when detected during a contribution/rollover).

### Goal contribution = internal transfer, **flexible** (ADR-006/007)
The monthly contribution **is not automatic**. The cycle is **propose → you confirm**, reusing the "To pay" queue and P3's seams:

1. **Propose (rollover).** `propose_goal_contributions(period, session)` —the rollover hook— for each `active` `Goal` creates a **`planned`** tx (`type=transfer`, `goal_id` set, **origin `Settings.default_source_account_id`** (ADR-015), destination `savings_account_id`, `amount=monthly_amount`, due at end of period). It **doesn't move money** (P3's `planned` rule). It lands in "To pay".
2. **Confirm.** The user confirms via `confirm_payment` (P3). Since the tx is a `planned` `type=transfer`, `confirm_payment` **doesn't post a single side**: it materializes the **real internal transfer** via P0's `transfer` (an atomic posted pair) into `savings_account_id`. The **post-confirm hook** (`record_confirmed_contribution`, from P4) then records the `GoalContribution(source=confirmed, amount, transaction_id=transfer)`. If the month came up tight, the user confirms with a smaller `amount` or **skips** (`skip_payment`).
3. **Standalone manual contribution.** `goal_contribution(goal_id, amount, date)` directly creates `GoalContribution(source=manual)` + a transfer, without going through the queue (for extra contributions outside the regular pace).

- The contribution (internal transfer) **is neither expense nor income** → out of all totals/reports (general §5).
- **Atomic:** the transfer + `GoalContribution` are created together or not at all (atomicity is guaranteed by the `confirm_payment` / `goal_contribution` transaction).
- **Proposal idempotency:** `propose_goal_contributions` doesn't create a second `planned` proposal if one already exists for `(goal_id, period)`. Re-running `close_month` doesn't duplicate proposals. `paused`/`reached` goals are skipped.
- After a confirmed contribution, if a defined goal reaches its `target` → `status=reached`.

> **P3↔P4 integration note:** that `confirm_payment` materializes a `planned` `type=transfer` as a real transfer is a **generic P3 capability** (not goal-specific): P3 supports planned transfers and delegates the monetary effect; P4 only supplies the `goal_id` and the hook that records the `GoalContribution`. P3 still **knows nothing about what a goal is**.

---

## Errors

Typed `domain` errors (general §11). API (P1) → 4xx; MCP (P2) → structured text.

- `ValidationError`: `monthly_amount <= 0`; goal with only `target` or only `deadline`; `amount_assigned < 0`; malformed `year_month` (not `YYYY-MM`).
- `ValidationError`: `savings_account_id` doesn't exist, isn't `type=savings`, or is `archived`.
- `NotFound`: nonexistent `category_id` / `goal_id`.
- Confirmed / standalone contributions are **atomic**: if the transfer fails (invalid account per P0), the `GoalContribution` is rolled back (rollback inside `confirm_payment` / `goal_contribution`).
- Proposing contributions during rollover **doesn't move money** → it can't fail for lack of funds; it only creates `planned`. It fails only on invalid data (archived savings account, etc.) and aborts the close (atomicity of `close_month`, P3).
- `MissingRate` doesn't apply: contributions and budgets are COP base, no FX.

---

## Testing and "done" criteria

`pytest` over `domain` + `services` with in-memory SQLite (general §11). **Done** when these pass:

- **`budget_status` (envelope with rollover):** sums only `expense`+`posted` for the month/category; ignores `planned`, transfers, other months/categories; **respects `exclude_from_budget`/`exclude_from_totals`**; `rollover_in = max(available previous month, 0)` (positive carries over, negative resets, ADR-005); `available`, `pct_used`, `over`/`under` correct; a 0 denominator doesn't divide by zero.
- **`safe_to_spend` (cascade):** `free = income_forecast − committed − assigned − unbudgeted_spending − overspend`; income = sum of the month's `income` recurring items (no override, A2). **Optional envelopes (A4):** spending in a category **without an envelope** reduces the pool; spending in a category **with an envelope** is already claimed by the assignment (doesn't subtract twice). **Double-count guard (ADR-014):** an obligation counted exactly once whether not-materialized, `planned`, or `posted` → confirming a `planned` (or posting an auto recurring item) **doesn't change** the safe-to-spend. **Due-driven stability (ADR-020):** `committed` projects the month's calendar (via `due_dates`), so the safe-to-spend on day 5 and day 25 of the same month match even though recurring items remain to be materialized. **Overspend (ADR-005):** `max(spent−(assigned+rollover_in),0)` reduces the pool; `rollover_in` protects against false overspend.
- **Defined goal:** `monthly_required = ceil(remaining/months_left)`; `on_track` true/false per `monthly_amount` vs required; `eta` projected at the current pace; a past deadline doesn't break it; `saved >= target` → `reached`.
- **Open-ended goal:** only `saved` accumulated; no `monthly_required`/`eta`/`on_track`.
- **`goal_contribution` (standalone):** creates `GoalContribution(source=manual)` + an internal transfer; doesn't appear as expense/income; atomic.
- **Propose + confirm (flexible, ADR-006):** `propose_goal_contributions(period)` creates for each active goal a **`planned`** tx (`goal_id`, `monthly_amount`, savings destination), **without moving any balance**; skips `paused`/`reached`; **idempotent** (re-running doesn't duplicate the proposal). On **confirming** that tx: the real transfer is materialized and the post-confirm hook records `GoalContribution(source=confirmed)`; confirming with a smaller amount adjusts the contribution; **skipping** contributes nothing. After confirming, a defined goal that reaches target → `reached`.
- **Wire:** P1 exposes the services at `/budgets` (incl. `/budgets/safe-to-spend`) and `/goals`; P2 exposes them as MCP tools (incl. "how much do I have free?"). (Wiring verification lives in P1/P2; P4 delivers stable services.)

---

## Integration with other sub-projects

- **P0 (Core):** consumes `transfer` (contributions = internal transfers), the `Transaction`/`Account`/`Category` model, `to_base`, and the atomic pattern. Doesn't reimplement transfers. Adds `goal_id?` to `Transaction` by migration.
- **P3 (Temporal engine):** P4 hooks in through **two seams** without touching `close_month`/`confirm_payment`: it registers `propose_goal_contributions` in the rollover hook (creates `planned` contributions) and `record_confirmed_contribution` in the post-confirm hook (records `GoalContribution`). It also **consumes** the month's obligations (`to_pay`/planned + recurring items) for the `safe_to_spend` "committed". Proposal idempotency per `(goal_id, period)`.
- **P1 (HTTP API):** `/budgets` routers (`set_budget`, `budget_status`, **`safe_to_spend`** at `/budgets/safe-to-spend`) and `/goals` (`create_goal`, `goal_contribution`, `goals_progress`) on top of these services.
- **P2 (MCP):** mirror tools (same verbs) so the agent can set a budget, check status, create a goal, contribute, and ask about progress in natural language.
- **P5 (Reports):** consumes `budget_status` (envelopes with rollover), **`safe_to_spend`** (in the report it goes **at the foot as a closing line, not in the header** — ADR-019) and `goals_progress` (accumulated + ETA of defined goals) for the monthly report. P4 doesn't generate markdown.
- **P6 (Frontend):** the v1 dashboard (general §8, ADR-008) shows `safe_to_spend` + the "To pay" widget; the `/budgets` and `/goals` routes stay in the backlog and hit P1's endpoints once they land.
