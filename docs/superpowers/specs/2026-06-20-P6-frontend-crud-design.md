# Quaestor — P6 Frontend CRUD (Phase 1)

**Date:** 2026-06-20
**Depends on:** P6 v1 (login, dashboard, reports, `ui/` design system, `lib/api.ts`). Consumes the P1 HTTP API contract already exposed by the backend.
**Part of:** `2026-06-16-P6-frontend-design.md` (this realizes the "backlog screens" it documented).
**Governed by:** ADR-008 (MCP-first, full CRUD to backlog), ADR-024 (importer no UI, minimal settings), **ADR-025 (graduate backlog frontend CRUD to a built UI, in two phases)**.

---

## Objective

P6 v1 shipped two read-first views (dashboard + report) and left **all CRUD as backlog**, operated through the agent (ADR-008). This sub-project **graduates that backlog to a built UI** so the full user workflow is doable from the frontend — without abandoning the agent path, which stays a co-equal write channel.

Scope is decided by **ADR-025**, in **two phases**:

- **Phase 1 (this spec, before P7):** build frontend CRUD for **every entity the API already exposes today**. The frontend remains a **thin client of the P1 API**: zero business logic.
- **Phase 2 (later sub-project, possibly post-P7):** add the missing backend endpoints (goals CRUD + contribute, budgets assign/status, recurring edit/delete) and their management UI. Out of scope here.

`/import` stays out of the UI (ADR-024 reaffirmed): usable through the endpoint/MCP if ever needed.

## Scope

**Stack (unchanged):** Next.js (App Router) · TypeScript · Tailwind · the app-agnostic `ui/` module (ADR-0002) · React Query · pnpm (ADR-0003).

**Phase 1 screens (10), all against endpoints that exist today:**

- **Movement:** `/transactions` (full CRUD + transfer + filters), `/to-pay` (confirm / skip / plan one-off), `/recurring` (create + list + skip).
- **Masters:** `/accounts`, `/categories`, `/category-groups`, `/tags` (uniform CRUD).
- **Planning (read-only):** `/goals`, `/budgets`.
- **Setup:** `/settings` (default source account + manual FX override).

Plus the existing dashboard (`/`) and `/reports`, unchanged.

**Build approach (ADR-025 / brainstorming decision B — tiered):**
- A lightweight generic scaffold (`EntityFormDialog` + simple list) for the **four uniform masters** only.
- **Bespoke pages** for the entities with their own shape: transactions (filterable `DataTable` + transfer + limited-edit), to-pay (confirm flow), recurring (create + skip with interval engine).
- **Bespoke read-only** pages for goals and budgets.

**Out of scope (Phase 1):**
- Goals/budgets **management** and recurring **edit/delete** → Phase 2 (need backend endpoints).
- `/import` UI (ADR-024). Change-password (no `/auth/change-password` endpoint exists).
- Re-activating archived masters (no un-archive endpoint exists; archiving is one-way via the API) → Phase 2.
- Automated UI tests (manual testing in v1, general §11). Server-side pagination (the API has none; client-side paging, single-user volume).

## Contribution to the data model

**None.** Phase 1 neither creates nor migrates entities. It consumes the existing P1 REST contract. The TypeScript types in `lib/api.ts` are representations of the API JSON (cents as integers), updated when the contract changes — never tables.

## API surface consumed (verified against the backend)

| Entity | Endpoints used | CRUD reach in Phase 1 |
|---|---|---|
| Transactions | `GET /transactions` (filters: `date_from,date_to,account_id,category_id,tag,type,status`) · `GET /transactions/{id}` · `POST /transactions` · `POST /transactions/transfer` · `PATCH /transactions/{id}` · `DELETE /transactions/{id}` | Full (edit limited to `payee/notes/category_id/date`; delete is hard) |
| Planned (to-pay) | `GET /planned/to-pay?since&until` · `POST /planned` · `POST /planned/{id}/confirm` · `POST /planned/{id}/skip` | Full enough |
| Recurring | `GET /recurring` · `POST /recurring` · `POST /recurring/{id}/skip` | Create + list + skip (no edit/delete → Phase 2) |
| Accounts | `GET /accounts` · `GET /accounts/{id}` · `POST` · `PATCH` (name, type) · `DELETE` (= **archive**, soft) | CRUD; "delete" archives one-way |
| Categories | `GET` · `GET /{id}` · `POST` · `PATCH` · `DELETE` (= **archive**, soft) | CRUD; "delete" archives one-way |
| Category groups | `GET` · `POST` · `PATCH` · `DELETE` (= **archive**, soft) | CRUD; "delete" archives one-way |
| Tags | `GET` · `POST` · `PATCH` · `DELETE` (= **hard delete**, removes tx links) | CRUD; "delete" removes |
| Settings | `GET /settings` · `PATCH /settings` (`default_source_account_id`) | Thin |
| FX | `GET /fx` · `POST /fx` (`date`, `usd_cop`) | Manual override |
| Goals | `GET /goals/progress` | Read-only |
| Budgets | `GET /budgets/safe-to-spend?month` (+ `GET /reports?month` for envelopes) | Read-only |

