# Quaestor — P3 Temporal engine (sub-project)

**Date:** 2026-06-16
**Depends on:** P0 (exposed via P1/P2)
**Part of:** 2026-06-16-quaestor-general-design.md

## Objective

Give Quaestor its **temporal** dimension: recurring obligations (expenses and income, automatic and manual), one-off future payments, the **"To-pay"** view, and the **month close** (rollover) that materializes whatever falls due each period. P3 implements the `planned` semantics on top of `Transaction.status` (a field defined by P0) and answers the central pain point: *"what do I still have to pay this week?"*.

## Scope

**In:**
- `RecurringItem` and `RecurringOccurrence` models (+ their migrations).
- Services for recurring items, planned/to-pay payments, confirmation, and skipping.
- `close_month(YYYY-MM)`: **atomic and idempotent** rollover with an extensible **hooks** mechanism.
- `planned` → `posted` semantics end-to-end (without touching the balance until confirmation).

**Out:**
- Budgets and goals (P4). P3 only **registers the hook seams** (rollover and post-confirm) so that P4 can hook in `propose_goal_contributions` and `record_confirmed_contribution`.
- Reports and aggregates of pending items in the monthly report (P5 consumes `to_pay`).
- The concrete wiring of tools/endpoints (P1/P2 expose them; here we specify the contract).
- Any change to money/FX/sign/balance rules: P3 **reuses** them from P0/domain, it does not redefine them.

## Contribution to the data model

P3 adds two entities (neither redefines anything from P0):

| Entity | Key fields |
|---|---|
| **RecurringItem** | `name`, `payee`, `type` (expense/income), `mode` (auto/manual), `amount` (default, cents of the original currency), `currency`, `category_id`, `account_id`, **`interval_unit`** (day/week/month/year), **`interval_count`** (≥1), `start_date` (anchor), `end_date?`, `active` |
| **RecurringOccurrence** | `recurring_id`, **`due_date`** (the concrete due date), `status` (posted/planned/skipped), `transaction_id?`, `created_at` |

- **Generic every-N frequency (ADR-020):** the frequency is `interval_count × interval_unit` anchored at `start_date`. Each due date = `start_date + k × interval`, with **end-of-month clamping** for unit `month`/`year` (day 31 → 30/28). It maps monthly=`1 month`, quarterly=`3 month`, every-4-months=`4 month`, semiannual=`6 month`, annual=`12 month`, weekly=`1 week`, biweekly=`2 week`.
- `RecurringOccurrence` is the **idempotency marker**: a **unique** index on `(recurring_id, due_date)` → a single occurrence per recurring item and due date (a sub-monthly recurring item generates several within the month, one per `due_date`).
- P3 puts `Transaction.status` ∈ `{planned, posted}` (a column already created by P0) and `Transaction.recurring_id?` (FK to `RecurringItem`) to real use.
- An occurrence with a `transaction_id` points to the tx that materialized it (auto→`posted`, manual→`planned`). `skipped` has no tx.

## Components

