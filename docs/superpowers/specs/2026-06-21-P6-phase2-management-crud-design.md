# Quaestor — P6 Frontend CRUD (Phase 2): Management of goals / budgets / recurring + un-archive

**Date:** 2026-06-21
**Depends on:** P6 Phase 1 (`2026-06-20-P6-frontend-crud-design.md`, shipped: 12 routes, `ui/` form primitives, `lib/api.ts` full P1 surface, grouped sidebar). Consumes and **extends** the backend (P3 recurring, P4 goals/budgets).
**Governed by:** ADR-008 (MCP-first, full CRUD to backlog), **ADR-025 (graduate backlog frontend CRUD in two phases — this is Phase 2)**. Introduces two new ADRs (see "ADRs introduced").

---

## Objective

Phase 1 graduated to a built UI every entity the API **already exposed**, leaving `/goals` and `/budgets` read-only, `/recurring` without edit/delete, and archived masters non-reversible — each behind a "Phase 2" banner, because managing them needs **backend write endpoints that did not exist**.

Phase 2 closes that gap. It exposes the **already-implemented domain services** as HTTP routes + MCP tools, fills the few missing service functions (edit/delete/restore), and graduates the four deferred surfaces to full management UI. This completes ADR-025.

**Key shape — Phase 2 is mostly exposure, not new domain logic.** A backend sweep shows the hard logic already exists and is tested:

- `services/goals.py`: `create_goal` (full validation), `goal_contribution` (atomic internal transfer + contribution record), `goals_progress`.
- `services/budgets.py`: `set_budget` (idempotent envelope upsert), `budget_status`, `safe_to_spend`.
- `services/recurring.py`: `create_recurring`, `list_recurring(active=…)`, `skip_recurring`, the `materialize_due` engine.

None of goals/budgets is currently reachable from **any** external write path (HTTP or MCP) — they are service-internal only (used by reports and rollover). Phase 2 makes them reachable from both the UI and the agent at once, honoring ADR-025's "agent stays a co-equal write path".

## Scope

**Stack (unchanged):** Next.js (App Router) · TypeScript · Tailwind · the app-agnostic `ui/` module (ADR-0002) · React Query · pnpm (ADR-0003). Backend: FastAPI routers + SQLModel services + FastMCP tools, the existing P0–P5 layering.

**Four areas, three backend layers + one frontend layer:**

| Area | Service layer | HTTP router | MCP | Frontend |
|---|---|---|---|---|
| **Goals** | exists (`create_goal`, `goal_contribution`); **add** `update_goal`, `pause_goal`, `restore_goal`, `list_goals` | new: list, create, patch, delete(pause), contribute, restore | new tools: create/update/contribute/pause/restore | `/goals` read → management |
| **Budgets** | exists (`set_budget`, `budget_status`); **add** `list_budgets(year_month)` | new: `GET ?month`, `PUT` (assign); `safe-to-spend` stays | new tool: assign | `/budgets` read → assign + status |
| **Recurring** | exists (create/list/skip); **add** `update_recurring`, `deactivate_recurring`, `restore_recurring` | add: PATCH, DELETE(deactivate), restore | add tools: update, delete | `/recurring` + edit / delete / restore |
| **Masters un-archive** | **add** `unarchive_account`, `unarchive_category`, `unarchive_group` | add: `POST /{id}/restore` per master | (optional, symmetric — not required) | "Restaurar" action on archived rows |

**Out of scope (Phase 2):**

- Tags un-archive — tags are **hard-deleted** (no `archived` flag), nothing to restore.
- Editing already-materialized recurring occurrences — they are real planned/posted transactions, edited/skipped through `/transactions` and `/to-pay` (Phase 1 paths). Recurring edit affects **future** occurrences only.
- Clawing back goal contributions on pause — contributions are real internal transfers and stay in the ledger (append-mostly).
- Budget "rollover" management UI — `services/rollover.py` runs via the scheduler/agent; no new UI here.
- `/import` UI (ADR-024, reaffirmed). Automated UI tests (manual smoke, ADR-008). Server-side pagination (single-user volume).

## Contribution to the data model

**None.** No new tables, no migrations. Every soft-delete/restore reuses an existing column:

