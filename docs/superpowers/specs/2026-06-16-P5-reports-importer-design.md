# Quaestor — P5 Reports + Importer (sub-project)

**Date:** 2026-06-16
**Depends on:** P0 (core), P3 (temporal engine), P4 (budgets + goals).
**Exposed via:** P1 (endpoints `/reports`, `/import`), P2 (MCP tools `monthly_report`, `import_csv`), P6 (screens `/reports`, `/import`).
**Part of:** `2026-06-16-quaestor-general-design.md` (reports §9, importer §10, conventions §5/§12).

---

## Objective

Provide two capabilities for closing the cycle: **read** the month with a monthly report (markdown for the chat + structured data for the frontend) and **load** history/batches with an atomic bulk CSV importer in a custom format. P5 is **aggregation + formatting + ingestion**; it does not recompute rules that belong elsewhere: it reuses the P0/P3/P4 services for the numbers.

## Scope

**Includes**
- Service `monthly_report(month) -> (data, markdown)` with all the sections in §9.
- Service `import_csv(content, dry_run=False) -> ImportResult` with row-by-row validation, atomicity, and error reporting with line numbers.
- Reusable aggregation helpers (expense by category, net, USD share, MoM drift).
- Data contract (`MonthlyReport`, `ImportResult`) for wiring in P1/P2 and P6 screens.

**Does not include**
- Recomputing budget/goal/rollover rules (these come from P4/P3 already calculated).
- HTML/PDF charts (v2; v1 is markdown + tables).
- A Lunch Money-specific migrator (only the generic custom CSV).
- Physical wiring of tools/endpoints/UI (P1/P2/P6 do this; P5 delivers the contract).

## Contribution to the data model

**No new entities.** P5 only **reads** (Transaction, Account, Category, Budget, Goal, GoalContribution, RecurringOccurrence, FxRate) and **writes Transaction/Tag/TransactionTag** via P0's creation services when importing. Imported rows are inserted with `source=import` and, if applicable, a default `status` of `posted`. It defines no migrations of its own.

## Components

- `services/reports.py` — `monthly_report`, aggregation helpers.
- `services/importer.py` — `import_csv`, parser and row validation.
- `domain/report_types.py` — contract dataclasses (`MonthlyReport`, `SafeToSpend`, `EnvelopesSummary`, `CategorySection`, `GroupSection`, `EnvelopeLine`, `GoalLine`, `AccountBalance`, `DriftMoM`, `ImportResult`, `RowError`).
- `domain/report_markdown.py` — pure renderer `data -> str markdown` (no I/O, testable on its own).
- Reuses from P0: `transactions` (reads, `record_*`), `money`/`fx` (`to_base`, `current_rate`), masters (resolve account/category by name). From P3: `to_pay`, occurrences. From P4: `budget_status`, `safe_to_spend`, `goals_progress`.

## Public interface

```python
def monthly_report(month: str) -> MonthlyReport            # month = "YYYY-MM"; .markdown is an attribute of the result
def import_csv(content: str, *, dry_run: bool = False) -> ImportResult
```

```python
@dataclass
class MonthlyReport:                                       # RETROSPECTIVE (ADR-019): "how did I do?"
    month: str
    income: int; expense: int; net: int                    # COP cents, posted only — HEADLINE
    envelopes_summary: EnvelopesSummary                    # (n_green, n_red, rollover_generated) — HEADLINE
    envelopes: list[EnvelopeLine]                          # (category, allocated, rollover_in, spent, available, status)
    by_category: list[CategorySection]                     # (category, group, total, pct)
    by_group: list[GroupSection]                           # rollup by CategoryGroup (group, total, pct) — ADR-023
    goals: list[GoalLine]                                  # (name, accumulated, target?, eta?, on_track?)
    balances: list[AccountBalance]                         # (account, currency, balance)
    drift_mom: DriftMoM | None                             # None if there is no previous month (cold start)
    usd_share: float                                       # % of the month's expense originated in USD
    pending: list[str]                                     # alert lines: unconfirmed manual entries
    safe_to_spend: SafeToSpend                             # CLOSING at the bottom (not headline, ADR-019): "you closed with $X free"
    markdown: str

@dataclass
class ImportResult:
    ok: bool
    inserted: int                                          # 0 if !ok or dry_run
    tags_created: list[str]
    errors: list[RowError]                                 # RowError(line: int, reason: str)
    dry_run: bool
```

**Custom CSV format** (mandatory header, exact):
```
date,type,payee,amount,currency,account,category,tags,notes
```

| Column | Meaning / contract |
|---|---|
| `date` | `YYYY-MM-DD`. Invalid → error with line. |
| `type` | ∈ `expense` / `income` / `transfer`. Anything else → error. |
| `payee` | free text; optional. |
| `amount` | number in the **original currency**, positive (sign is given by `type`). ≤0 or non-numeric → error. |
| `currency` | `COP` / `USD`. A current rate must exist if `USD` → otherwise, error (`MissingRate`). |
| `account` | **name** of an existing Account (not archived). Does not exist → error with line. |
| `category` | **name** of an existing Category. Does not exist → error with line (empty allowed only if `type=transfer`). |
| `tags` | list separated by `;`; **auto-created** if they don't exist. |
| `notes` | free text; optional. |

## Logic and key rules