## Components

New layout additions under `frontend/`:

```
app/(app)/
  layout.tsx                 # unchanged guard; AppShell rewritten to sidebar
  transactions/page.tsx
  to-pay/page.tsx
  recurring/page.tsx
  accounts/page.tsx
  categories/page.tsx
  category-groups/page.tsx
  tags/page.tsx
  goals/page.tsx             # read-only + Phase-2 banner
  budgets/page.tsx           # read-only + Phase-2 banner
  settings/page.tsx
ui/components/                # new app-agnostic primitives (ADR-0002)
  dialog.tsx  select.tsx  checkbox.tsx  textarea.tsx  dropdown-menu.tsx
components/                   # new shared, domain-aware
  app-shell.tsx              # rewritten: grouped sidebar + responsive drawer
  data-table.tsx             # generic: columns, filter bar, client paging, row actions
  entity-form-dialog.tsx     # schema-driven CRUD modal for the 4 uniform masters
  money-input.tsx            # text -> cents (display formatting only)
  entity-select.tsx          # Select bound to a React Query list (id <-> name)
  confirm-dialog.tsx         # destructive-action confirmation
  status-badge.tsx           # planned/posted/skipped, auto/manual, archived, on-track
lib/
  api.ts                     # grows ~7 -> ~35 methods + Create/Update/Out types + enums
  query.ts                   # query keys per entity + explicit invalidation map
```

- **`ui/` primitives** stay app-agnostic by contract (ADR-0002); the ESLint boundary forbids domain imports.
- **`DataTable`** encapsulates filters, client-side pagination and row actions; the page provides the fetch and column config.
- **`EntityFormDialog`** is a single CRUD modal parameterized by a field schema (name / type / options), avoiding ~4 near-identical master forms.
- **`MoneyInput`** parses user text into cents per currency (COP no decimals, dot thousands; USD two decimals). It is **presentation only** — no business arithmetic.
- **`AppShell`** is rewritten into a grouped left sidebar (Resumen / Movimiento / Planeación / Configuración), collapsing to a drawer on mobile; active highlight and logout preserved.

## Public interface (routes)

> Phase 1 adds the rows below to the P6 table. Every route requires a session (guard in `(app)/layout.tsx`); no valid cookie → redirect to `/login`.

| Route | What it does | Key endpoints |
|---|---|---|
| `/transactions` | Filterable table (date range, account, category, tag, type, status); create (normal/transfer, two-mode form); edit (payee/notes/category/date only); delete | `GET/POST/PATCH/DELETE /transactions`, `POST /transactions/transfer` |
| `/to-pay` | List `planned` (week/month toggle); confirm (actual amount + date); skip; plan a one-off payment | `GET /planned/to-pay`, `POST /planned`, `POST /planned/{id}/confirm`, `POST /planned/{id}/skip` |
| `/recurring` | List (interval rendered human-readable); create (type, auto/manual mode, every-N interval: unit + count, dates); skip an occurrence. Banner: edit/delete → Phase 2 | `GET/POST /recurring`, `POST /recurring/{id}/skip` |
| `/accounts` | CRUD (create: name/type/currency/opening balance; edit: name/type); archive (soft) + "show archived" filter | `…/accounts` |
| `/categories` | CRUD (name, group via `EntitySelect`, flags `is_income`/`exclude_from_budget`/`exclude_from_totals`); archive (soft) + filter | `…/categories` |
| `/category-groups` | CRUD (name, sort_order); archive (soft) | `…/category-groups` |
| `/tags` | CRUD (name); delete is real (removes tx links) — emphatic confirm | `…/tags` |
| `/goals` | Read-only: per goal saved vs target, % progress, ETA, on-track, monthly required, remaining. Banner: management → Phase 2 | `GET /goals/progress` |
| `/budgets` | Read-only: month selector + safe-to-spend breakdown + envelope status. Banner: assign → Phase 2 | `GET /budgets/safe-to-spend`, `GET /reports` |
| `/settings` | Default source account (`EntitySelect`) + manual USD→COP rate override | `GET/PATCH /settings`, `GET/POST /fx` |