- `Goal.status: GoalStatus` already has `active | reached | paused`. Delete → `paused`; restore → `active`.
- `RecurringItem.active: bool` already exists, and `list_recurring(active=…)` already filters on it. Delete → `active=false`; restore → `active=true`.
- `Account.archived` / `Category.archived` / `CategoryGroup.archived` already exist (Phase 1 archives them). Restore → `archived=false`.
- `Budget` is keyed by `(category_id, year_month)` with `amount_assigned`. Assign is an upsert (`set_budget`); "unassign" = assign `0`.

The TypeScript types in `lib/api.ts` are representations of the API JSON (cents as integers), extended — never tables.

## ADRs introduced

Per `CLAUDE.md`, architecturally-significant decisions are recorded in `docs/adr/` via the `adr` skill (current numbering 0001–0004; these become 0005+). Two are introduced before implementation:

1. **Soft-delete + restore as the uniform lifecycle for goals / recurring / masters.** Decision: "delete" never removes ledger history; it deactivates (`Goal.status=paused`, `RecurringItem.active=false`, master `archived=true`) and is reversible via a dedicated `POST /{id}/restore`. Rationale: the ledger (transactions) is append-mostly (consistent with transfers → 422 on delete); goal contributions and recurring occurrences are real transactions that must persist; the columns already exist. Matches how budgeting apps (YNAB, Actual, Lunch Money, Monarch) treat scheduled rules and goals.
2. **Goals/budgets write API + MCP parity.** Decision: state transitions and create-actions use `POST /{id}/<verb>` (`contribute`, `restore`) mirroring the existing `confirm`/`skip` convention; the idempotent envelope assign uses `PUT /budgets` (set-to-value by `(category, month)`), the one deliberate new verb in the API. Every new write is exposed simultaneously as an HTTP route (for the UI) and an MCP tool (for the agent), so goals/budgets gain their first external write path on both channels at once.

## API surface (new + verified against existing conventions)

Existing repo conventions (extracted from `accounts`, `planned`, `transactions`, `tags` routers): collection `GET ""`/`POST ""`(201); item `GET /{id}`, `PATCH /{id}`(200, partial, returns Out), `DELETE /{id}`(204, no body); **state transitions = `POST /{id}/<verb>`** (`confirm`, `skip`) returning the affected Out (200); the lifecycle state (`archived`) is kept **out** of the PATCH body. Phase 2 follows these.

All paths relative to `/api`. Money fields are int cents.

| Resource | Method · path | Status | Body / query → response |
|---|---|---|---|
| **Goals** | `GET /goals` | 200 | → `GoalOut[]` (entity incl. `status`, `monthly_amount`, `savings_account_id` — for the edit form) |
| | `GET /goals/progress` | 200 | unchanged → `GoalProgress[]` (computed view) |
| | `POST /goals` | 201 | `{name, monthly_amount, savings_account_id, target_amount?, deadline?}` → `GoalOut`. Defined goal needs both `target_amount`+`deadline`, open-ended needs neither (service rule) |
| | `PATCH /goals/{id}` | 200 | `{name?, monthly_amount?, target_amount?, deadline?, savings_account_id?}` → `GoalOut` |
| | `DELETE /goals/{id}` | 204 | soft → `status=paused` (contributions stay) |
| | `POST /goals/{id}/contribute` | 201 | `{amount, date}` → `GoalContributionOut`. Internal transfer from default source → savings account; requires default source configured (else 422) |
| | `POST /goals/{id}/restore` | 200 | `paused → active` → `GoalOut` |
| **Budgets** | `GET /budgets?month=YYYY-MM` | 200 | → `BudgetLine[]` (per category: `assigned, spent, available, status`) |
| | `PUT /budgets` | 200 | `{category_id, year_month, amount_assigned}` → `BudgetLine`. Idempotent upsert (`amount_assigned >= 0`; `0` = unassign) |
| | `GET /budgets/safe-to-spend?month=YYYY-MM` | 200 | unchanged → `SafeToSpend` |
| **Recurring** | `PATCH /recurring/{id}` | 200 | `{name?, payee?, mode?, amount?, account_id?, category_id?, interval_unit?, interval_count?, start_date?, end_date?}` → `RecurringOut`. `type`/`currency` immutable (delete + recreate). Affects **future** un-materialized occurrences only |
| | `DELETE /recurring/{id}` | 204 | soft → `active=false` |
| | `POST /recurring/{id}/restore` | 200 | `active=false → true` → `RecurringOut` |
| **Masters** | `POST /accounts/{id}/restore` | 200 | `archived → false` → `AccountOut` |
| | `POST /categories/{id}/restore` | 200 | `archived → false` → `CategoryOut` |
| | `POST /category-groups/{id}/restore` | 200 | `archived → false` → `CategoryGroupOut` |

