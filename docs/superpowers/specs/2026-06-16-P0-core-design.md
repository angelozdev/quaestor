# Quaestor — P0 Core (sub-project)

**Date:** 2026-06-16
**Depends on:** —
**Part of:** `2026-06-16-quaestor-general-design.md`

---

## Objective

Deliver the backend **foundation**: the persisted data model, money/FX arithmetic, balance rules, and the **base services** to operate accounts, categories, tags, rates, and transactions (expense/income/transfer). Boundary: **no HTTP, no MCP, no UI** and no temporal logic (recurring items, rollover, budgets, goals). Everything is callable and testable from pure code.

## Scope

**In:**
- `domain/models.py`: Account, Category, Transaction, Tag, TransactionTag, FxRate, Settings.
- `domain/money.py`: the `Money` type, per-currency scale, FX conversion, display formatting.
- `domain/rules.py`: incremental balance update on `posted` transactions.
- `db.py`: SQLite engine, session, migration strategy.
- Services: `transactions.py`, `accounts.py`, `categories.py`, `tags.py`, `fx.py` + reads.

**Out:**
- RecurringItem, RecurringOccurrence, Budget, Goal, GoalContribution (created by **P3/P4**).
- Full semantics of `planned` / "to-pay" and `close_month` (**P3**).
- REST API (**P1**), MCP tools (**P2**), reports/importer (**P5**), frontend (**P6**).

## Contribution to the data model

P0 creates **only** these entities (the rest live in §5 of the general design, added by other sub-projects):

| Entity | Key fields |
|---|---|
| **Account** | `name`, `type` (debit/credit/cash/savings), `currency`, `balance` (cents), `archived`. **Credit card** (`type=credit`): a normal account with a negative balance = debt; the statement payment is a `transfer` (debit → card), not an expense (ADR-021) |
| **CategoryGroup** | `name`, `sort_order`, `archived` — container of categories; its own entity (ADR-023) |
| **Category** | `name`, `group_id?` (FK CategoryGroup), `is_income`, `exclude_from_budget`, `exclude_from_totals`, `archived` |
| **Transaction** | `date`, `payee`, `notes`, `type` (expense/income/transfer), `status` (planned/posted), `amount` (cents, original currency), `currency`, `fx_rate`, `to_base` (cents COP), `account_id`, `category_id?`, `transfer_group_id?`, `source` (manual/agent/import), `created_at` |
| **Tag** + **TransactionTag** | `name`; m2m relationship |
| **FxRate** | `date`, `usd_cop` (rate); unique per date |
| **Settings** | `base_currency=COP`, `default_source_account_id?` (FK Account, the global source account for goal contributions — used by P4, ADR-015), app config (singleton row) |

> P0 includes the `status` and `transfer_group_id` fields on Transaction, but only exercises `status=posted` and the transfer pairs. The advanced semantics of `planned` (due dates, confirmation) are landed by P3 without redefining the model.

## Components

- `src/quaestor/domain/models.py` — SQLModel tables + enums (`AccountType`, `CategoryKind`, `TxType`, `TxStatus`, `Source`).
- `src/quaestor/domain/money.py` — `Money`, scales, `to_base`, formatting.
- `src/quaestor/domain/rules.py` — `apply_to_balance`, `delta_balance`, sign by type.
- `src/quaestor/db.py` — `engine`, `get_session`, `init_db`, atomic transaction.
- `src/quaestor/services/{accounts,categories,tags,fx,transactions}.py` — use cases + reads.
- `tests/` — pytest over domain + services with in-memory SQLite.

## Public interface (services)

```python
# accounts.py
create_account(name, type, currency, balance=0) -> Account
list_accounts(include_archived=False) -> list[Account]
get_account(account_id) -> Account
archive_account(account_id) -> Account

# categories.py
create_group(name, sort_order=0) -> CategoryGroup            # group entity (ADR-023)
list_groups(include_archived=False) -> list[CategoryGroup]
create_category(name, group_id=None, is_income=False, **flags) -> Category
list_categories(include_archived=False) -> list[Category]

# tags.py
create_tag(name) -> Tag
list_tags() -> list[Tag]
tag(tx_id, tags: list[str]) -> Transaction   # creates missing tags (upsert)

# fx.py
set_fx_rate(date, usd_cop) -> FxRate               # upsert by date
current_rate(date) -> Decimal                       # latest <= date; MissingRate if none

# transactions.py
record_expense(account_id, amount, currency, date, payee, category_id=None,
               notes=None, source="manual", fx_rate=None) -> Transaction
record_income(account_id, amount, currency, date, payee, category_id=None,
              notes=None, source="manual", fx_rate=None) -> Transaction
transfer(from_account_id, to_account_id, amount, currency, date,
         notes=None, source="manual", fx_rate=None) -> tuple[Transaction, Transaction]
list_transactions(filters...) -> list[Transaction]   # account/category/tag/type/status/range
get_transaction(tx_id) -> Transaction
```

