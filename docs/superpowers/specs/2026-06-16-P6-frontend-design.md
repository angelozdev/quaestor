# Quaestor — P6 Frontend (sub-project)

**Date:** 2026-06-16
**Depends on:** P1 (HTTP API contract + session auth). Grows feature by feature as P3 (recurring/to-pay), P4 (budgets/goals) and P5 (reports/importer) land.
**Part of:** `2026-06-16-quaestor-general-design.md` (frontend §8, auth §4, conventions §12).

---

## Objective

**MCP-first (ADR-008):** the product driver is agent-native; day-to-day recording/CRUD happens by **talking to the agent**. The **v1 frontend is minimal** and covers only what chat does poorly: **reviewing at a glance**. Two views:
1. **Dashboard** with the month's **safe-to-spend** and the **"to-pay"** widget ("what do I still have to pay this week?" + mark paid in one click) — the main pain point.
2. **Monthly report** (markdown + tables).

The rest of the screens (full CRUD for every entity) is **documented as backlog**: the *Public interface* table describes the full target, but v1 ships only the two views above. The frontend remains a **thin client of the P1 API**: zero business logic.

The frontend is a **thin client of the P1 API**. It has no business logic: validation, FX conversion, balancing transfers, computing goals, rollover — all of that lives in `services` (backend) and is consumed over HTTP.

## Scope