New Out shapes:
- `GoalOut`: `id, name, target_amount:int|null, deadline:string|null, monthly_amount, savings_account_id, status`.
- `GoalContributionOut`: `id, goal_id, date, amount, source, transaction_id:int|null`.
- `BudgetLine`: `category_id, category_name, assigned, spent, available, status` (status from `budget_status`).

## Components

**Backend (new/changed):**

```
services/
  goals.py          # + update_goal, pause_goal, restore_goal, list_goals
  budgets.py        # + list_budgets(year_month) -> BudgetLine[]
  recurring.py      # + update_recurring, deactivate_recurring, restore_recurring
  accounts.py       # + unarchive_account
  categories.py     # + unarchive_category, unarchive_group
api/routers/
  goals.py          # + list, create, patch, delete(pause), contribute, restore
  budgets.py        # + GET ?month (lines), PUT (assign)
  recurring.py      # + patch, delete(deactivate), restore
  accounts.py       # + POST /{id}/restore
  categories.py     # + POST /{id}/restore
  category_groups.py# + POST /{id}/restore
mcp/tools/
  core.py           # + goals (create/update/contribute/pause/restore), budgets (assign)
  temporal.py       # + update_recurring, delete_recurring
domain/dtos.py      # + BudgetLine (if not derivable from existing DTOs)
```

**Frontend (new/changed):**

```
lib/
  api.ts            # + methods: listGoals/createGoal/updateGoal/contributeGoal/pauseGoal/restoreGoal;
                    #   listBudgets/assignBudget; updateRecurring/deleteRecurring/restoreRecurring;
                    #   restoreAccount/restoreCategory/restoreCategoryGroup; + GoalOut/BudgetLine/GoalContribution types
  query.ts          # + INVALIDATION.goalWrite, budgetWrite; reuse recurring/account/category groups + add 'planned' where relevant
app/(app)/
  goals/page.tsx       # read -> management: create/edit/pause/restore + contribute (MoneyInput); banner removed
  budgets/page.tsx     # + per-category assign (selected month) + envelope status; banner removed
  recurring/page.tsx   # + edit (reuse create form) + delete + restore + "show inactive" filter; banner removed
  accounts/page.tsx    # + "Restaurar" row action on archived rows
  categories/page.tsx  # + "Restaurar" row action on archived rows
  category-groups/page.tsx # + "Restaurar" row action on archived rows
components/
  status-badge.tsx  # + "paused" (goal) variant
```

Reuses Phase 1 primitives unchanged: `EntityFormDialog`, `ConfirmDialog`, `DataTable`, `EntitySelect`, `MoneyInput`, `StatusBadge`. No new `ui/` primitive is anticipated; if one is, it stays app-agnostic under the ADR-0002 boundary.

## Public interface (routes — UI behavior changes)

> Phase 2 changes the behavior of four existing routes; it adds **no** new routes.

| Route | Phase 1 (now) | Phase 2 (after) |
|---|---|---|
| `/goals` | read-only progress + Phase-2 banner | create / edit / pause / restore + record a manual contribution; banner removed |
| `/budgets` | read-only safe-to-spend + envelopes + banner | + assign an envelope amount per category for the selected month, live status; banner removed |
| `/recurring` | list + create + skip + banner | + edit (future occurrences), deactivate, restore, "show inactive" filter; banner removed |
| `/accounts`, `/categories`, `/category-groups` | archive (soft) + "show archived" filter | + "Restaurar" on archived rows |

## Logic and key rules