**Reports**
- **Only `posted`** in every aggregate/balance (convention §5). `planned` never adds to income/expense/net.
- Every number in **`to_base` (COP)** is already frozen on each tx; the report **does not reconvert** FX.
- **Transfers excluded** from income/expense/by-category (same as in §5). They do affect account balances.
- Respects `exclude_from_totals` / `exclude_from_budget` when aggregating (applied by the category/budget helper, aligned with P4).
- `by_category`: groups the month's posted expenses by category, sorts descending, `pct` over total expense. Includes expense from **all accounts, incl. credit card** (on an accrual basis, ADR-021).
- `by_group`: rollup of the above by **`CategoryGroup`** (ADR-023) — sums the categories of each group, sorts descending, `pct` over total expense. Resolves the group name by FK.
- **MoM Drift**: compares the month's income/expense/net vs the previous calendar month (abs and %); if there is no prior data, `pct=None`.
- **USD share**: `Σ to_base(month's posted expenses with currency=USD) / total expense`. If expense=0 → `0.0`.
- **Retrospective report (ADR-019):** the **headline** is the **month's net** + the **envelope performance** (`envelopes_summary`: how many green/red, `rollover_generated` = Σ positive availables that roll into the next month). The **safe-to-spend goes at the bottom** as a closing line ("you closed with $X free"), **not** as a header. The renderer orders: net → envelopes → by category/group → goals → balances → drift/USD → pending → safe-to-spend.
- **Safe-to-spend / envelopes / goals**: requested from `safe_to_spend`, `budget_status`, and `goals_progress` (P4); P5 only formats them. **Envelopes** show allocated/spent/available/rollover. ETA/on-track only on **defined** goals (undefined ones show only the accumulated amount).
- **Cold start (ADR-009):** with no previous month, `drift_mom=None` and envelopes have not yet accumulated rollover; the report degrades gracefully (it does not break). The importer (below) remains available to backfill LM history if decided later.
- **Pending**: if `to_pay` (P3) reports the month's unconfirmed manual recurring entries, it emits an alert line (account + estimated total).
- `markdown` is generated by the pure renderer from `data`; the two views (MCP chat / P6 frontend) consume the same object.

**Importer**
- **Atomic (all or nothing):** it parses and validates the N rows in memory; **if a single one fails, it inserts none** and returns `ok=False` with all the `errors`. Only if there are 0 errors does it open a DB transaction and commit it or roll it back as a block.
- **Row-by-row validation** accumulating errors (it does not abort at the first one) → the user sees all the problems at once.
- Resolves `account`/`category` by **name** via P0's masters; **tags are auto-created** (recorded in `tags_created`).
- Computes `to_base` with the **`current_rate`** of the row's date (FX from P0); USD without a rate → error on that line.
- Inserts via P0's services (`record_expense/record_income/transfer`) → reuses sign-by-`type`, balance, and atomicity already proven. `source=import`.
- **`dry_run=True`**: runs the entire validation pipeline (incl. name and rate resolution) and **inserts nothing**; feeds the pre-validation of the `/import` screen and the tool.
- Missing/different header or empty CSV → global error (line 0/1), nothing is imported.

## Errors

- Row errors accumulate in `ImportResult.errors` as `RowError(line, reason)` — they are **not** raised; they allow the full report.
- Typed `domain` errors that do propagate in reports: `MissingRate` (missing FX when aggregating USD if needed), `ValidationError` (malformed month). The API (P1) maps them to 4xx; MCP (P2) returns them as structured text.
- Importer: `MissingRate` per row → reason "no usd_cop rate for `<date>`". Nonexistent name → "account/category `<n>` does not exist". Invalid `type`/`amount`/`date` → specific reason with the line.
- Any failure in the commit (unlikely, already validated) → full rollback and `ok=False`.

## Testing and "done" criteria

`pytest` over `services` + renderer with in-memory SQLite.

**Reports**
- Correct aggregates: income/expense/net only with `posted`; `planned` and `transfer` excluded from income/expense.
- By category sorted and with correct `pct`; respects `exclude_*`.
- **MoM Drift** with and without a previous month (`None` on cold start); **USD share** correct and `0.0` if expense 0.
- **Safe-to-spend** and envelopes (with rollover) formatted from P4; goals (defined with ETA, undefined without ETA).
- The pending line appears only if there are unconfirmed manual entries.
- Deterministic markdown renderer for a given `MonthlyReport`.

**Importer**
- Validation: bad rows (date/type/amount/currency) report the correct line + reason.
- **Atomicity**: one invalid row ⇒ **0 inserted**, DB intact.
- Name mapping: account/category resolved by name; nonexistent ⇒ error with line.
- Tags: auto-creation and reporting in `tags_created`.
- `to_base` with current rate; `source=import` on all of them.
- `dry_run` validates without inserting (inserted=0, errors populated all the same).

**Done when:** all tests green; `monthly_report` and `import_csv` with their stable contracts; pure renderer with no I/O; CSV format documented. Wiring of tools (P2), endpoints (P1), and the `/reports` and `/import` screen contracts (P6) referenced and available.

## Integration with other sub-projects

- **P0**: consumes reads from transactions, `money`/`fx` (`to_base`, `current_rate`), masters (resolve by name), and `record_*` to insert the import. Does not touch the DB directly (golden rule §3).
- **P3**: `monthly_report` reads `to_pay`/occurrences for the pending line; it does not trigger rollover.
- **P4**: takes `budget_status` and `goals_progress` already calculated; P5 only formats.
- **P1**: exposes `GET /reports?month=YYYY-MM` (returns data + markdown) and `POST /import` (CSV body, `?dry_run`); a direct mirror of the services.
- **P2**: MCP tools `monthly_report` (shows `.markdown` in the chat) and `import_csv` (accepts dry-run); thin 1:1 adapters.
- **P6**: the `/reports` screen renders data + markdown with a month selector; `/import` uploads a CSV, shows the pre-validation (dry-run) and errors with line before confirming.