Every write is **atomic** (commit/rollback). Services never expose the session; they receive/open their own unit of work.

## Key logic and rules

- **Money = integer in cents**, never float. `Money` wraps `(cents: int, currency)` and knows the per-currency scale (COP and USD use 2 decimals → scale 100).
- **Sign by `type`, not in the amount.** `amount` is **always stored positive**; the service applies the sign: `expense` subtracts, `income` adds. `delta_balance` in `rules.py` centralizes this.
- **Frozen FX.** If `currency != base (COP)`: `fx_rate` = the one passed in or `current_rate(date)`; `to_base = amount × fx_rate` is computed and **stored fixed** at record time. Transactions in COP → `fx_rate=1`, `to_base=amount`. Changing the rate later does not alter transactions already stored. The `FxRate` table is **populated by a daily job** (P7, ADR-011) calling `set_fx_rate`; this service also remains available as a **manual override**. `current_rate` does not change: it reads the latest ≤ date.
- **Incremental balance only on `posted`.** When recording a `posted` transaction, the service adjusts `Account.balance` with `delta_balance` (in the account's currency). `planned` transactions **do not touch the balance**. The balance is not recomputed from scratch.
- **Transfer = atomic pair.** `transfer` produces two transactions with the same `transfer_group_id` and `type=transfer`: one subtracts from `from_account`, the other adds to `to_account`. Both are persisted or neither is. They are **excluded from income/expense** (a flag consumable by reports in P5).
- **Settings singleton.** A single row; `base_currency=COP` fixes the currency of every `to_base`.

## Errors

`domain` raises typed errors (later mappable to 4xx in P1 / text in P2):

- `ValidationError` — amount ≤ 0, unsupported currency, nonexistent or archived account/category, invalid `type`.
- `MissingRate` — non-COP transaction without an explicit `fx_rate` and without a current rate for the date. Actionable message: "set the usd_cop rate for {date}".
- `TransferImbalance` — source == destination, or the pair does not balance (must not happen; invariant guard).
- `NotFound` — nonexistent id in reads/writes.

Transfers and any multi-row write: **atomic commit/rollback**; a failure leaves the DB intact.

## Testing and "done" criteria

`pytest` over `domain` + `services` with **in-memory SQLite** (per-test session fixture):

- Money/FX: COP/USD scales, rounding to cents, `to_base` frozen after the rate changes.
- Balance: expense subtracts, income adds, amount always positive; `posted` moves the balance.
- Transfer: pair with the same `transfer_group_id`, source−/destination+, **atomic** (failure → no rows).
- FX: `current_rate` takes the latest ≤ date; `MissingRate` when missing.
- Reads: filters by account/category/tag/type/status/range.
- Validation: invalid amounts, unsupported currency, nonexistent ids → typed error.

**Done when:** in code/tests you can record an expense, income, and transfer; balances come out correct; the USD `to_base` is frozen; transfers are atomic; and `init_db` brings up the schema in-memory.

## Integration with other sub-projects

- **P1 (API)** and **P2 (MCP)** are thin adapters over these services; they do not touch the DB directly nor add logic.
- **P3 (Temporal engine)** adds RecurringItem/RecurringOccurrence and the full semantics of `planned` (due dates, `confirm_payment`, `close_month`), **reusing** `record_*`/`transfer` and the `status` field already defined here.
- **P4 (Budgets/Goals)** adds Budget (with rollover)/Goal/GoalContribution and the `goal_id?` column on Transaction (its own migration), building on `to_base`, the category-exclusion flag, and `transfer` (goal contributions, materialized when confirming in "to-pay").
- **P5 (Reports/Importer)** reads transactions, consumes the transfer flag to exclude them from income/expense, and uses `to_base` for aggregates; the importer calls `record_*`.

**Cross-cutting conventions respected:** `int` cents, aggregates in `to_base` COP, sign by `type`, **only `posted` counts**, atomic transfers. P0 does not re-litigate these rules; it implements them.