- **Zero business logic in the client (unchanged).** Fetch + render + format. `assigned/spent/available`, `status`, contribution amounts, balances all arrive resolved from the API. `MoneyInput` text↔cents is the only numeric transform.
- **Soft-delete is uniform and reversible.** "Delete" deactivates and preserves all ledger history; "restore" re-activates. Goal → `paused`; recurring → `active=false`; master → `archived=true`. Delete confirmations state the soft semantics ("se puede restaurar").
- **Goal contribution is a real transfer.** `POST /goals/{id}/contribute` runs the existing atomic `goal_contribution` (internal transfer default-source → savings account + `GoalContribution`). Requires a default source account in settings — absent → 422 with an actionable message linking to `/settings`. Currency of source must match the savings account (service rule).
- **Recurring edit affects the future only.** `materialize_due` reads the item's current fields when generating un-materialized occurrences, so a PATCH changes upcoming occurrences; already-materialized planned/posted transactions are untouched (edit those via `/transactions` / `/to-pay`). `type` and `currency` are immutable to avoid mixed-currency occurrence history.
- **Budget assign is idempotent.** `PUT /budgets` sets `amount_assigned` for `(category, month)` to the given value (`>= 0`); re-assigning overwrites; `0` unassigns. The response is the recomputed `BudgetLine` so the envelope status refreshes immediately.
- **Invalidation.** New groups in `lib/query.ts`: `goalWrite → [goals, accounts, transactions, reports]` (contribution moves money), `budgetWrite → [budgets, reports]`. Recurring/master writes reuse the existing groups; restore invalidates the same roots as the archive did. Optimistic updates for restore/pause where it improves perceived latency, rolled back on error.
- **Agent parity.** Each new HTTP write has a sibling MCP tool over the same service function, so what the agent records and what the UI records are identical (shared DB).

## Errors

- **API errors** normalize to `ApiError { status, code, message }` (Phase 1 contract). Mutations → toast; page loads → `ErrorState` with retry.
- **Goal contribute without default source / currency mismatch → 422**; the toast is actionable (link to `/settings`).
- **Restore of an already-active/non-archived resource** → idempotent **200 no-op** returning the unchanged Out (REST idempotency); never an error, never blocks the UI.
- **Recurring PATCH of `type`/`currency`** → rejected client-side (fields disabled with a note) and authoritatively by the backend (422).
- **401** → cache clear + redirect to `/login` (Phase 1 interceptor, unchanged).

## Testing and "done" criteria

**Testing:** TDD on the backend (services first, then routers), manual smoke on the frontend (ADR-008, general §11).

- **Service tests (new functions):** `update_goal`, `pause_goal`/`restore_goal`, `list_goals`; `list_budgets`; `update_recurring`, `deactivate_recurring`/`restore_recurring`; `unarchive_*`. Cover validation, soft-delete reversibility, recurring-edit-affects-future-only.
- **Router/API tests:** status codes (201/204/200), 422 guards (transfer-recurring rejection paths, contribute without default source, immutable fields), assign idempotency, restore round-trips.
- **MCP tests:** the new tools return the formatted strings over the same services.
- **Frontend smoke per screen:** load · create · edit · pause/delete · restore · assign · contribute · filters · money formatting · error handling.

**Phase 2 "done" (minimum acceptable):**
1. **Goals:** create / edit / pause / restore / contribute from `/goals`, reflecting in dashboard, balances, reports; banner gone.
2. **Budgets:** assign per category for a month, envelope status updates live; banner gone.
3. **Recurring:** edit (future occurrences), deactivate, restore, show-inactive filter; banner gone.
4. **Masters:** restore archived accounts/categories/category-groups.
5. **Agent parity:** every new goals/budgets/recurring write is also an MCP tool.
6. **Thin-client purity preserved:** no business arithmetic in the client (lint/review on `lib/` + components).
7. **Two ADRs recorded** (soft-delete/restore lifecycle; goals-budgets write API + MCP parity).

## Integration with other sub-projects

- **P1 (HTTP API + Auth):** the contact surface; `lib/api.ts` extends with the new methods.
- **P3 (Temporal):** Phase 2 adds recurring edit/delete over the existing `materialize_due` engine; no engine change, edits are future-only.
- **P4 (Budgets + Goals):** Phase 2 is the trigger ADR-025 named — it exposes P4's goals CRUD + contribute and budgets assign/status, which existed only as services. No new domain rules.
- **P5 (Reports):** `goalWrite`/`budgetWrite` invalidate `reports` so envelope/goal sections refresh.
- **P2 (MCP):** gains goals/budgets tools + recurring edit/delete — the agent reaches parity with the UI.
- **P7 (Deployment):** no new deployment surface (same Next.js + FastAPI services, same env).