## Logic and key rules

- **Zero business logic in the client.** Fetch + render + format. Net, %, FX `to_base`, balances, total-to-pay arrive resolved from the API; the frontend never recomputes them. `MoneyInput`'s text↔cents conversion is display formatting, not arithmetic on resolved values.
- **Transactions are append-mostly.** Create sets the immutable core (type, account, amount, currency); `PATCH` only touches `payee/notes/category_id/date`. The edit form disables the immutable fields with a note ("to change amount/account, delete and recreate"). `type=transfer` is rejected by `POST /transactions` → the create form routes transfers to `POST /transactions/transfer` (two legs).
- **Money input.** `amount` is always cents (int). `MoneyInput` shows the currency prefix and parses per currency. `fx_rate` is optional on create; omitted, the backend resolves the day's rate (ADR-011); a manual override is offered only when currency ≠ COP.
- **Archive vs delete (not uniform).** `DELETE` on accounts/categories/category-groups **archives** (soft, `archived=true`) — the UI labels it "Archivar" and offers a "show archived" filter; re-activation is **not** available via API (Phase 2). `DELETE` on tags is a **hard delete** that removes transaction links — the UI labels it "Eliminar" with an emphatic confirm. Transaction `DELETE` is a hard delete.
- **planned vs posted.** Distinguished by badge; confirming/skipping triggers the mutation and invalidates the to-pay, dashboard and balances queries.
- **Invalidation.** Each mutation declares its related keys in `lib/query.ts` (e.g. confirm payment → `planned, dashboard, accounts`; any transaction write → `transactions, dashboard, reports, accounts`) so balances reflect instantly. Optimistic updates where it improves perceived latency (mark paid, skip), rolled back on error.
- **Read-only planning.** `/goals` and `/budgets` render existing read endpoints with an explicit Phase-2 banner; their write paths stay agent-only until Phase 2.

## Errors

- **API errors:** `lib/api.ts` normalizes the typed backend errors to `ApiError { status, code, message }`. Mutations show `message` in a **toast**; page loads show `ErrorState` with retry (React Query refetch).
- **Expired session (401):** intercepted in the API client → clears the cache and redirects to `/login`.
- **`MissingRate`:** actionable toast linking to `/settings` to set `usd_cop`.
- **Form validation:** client-side shape validation (required fields, formats) for UX; the **authoritative** validation is always the backend's. Per-field server errors surfaced inline where the contract returns them, otherwise as a toast.

## Testing and "done" criteria

**Testing:** manual end-to-end against a real P1 API (general §11, ADR-008). Smoke checklist per screen: load · create · edit · archive/delete · filters · money formatting · error handling.

**Phase 1 "done" (minimum acceptable):**
1. **Navigation:** grouped sidebar renders all 12 routes, active highlight works, responsive drawer on mobile, logout clears.
2. **Transactions:** filterable table; create (normal + transfer); limited edit; delete — each reflecting in dashboard/balances.
3. **To-pay:** list + confirm + skip + plan one-off, reflecting changes.
4. **Recurring:** list + create + skip; Phase-2 banner present.
5. **Masters:** accounts/categories/category-groups/tags CRUD with the correct archive-vs-delete semantics and filters.
6. **Planning:** goals and budgets render read-only with Phase-2 banners.
7. **Settings:** default source account + FX override persist.
8. **Thin-client purity preserved:** no business arithmetic in the client (lint/review check on `lib/` + components).

## Integration with other sub-projects

- **P1 (HTTP API + Auth):** hard dependency; the single point of contact. Any contract change reflects in `lib/api.ts`.
- **P3 (Temporal):** enables `/to-pay` and `/recurring` (endpoints `/planned`, `/recurring`).
- **P4 (Budgets + Goals):** Phase 1 consumes only its **read** endpoints (`/goals/progress`, `/budgets/safe-to-spend`). **Phase 2 depends on P4 exposing** goals CRUD + contribute and budgets assign/status — those endpoints are the Phase-2 backend work.
- **P5 (Reports + Importer):** `/budgets` reuses `/reports` for envelope status. `/import` stays out (ADR-024).
- **P2 (MCP):** no coupling; a co-equal write path. What the agent records still appears in the UI (shared DB).
- **P7 (Deployment):** Phase 1 ships before P7; no new deployment surface (same Next.js service, same `NEXT_PUBLIC_API_URL`).
