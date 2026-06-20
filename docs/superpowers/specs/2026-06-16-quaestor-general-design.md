# Quaestor — General Design (umbrella)

> *Quaestor*: the Roman magistrate in charge of the treasury. You talk to your Quaestor to record, query, and plan your money.

**Date:** 2026-06-16
**Status:** design approved, implementation plan pending
**Author:** angelozam17 (+ assistant)

This is the **general design**. It pins down the cross-cutting concerns (objective, architecture, data model, money conventions, auth, deployment) and breaks the system into **8 sub-projects**, each with its own design. See [§12 Sub-projects](#12-sub-projects).

Sub-specs (in this same folder):
- `2026-06-16-P0-core-design.md`
- `2026-06-16-P1-api-auth-design.md`
- `2026-06-16-P2-mcp-design.md`
- `2026-06-16-P3-temporal-engine-design.md`
- `2026-06-16-P4-budgets-goals-design.md`
- `2026-06-16-P5-reports-importer-design.md`
- `2026-06-16-P6-frontend-design.md`
- `2026-06-16-P7-deployment-design.md`

---

## 1. Objective and context

A personal finance system, **single-user**, that replaces Lunch Money as my own system of record. It covers expenses, income, recurring items (auto and manual), transfers, budgets, savings goals, and monthly reports.

Two ways to interact:
- **Natural language** via an **MCP server** (Claude Code today; MiniMax or another MCP client tomorrow). The backend is LLM-agnostic. **The primary path for v1.**
- **Web frontend** for reviewing and planning. In v1 it is **minimal** (a "To-pay" dashboard + monthly report); full CRUD stays in the backlog (see [ADR-008](../../decisions/product-decisions.md)).

**Project driver.** The primary motivation is **having my own, agent-native backend** (my own DB, talking to an agent about *my* schema without depending on a third party's API). The 3 pain points below are the **proof of value for v1**, not the justification for the system. The **budget** (§6) is the explicit product differentiator versus Lunch Money. See [ADR-001](../../decisions/product-decisions.md).

**Today** the user uses Claude Code + a Lunch Money API key ("just the backend"). Quaestor recreates that flow —talking to an agent that writes to a backend— but on **my own database**, deployable to a VPS.

> **Product decisions are recorded as ADRs** in `docs/decisions/product-decisions.md`. This design and the P0–P7 sub-specs already reflect those ADRs.

**Pain points it explicitly solves:**
1. Not knowing **what's left to pay** at a given point in the week → the "To-pay" view.
2. Wanting to **save month over month** toward a goal (a trip, tech gear) → goals with a fixed monthly contribution.
3. Wanting **monthly reports** without opening someone else's UI → a markdown report in the chat + the frontend.

### Out of scope (v1)
- Multi-user, roles, sharing.
- Reports with HTML/PDF charts (v2; v1 is markdown + tables).
- Goal rules by % of income (v1 is fixed **amount** only).
- Automatic sync with banks / Plaid.
- A Lunch Money-specific migrator (we start from scratch + a generic CSV importer).

---

## 2. Settled decisions

| Topic | Decision |
|---|---|
| Relationship to LM | A **new, standalone** project. Does not depend on LM or the `my_finances` project. |
| AI layer | An **MCP server** over my own DB. LLM-agnostic (Claude Code today, MiniMax later). |
| Backend stack | Python 3.12 · FastAPI · SQLModel (SQLAlchemy+Pydantic) · official MCP SDK · uv |
| Storage | **SQLite** (single-user, one file). Migratable to Postgres via connection string if needed. |
| Frontend | **Next.js** (App Router) · TS · Tailwind · shadcn/ui. **Minimal v1** ("To-pay" dashboard + report); full CRUD to the backlog. **MCP-first** (ADR-008). |
| Data fidelity | Complete: multi-currency COP+USD, multi-account+balances, internal transfers, tags, budgets, recurring items, goals |
| Data bootstrap | DB **from scratch** + a **bulk CSV importer** (a documented custom format) |
| Budget | **Hybrid**: per-category envelopes **with rollover** + **safe-to-spend** (unassigned money = forecast income − committed − assigned). Differentiator vs LM (ADR-002/003). |
| Goals | **Fixed monthly amount**; defined (target+deadline) or open-ended. **Flexible** contribution: proposed as `planned`, you confirm it in "To-pay" (no forced transfer) (ADR-006). |
| FX | Full multi-currency COP+USD; `usd_cop` rate **auto-fetched daily** + manual override; `to_base` frozen (ADR-010/011). |
| Recurring items | Expense **and** income; **auto** and **manual** modes |
| Future payments | `Transaction.status` ∈ `planned`/`posted`; the "To-pay" view |
| Reports | **Markdown in the chat** (MCP) + rendered in the frontend |
| Deployment | **Self-hosted VPS**, Docker Compose behind **Caddy** (auto HTTPS) |
| Auth | Single-user: password → session (frontend, **public**) + bearer `APP_TOKEN` for the API and MCP. **`/mcp` behind Tailscale** (private network, off the internet) (ADR-013). |

---

## 3. Architecture

A single SQLite as the source of truth. A shared core (`domain` + `services`); two adapters (MCP, HTTP API); one frontend.

```
        ┌───────────── domain (models + calculations, pure) ──────────┐
        │                    services (use cases)                      │
        └──────────────────────────┬───────────────────────────┬──────┘
                                    │                           │
                          MCP server (NL/agent)         HTTP API (FastAPI)
                                                                │
                                                          Web frontend (CRUD + reports)
```

**Golden rule:** the API and MCP **never** touch the DB directly. Both call `services`. All the logic (validate, convert FX, balance transfers, compute goals, rollover) lives in `services`/`domain` → testable without HTTP or MCP, with no duplication.

### Repo structure (monorepo)

```
quaestor/
├── backend/
│   ├── pyproject.toml            # uv, Python 3.12
│   ├── quaestor.db               # SQLite (gitignored)
│   ├── src/quaestor/
│   │   ├── domain/
│   │   │   ├── models.py         # SQLModel: Account, Category, Transaction...
│   │   │   ├── money.py          # Money (cents, int), FX conversion
│   │   │   └── rules.py          # goal calc, budget vs actual, rollover
│   │   ├── db.py                 # SQLite engine, session, migrations
│   │   ├── services/
│   │   │   ├── transactions.py   # record_expense, record_income, transfer
│   │   │   ├── planned.py        # plan_payment, confirm_payment, to_pay
│   │   │   ├── recurring.py      # create_recurring, list
│   │   │   ├── budgets.py        # set_budget, budget_status
│   │   │   ├── goals.py          # create_goal, contribution, progress
│   │   │   ├── rollover.py       # close_month
│   │   │   ├── reports.py        # monthly_report -> (data, markdown)
│   │   │   ├── fx.py             # set_rate, current_rate
│   │   │   └── importer.py       # bulk CSV
│   │   ├── api/                  # FastAPI: REST routers over services
│   │   └── mcp/                  # MCP server: tools over services
│   └── tests/                    # pytest over domain + services
├── frontend/                     # Next.js (App Router, TS, Tailwind, shadcn/ui)
│   ├── app/                      # /transactions /to-pay /budgets /goals /reports ...
│   └── lib/api.ts                # typed API client
├── docker-compose.yml            # api · mcp · frontend · caddy
├── Caddyfile
└── docs/superpowers/specs/       # this document
```

### How it runs (local dev)
- `uv run uvicorn quaestor.api:app` → API on `:8000`
- `uv run python -m quaestor.mcp` → MCP server
- `npm run dev` in `frontend/` → UI on `:3000`, hits `:8000`
- All three share the same `quaestor.db`.

---

## 4. Deployment and auth

It lives on a **VPS** with a domain + HTTPS. Nothing runs on the laptop except the browser and the MCP client (Claude Code) pointing at a remote URL.

```
   VPS (domain, HTTPS)
   ┌─────────────────────────────────────────────┐
   │  Caddy (reverse proxy + auto HTTPS)          │
   │    ├── quaestor.yourdomain.com    → Frontend │
   │    ├── /api/*                     → FastAPI  │
   │    └── /mcp                       → MCP (HTTP)│
   │  ─────────────────────────────────────────── │
   │  services + domain  →  quaestor.db (volume)  │
   └─────────────────────────────────────────────┘
        ▲                         ▲
        │ browser (login)         │ Claude Code / MiniMax
     laptop                    (remote MCP URL + token)
```

- **Remote MCP, not local stdio.** The MCP server is exposed via the official SDK's **streamable-HTTP** transport, at `/mcp`, protected by a token. Claude Code connects to the remote URL with an auth header. (The local stdio shim is dropped because it would force something to keep running on the laptop.)
- **Auth:**
  - Frontend: a single **password** → session cookie. No sign-up, no users. **Public** behind HTTPS.
  - API and MCP: a **static bearer token** (`APP_TOKEN` in env). The frontend uses it via the session; Claude Code sends it in the header.
  - **`/mcp` is not exposed to the public internet:** it lives behind **Tailscale** (private network). The user reaches it from their own devices; the static token stops being the only thing protecting the sensitive endpoint (ADR-013). The frontend (`/` and `/api/*`) does stay public.
  - Everything behind HTTPS (Caddy issues and renews the cert on its own).
  - **Trade-off:** cloud MCP clients (claude.ai web) can't reach `/mcp` through Tailscale; if they ever become necessary, we revisit the stance.
- **Deployment:** `docker-compose.yml` with the `api`, `mcp`, `frontend`, `caddy` services. `quaestor.db` on a **persistent volume**. Deploy = `git pull && docker compose up -d --build`.
- **Backups:** **Litestream** continuously replicates the `.db` to a bucket (S3/R2/Backblaze). Acceptable minimum: a daily `sqlite3 .backup` cron.

---

## 5. Data model

Amounts = **integers in cents**, never float. Base currency = **COP**.

| Entity | Key fields |
|---|---|
| **Account** | `name`, `type` (debit/credit/cash/savings), `currency`, `balance` (cents), `archived`. A **credit card** = a normal account with a negative balance = debt; the expense counts at purchase time and the statement payment is a `transfer`, not an expense (ADR-021) |
| **CategoryGroup** | `name`, `sort_order`, `archived` — a container of categories ("Essentials", "Leisure"); its own entity so you can rename/order it and report by group (ADR-023) |
| **Category** | `name`, `group_id?` (FK CategoryGroup), `is_income`, `exclude_from_budget`, `exclude_from_totals`, `archived` |
| **Transaction** | `date`, `payee`, `notes`, `type` (expense/income/transfer), `status` (planned/posted), `amount` (cents, original currency), `currency`, `fx_rate`, `to_base` (cents COP), `account_id`, `category_id?`, `recurring_id?`, `transfer_group_id?`, `source` (manual/agent/import), `created_at` |
| **Tag** + **TransactionTag** | `name`; m2m relationship |
| **RecurringItem** | `name`, `payee`, `type` (expense/income), `mode` (auto/manual), `amount` (default), `currency`, `category_id`, `account_id`, `interval_unit` (day/week/month/year), `interval_count` (≥1), `start_date` (anchor), `end_date?`, `active`. A generic every-N interval (ADR-020): monthly=`1 month`, quarterly=`3 month`, semiannual=`6 month`, annual=`12 month`, weekly=`1 week`, biweekly=`2 week` |
| **RecurringOccurrence** | `recurring_id`, `due_date` (the concrete due date), `status` (posted/planned/skipped), `transaction_id?`, `created_at` — an idempotency marker, unique per `(recurring_id, due_date)` (ADR-020) |
| **Budget** (envelope) | `category_id`, `year_month` (YYYY-MM), `amount_assigned` (cents COP). Rollover derived from the previous month (ADR-002/005) |
| **Goal** | `name`, `target_amount?` (COP), `deadline?`, `monthly_amount` (COP, fixed), `savings_account_id`, `status` (active/reached/paused) |
| **GoalContribution** | `goal_id`, `date`, `amount`, `source` (confirmed/manual), `transaction_id?` |
| **FxRate** | `date`, `usd_cop` (rate) |
| **Settings** | `base_currency=COP`, `default_source_account_id` (the global source account for goal contributions, ADR-015), app config |

### Money / FX / sign rules (in `domain`)
- **Explicit sign by `type`**, not a sign on the amount. `amount` is always positive; the service knows that an expense subtracts and income adds. Avoids LM's sign confusion.
- **Every aggregate uses `to_base` (COP).** A tx in USD computes `to_base = amount × fx_rate` at recording time and **freezes** it → historical reports stay stable even if the rate changes.
- **The account balance** is updated by the service on each `posted` tx (not recomputed from scratch).
- **`usd_cop` rate auto-fetch.** A daily job (P7) hits a free FX API and stores the rate in `FxRate`; `set_fx_rate` remains a **manual override / fallback**. With USD at ~50% of the volume, keeping the rate by hand was constant friction (ADR-011).
- FX with no rate for the date → uses the last current one; if there is none → a clear "set the usd_cop rate" error. `to_base` is frozen at recording time (historical consistency intact).

### Internal transfers
A pair of transactions with the same `transfer_group_id`, `type=transfer` → one subtracts from the source account, the other adds to the destination. **Excluded from income/expense** in every report. The service creates them **atomically** (both or neither).

### Transaction states: `planned` vs `posted`
- `posted` = it actually happened (the default when recording). Affects balance and reports.
- `planned` = a future obligation. **Touches neither balance nor totals** until confirmed. Has a due date.
- **Firm rule:** every aggregate/balance/report counts **only `posted`**.

---

## 6. Temporal logic

The temporal engine runs **on its own**, via the daily `scheduler` (P7). It has **two distinct clocks** (ADR-020/022): the **materialization of recurring items runs by date** (due-driven, supports any interval); the **budget/goal close runs by calendar month**.

### Materialization of recurring items — daily, due-driven (ADR-020)
Each day the scheduler materializes the `RecurringOccurrence`s with `due_date ≤ today` that don't yet exist (not the whole month in advance → the balance doesn't pull expenses forward). For each active `RecurringItem`, generating dates with `start_date + k × (interval_count × interval_unit)`:
- `mode=auto` → posts a `posted` transaction on its `due_date` with the defined amount; occurrence `status=posted`. (A weekly item posts each week on its date, not 4 at once.)
- `mode=manual` → for the current month a **`planned`** transaction is generated (due on `due_date`) **without affecting the balance**, visible in "To-pay"; occurrence `status=planned`. You confirm it with the real amount.
- **Idempotent** by `(recurring_id, due_date)`: a missed day self-heals, re-running doesn't duplicate.

### Monthly close — `close_month(YYYY-MM)`, idempotent (ADR-017/022)
**Automatic trigger:** the `scheduler` runs `ensure_month_closed(current_month)` daily — on the 1st it materializes the close of the **calendar month**, on other days it's a no-op, and a missed day self-heals. It is not a user tool.
1. **Envelope rollover:** carries the positive balance of each envelope into the next month (`rollover_in`, P4/ADR-005).
2. **Goals (flexible, ADR-006):** for each active `Goal` → creates a **`planned`** obligation (a proposed contribution to `savings_account_id`, due at the end of the period). **It does not move money.** It shows up in "To-pay"; when you confirm it, it becomes `posted` (an internal transfer) and the `GoalContribution` is recorded. If the month came in tight, you confirm less or skip it.
3. Re-running doesn't duplicate (the rollover / proposed contribution for the period already exists).

### Recurring items (expense/income, auto/manual)
- `type` distinguishes an expense (rent, subs, Netflix) from income (salary, fixed freelance).
- `interval_unit` + `interval_count` give the generic frequency (ADR-020): weekly, biweekly, monthly, quarterly, every-4-months, semiannual, annual…
- `mode=auto` → posts on its own on its `due_date`.
- `mode=manual` → lands as `planned`; you confirm it with the real amount (handy for variable ones: power, water, credit card).

### Future payments / "To-pay"
- `to_pay(from, to)` → a list of `planned` transactions in the window + a total. Solves "what's left for me to pay this week?".
- `confirm_payment(tx_id, amount?, date?)` → `planned` → `posted` (you adjust the real amount).
- `plan_payment(...)` → a one-off future payment (e.g. "I owe a friend on Friday"), with no recurring item.

### Goals (fixed amount)
| Type | `target_amount` | `deadline` | `monthly_amount` | Calculation |
|---|---|---|---|---|
| **Defined** | yes | yes | yes | fixed contribution + **on-track/behind + ETA** vs deadline (compares the required `(target−saved)/months` against the fixed amount) |
| **Open-ended** | no | no | yes | just accumulates the fixed amount; **no ETA, no required figure**, only the total saved |

`goal_contribution(goal_id, amount, date)` allows one-off manual contributions. The monthly contribution is **not automatic**: the rollover **proposes** it as `planned` and you confirm it in "To-pay" (ADR-006). The contribution (manual or confirmed) is an internal transfer to the savings account → it is neither expense nor income.

### Budget — hybrid (differentiator, ADR-002/003)

Two layers that are **a single model** (nothing is counted twice):

**1. Per-category envelopes with rollover.** Each category has a monthly envelope (`Budget`).
- `available(cat, month) = rollover_in + assigned − spent_posted`, with `spent = Σ to_base(expense, cat, month, posted, respecting exclude_flags)`.
- **Accrual-based, all accounts (ADR-021).** `spent` sums the expenses across **all accounts including the credit card**, on the **purchase date** (not when paying the statement). The statement payment is a `transfer` (debit → card), already excluded from expense → never counted twice.
- **Rollover:** `rollover_in(cat, month) = max(available(cat, month−1), 0)` → the unspent portion is carried forward; overspend is absorbed by the global pool and the envelope **resets to 0** (ADR-005).

**2. Global safe-to-spend** = the money you **haven't** assigned to any envelope. Envelopes are **optional** (A4/ADR-016): only some categories carry an envelope; the rest spend straight from the pool.
```
safe_to_spend(month) = forecast_income(month)
                     − committed(month)
                     − Σ assigned_to_envelopes(month)    # categories WITH an envelope
                     − Σ unbudgeted_spend(month)          # posted spend in categories WITHOUT an envelope
                     − Σ overspend(month)                 # max(spent − (assigned + rollover_in), 0)
```
- `forecast_income` = the sum of the `income` recurring items that touch the month; **no typed-in override** (ADR-004/A2).
- `committed` = the month's obligations (auto recurring items + `planned` + proposed goal contributions), **counted exactly once** whether `planned` or already `posted` (ADR-014). When an obligation posts, safe-to-spend **doesn't move** (it was already deducted).
- `assigned_to_envelopes` = Σ `Budget.amount_assigned` of the categories with an envelope.
- `unbudgeted_spend` = spend in categories **without an envelope** (without this, the pool would overestimate what's free, A4).
- `overspend` = the amount overspent in an envelope beyond `assigned + rollover_in` (ADR-005); `rollover_in` (prior money) does not add to this month's pool.

`budget_status(category, month)` returns the envelope's state (`assigned`, `rollover_in`, `spent`, `available`, `pct_used`, over/under). `safe_to_spend(month)` returns the headline number **of the live dashboard** + its breakdown (in the monthly report it goes in the footer, ADR-019). Full detail in P4.

---

## 7. Services, MCP, and API

### The `services` layer (the brain)
`record_expense · record_income · transfer · create_group · create_category · plan_payment · confirm_payment · to_pay · create_recurring · list_recurring · materialize_due · set_budget · budget_status · safe_to_spend · create_goal · goal_contribution · goals_progress · set_fx_rate · close_month · monthly_report · import_csv` + reads (list/query). `materialize_due` and `close_month` are run by the scheduler (P7), not the user.

### MCP tools
1 tool = 1 service (a thin adapter). Same verbs. The agent records, queries, closes the month, asks "what's left for me to pay?", requests a report — all in natural language → tool → service.

### HTTP API (FastAPI)
REST routers mirroring services: `/transactions /accounts /categories /tags /recurring /budgets /goals /planned /reports /import /fx /rollover /settings`. Same services, zero duplicated logic.

---

## 8. Frontend (Next.js)

> **v1 scope (MCP-first, ADR-008):** only **`/` Dashboard** (with a "To-pay" widget) and **`/reports`**. The rest of the table is **backlog** — operated by the agent until each screen lands. The table describes the full destination, not v1.

| Route | What it does |
|---|---|
| `/` **Dashboard** | income vs expense for the month + net · **"To-pay" widget** (this week / this month + total + mark paid) · goal progress · balances · budgets at risk |
| `/transactions` | full CRUD, filterable table (date/account/category/tag/type/status) |
| `/to-pay` | a list of `planned`, confirm a payment (real amount), plan a one-off payment |
| `/recurring` | recurring CRUD (type, mode auto/manual, every-N interval: unit + count) |
| `/budgets` | set a category×month budget, status vs actual |
| `/goals` | goal CRUD (defined/open-ended), progress/ETA, manual contribution |
| `/accounts` · `/categories` · `/category-groups` · `/tags` | master-data CRUD (category groups as an entity, ADR-023) + flags + balances |
| `/reports` | monthly report (rendered markdown + tables), month selector |
| `/import` | upload a bulk CSV |
| `/settings` | base currency, FX rate (usd_cop), password |

---

## 9. Reports

`monthly_report(month)` returns `(structured data, markdown)`. MCP shows the markdown in the chat; the frontend renders data + markdown.

**A retrospective report (ADR-019):** answers *"how did I do?"* (not "how much do I have left" — that's the live dashboard). The **headline is the month's net + the envelope performance** (how many in green/red, how much rollover you generated); the **safe-to-spend goes in the footer as a closing line** ("you closed with $X free"), not as a header.

**Contents (in order):** **net** (income / expense) · **envelope performance** (assigned / spent / available / rollover; a green-red summary + total rollover generated) · by category and **by group** (ADR-023) · goals (cumulative + ETA on the defined ones) · account balances · MoM drift · USD share · **recurring items / pending payments** (an alert line if there are unconfirmed manual ones) · **closing safe-to-spend** (in the footer).

> **Cold start (ADR-009):** for the first ~2-3 months the report degrades gracefully — with no prior month there is no MoM drift, and envelopes haven't accumulated rollover yet. The CSV importer (§10) stays available to backfill LM history if decided later.

---

## 10. Bulk CSV importer

A documented custom format:

```
date,type,payee,amount,currency,account,category,tags,notes
```

- Validates row by row; reports errors with the line number.
- An atomic transaction: all or nothing.
- Exposed as an MCP tool (`import_csv`) and the `/import` screen.

---

## 11. Errors and testing

### Errors
- `domain` raises typed errors (`ValidationError`, `MissingRate`, `TransferImbalance`...). The API maps them to 4xx; MCP returns them as structured text the agent explains.
- Transfers and rollover: **atomic** (commit/rollback). Rollover is **idempotent**.

### Testing
- `pytest` over `domain` + `services` with an in-memory SQLite: money/FX, goal calculation (defined/open-ended), budget status, **rollover idempotency**, transfer balancing, `planned` not affecting the balance, payment confirmation, the importer.
- API: `TestClient` happy-path + validation.
- Frontend v1: manual testing; component tests later.

---

## 12. Sub-projects

The system is built as **8 sub-projects**, each with its own design in this folder. Each has a clear purpose, a well-defined interface, and can be understood/tested in isolation.

| # | Project | What it includes | Depends on | Spec |
|---|---|---|---|---|
| **P0** | **Core** | domain (models, money/FX, rules), db/SQLite, base services: accounts, categories, transactions, transfers | — | `…-P0-core-design.md` |
| **P1** | **HTTP API + Auth** | FastAPI REST mirroring services, `APP_TOKEN` token, the contract for the frontend | P0 | `…-P1-api-auth-design.md` |
| **P2** | **MCP server** | remote streamable-HTTP transport, auth, tools over services (the natural-language interface) | P0 | `…-P2-mcp-design.md` |
| **P3** | **Temporal engine** | recurring items (auto/manual), `planned`/To-pay, `close_month` (rollover) | P0 | `…-P3-temporal-engine-design.md` |
| **P4** | **Budgets + Goals** | category×month envelopes **with rollover** + **safe-to-spend**; goals (defined/open-ended, fixed amount) with a **flexible** contribution | P0, **P3** | `…-P4-budgets-goals-design.md` |
| **P5** | **Reports + Importer** | `monthly_report` (markdown), bulk CSV importer | P0, P3, P4 | `…-P5-reports-importer-design.md` |
| **P6** | **Frontend** | Next.js: dashboard, To-pay, CRUDs, reports | P1 | `…-P6-frontend-design.md` |
| **P7** | **Deployment** | Docker Compose, Caddy, Litestream, VPS | all | `…-P7-deployment-design.md` |

**Build order:** `P0 → (P1 ∥ P2) → P3 → P4 → P5 → P6 → P7`.
The frontend (P6) can start as soon as the P1 contract exists and grow feature by feature as P3/P4/P5 land.

**How the data model is split** (fully defined in §5): P0 creates Account, CategoryGroup, Category, Transaction (with `status`), Tag, FxRate, Settings. P3 adds RecurringItem, RecurringOccurrence and the `planned` semantics. P4 adds Budget (with rollover semantics), Goal, GoalContribution, and wires the proposed goal contribution into P3's `planned` queue (via `goal_id` on the proposed tx). Each sub-project adds its own migrations; none redefines another's.

**Cross-cutting conventions everyone respects:** money in cents (int), aggregates in `to_base` COP, sign by `type`, **only `posted` counts** in balances/reports, transfers and rollover atomic and idempotent. Each sub-spec assumes these rules; it does not re-litigate them.