- **Stack:** Next.js (App Router) · TypeScript · Tailwind · shadcn/ui. An authenticated SPA that hits the P1 HTTP API.
- **Auth:** login page (password → session cookie via P1's `/auth/login`), route guard, logout.
- **`lib/api.ts`:** typed API client (one method per endpoint) + types mirroring the P1 contract.
- **v1 screens:** login, **dashboard** (safe-to-spend + to-pay), **reports**. (details in *Public interface*).
- **Backlog screens:** transactions, to-pay (dedicated view), recurring, budgets, goals, accounts, categories, tags, import, settings — built feature by feature after v1; in the meantime they are operated through the agent (MCP).
- **Money format:** every amount that arrives is in **cents (int)**; the frontend formats it for display per currency. It never does business arithmetic on amounts.

**Out of scope (v1):** all UI CRUD (that's backlog, done through the agent — ADR-008); computation logic (lives in the backend); automated UI tests in v1 (manual testing; component tests later, general §11); PDF/HTML charts (v2); PWA/offline; i18n beyond es-CO.

## Contribution to the data model

**None.** P6 neither creates nor migrates entities. It consumes exclusively the P1 REST contract (which in turn mirrors `services` over the §5 model). The "types" that `lib/api.ts` defines are TypeScript representations of the API's JSON, not tables: they live in the client and are updated when the contract changes, without touching the DB.

## Components

Layout under `frontend/`:

```
app/
  (auth)/login/page.tsx          # the only public route
  (app)/                          # layout with guard + nav; everything else hangs here
    layout.tsx  page.tsx          # shell + Dashboard (/)
    transactions/ to-pay/ recurring/ budgets/ goals/
    accounts/ categories/ tags/ reports/ import/ settings/
  api/session/route.ts            # route handler: set/clear httpOnly cookie after login/logout
lib/
  api.ts                          # typed client (fetch + P1 contract types)
  money.ts                        # formatCents(cents, currency) -> "$ 1.234.567" / "US$ 12.34"
  query.ts                        # QueryClient + keys
components/
  ui/                             # shadcn/ui (button, dialog, table, select, toast...)
  money-amount.tsx                # render amount with sign by type and color
  data-table.tsx                  # generic filterable/paginated table (transactions, lists)
  to-pay-widget.tsx               # week/month toggle + total + mark paid (reused in / and /to-pay)
  entity-form-dialog.tsx          # reusable CRUD form (account/category/tag/recurring/budget/goal)
  month-picker.tsx                # YYYY-MM selector (reports, budgets)
  empty-state.tsx  error-state.tsx  page-header.tsx
```

- **`MoneyAmount`** and **`money.ts`**: single point of cents→display formatting; expense in red, income in green, sign derived from `type` (not from the amount, which is always positive — §5 convention).
- **`DataTable`**: encapsulates filters, sorting and pagination; configurable by columns. The page only provides the fetch and the columns.
- **`ToPayWidget`**: the star component; shared between Dashboard and `/to-pay`.
- **`EntityFormDialog`**: a single CRUD modal pattern parameterized by schema, avoiding 8 nearly identical forms.

## Public interface (screens / routes)

> **v1** = `/login`, `/` Dashboard, `/reports`. Everything else is **backlog** (ADR-008): full target, not v1.

| Route | v1? | What it does | P1 endpoints |
|---|---|---|---|
| `/login` | **v1** | password → session; redirects to `/` | `POST /auth/login` |
| `/` **Dashboard** | **v1** | **month's safe-to-spend** · **to-pay widget** (this-week/this-month toggle + total + mark paid) · income/expense/net · goal progress · balances · envelopes at risk | `/reports?month`, `/budgets/safe-to-spend`, `/planned`, `/goals`, `/accounts`, `/budgets` |
| `/reports` | **v1** | **retrospective** report (ADR-019): net headline + envelope performance; by category/group; safe-to-spend at the bottom; **month selector** | `GET /reports?month` |
| `/transactions` | backlog | full CRUD; table filterable by date/account/category/tag/type/status | `GET/POST/PATCH/DELETE /transactions` |
| `/to-pay` | backlog | list of `planned`; **confirm payment** (actual amount, date) and **plan a one-off payment** | `GET /planned`, `POST /planned/{id}/confirm`, `POST /planned` |
| `/recurring` | backlog | CRUD recurring (type, auto/manual mode, every-N interval: unit + count) | `…/recurring` |
| `/budgets` | backlog | assign envelopes per category×month; status with rollover; safe-to-spend | `GET/PUT /budgets`, `GET /budgets/status?month`, `GET /budgets/safe-to-spend?month` |
| `/goals` | backlog | CRUD goals (defined/open-ended), progress + ETA, **manual contribution** (the monthly one is confirmed in to-pay) | `…/goals`, `POST /goals/{id}/contribute` |
| `/accounts` `/categories` `/category-groups` `/tags` | backlog | CRUD masters (category groups as an entity, ADR-023) + flags (archived, is_income, exclude_*) + balances | `…/accounts` `…/categories` `…/category-groups` `…/tags` |
| `/import` | backlog | upload bulk CSV; shows **per-line errors** from the P5 validator | `POST /import` (multipart) |
| `/settings` | backlog | base currency, **usd_cop FX rate** (auto-fetch + manual override), change password | `…/settings`, `…/fx`, `POST /auth/change-password` |

Every route except `/login` requires a session: no valid cookie → redirect to `/login`.

## Logic and key rules

- **Zero business logic in the client.** The frontend orchestrates fetch + render + formatting. Any computation (net, budget %, goal ETA, total to pay) arrives already resolved from the API; the frontend displays it, it does not recompute it.
- **Data fetching — recommendation: React Query (TanStack Query).** Rationale: the app is a **highly interactive, single-user, mutation-heavy SPA** (mark paid, confirm, constant CRUD) where caching, invalidation and *optimistic updates* matter — strengths of React Query that Server Components don't cover well. RSC shines for mostly-static pages with server rendering; here almost everything is post-login interaction behind a session guard, so server rendering adds little and complicates handling the session cookie toward the API. The pages are Client Components that consume `lib/api.ts` via React Query hooks; the session is set with a route handler (httpOnly cookie).
- **Auth flow:** `/login` posts the password → P1 responds with a session → a route handler stores the **httpOnly** cookie; the `(app)` layout guard validates on every navigation. Logout clears the cookie and the React Query cache. The `APP_TOKEN` token never touches the client: the browser manages the session, and the route handler mediates with the API.
- **Money:** `formatCents` formats per currency (COP without decimals and thousands separated by a dot; USD with `US$` and 2 decimals). USD amounts also show their `to_base` (COP) when the context is aggregated, already frozen by the backend.
- **`planned` vs `posted`:** the UI distinguishes them visually (badge); marking paid/confirming triggers the mutation and invalidates the to-pay, dashboard and balances queries.
- **Invalidation:** each mutation invalidates its related query keys (e.g. confirm payment → `planned`, `dashboard`, `accounts`) to reflect balances instantly.
- **Build order:** **v1 = Dashboard (safe-to-spend + to-pay) + Reports** (the two views chat does poorly). Backlog afterward: CRUDs (transactions, masters, recurring, budgets, goals) and import — feature by feature, operated through the agent in the meantime.

## Errors

- **API errors:** P1 maps the typed `domain` errors (`ValidationError`, `MissingRate`, `TransferImbalance`…) to 4xx with a structured body. `lib/api.ts` normalizes them to an `ApiError { status, code, message }`; the UI shows the `message` in a **toast** (mutations) or in `ErrorState` (page loads).
- **FX without a rate (`MissingRate`):** an actionable message that links to `/settings` to set `usd_cop`.
- **Import (P5):** the response carries **per-line-number** errors; `/import` lists them in a table (line + reason) and makes clear that the operation is **atomic** (all or nothing): nothing was imported if there were errors.
- **Expired session (401):** intercepted in the API client → clears the cache and redirects to `/login`.
- **Network / 5xx:** `ErrorState` with a *retry* button (React Query refetch); mutations roll back their optimistic update.
- **Form validation:** shape validation on the client (required fields, formats) for UX; the **authoritative** validation is always the backend's.

## Testing and "done" criteria

**v1 testing:** manual end-to-end testing against a real P1 API (aligned with general §11: "Frontend v1: manual testing; component tests later"). Smoke checklist per screen: load, CRUD, filters, money formatting, error handling.

**v1 "done" criteria (minimum acceptable, ADR-008):**
1. **Login works:** password → session → access to the shell; protected routes redirect when there is no session; logout clears.
2. **Dashboard shows the month's safe-to-spend + "to-pay"** with this-week/this-month toggle + total, and **allows marking paid** while reflecting the change (to-pay, safe-to-spend and balances update).
3. **`/reports` renders the retrospective monthly report** (ADR-019: net headline + envelope performance, by category/group, safe-to-spend at the bottom) with a month selector, degrading gracefully on a cold start (no MoM drift).

**Backlog (post-v1):** transaction CRUD and the rest of the screens (dedicated to-pay, recurring, budgets, goals, masters, import, settings) working against their endpoints — built feature by feature; operated through the agent in the meantime.

## Integration with other sub-projects

- **P1 (HTTP API + Auth):** hard dependency. The frontend's single point of contact with the backend; P6 starts as soon as P1 publishes the contract. Any contract change is reflected in `lib/api.ts` and its types.
- **P3 (Temporal engine):** enables `/to-pay`, the dashboard widget and the `/recurring` CRUD (endpoints `/planned`, `/recurring`). Until P3 lands, those views are stubbed.
- **P4 (Budgets + Goals):** enables `/budgets` and `/goals` and the dashboard's "goals" and "budgets at risk" cards.
- **P5 (Reports + Importer):** enables `/reports` (markdown + data render) and `/import` (with per-line errors from the validator).
- **P2 (MCP):** no coupling — an alternate entry path to the same backend; the frontend ignores it. (What the agent records still appears in the UI because they share the DB.)
- **P7 (Deployment):** the frontend is a `docker-compose` service; Caddy routes `quaestor.tudominio.com` → frontend and `/api/*` → FastAPI. The frontend reads the API base URL from an env var (`NEXT_PUBLIC_API_URL` or an internal proxy).