- `services/recurring.py` — creating/listing recurring items, skipping a recurring item, and **`materialize_due(until_date)`** (due-driven: creates the occurrences with `due_date ≤ until_date` that don't yet exist).
- `services/planned.py` — `plan_payment`, `confirm_payment`, `skip_payment`, `to_pay`.
- `services/rollover.py` — `close_month` (close of the **calendar month**: envelope rollover + hooks) + the **rollover hook registry**.
- `domain/rules.py` (extension) — `due_dates(item, since, until)` (generates the recurring item's `due_date`s in the window `[since, until]` by interval `interval_count × interval_unit` from `start_date`, respecting `end_date` and with **end-of-month clamping** for unit month/year).
- Everything writes via the P0 session/transaction; no money logic is duplicated (amounts in cents, `to_base` COP, sign by `type`, balance only on `posted`).

## Public interface (services)

Signatures (relevant params; they return the created/affected object or the requested view):

- `create_recurring(name, payee, type, mode, amount, currency, category_id, account_id, interval_unit, interval_count, start_date, end_date=None) -> RecurringItem` — generic every-N frequency (ADR-020).
- `list_recurring(active=None) -> list[RecurringItem]`
- `materialize_due(until_date, session) -> list[RecurringOccurrence]` — **due-driven** (run by the daily scheduler, P7): for each active recurring item it creates the occurrences with `due_date ≤ until_date` that don't yet exist (`auto`→tx `posted` on its date and balance; `manual`→tx `planned`, without balance). Idempotent by `(recurring_id, due_date)`. **Not a user tool.**
- `plan_payment(payee, amount, currency, due_date, account_id, category_id, notes=None) -> Transaction` — creates a standalone **`planned`** tx (without `recurring_id`). Does not affect the balance.
- `confirm_payment(tx_id, amount=None, date=None) -> Transaction` — `planned` → `posted`; applies the real amount/date if provided, recomputes `to_base`, updates the account balance. If the tx comes from a **manual occurrence**, it syncs that occurrence to `status=posted`.
  - **Planned transfer:** if the tx is `type=transfer`, instead of posting a single side it **materializes the real transfer** via P0's `transfer` (a posted pair, atomic) into the destination account. A generic capability (not specific to goals).
  - At the end it fires the **post-confirm hooks** (seam below) in the same transaction — this is how P4 records the `GoalContribution` when the tx carries a `goal_id`, without P3 knowing anything about goals.
- `skip_payment(tx_id) -> Transaction` — marks a standalone `planned` tx as skipped (canceled); if it comes from an occurrence, the occurrence becomes `skipped`.
- `skip_recurring(recurring_id, due_date) -> RecurringOccurrence` — creates/marks the occurrence for that due date as `skipped` (`materialize_due` won't touch it again). Skips **a single occurrence** (not the whole recurring item; for that, use `active=False`).
- `to_pay(since, until) -> {items: list[Transaction], total_base: int}` — all `planned` txs due within the window `[since, until]`, ordered by date, + the total in `to_base` COP. It is the **single confirmation queue** (ADR-007): it includes manual recurring items, standalone payments (`plan_payment`), and proposed goal contributions (P4) — all three are `planned` txs, with no special branches.

`close_month` and the hook registry are specified below.

## Key logic and rules

### Firm rules (inherited, not re-litigated)
- Only `posted` affects the balance and reports. `planned` lives **only** in `to_pay` (and, via P5, in the report as an alert).
- **`confirm_payment` is the only `planned` → `posted` transition.** Nothing else moves that state forward.
- `plan_payment` and the manual arm of the rollover create `planned` txs **without touching the balance**.
- Rollover is **atomic** (commit/rollback) and **idempotent**.

**Two clocks (ADR-020/022).** The engine separates what runs **by date** from what runs **by calendar month**: the **materialization of recurring items** is daily and due-driven (it supports any interval); the **budget/goals close** is monthly. Both are run by P7's `scheduler` (P3 is not a user tool in either case).

### Materialization of recurring items — `materialize_due(until_date)`, due-driven (ADR-020)
**Automatic trigger:** the `scheduler` runs it **daily** with `until_date=today`. It materializes by **date**, not by month → a sub-monthly item (weekly, biweekly) generates several occurrences within the month, one per `due_date`.

1. For each `RecurringItem` with `active=True`, it generates the `due_date ≤ until_date` values not yet materialized via `due_dates(item, ...)` (interval `interval_count × interval_unit` from `start_date`, end-of-month clamping, respecting `end_date`).
2. For each `due_date` **that does not yet have a `RecurringOccurrence`**:
   - `mode=auto` → creates a **`posted`** tx on that `due_date` with the default `amount` (sign by `type`, frozen `to_base`), updates the balance; linked occurrence `status=posted`. (It posts on each real date, **not the whole month in advance** → the balance doesn't front-run expenses.)
   - `mode=manual` → creates a **`planned`** tx that falls due on `due_date`, **without touching the balance**; linked occurrence `status=planned` (it shows up in `to_pay`).
3. If an occurrence already exists (any status) for `(recurring_id, due_date)` → **it is skipped**.

**Idempotency** via the unique `(recurring_id, due_date)`: a missed day self-heals on the next run; re-running is a no-op for dates already materialized.

### Monthly close — `close_month(YYYY-MM)`, idempotent with hooks (ADR-017/022)
**Automatic trigger:** the `scheduler` runs `ensure_month_closed(current_month)` daily — on the 1st it closes the **calendar month**, on other days it's a no-op, a missed day self-heals. Idempotency is a robustness requirement, not just a correctness one.

`close_month` covers what is genuinely **monthly** (**no longer** the materialization of recurring items, which is daily by date): the **envelope rollover** and the **proposal of goal contributions**. It doesn't hardcode the steps: it runs a **registered list of rollover hooks** in **a single transaction**; if any step fails, a full rollback.

```
ROLLOVER_HOOKS: list[Callable[[period, session], None]] = []

def register_rollover_hook(fn): ROLLOVER_HOOKS.append(fn)

def close_month(period):
    with session.begin():            # atomic
        for hook in ROLLOVER_HOOKS:  # registration order
            hook(period, session)
```

**Registered hooks (all from P4):** `propose_goal_contributions` (creates the month's `planned` contributions, ADR-006) and, optionally, the snapshot of the envelopes' `rollover_in`. Each hook is idempotent by its own key `(…, period)` (the proposal / snapshot for the period already exists → it is skipped). Re-running `close_month` does not duplicate.

### Seam with P4 (rollover hooks) — explicit
The monthly close must **propose goal contributions**, but **goals are defined by P4** and the build order is **P3 → P4**. To avoid coupling P3 to a model that doesn't exist yet, `close_month` is designed as an **extensible list of hooks** (the materialization of recurring items does **not** go through here: it's the daily, by-date `materialize_due`):

- **P3** registers no hook of its own in `close_month` (its temporal work lives in `materialize_due`). It leaves the seam ready and empty.
- **P4**, once it exists, will register `propose_goal_contributions` via `register_rollover_hook(...)` **without modifying `close_month`**. A **flexible** contribution (ADR-006): that hook **does not move money**; for each active `Goal` it creates a **`planned`** tx (a proposed contribution to the savings account, due at the end of the period) that lands in "To-pay". The `GoalContribution` is recorded on **confirmation** (see the post-confirm seam), not here. Idempotency: P4 defines it (one `planned` proposal per `(goal_id, period)`).
- Seam contract: each hook is `(period, session) -> None`, runs inside the same close transaction, must be **idempotent on its own**, and a failure in any hook aborts the entire close.

This leaves P3 closed and testable without P4, and lets P4 hook in by composition.

### Post-confirm seam (so P4 can record the `GoalContribution`)
A proposed goal contribution is a `planned` tx that goes through the **same "To-pay" queue** as everything else (ADR-007). When it's confirmed, in addition to becoming `posted` (an internal transfer to the savings account), P4 needs to record the `GoalContribution`. So that **P3 knows nothing about goals**, `confirm_payment` exposes a **post-confirm hook** symmetric to the rollover one:

```
POST_CONFIRM_HOOKS: list[Callable[[tx, session], None]] = []
def register_post_confirm_hook(fn): POST_CONFIRM_HOOKS.append(fn)
# inside confirm_payment, after posted, in the same transaction:
for hook in POST_CONFIRM_HOOKS: hook(tx, session)
```

- **P4** registers a hook that, if the confirmed tx carries a `goal_id` (an FK that P4 adds via migration), creates the `GoalContribution(source=confirmed, amount=tx.amount, transaction_id=tx.id)`.
- The hook runs **inside the transaction** of `confirm_payment`; if it fails, the whole confirmation rolls back. P3 ignores what the hook does.
- For a `planned` tx without a `goal_id` (a standalone payment, a manual recurring item), no hook applies → behavior identical to the current one.

## Errors

Typed `domain` errors, mapped by P1 to 4xx and by P2 to structured text:
- `ValidationError` — `interval_count < 1`, invalid `interval_unit`, `end_date < start_date`, `amount ≤ 0`, invalid `currency`/`type`/`mode`, an inverted `to_pay` window.
- `NotFound` — nonexistent `recurring_id` / `tx_id`.
- `IllegalTransition` — `confirm_payment`/`skip_payment` on a tx that is not in `planned`.
- `MissingRate` (from P0) — `confirm_payment`/rollover of a foreign-currency tx with no FX rate for the date; the rollover does a full rollback.

## Testing and "done" criteria

`pytest` over `services` + `domain` with SQLite in-memory:
- **Generic frequency + dates (ADR-020):** `due_dates` generates the correct `due_date`s for monthly, biweekly (`2 week`), every-3-months, annual…; **end-of-month clamping** (a day-31 recurring item → 30/28). `materialize_due(today)` creates one occurrence per `due_date ≤ today`; a sub-monthly item generates **several** within the month.
- **Idempotency (due-driven):** a repeated `materialize_due` does not duplicate occurrences or txs (unique `(recurring_id, due_date)`); a "missed day" is materialized on the next run. `close_month(M)` two/three times does not duplicate proposed contributions; balances equal after the 2nd run.
- **Auto vs manual:** auto leaves a `posted` tx **on its `due_date`** and moves the balance (it doesn't post the whole month in advance); manual leaves a `planned` tx, a `planned` occurrence, **balance unchanged**.
- **`planned` does not affect the balance:** `plan_payment` and manual do not alter `Account.balance` or aggregates.
- **`to_pay` by window:** returns only the `planned` txs within `[since, until]`, ordered, with a correct `total_base`; it excludes `posted` and `skipped`.
- **`confirm_payment` with an adjusted amount:** `planned` → `posted` with the real amount/date, `to_base` recomputed, balance moved; if it came from a manual occurrence, the occurrence becomes `posted`.
- **Skipping:** `skip_recurring` leaves the occurrence for that `due_date` as `skipped` and `materialize_due` respects it (does not recreate it); `skip_payment` cancels the standalone tx.
- **Atomicity:** a failure midway through the rollover (e.g. `MissingRate`) reverts everything.
- **Seam:** a test hook registered via `register_rollover_hook` runs inside the same transaction and a failure of its own aborts the close.

**Done when** all the tests above pass green, the unique constraint `(recurring_id, due_date)` is applied, and the user **MCP tools** exist (`create_recurring`, `list_recurring`, `plan_payment`, `confirm_payment`, `skip_payment`, `skip_recurring`, `to_pay`) along with the corresponding **REST endpoints**. **`materialize_due` and `close_month` are NOT user tools** (ADR-017/020): they are invoked by P7's `scheduler` (daily); they remain services (+ an optional internal `/rollover` endpoint for admin/debug). The **concrete wiring** is done by P2 (`/recurring`, `/planned`) and P1 on top of these services, with no duplicated logic.

## Integration with other sub-projects

- **P0 (depends on):** consumes models/db/session, the money/FX/sign rules, `Transaction.status` and `Transaction.recurring_id`. It does not redefine anything from P0.
- **P1 (HTTP API):** exposes the `/recurring`, `/planned`, `/rollover` routers as a mirror of these services; maps typed errors to 4xx.
- **P2 (MCP):** exposes one tool per user-facing service (the same verbs in natural language: *"what do I still have to pay this week?"* → `to_pay`; *"confirm the electricity payment"* → `confirm_payment`). `close_month` is not exposed (the scheduler runs it, ADR-017).
- **P4 (Budgets + Goals):** hooks in via **two seams** without touching P3: into the **rollover hook** with `propose_goal_contributions` (creates `planned` contributions, doesn't move money) and into the **post-confirm hook** of `confirm_payment` (records the `GoalContribution` on confirmation). P4 adds `goal_id` to `Transaction` via its own migration. Build order P3 → P4. P4's `safe_to_spend` **consumes the month's obligations** that P3 exposes (`to_pay` / `planned` + recurring items) to compute "committed".
- **P5 (Reports + Importer):** consumes `to_pay` for the "recurring items / pending payments" line and the alert for unconfirmed manuals in the monthly report.
