# P6 Frontend CRUD (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 12-route Next.js UI that lets the user do the full day-to-day finance workflow (transactions, to-pay, recurring, masters CRUD, read-only goals/budgets, settings) directly from the frontend, as a thin client of the existing P1 HTTP API.

**Architecture:** Thin client — fetch + render + format, zero business logic. New app-agnostic form primitives go under `ui/` (ADR-0002 boundary). Domain-aware shared components (`DataTable`, `EntityFormDialog`, `MoneyInput`, `EntitySelect`, `ConfirmDialog`, `StatusBadge`, rewritten `AppShell`) go under `components/`. `lib/api.ts` grows to the full API surface; `lib/query.ts` holds query keys + an explicit invalidation map. Each screen is a client page under `app/(app)/`. The agent (MCP) stays a co-equal write path; the UI never replaces it.

**Tech Stack:** Next.js 16 (App Router) · React 19 · TypeScript (strict) · Tailwind v4 · `@base-ui/react` primitives · `@tanstack/react-query` v5 · `sonner` toasts · `date-fns` · `lucide-react` · pnpm.

## Global Constraints

- **Read the bundled Next.js docs before writing route/page code.** `frontend/AGENTS.md` warns this Next.js (16.2.9) differs from training data. Consult `frontend/node_modules/next/dist/docs/01-app/` for App Router specifics (route segments, `"use client"`, `next/navigation`) before each page task.
- **Thin client — no business arithmetic.** Net, %, FX `to_base`, balances, totals arrive resolved from the API. The client only fetches, renders, and formats. `MoneyInput` text↔cents conversion is the only numeric transform allowed, and it is presentation, not arithmetic on resolved values.
- **Money is always integer cents.** Every `amount`/`balance` is an int in the entity's own currency. Display via `formatCents(cents, currency)` (`lib/money.ts`). Never divide/multiply resolved amounts in pages.
- **`ui/` is app-agnostic (ADR-0002).** Files under `ui/**` may import only React, generic UI libs (`@base-ui/react`, `lucide-react`, `cva`), and `ui/` internals — never `@/app`, `@/lib`, `@/components`, `@/hooks`. The ESLint boundary fails `pnpm lint` if violated. Domain-aware components belong in `components/`.
- **All identifiers in English (ADR-0001).** User-facing copy is Spanish (Colombia), with correct diacritics.
- **API base path.** The browser calls same-origin `/api/...` (proxied by `app/api/[...path]/route.ts` to the backend). All `api.*` methods already prefix `/api`. Cookie auth (`quaestor_session`) flows automatically with `credentials: "include"`.
- **Error contract.** Backend errors are `{ error, detail }` → normalized to `ApiError { status, code, message }`. Mutations show `message` in a toast; page loads show `<ErrorState>` with retry. A 401 on any non-`/auth` call clears the React Query cache and redirects to `/login`.
- **Archive vs delete is not uniform.** `DELETE` on accounts/categories/category-groups = **archive** (soft, label "Archivar", offer "show archived"); re-activation is NOT available (Phase 2). `DELETE` on tags = **hard delete** (label "Eliminar", emphatic confirm). `DELETE` on transactions = hard delete (transfers cannot be deleted → 422).
- **Testing is manual (spec §"Testing", ADR-008).** No automated UI test runner is added in Phase 1 (adding one is a separate testing-strategy ADR). Each task's gate is: `pnpm lint` passes, `pnpm exec tsc --noEmit` passes, then the task's manual smoke checklist against a running backend + `pnpm dev`.
- **Verification commands run from `frontend/`.** `pnpm lint` · `pnpm exec tsc --noEmit` · `pnpm dev` (needs backend at `API_URL`, default `http://localhost:8000`).

## File Structure

```
app/(app)/
  layout.tsx                  # unchanged guard; wraps rewritten AppShell
  transactions/page.tsx       # NEW — filterable table + create + edit + delete
  to-pay/page.tsx             # NEW — planned queue: confirm/skip/plan one-off
  recurring/page.tsx          # NEW — list + create + skip + Phase-2 banner
  accounts/page.tsx           # NEW — master CRUD (archive)
  categories/page.tsx         # NEW — master CRUD (archive)
  category-groups/page.tsx    # NEW — master CRUD (archive)
  tags/page.tsx               # NEW — master CRUD (hard delete)
  goals/page.tsx              # NEW — read-only + Phase-2 banner
  budgets/page.tsx            # NEW — read-only + Phase-2 banner
  settings/page.tsx           # NEW — default source account + FX override
ui/components/                # NEW app-agnostic primitives (ADR-0002)
  dialog.tsx  select.tsx  checkbox.tsx  textarea.tsx  dropdown-menu.tsx
ui/index.ts                   # re-export the new primitives
components/                    # NEW domain-aware shared
  app-shell.tsx               # REWRITTEN — grouped sidebar + responsive drawer
  data-table.tsx              # generic: columns, filter bar, client paging, row actions
  entity-form-dialog.tsx      # schema-driven CRUD modal (4 uniform masters)
  money-input.tsx             # text -> cents (presentation only)
  entity-select.tsx           # Select bound to a React Query list (id <-> name)
  confirm-dialog.tsx          # destructive-action confirmation
  status-badge.tsx            # planned/posted/skipped, auto/manual, archived, on-track
lib/
  api.ts                      # MODIFIED — ~35 methods + Create/Update/Out types + enums + 401 hook
  query.ts                    # MODIFIED — query keys per entity + invalidation map
app/providers.tsx             # MODIFIED — register the 401 handler
```

---

## API Contract Reference (verified against backend)

All paths below are relative to `/api`. Money fields are int cents. `fx_rate`/`usd_cop` are decimal **strings** in JSON. Enums: `TxType=expense|income|transfer`, `TxStatus=planned|posted|skipped`, `AccountType=debit|credit|cash|savings`, `IntervalUnit=day|week|month|year`, `RecurringMode=auto|manual`, `OccurrenceStatus=posted|planned|skipped`, `source=manual|agent|import`.

| Resource | Method · path | Body / query → response |
|---|---|---|
| Transactions | `GET /transactions` | query `date_from,date_to,account_id,category_id,tag,type,status` (all optional) → `TransactionOut[]` |
| | `GET /transactions/{id}` | → `TransactionOut` |
| | `POST /transactions` (201) | `{type(expense\|income), account_id, amount, currency, date, payee?, category_id?, notes?, source?, fx_rate?}` → `TransactionOut`. `type=transfer` → 422 |
| | `POST /transactions/transfer` (201) | `{from_account_id, to_account_id, amount, currency, date, notes?, source?, fx_rate?}` → `{from_leg, to_leg}` |
| | `PATCH /transactions/{id}` | `{payee?, notes?, category_id?, date?}` only → `TransactionOut` |
| | `DELETE /transactions/{id}` (204) | hard delete; transfers → 422 |
| Planned | `GET /planned/to-pay` | query `since,until` (required) → `{ items: TransactionOut[], total_base }` |
| | `POST /planned` (201) | `{payee, amount, due_date, account_id, currency?, category_id?, notes?}` → `TransactionOut` |
| | `POST /planned/{id}/confirm` | `{amount?, date?}` → `TransactionOut` |
| | `POST /planned/{id}/skip` | no body → `TransactionOut` |
| Recurring | `GET /recurring` | query `active?` → `RecurringOut[]` |
| | `POST /recurring` (201) | `{name, type(expense\|income), mode(auto\|manual), amount, account_id, interval_unit, start_date, payee?, currency?, category_id?, interval_count?, end_date?}` → `RecurringOut` |
| | `POST /recurring/{id}/skip` | `{due_date}` → `OccurrenceOut` |
| Accounts | `GET /accounts` | query `archived?` (default false) → `AccountOut[]` |
| | `POST /accounts` (201) | `{name, type, currency, balance?}` (`balance`=opening, cents) → `AccountOut` |
| | `PATCH /accounts/{id}` | `{name?, type?}` only → `AccountOut` |
| | `DELETE /accounts/{id}` (204) | archive (soft) |
| Categories | `GET /categories` | query `archived?` → `CategoryOut[]` |
| | `POST /categories` (201) | `{name, group_id?, is_income?, exclude_from_budget?, exclude_from_totals?}` → `CategoryOut` |
| | `PATCH /categories/{id}` | any of `{name, group_id, is_income, exclude_from_budget, exclude_from_totals}` → `CategoryOut` |
| | `DELETE /categories/{id}` (204) | archive (soft) |
| Category groups | `GET /category-groups` | query `archived?` → `CategoryGroupOut[]` |
| | `POST /category-groups` (201) | `{name, sort_order?}` → `CategoryGroupOut` |
| | `PATCH /category-groups/{id}` | `{name?, sort_order?}` → `CategoryGroupOut` |
| | `DELETE /category-groups/{id}` (204) | archive (soft) |
| Tags | `GET /tags` | → `TagOut[]` |
| | `POST /tags` (201) | `{name}` (idempotent) → `TagOut` |
| | `PATCH /tags/{id}` | `{name}` → `TagOut` |
| | `DELETE /tags/{id}` (204) | hard delete (removes tx links) |
| Settings | `GET /settings` | → `SettingsOut` |
| | `PATCH /settings` | `{default_source_account_id?, base_currency?}` → `SettingsOut` |
| FX | `GET /fx` | query `date?` → `FxOut`; no rate → 409 `MissingRate` |
| | `POST /fx` (201) | `{date, usd_cop}` → `FxOut` |
| Goals | `GET /goals/progress` | → `GoalProgress[]` |
| Budgets | `GET /budgets/safe-to-spend` | query `month` (YYYY-MM, required) → `SafeToSpend` |

Out shapes (response objects):
- `TransactionOut` (already typed as `Transaction`): `id, date, payee, notes, type, status, amount, currency, fx_rate, to_base, account_id, category_id, transfer_group_id, source, created_at`.
- `AccountOut` (`Account`): `id, name, type, currency, balance, archived`.
- `CategoryOut`: `id, name, group_id:number|null, is_income, exclude_from_budget, exclude_from_totals, archived`.
- `CategoryGroupOut`: `id, name, sort_order, archived`.
- `TagOut`: `id, name`.
- `RecurringOut`: `id, name, payee, type, mode, amount, currency, category_id:number|null, account_id, interval_unit, interval_count, start_date, end_date:string|null, active`.
- `OccurrenceOut`: `id, recurring_id, due_date, status, transaction_id:number|null`.
- `SettingsOut`: `id, base_currency, default_source_account_id:number|null`.
- `FxOut`: `date, usd_cop` (string).

---

## Phase A — Foundation

### Task 1: Grow `lib/api.ts` to the full API surface

**Files:**
- Modify: `frontend/lib/api.ts` (replace whole file)

**Interfaces:**
- Produces: enums `AccountType`, `IntervalUnit`, `RecurringMode`, `OccurrenceStatus`; interfaces `Category`, `CategoryGroup`, `Tag`, `Recurring`, `Occurrence`, `Settings`, `Fx`, `TransferOut`, and all `*Create`/`*Update`/`*In` payload types; the `api` object with all methods (signatures below); `setUnauthorizedHandler(fn)`. Consumed by every later task.

- [ ] **Step 1: Replace `lib/api.ts` with the full surface**

```typescript
// Types mirror the P1 /api JSON contract (cents are integers).
export type TxType = "income" | "expense" | "transfer";
export type TxStatus = "planned" | "posted" | "skipped";
export type AccountType = "debit" | "credit" | "cash" | "savings";
export type IntervalUnit = "day" | "week" | "month" | "year";
export type RecurringMode = "auto" | "manual";
export type RecurringType = "expense" | "income";
export type OccurrenceStatus = "posted" | "planned" | "skipped";

export interface Transaction {
  id: number;
  date: string;
  payee: string;
  notes: string | null;
  type: TxType;
  status: TxStatus;
  amount: number;
  currency: string;
  fx_rate: string;
  to_base: number;
  account_id: number;
  category_id: number | null;
  transfer_group_id: string | null;
  source: string;
  created_at: string;
}

export interface Account {
  id: number;
  name: string;
  type: AccountType;
  currency: string;
  balance: number;
  archived: boolean;
}

export interface Category {
  id: number;
  name: string;
  group_id: number | null;
  is_income: boolean;
  exclude_from_budget: boolean;
  exclude_from_totals: boolean;
  archived: boolean;
}

export interface CategoryGroup {
  id: number;
  name: string;
  sort_order: number;
  archived: boolean;
}

export interface Tag {
  id: number;
  name: string;
}

export interface Recurring {
  id: number;
  name: string;
  payee: string;
  type: RecurringType;
  mode: RecurringMode;
  amount: number;
  currency: string;
  category_id: number | null;
  account_id: number;
  interval_unit: IntervalUnit;
  interval_count: number;
  start_date: string;
  end_date: string | null;
  active: boolean;
}

export interface Occurrence {
  id: number;
  recurring_id: number;
  due_date: string;
  status: OccurrenceStatus;
  transaction_id: number | null;
}

export interface Settings {
  id: number;
  base_currency: string;
  default_source_account_id: number | null;
}

export interface Fx {
  date: string;
  usd_cop: string;
}

export interface TransferOut {
  from_leg: Transaction;
  to_leg: Transaction;
}

export interface ToPay {
  items: Transaction[];
  total_base: number;
}

export interface CommittedItem {
  kind: string;
  name: string;
  date: string;
  amount: number;
}

export interface SafeToSpend {
  year_month: string;
  income_forecast: number;
  committed: number;
  assigned_envelopes: number;
  free: number;
  committed_breakdown: CommittedItem[];
}

export interface GoalProgress {
  goal_id: number;
  name: string;
  type: string;
  monthly_amount: number;
  saved: number;
  target_amount: number | null;
  deadline: string | null;
  monthly_required: number | null;
  on_track: boolean | null;
  eta: string | null;
  remaining: number | null;
}

export interface EnvelopesSummary {
  n_green: number;
  n_red: number;
  rollover_generated: number;
}
export interface EnvelopeLine {
  category: string;
  allocated: number;
  rollover_in: number;
  spent: number;
  available: number;
  status: string;
}
export interface CategorySection {
  category: string;
  group: string | null;
  total: number;
  pct: number;
}
export interface GroupSection {
  group: string;
  total: number;
  pct: number;
}
export interface GoalLine {
  name: string;
  accumulated: number;
  target: number | null;
  eta: string | null;
  on_track: boolean | null;
}
export interface AccountBalance {
  account: string;
  currency: string;
  balance: number;
}
export interface DriftMoM {
  prev_month: string;
  income_abs: number;
  income_pct: number | null;
  expense_abs: number;
  expense_pct: number | null;
  net_abs: number;
  net_pct: number | null;
}
export interface MonthlyReport {
  month: string;
  income: number;
  expense: number;
  net: number;
  envelopes_summary: EnvelopesSummary;
  envelopes: EnvelopeLine[];
  by_category: CategorySection[];
  by_group: GroupSection[];
  goals: GoalLine[];
  balances: AccountBalance[];
  drift_mom: DriftMoM | null;
  usd_share: number;
  pending: string[];
  safe_to_spend: SafeToSpend;
  markdown: string;
}

// ---- Request payloads (only fields the API accepts) ----
export interface TransactionFilters {
  date_from?: string;
  date_to?: string;
  account_id?: number;
  category_id?: number;
  tag?: string;
  type?: TxType;
  status?: TxStatus;
}
export interface TransactionCreate {
  type: "expense" | "income";
  account_id: number;
  amount: number;
  currency: string;
  date: string;
  payee?: string;
  category_id?: number | null;
  notes?: string | null;
  fx_rate?: string;
}
export interface TransferCreate {
  from_account_id: number;
  to_account_id: number;
  amount: number;
  currency: string;
  date: string;
  notes?: string | null;
  fx_rate?: string;
}
export interface TransactionUpdate {
  payee?: string;
  notes?: string | null;
  category_id?: number | null;
  date?: string;
}
export interface PlanPaymentCreate {
  payee: string;
  amount: number;
  due_date: string;
  account_id: number;
  currency?: string;
  category_id?: number | null;
  notes?: string | null;
}
export interface ConfirmPaymentBody {
  amount?: number;
  date?: string;
}
export interface RecurringCreate {
  name: string;
  type: RecurringType;
  mode: RecurringMode;
  amount: number;
  account_id: number;
  interval_unit: IntervalUnit;
  start_date: string;
  payee?: string;
  currency?: string;
  category_id?: number | null;
  interval_count?: number;
  end_date?: string | null;
}
export interface AccountCreate {
  name: string;
  type: AccountType;
  currency: string;
  balance?: number;
}
export interface AccountUpdate {
  name?: string;
  type?: AccountType;
}
export interface CategoryCreate {
  name: string;
  group_id?: number | null;
  is_income?: boolean;
  exclude_from_budget?: boolean;
  exclude_from_totals?: boolean;
}
export interface CategoryUpdate {
  name?: string;
  group_id?: number | null;
  is_income?: boolean;
  exclude_from_budget?: boolean;
  exclude_from_totals?: boolean;
}
export interface CategoryGroupCreate {
  name: string;
  sort_order?: number;
}
export interface CategoryGroupUpdate {
  name?: string;
  sort_order?: number;
}
export interface TagCreate {
  name: string;
}
export interface TagUpdate {
  name: string;
}
export interface SettingsUpdate {
  default_source_account_id?: number | null;
  base_currency?: string;
}
export interface FxCreate {
  date: string;
  usd_cop: string;
}

export class ApiError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

// 401 interceptor: the app registers a handler (clear cache + redirect) in
// app/providers.tsx. lib/ stays free of React/router imports.
let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null) {
  onUnauthorized = fn;
}

function qs(params: Record<string, string | number | boolean | undefined>): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") usp.set(k, String(v));
  }
  const s = usp.toString();
  return s ? `?${s}` : "";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (res.status === 401 && !path.startsWith("/auth")) {
    onUnauthorized?.();
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const code = (data && data.error) || "Error";
    const message = (data && data.detail) || `Request failed (${res.status})`;
    throw new ApiError(res.status, code, message);
  }
  return data as T;
}

export const api = {
  // auth
  login: (password: string) =>
    request<{ ok: boolean }>("/auth/login", { method: "POST", body: JSON.stringify({ password }) }),
  logout: () => request<{ ok: boolean }>("/auth/logout", { method: "POST" }),
  me: () => request<{ authenticated: boolean }>("/auth/me"),

  // transactions
  listTransactions: (filters: TransactionFilters = {}) =>
    request<Transaction[]>(`/transactions${qs(filters)}`),
  getTransaction: (id: number) => request<Transaction>(`/transactions/${id}`),
  createTransaction: (body: TransactionCreate) =>
    request<Transaction>("/transactions", { method: "POST", body: JSON.stringify(body) }),
  createTransfer: (body: TransferCreate) =>
    request<TransferOut>("/transactions/transfer", { method: "POST", body: JSON.stringify(body) }),
  updateTransaction: (id: number, body: TransactionUpdate) =>
    request<Transaction>(`/transactions/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteTransaction: (id: number) =>
    request<void>(`/transactions/${id}`, { method: "DELETE" }),

  // planned / to-pay
  toPay: (since: string, until: string) =>
    request<ToPay>(`/planned/to-pay${qs({ since, until })}`),
  planPayment: (body: PlanPaymentCreate) =>
    request<Transaction>("/planned", { method: "POST", body: JSON.stringify(body) }),
  confirmPayment: (id: number, body: ConfirmPaymentBody = {}) =>
    request<Transaction>(`/planned/${id}/confirm`, { method: "POST", body: JSON.stringify(body) }),
  skipPlanned: (id: number) =>
    request<Transaction>(`/planned/${id}/skip`, { method: "POST", body: JSON.stringify({}) }),

  // recurring
  listRecurring: (active?: boolean) => request<Recurring[]>(`/recurring${qs({ active })}`),
  createRecurring: (body: RecurringCreate) =>
    request<Recurring>("/recurring", { method: "POST", body: JSON.stringify(body) }),
  skipRecurring: (id: number, due_date: string) =>
    request<Occurrence>(`/recurring/${id}/skip`, { method: "POST", body: JSON.stringify({ due_date }) }),

  // accounts
  listAccounts: (archived = false) => request<Account[]>(`/accounts${qs({ archived })}`),
  getAccount: (id: number) => request<Account>(`/accounts/${id}`),
  createAccount: (body: AccountCreate) =>
    request<Account>("/accounts", { method: "POST", body: JSON.stringify(body) }),
  updateAccount: (id: number, body: AccountUpdate) =>
    request<Account>(`/accounts/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  archiveAccount: (id: number) => request<void>(`/accounts/${id}`, { method: "DELETE" }),

  // categories
  listCategories: (archived = false) => request<Category[]>(`/categories${qs({ archived })}`),
  createCategory: (body: CategoryCreate) =>
    request<Category>("/categories", { method: "POST", body: JSON.stringify(body) }),
  updateCategory: (id: number, body: CategoryUpdate) =>
    request<Category>(`/categories/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  archiveCategory: (id: number) => request<void>(`/categories/${id}`, { method: "DELETE" }),

  // category groups
  listCategoryGroups: (archived = false) =>
    request<CategoryGroup[]>(`/category-groups${qs({ archived })}`),
  createCategoryGroup: (body: CategoryGroupCreate) =>
    request<CategoryGroup>("/category-groups", { method: "POST", body: JSON.stringify(body) }),
  updateCategoryGroup: (id: number, body: CategoryGroupUpdate) =>
    request<CategoryGroup>(`/category-groups/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  archiveCategoryGroup: (id: number) =>
    request<void>(`/category-groups/${id}`, { method: "DELETE" }),

  // tags
  listTags: () => request<Tag[]>("/tags"),
  createTag: (body: TagCreate) =>
    request<Tag>("/tags", { method: "POST", body: JSON.stringify(body) }),
  updateTag: (id: number, body: TagUpdate) =>
    request<Tag>(`/tags/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteTag: (id: number) => request<void>(`/tags/${id}`, { method: "DELETE" }),

  // settings
  getSettings: () => request<Settings>("/settings"),
  updateSettings: (body: SettingsUpdate) =>
    request<Settings>("/settings", { method: "PATCH", body: JSON.stringify(body) }),

  // fx
  getFx: (date?: string) => request<Fx>(`/fx${qs({ date })}`),
  setFx: (body: FxCreate) =>
    request<Fx>("/fx", { method: "POST", body: JSON.stringify(body) }),

  // planning reads
  safeToSpend: (month: string) => request<SafeToSpend>(`/budgets/safe-to-spend${qs({ month })}`),
  goalsProgress: () => request<GoalProgress[]>("/goals/progress"),
  report: (month: string) => request<MonthlyReport>(`/reports${qs({ month })}`),
};
```

- [ ] **Step 2: Typecheck and lint**

Run from `frontend/`: `pnpm exec tsc --noEmit && pnpm lint`
Expected: PASS (existing `dashboard`/`reports`/`to-pay-widget` still compile — they use `api.toPay`, `api.safeToSpend`, `api.goalsProgress`, `api.report`, `api.confirmPayment`, `api.accounts`). NOTE: the old `api.accounts()` was renamed to `api.listAccounts()`. Grep for callers: `grep -rn "api.accounts(" app components`. Update each call site (`app/(app)/page.tsx`) from `api.accounts()` to `api.listAccounts()` in this step, and re-run.

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/api.ts frontend/app
git commit -m "feat(frontend): grow api client to full P1 CRUD surface"
```

---

### Task 2: Query keys + invalidation map (`lib/query.ts`) and 401 wiring

**Files:**
- Modify: `frontend/lib/query.ts` (replace whole file)
- Modify: `frontend/app/providers.tsx`

**Interfaces:**
- Produces: `qk` (query-key factory per entity), `invalidate(qc, group)` where `group` is a key of `INVALIDATION`. Consumed by every mutation in later tasks.

- [ ] **Step 1: Replace `lib/query.ts`**

```typescript
import type { QueryClient } from "@tanstack/react-query";
import type { TransactionFilters } from "@/lib/api";

// Query-key factory. First element is the entity root used for broad invalidation.
export const qk = {
  transactions: (filters: TransactionFilters = {}) => ["transactions", filters] as const,
  transaction: (id: number) => ["transactions", "detail", id] as const,
  toPay: (since: string, until: string) => ["planned", "to-pay", since, until] as const,
  recurring: (active?: boolean) => ["recurring", active ?? "all"] as const,
  accounts: (archived = false) => ["accounts", archived] as const,
  account: (id: number) => ["accounts", "detail", id] as const,
  categories: (archived = false) => ["categories", archived] as const,
  categoryGroups: (archived = false) => ["category-groups", archived] as const,
  tags: () => ["tags"] as const,
  settings: () => ["settings"] as const,
  fx: (date?: string) => ["fx", date ?? "latest"] as const,
  safeToSpend: (month: string) => ["budgets", "safe-to-spend", month] as const,
  goalsProgress: () => ["goals", "progress"] as const,
  report: (month: string) => ["reports", month] as const,
};

// Each mutation declares the entity roots it must invalidate so derived numbers
// (balances, dashboard, reports) refresh instantly. Roots match qk[...][0].
export const INVALIDATION = {
  transactionWrite: [["transactions"], ["reports"], ["accounts"], ["budgets"], ["planned"]],
  plannedWrite: [["planned"], ["reports"], ["accounts"], ["budgets"]],
  recurringWrite: [["recurring"], ["planned"], ["reports"], ["budgets"]],
  accountWrite: [["accounts"], ["settings"], ["reports"], ["budgets"]],
  categoryWrite: [["categories"], ["reports"], ["budgets"]],
  categoryGroupWrite: [["category-groups"], ["categories"], ["reports"]],
  tagWrite: [["tags"], ["transactions"]],
  settingsWrite: [["settings"]],
  fxWrite: [["fx"], ["reports"], ["budgets"], ["accounts"]],
} as const;

export type InvalidationGroup = keyof typeof INVALIDATION;

export function invalidate(qc: QueryClient, group: InvalidationGroup) {
  for (const key of INVALIDATION[group]) {
    qc.invalidateQueries({ queryKey: key });
  }
}
```

- [ ] **Step 2: Wire the 401 handler in `app/providers.tsx`**

Replace the file with:

```typescript
"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Toaster } from "@/ui";
import { setUnauthorizedHandler } from "@/lib/api";

export function Providers({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [client] = useState(
    () => new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 1 } } }),
  );

  useEffect(() => {
    setUnauthorizedHandler(() => {
      client.clear();
      router.replace("/login");
      router.refresh();
    });
    return () => setUnauthorizedHandler(null);
  }, [client, router]);

  return (
    <QueryClientProvider client={client}>
      {children}
      <Toaster richColors position="top-right" />
    </QueryClientProvider>
  );
}
```

- [ ] **Step 3: Typecheck, lint, commit**

Run from `frontend/`: `pnpm exec tsc --noEmit && pnpm lint` → PASS. Update `app/(app)/page.tsx` and `components/to-pay-widget.tsx` to use `qk.accounts(false)` if they referenced `qk.accounts()` with no arg (the signature now takes an optional `archived`; `qk.accounts()` still works via default). Then:

```bash
git add frontend/lib/query.ts frontend/app/providers.tsx
git commit -m "feat(frontend): per-entity query keys + invalidation map + 401 handler"
```

---

### Task 3: `ui/components/dialog.tsx` primitive

**Files:**
- Create: `frontend/ui/components/dialog.tsx`
- Modify: `frontend/ui/index.ts`

**Interfaces:**
- Produces: `Dialog`, `DialogTrigger`, `DialogPortal`, `DialogBackdrop`, `DialogPopup`, `DialogTitle`, `DialogDescription`, `DialogClose`. Thin wrappers over `@base-ui/react/dialog`, styled with token classes. Consumed by `EntityFormDialog`, `ConfirmDialog`, transaction forms, to-pay confirm.

- [ ] **Step 1: Create `ui/components/dialog.tsx`**

```tsx
"use client";

import { Dialog as DialogPrimitive } from "@base-ui/react/dialog";
import { cn } from "../lib/cn";

function Dialog(props: DialogPrimitive.Root.Props) {
  return <DialogPrimitive.Root {...props} />;
}

function DialogTrigger(props: DialogPrimitive.Trigger.Props) {
  return <DialogPrimitive.Trigger data-slot="dialog-trigger" {...props} />;
}

function DialogClose(props: DialogPrimitive.Close.Props) {
  return <DialogPrimitive.Close data-slot="dialog-close" {...props} />;
}

function DialogPortal(props: DialogPrimitive.Portal.Props) {
  return <DialogPrimitive.Portal {...props} />;
}

function DialogBackdrop({ className, ...props }: DialogPrimitive.Backdrop.Props) {
  return (
    <DialogPrimitive.Backdrop
      data-slot="dialog-backdrop"
      className={cn(
        "fixed inset-0 z-50 bg-black/40 transition-opacity duration-150 data-[ending-style]:opacity-0 data-[starting-style]:opacity-0",
        className,
      )}
      {...props}
    />
  );
}

function DialogPopup({ className, children, ...props }: DialogPrimitive.Popup.Props) {
  return (
    <DialogPortal>
      <DialogBackdrop />
      <DialogPrimitive.Popup
        data-slot="dialog-popup"
        className={cn(
          "fixed top-1/2 left-1/2 z-50 grid w-[calc(100vw-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 gap-4 rounded-xl border border-border bg-card p-6 shadow-lg transition-all duration-150 data-[ending-style]:scale-95 data-[ending-style]:opacity-0 data-[starting-style]:scale-95 data-[starting-style]:opacity-0",
          className,
        )}
        {...props}
      >
        {children}
      </DialogPrimitive.Popup>
    </DialogPortal>
  );
}

function DialogTitle({ className, ...props }: DialogPrimitive.Title.Props) {
  return (
    <DialogPrimitive.Title
      data-slot="dialog-title"
      className={cn("text-base font-semibold tracking-tight", className)}
      {...props}
    />
  );
}

function DialogDescription({ className, ...props }: DialogPrimitive.Description.Props) {
  return (
    <DialogPrimitive.Description
      data-slot="dialog-description"
      className={cn("text-sm text-muted-foreground", className)}
      {...props}
    />
  );
}

export {
  Dialog,
  DialogTrigger,
  DialogClose,
  DialogPortal,
  DialogBackdrop,
  DialogPopup,
  DialogTitle,
  DialogDescription,
};
```

- [ ] **Step 2: Re-export from `ui/index.ts`**

Append to `frontend/ui/index.ts`:

```typescript
export {
  Dialog,
  DialogTrigger,
  DialogClose,
  DialogPortal,
  DialogBackdrop,
  DialogPopup,
  DialogTitle,
  DialogDescription,
} from "./components/dialog";
```

- [ ] **Step 3: Typecheck + lint (boundary check)**

Run from `frontend/`: `pnpm exec tsc --noEmit && pnpm lint` → PASS. The lint MUST pass the `ui/**` boundary rule (no `@/` imports). If base-ui part names differ, verify against `frontend/node_modules/@base-ui/react/dialog/index.d.ts`.

- [ ] **Step 4: Commit**

```bash
git add frontend/ui/components/dialog.tsx frontend/ui/index.ts
git commit -m "feat(ui): add Dialog primitive over base-ui"
```

---

### Task 4: `ui/components/select.tsx` primitive

**Files:**
- Create: `frontend/ui/components/select.tsx`
- Modify: `frontend/ui/index.ts`

**Interfaces:**
- Produces: a composed `Select` component:
  `Select({ value: string | null, onValueChange: (v: string | null) => void, items: { value: string; label: string }[], placeholder?: string, disabled?: boolean, id?: string, "aria-label"?: string })`.
  Values are strings (callers convert ids via `String(id)` / `Number(v)`). Consumed by `EntitySelect`, `EntityFormDialog`, transaction/recurring forms, filters.

- [ ] **Step 1: Create `ui/components/select.tsx`**

```tsx
"use client";

import { Select as SelectPrimitive } from "@base-ui/react/select";
import { Check, ChevronsUpDown } from "lucide-react";
import { cn } from "../lib/cn";

export interface SelectItem {
  value: string;
  label: string;
}

export interface SelectProps {
  value: string | null;
  onValueChange: (value: string | null) => void;
  items: SelectItem[];
  placeholder?: string;
  disabled?: boolean;
  id?: string;
  "aria-label"?: string;
  className?: string;
}

function Select({
  value,
  onValueChange,
  items,
  placeholder = "Selecciona…",
  disabled,
  id,
  className,
  "aria-label": ariaLabel,
}: SelectProps) {
  const labelFor = (v: string | null) => items.find((it) => it.value === v)?.label ?? null;
  return (
    <SelectPrimitive.Root
      value={value}
      onValueChange={(v) => onValueChange(v)}
      disabled={disabled}
      items={items.reduce<Record<string, string>>((acc, it) => {
        acc[it.value] = it.label;
        return acc;
      }, {})}
    >
      <SelectPrimitive.Trigger
        id={id}
        aria-label={ariaLabel}
        data-slot="select-trigger"
        className={cn(
          "flex h-8 w-full items-center justify-between gap-2 rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-50 data-[popup-open]:border-ring",
          className,
        )}
      >
        <SelectPrimitive.Value>
          {(v: string | null) =>
            labelFor(v) ?? <span className="text-muted-foreground">{placeholder}</span>
          }
        </SelectPrimitive.Value>
        <SelectPrimitive.Icon>
          <ChevronsUpDown className="size-4 text-muted-foreground" />
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>

      <SelectPrimitive.Portal>
        <SelectPrimitive.Positioner sideOffset={4} className="z-50">
          <SelectPrimitive.Popup className="max-h-72 min-w-[var(--anchor-width)] overflow-y-auto rounded-lg border border-border bg-popover p-1 text-sm shadow-md outline-none">
            {items.map((it) => (
              <SelectPrimitive.Item
                key={it.value}
                value={it.value}
                className="flex cursor-default items-center justify-between gap-2 rounded-md px-2 py-1.5 outline-none data-[highlighted]:bg-muted"
              >
                <SelectPrimitive.ItemText>{it.label}</SelectPrimitive.ItemText>
                <SelectPrimitive.ItemIndicator>
                  <Check className="size-4" />
                </SelectPrimitive.ItemIndicator>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Popup>
        </SelectPrimitive.Positioner>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
}

export { Select };
```

- [ ] **Step 2: Re-export from `ui/index.ts`**

```typescript
export { Select } from "./components/select";
export type { SelectItem, SelectProps } from "./components/select";
```

- [ ] **Step 3: Typecheck + lint** → PASS. If `SelectPrimitive.Value`'s render-function signature or `items` prop shape mismatches, check `frontend/node_modules/@base-ui/react/select/root/SelectRoot.d.ts` (it accepts `items` as `Record<string, ReactNode>` or an array, and `value`/`onValueChange`).

- [ ] **Step 4: Commit**

```bash
git add frontend/ui/components/select.tsx frontend/ui/index.ts
git commit -m "feat(ui): add Select primitive over base-ui"
```

---

### Task 5: `ui/components/checkbox.tsx` primitive

**Files:**
- Create: `frontend/ui/components/checkbox.tsx`
- Modify: `frontend/ui/index.ts`

**Interfaces:**
- Produces: `Checkbox({ checked: boolean, onCheckedChange: (checked: boolean) => void, id?: string, disabled?: boolean, className?: string })`. Consumed by `EntityFormDialog` (category flags) and forms.

- [ ] **Step 1: Create `ui/components/checkbox.tsx`**

```tsx
"use client";

import { Checkbox as CheckboxPrimitive } from "@base-ui/react/checkbox";
import { Check } from "lucide-react";
import { cn } from "../lib/cn";

export interface CheckboxProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  id?: string;
  disabled?: boolean;
  className?: string;
}

function Checkbox({ checked, onCheckedChange, id, disabled, className }: CheckboxProps) {
  return (
    <CheckboxPrimitive.Root
      id={id}
      checked={checked}
      onCheckedChange={(c) => onCheckedChange(c)}
      disabled={disabled}
      data-slot="checkbox"
      className={cn(
        "flex size-4 shrink-0 items-center justify-center rounded border border-input bg-transparent outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 data-[checked]:border-primary data-[checked]:bg-primary data-[checked]:text-primary-foreground disabled:pointer-events-none disabled:opacity-50",
        className,
      )}
    >
      <CheckboxPrimitive.Indicator>
        <Check className="size-3" />
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  );
}

export { Checkbox };
```

- [ ] **Step 2: Re-export from `ui/index.ts`**

```typescript
export { Checkbox } from "./components/checkbox";
export type { CheckboxProps } from "./components/checkbox";
```

- [ ] **Step 3: Typecheck + lint** → PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/ui/components/checkbox.tsx frontend/ui/index.ts
git commit -m "feat(ui): add Checkbox primitive over base-ui"
```

---

### Task 6: `ui/components/textarea.tsx` primitive

**Files:**
- Create: `frontend/ui/components/textarea.tsx`
- Modify: `frontend/ui/index.ts`

**Interfaces:**
- Produces: `Textarea` — a styled native `<textarea>` (base-ui has no textarea part). Props are native `React.ComponentProps<"textarea">`. Consumed by forms with a `notes` field.

- [ ] **Step 1: Create `ui/components/textarea.tsx`**

```tsx
import * as React from "react";
import { cn } from "../lib/cn";

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "min-h-16 w-full rounded-lg border border-input bg-transparent px-2.5 py-1.5 text-sm outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}

export { Textarea };
```

- [ ] **Step 2: Re-export from `ui/index.ts`**

```typescript
export { Textarea } from "./components/textarea";
```

- [ ] **Step 3: Typecheck + lint** → PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/ui/components/textarea.tsx frontend/ui/index.ts
git commit -m "feat(ui): add Textarea primitive"
```

---

### Task 7: `ui/components/dropdown-menu.tsx` primitive

**Files:**
- Create: `frontend/ui/components/dropdown-menu.tsx`
- Modify: `frontend/ui/index.ts`

**Interfaces:**
- Produces: `DropdownMenu`, `DropdownMenuTrigger`, `DropdownMenuContent`, `DropdownMenuItem`. Thin wrappers over `@base-ui/react/menu`. `DropdownMenuItem` accepts `onClick` and an optional `variant="destructive"`. Consumed by `DataTable` row actions and `AppShell` (mobile).

- [ ] **Step 1: Create `ui/components/dropdown-menu.tsx`**

```tsx
"use client";

import { Menu as MenuPrimitive } from "@base-ui/react/menu";
import { cn } from "../lib/cn";

function DropdownMenu(props: MenuPrimitive.Root.Props) {
  return <MenuPrimitive.Root {...props} />;
}

function DropdownMenuTrigger(props: MenuPrimitive.Trigger.Props) {
  return <MenuPrimitive.Trigger data-slot="dropdown-trigger" {...props} />;
}

function DropdownMenuContent({ className, children, ...props }: MenuPrimitive.Popup.Props) {
  return (
    <MenuPrimitive.Portal>
      <MenuPrimitive.Positioner sideOffset={4} align="end" className="z-50">
        <MenuPrimitive.Popup
          data-slot="dropdown-content"
          className={cn(
            "min-w-36 rounded-lg border border-border bg-popover p-1 text-sm shadow-md outline-none",
            className,
          )}
          {...props}
        >
          {children}
        </MenuPrimitive.Popup>
      </MenuPrimitive.Positioner>
    </MenuPrimitive.Portal>
  );
}

function DropdownMenuItem({
  className,
  variant = "default",
  ...props
}: MenuPrimitive.Item.Props & { variant?: "default" | "destructive" }) {
  return (
    <MenuPrimitive.Item
      data-slot="dropdown-item"
      className={cn(
        "flex cursor-default items-center gap-2 rounded-md px-2 py-1.5 outline-none data-[highlighted]:bg-muted",
        variant === "destructive" && "text-destructive data-[highlighted]:bg-destructive/10",
        className,
      )}
      {...props}
    />
  );
}

export { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem };
```

- [ ] **Step 2: Re-export from `ui/index.ts`**

```typescript
export {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "./components/dropdown-menu";
```

- [ ] **Step 3: Typecheck + lint** → PASS. Verify `Menu` part names against `frontend/node_modules/@base-ui/react/menu/index.d.ts` (`Root, Trigger, Portal, Positioner, Popup, Item`).

- [ ] **Step 4: Commit**

```bash
git add frontend/ui/components/dropdown-menu.tsx frontend/ui/index.ts
git commit -m "feat(ui): add DropdownMenu primitive over base-ui"
```

---

### Task 8: `components/money-input.tsx` (text → cents)

**Files:**
- Create: `frontend/components/money-input.tsx`

**Interfaces:**
- Produces:
  - `parseMoneyToCents(text: string, currency: string): number | null` — pure helper, exported for reuse.
  - `MoneyInput({ currency: string, value: number | null, onChange: (cents: number | null) => void, id?: string, placeholder?: string, disabled?: boolean })`.
  Presentation-only: COP = integer pesos × 100; USD = major × 100 rounded. Consumed by transaction/transfer/plan/recurring forms, accounts opening balance, FX is NOT money (decimal string).

- [ ] **Step 1: Create `components/money-input.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { Input } from "@/ui";

/**
 * Parse user text into integer cents for a currency. Presentation-only — never
 * applied to amounts already resolved by the API.
 * COP: digits only, value is whole pesos -> ×100. USD: one decimal point allowed,
 * major units -> ×100 rounded. Returns null for empty/invalid input.
 */
export function parseMoneyToCents(text: string, currency: string): number | null {
  const trimmed = text.trim();
  if (trimmed === "") return null;
  if (currency === "USD") {
    const cleaned = trimmed.replace(/[^0-9.]/g, "");
    if (cleaned === "" || cleaned === ".") return null;
    const major = Number.parseFloat(cleaned);
    if (!Number.isFinite(major)) return null;
    return Math.round(major * 100);
  }
  const digits = trimmed.replace(/[^0-9]/g, "");
  if (digits === "") return null;
  const pesos = Number.parseInt(digits, 10);
  if (!Number.isFinite(pesos)) return null;
  return pesos * 100;
}

function centsToText(cents: number | null, currency: string): string {
  if (cents === null) return "";
  if (currency === "USD") return (cents / 100).toString();
  return Math.round(cents / 100).toString();
}

export function MoneyInput({
  currency,
  value,
  onChange,
  id,
  placeholder,
  disabled,
}: {
  currency: string;
  value: number | null;
  onChange: (cents: number | null) => void;
  id?: string;
  placeholder?: string;
  disabled?: boolean;
}) {
  const [text, setText] = useState(() => centsToText(value, currency));

  // Re-sync when the external value or currency changes (e.g. form reset, currency switch).
  useEffect(() => {
    setText(centsToText(value, currency));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currency]);

  const prefix = currency === "USD" ? "US$" : "$";

  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-muted-foreground tabular-nums">{prefix}</span>
      <Input
        id={id}
        inputMode={currency === "USD" ? "decimal" : "numeric"}
        value={text}
        placeholder={placeholder}
        disabled={disabled}
        onChange={(e) => {
          const next = e.target.value;
          setText(next);
          onChange(parseMoneyToCents(next, currency));
        }}
        className="tabular-nums"
      />
    </div>
  );
}
```

- [ ] **Step 2: Typecheck + lint** → PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/money-input.tsx
git commit -m "feat(frontend): MoneyInput (text<->cents, presentation only)"
```

---

### Task 9: `components/entity-select.tsx` (Select bound to a React Query list)

**Files:**
- Create: `frontend/components/entity-select.tsx`

**Interfaces:**
- Produces:
  `EntitySelect({ value: number | null, onChange: (id: number | null) => void, queryKey: readonly unknown[], queryFn: () => Promise<{ id: number; name: string }[]>, placeholder?: string, allowNullLabel?: string, disabled?: boolean, id?: string })`.
  Internally runs `useQuery`, maps id↔name, renders the `ui` `Select`. When `allowNullLabel` is set, prepends a clear option whose value maps back to `null`. Consumed by categories form (group), transactions/plan forms (account, category), settings (default source account).

- [ ] **Step 1: Create `components/entity-select.tsx`**

```tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import { Select } from "@/ui";

const NULL_VALUE = "__null__";

export function EntitySelect({
  value,
  onChange,
  queryKey,
  queryFn,
  placeholder = "Selecciona…",
  allowNullLabel,
  disabled,
  id,
}: {
  value: number | null;
  onChange: (id: number | null) => void;
  queryKey: readonly unknown[];
  queryFn: () => Promise<{ id: number; name: string }[]>;
  placeholder?: string;
  allowNullLabel?: string;
  disabled?: boolean;
  id?: string;
}) {
  const { data, isLoading } = useQuery({ queryKey, queryFn });

  const items = [
    ...(allowNullLabel ? [{ value: NULL_VALUE, label: allowNullLabel }] : []),
    ...(data ?? []).map((e) => ({ value: String(e.id), label: e.name })),
  ];

  return (
    <Select
      id={id}
      value={value === null ? (allowNullLabel ? NULL_VALUE : null) : String(value)}
      onValueChange={(v) => onChange(v === null || v === NULL_VALUE ? null : Number(v))}
      items={items}
      placeholder={isLoading ? "Cargando…" : placeholder}
      disabled={disabled || isLoading}
    />
  );
}
```

- [ ] **Step 2: Typecheck + lint** → PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/entity-select.tsx
git commit -m "feat(frontend): EntitySelect bound to a React Query list"
```

---

### Task 10: `components/status-badge.tsx`

**Files:**
- Create: `frontend/components/status-badge.tsx`

**Interfaces:**
- Produces: `StatusBadge({ kind: "tx" | "mode" | "archived" | "onTrack", value: string | boolean })` rendering a `ui` `Badge` with the right Spanish label + variant. Mapping:
  - `tx`: `planned`→"Planeado"(outline), `posted`→"Registrado"(secondary), `skipped`→"Omitido"(ghost).
  - `mode`: `auto`→"Automático"(secondary), `manual`→"Manual"(outline).
  - `archived`: `true`→"Archivado"(ghost).
  - `onTrack`: `true`→"En camino"(secondary), `false`→"Atrasado"(destructive).
  Consumed by transactions table, to-pay, recurring, goals, masters.

- [ ] **Step 1: Create `components/status-badge.tsx`**

```tsx
import { Badge } from "@/ui";

type Variant = "default" | "secondary" | "destructive" | "outline" | "ghost";

const TX: Record<string, { label: string; variant: Variant }> = {
  planned: { label: "Planeado", variant: "outline" },
  posted: { label: "Registrado", variant: "secondary" },
  skipped: { label: "Omitido", variant: "ghost" },
};
const MODE: Record<string, { label: string; variant: Variant }> = {
  auto: { label: "Automático", variant: "secondary" },
  manual: { label: "Manual", variant: "outline" },
};

export function StatusBadge({
  kind,
  value,
}: {
  kind: "tx" | "mode" | "archived" | "onTrack";
  value: string | boolean;
}) {
  let label = String(value);
  let variant: Variant = "outline";

  if (kind === "tx") {
    const m = TX[String(value)];
    if (m) ({ label, variant } = m);
  } else if (kind === "mode") {
    const m = MODE[String(value)];
    if (m) ({ label, variant } = m);
  } else if (kind === "archived") {
    if (value !== true) return null;
    label = "Archivado";
    variant = "ghost";
  } else if (kind === "onTrack") {
    if (value === true) ({ label, variant } = { label: "En camino", variant: "secondary" });
    else ({ label, variant } = { label: "Atrasado", variant: "destructive" });
  }

  return <Badge variant={variant}>{label}</Badge>;
}
```

- [ ] **Step 2: Typecheck + lint** → PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/status-badge.tsx
git commit -m "feat(frontend): StatusBadge for tx/mode/archived/on-track"
```

---

### Task 11: `components/confirm-dialog.tsx`

**Files:**
- Create: `frontend/components/confirm-dialog.tsx`

**Interfaces:**
- Produces:
  `ConfirmDialog({ open, onOpenChange, title, description, confirmLabel?, onConfirm, destructive?, pending?, requireTextMatch? })`
  - `open: boolean`, `onOpenChange: (o: boolean) => void`, `title: string`, `description: React.ReactNode`, `confirmLabel?: string` (default "Confirmar"), `onConfirm: () => void`, `destructive?: boolean`, `pending?: boolean`, `requireTextMatch?: string` (when set, the confirm button is disabled until the user types this exact string — used for the emphatic tag-delete).
  Consumed by master pages (archive/delete), transactions delete.

- [ ] **Step 1: Create `components/confirm-dialog.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import {
  Dialog,
  DialogPopup,
  DialogTitle,
  DialogDescription,
  Button,
  Input,
} from "@/ui";

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Confirmar",
  onConfirm,
  destructive = false,
  pending = false,
  requireTextMatch,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: React.ReactNode;
  confirmLabel?: string;
  onConfirm: () => void;
  destructive?: boolean;
  pending?: boolean;
  requireTextMatch?: string;
}) {
  const [typed, setTyped] = useState("");

  useEffect(() => {
    if (!open) setTyped("");
  }, [open]);

  const blocked = requireTextMatch !== undefined && typed.trim() !== requireTextMatch;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPopup className="max-w-sm">
        <DialogTitle>{title}</DialogTitle>
        <DialogDescription>{description}</DialogDescription>

        {requireTextMatch !== undefined && (
          <Input
            autoFocus
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder={requireTextMatch}
            aria-label="Confirmación por texto"
          />
        )}

        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={pending}>
            Cancelar
          </Button>
          <Button
            variant={destructive ? "destructive" : "default"}
            onClick={onConfirm}
            disabled={pending || blocked}
          >
            {pending ? "…" : confirmLabel}
          </Button>
        </div>
      </DialogPopup>
    </Dialog>
  );
}
```

- [ ] **Step 2: Typecheck + lint** → PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/confirm-dialog.tsx
git commit -m "feat(frontend): ConfirmDialog with optional text-match guard"
```

---

### Task 12: `components/data-table.tsx` (generic table: columns, filter bar, client paging, row actions)

**Files:**
- Create: `frontend/components/data-table.tsx`

**Interfaces:**
- Produces:
  ```ts
  interface Column<T> { key: string; header: string; align?: "left" | "right"; render: (row: T) => React.ReactNode }
  interface RowAction<T> { label: string; onClick: (row: T) => void; variant?: "default" | "destructive" }
  function DataTable<T>(props: {
    rows: T[] | undefined; columns: Column<T>[]; rowKey: (row: T) => string | number;
    actions?: RowAction<T>[]; pageSize?: number; filterBar?: React.ReactNode;
    isLoading?: boolean; isError?: boolean; onRetry?: () => void; emptyMessage?: string;
  }): React.ReactElement
  ```
  Client-side paging only (the API has no pagination — single-user volume, spec §"Out of scope"). Consumed by `/transactions` (and reusable elsewhere).

- [ ] **Step 1: Create `components/data-table.tsx`**

```tsx
"use client";

import { useMemo, useState } from "react";
import { MoreHorizontal } from "lucide-react";
import {
  Button,
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/ui";
import { ErrorState } from "@/components/error-state";
import { EmptyState } from "@/components/empty-state";

export interface Column<T> {
  key: string;
  header: string;
  align?: "left" | "right";
  render: (row: T) => React.ReactNode;
}

export interface RowAction<T> {
  label: string;
  onClick: (row: T) => void;
  variant?: "default" | "destructive";
}

export function DataTable<T>({
  rows,
  columns,
  rowKey,
  actions,
  pageSize = 25,
  filterBar,
  isLoading,
  isError,
  onRetry,
  emptyMessage = "Sin resultados",
}: {
  rows: T[] | undefined;
  columns: Column<T>[];
  rowKey: (row: T) => string | number;
  actions?: RowAction<T>[];
  pageSize?: number;
  filterBar?: React.ReactNode;
  isLoading?: boolean;
  isError?: boolean;
  onRetry?: () => void;
  emptyMessage?: string;
}) {
  const [page, setPage] = useState(0);
  const all = rows ?? [];
  const pageCount = Math.max(1, Math.ceil(all.length / pageSize));
  const clampedPage = Math.min(page, pageCount - 1);
  const slice = useMemo(
    () => all.slice(clampedPage * pageSize, clampedPage * pageSize + pageSize),
    [all, clampedPage, pageSize],
  );

  return (
    <div className="space-y-3">
      {filterBar}

      {isError ? (
        <ErrorState message="No se pudieron cargar los datos" onRetry={onRetry ?? (() => {})} />
      ) : isLoading ? (
        <div className="space-y-2">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-10 animate-pulse rounded" style={{ background: "var(--muted)" }} />
          ))}
        </div>
      ) : all.length === 0 ? (
        <EmptyState message={emptyMessage} />
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border" style={{ borderColor: "var(--border)" }}>
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--muted-foreground)" }}>
                  {columns.map((c) => (
                    <th
                      key={c.key}
                      className={`px-3 py-2.5 text-xs font-medium ${c.align === "right" ? "text-right" : "text-left"}`}
                    >
                      {c.header}
                    </th>
                  ))}
                  {actions && actions.length > 0 && <th className="w-10 px-3 py-2.5" />}
                </tr>
              </thead>
              <tbody>
                {slice.map((row) => (
                  <tr key={rowKey(row)} className="border-t" style={{ borderColor: "var(--border)" }}>
                    {columns.map((c) => (
                      <td
                        key={c.key}
                        className={`px-3 py-2.5 ${c.align === "right" ? "text-right tabular-nums" : "text-left"}`}
                      >
                        {c.render(row)}
                      </td>
                    ))}
                    {actions && actions.length > 0 && (
                      <td className="px-3 py-2.5 text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger
                            render={<Button variant="ghost" size="icon-sm" aria-label="Acciones" />}
                          >
                            <MoreHorizontal className="size-4" />
                          </DropdownMenuTrigger>
                          <DropdownMenuContent>
                            {actions.map((a) => (
                              <DropdownMenuItem
                                key={a.label}
                                variant={a.variant}
                                onClick={() => a.onClick(row)}
                              >
                                {a.label}
                              </DropdownMenuItem>
                            ))}
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {pageCount > 1 && (
            <div className="flex items-center justify-between text-xs" style={{ color: "var(--muted-foreground)" }}>
              <span>
                {all.length} resultados · página {clampedPage + 1} de {pageCount}
              </span>
              <div className="flex gap-1">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={clampedPage === 0}
                  onClick={() => setPage(clampedPage - 1)}
                >
                  Anterior
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={clampedPage >= pageCount - 1}
                  onClick={() => setPage(clampedPage + 1)}
                >
                  Siguiente
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Typecheck + lint** → PASS. Note: `DropdownMenuTrigger` uses base-ui's `render` prop to compose with `Button` (avoids nested buttons). If the `render` prop API differs, check `frontend/node_modules/@base-ui/react/menu/trigger/MenuTrigger.d.ts`.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/data-table.tsx
git commit -m "feat(frontend): generic DataTable (columns, filter bar, paging, row actions)"
```

---

### Task 13: `components/entity-form-dialog.tsx` (schema-driven CRUD modal)

**Files:**
- Create: `frontend/components/entity-form-dialog.tsx`

**Interfaces:**
- Produces:
  ```ts
  type Field =
    | { kind: "text"; name: string; label: string; required?: boolean; placeholder?: string; disabled?: boolean }
    | { kind: "number"; name: string; label: string; required?: boolean; min?: number; disabled?: boolean }
    | { kind: "select"; name: string; label: string; options: { value: string; label: string }[]; required?: boolean; disabled?: boolean }
    | { kind: "entity"; name: string; label: string; queryKey: readonly unknown[]; queryFn: () => Promise<{ id: number; name: string }[]>; allowNullLabel?: string; disabled?: boolean }
    | { kind: "checkbox"; name: string; label: string }
    | { kind: "money"; name: string; label: string; currencyFrom: string; required?: boolean; disabled?: boolean };

  type FormValues = Record<string, string | number | boolean | null>;

  function EntityFormDialog(props: {
    open: boolean; onOpenChange: (o: boolean) => void; title: string;
    fields: Field[]; initialValues: FormValues;
    submitLabel?: string; pending?: boolean;
    onSubmit: (values: FormValues) => void;
  }): React.ReactElement
  ```
  Holds local form state seeded from `initialValues` each time it opens. `text`→string, `number`→number|null, `select`→string|null, `entity`→number|null, `checkbox`→boolean, `money`→cents number|null (reads currency from the sibling field named in `currencyFrom`). Validates `required` (non-empty / non-null) before calling `onSubmit`. The mutation lives in the caller; the caller closes the dialog on success and toasts errors. Consumed by all four master pages.

- [ ] **Step 1: Create `components/entity-form-dialog.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import {
  Dialog,
  DialogPopup,
  DialogTitle,
  Input,
  Label,
  Select,
  Checkbox,
  Button,
} from "@/ui";
import { EntitySelect } from "@/components/entity-select";
import { MoneyInput } from "@/components/money-input";

export type Field =
  | { kind: "text"; name: string; label: string; required?: boolean; placeholder?: string; disabled?: boolean }
  | { kind: "number"; name: string; label: string; required?: boolean; min?: number; disabled?: boolean }
  | { kind: "select"; name: string; label: string; options: { value: string; label: string }[]; required?: boolean; disabled?: boolean }
  | {
      kind: "entity";
      name: string;
      label: string;
      queryKey: readonly unknown[];
      queryFn: () => Promise<{ id: number; name: string }[]>;
      allowNullLabel?: string;
      disabled?: boolean;
    }
  | { kind: "checkbox"; name: string; label: string }
  | { kind: "money"; name: string; label: string; currencyFrom: string; required?: boolean; disabled?: boolean };

export type FormValues = Record<string, string | number | boolean | null>;

export function EntityFormDialog({
  open,
  onOpenChange,
  title,
  fields,
  initialValues,
  submitLabel = "Guardar",
  pending = false,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  title: string;
  fields: Field[];
  initialValues: FormValues;
  submitLabel?: string;
  pending?: boolean;
  onSubmit: (values: FormValues) => void;
}) {
  const [values, setValues] = useState<FormValues>(initialValues);
  const [touched, setTouched] = useState(false);

  // Reseed whenever the dialog opens (create vs edit pass different initialValues).
  useEffect(() => {
    if (open) {
      setValues(initialValues);
      setTouched(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const set = (name: string, v: FormValues[string]) =>
    setValues((prev) => ({ ...prev, [name]: v }));

  const missingRequired = fields.some((f) => {
    if (!("required" in f) || !f.required) return false;
    const v = values[f.name];
    return v === null || v === undefined || v === "";
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (missingRequired) return;
    onSubmit(values);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPopup>
        <DialogTitle>{title}</DialogTitle>
        <form onSubmit={submit} className="space-y-4">
          {fields.map((f) => {
            const invalid =
              touched && "required" in f && f.required && (values[f.name] === null || values[f.name] === "");
            return (
              <div key={f.name} className="space-y-1.5">
                {f.kind !== "checkbox" && (
                  <Label htmlFor={f.name}>
                    {f.label}
                    {"required" in f && f.required && <span className="text-destructive"> *</span>}
                  </Label>
                )}

                {f.kind === "text" && (
                  <Input
                    id={f.name}
                    value={(values[f.name] as string) ?? ""}
                    placeholder={f.placeholder}
                    disabled={f.disabled}
                    aria-invalid={invalid || undefined}
                    onChange={(e) => set(f.name, e.target.value)}
                  />
                )}

                {f.kind === "number" && (
                  <Input
                    id={f.name}
                    type="number"
                    min={f.min}
                    value={values[f.name] === null ? "" : String(values[f.name])}
                    disabled={f.disabled}
                    aria-invalid={invalid || undefined}
                    onChange={(e) => set(f.name, e.target.value === "" ? null : Number(e.target.value))}
                  />
                )}

                {f.kind === "select" && (
                  <Select
                    id={f.name}
                    value={(values[f.name] as string) ?? null}
                    onValueChange={(v) => set(f.name, v)}
                    items={f.options}
                    disabled={f.disabled}
                  />
                )}

                {f.kind === "entity" && (
                  <EntitySelect
                    id={f.name}
                    value={(values[f.name] as number | null) ?? null}
                    onChange={(id) => set(f.name, id)}
                    queryKey={f.queryKey}
                    queryFn={f.queryFn}
                    allowNullLabel={f.allowNullLabel}
                    disabled={f.disabled}
                  />
                )}

                {f.kind === "money" && (
                  <MoneyInput
                    id={f.name}
                    currency={(values[f.currencyFrom] as string) ?? "COP"}
                    value={(values[f.name] as number | null) ?? null}
                    disabled={f.disabled}
                    onChange={(cents) => set(f.name, cents)}
                  />
                )}

                {f.kind === "checkbox" && (
                  <label className="flex items-center gap-2 text-sm">
                    <Checkbox
                      id={f.name}
                      checked={Boolean(values[f.name])}
                      onCheckedChange={(c) => set(f.name, c)}
                    />
                    {f.label}
                  </label>
                )}
              </div>
            );
          })}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={pending}>
              Cancelar
            </Button>
            <Button type="submit" disabled={pending || missingRequired}>
              {pending ? "…" : submitLabel}
            </Button>
          </div>
        </form>
      </DialogPopup>
    </Dialog>
  );
}
```

- [ ] **Step 2: Typecheck + lint** → PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/entity-form-dialog.tsx
git commit -m "feat(frontend): schema-driven EntityFormDialog for uniform masters"
```

---

### Task 14: Rewrite `components/app-shell.tsx` (grouped sidebar + responsive drawer)

**Files:**
- Modify: `frontend/components/app-shell.tsx` (replace whole file)

**Interfaces:**
- Consumes: `api.logout`, `useQueryClient`, `usePathname`, `useRouter`.
- Produces: `AppShell` with a fixed left sidebar on `md+` grouped as Resumen / Movimiento / Planeación / Configuración, collapsing to a top bar + slide-in drawer on mobile. Active highlight + logout preserved. Renders all 12 routes.

- [ ] **Step 1: Read the Next.js navigation guide**

Skim `frontend/node_modules/next/dist/docs/01-app/` for `usePathname`/`Link` usage (App Router). Confirm `next/link` + `next/navigation` are the right imports (they are in the current file).

- [ ] **Step 2: Replace `components/app-shell.tsx`**

```tsx
"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Menu, X } from "lucide-react";
import { api } from "@/lib/api";

const GROUPS: { title: string; items: { href: string; label: string }[] }[] = [
  {
    title: "Resumen",
    items: [
      { href: "/", label: "Dashboard" },
      { href: "/reports", label: "Reportes" },
    ],
  },
  {
    title: "Movimiento",
    items: [
      { href: "/transactions", label: "Transacciones" },
      { href: "/to-pay", label: "Por pagar" },
      { href: "/recurring", label: "Recurrentes" },
    ],
  },
  {
    title: "Planeación",
    items: [
      { href: "/goals", label: "Metas" },
      { href: "/budgets", label: "Presupuestos" },
    ],
  },
  {
    title: "Configuración",
    items: [
      { href: "/accounts", label: "Cuentas" },
      { href: "/categories", label: "Categorías" },
      { href: "/category-groups", label: "Grupos" },
      { href: "/tags", label: "Etiquetas" },
      { href: "/settings", label: "Ajustes" },
    ],
  },
];

function NavLinks({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
  return (
    <nav className="space-y-5">
      {GROUPS.map((g) => (
        <div key={g.title} className="space-y-1">
          <p className="px-2 text-[0.7rem] font-medium uppercase tracking-wider" style={{ color: "var(--muted-foreground)" }}>
            {g.title}
          </p>
          {g.items.map((n) => {
            const active = pathname === n.href;
            return (
              <Link
                key={n.href}
                href={n.href}
                onClick={onNavigate}
                className="block rounded-md px-2 py-1.5 text-sm transition-colors"
                style={{
                  color: active ? "var(--foreground)" : "var(--muted-foreground)",
                  fontWeight: active ? 500 : 400,
                  background: active ? "var(--muted)" : "transparent",
                }}
              >
                {n.label}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const qc = useQueryClient();
  const [drawer, setDrawer] = useState(false);

  async function logout() {
    try {
      await api.logout();
    } finally {
      qc.clear();
      router.replace("/login");
      router.refresh();
    }
  }

  return (
    <div className="flex min-h-screen">
      {/* Desktop sidebar */}
      <aside
        className="sticky top-0 hidden h-screen w-56 shrink-0 flex-col justify-between border-r p-4 md:flex"
        style={{ background: "var(--sidebar)", borderColor: "var(--sidebar-border)" }}
      >
        <div className="space-y-6">
          <Link href="/" className="px-2 text-sm font-semibold tracking-tight">
            Quaestor
          </Link>
          <NavLinks pathname={pathname} />
        </div>
        <button onClick={logout} className="px-2 text-left text-sm" style={{ color: "var(--muted-foreground)" }}>
          Salir
        </button>
      </aside>

      {/* Mobile top bar */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-12 items-center gap-3 border-b bg-white px-4 md:hidden" style={{ borderColor: "var(--border)" }}>
          <button onClick={() => setDrawer(true)} aria-label="Abrir menú">
            <Menu className="size-5" />
          </button>
          <span className="text-sm font-semibold tracking-tight">Quaestor</span>
        </header>

        {/* Mobile drawer */}
        {drawer && (
          <div className="fixed inset-0 z-50 md:hidden">
            <div className="absolute inset-0 bg-black/40" onClick={() => setDrawer(false)} />
            <aside
              className="absolute left-0 top-0 flex h-full w-64 flex-col justify-between p-4"
              style={{ background: "var(--sidebar)" }}
            >
              <div className="space-y-6">
                <div className="flex items-center justify-between px-2">
                  <span className="text-sm font-semibold tracking-tight">Quaestor</span>
                  <button onClick={() => setDrawer(false)} aria-label="Cerrar menú">
                    <X className="size-5" />
                  </button>
                </div>
                <NavLinks pathname={pathname} onNavigate={() => setDrawer(false)} />
              </div>
              <button onClick={logout} className="px-2 text-left text-sm" style={{ color: "var(--muted-foreground)" }}>
                Salir
              </button>
            </aside>
          </div>
        )}

        <main className="mx-auto w-full max-w-5xl flex-1 px-5 py-8">{children}</main>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Typecheck + lint** → PASS.

- [ ] **Step 4: Manual smoke (needs `pnpm dev` + backend + a logged-in session)**

  - Sidebar shows 4 groups, 12 links; the current route is highlighted.
  - Click each group's links → navigates; highlight follows.
  - Resize to mobile width → sidebar hides, top bar shows; tap the menu → drawer opens; tap a link → navigates and drawer closes.
  - "Salir" logs out → redirects to `/login`, cache cleared.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/app-shell.tsx
git commit -m "feat(frontend): grouped sidebar + responsive drawer AppShell"
```

---

## Phase B — Masters (uniform CRUD via EntityFormDialog)

> Pattern shared by all four: a client page with a list query, a "Nuevo" button opening `EntityFormDialog` for create, a row action opening it for edit (different `fields`/`initialValues`), and a delete/archive action via `ConfirmDialog`. Every mutation calls `invalidate(qc, <group>)` and toasts. Read `frontend/node_modules/next/dist/docs/01-app/` once before the first page if unsure about App Router page files.

### Task 15: `/category-groups` page

**Files:**
- Create: `frontend/app/(app)/category-groups/page.tsx`

**Interfaces:**
- Consumes: `api.listCategoryGroups`, `api.createCategoryGroup`, `api.updateCategoryGroup`, `api.archiveCategoryGroup`; `qk.categoryGroups`; `invalidate(qc, "categoryGroupWrite")`; `EntityFormDialog`, `ConfirmDialog`, `StatusBadge`, `PageHeader`, `ErrorState`, `EmptyState`, `Button`.

- [ ] **Step 1: Create the page**

```tsx
"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError, type CategoryGroup } from "@/lib/api";
import { qk, invalidate } from "@/lib/query";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/error-state";
import { EmptyState } from "@/components/empty-state";
import { StatusBadge } from "@/components/status-badge";
import { EntityFormDialog, type Field, type FormValues } from "@/components/entity-form-dialog";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Button } from "@/ui";

const FIELDS: Field[] = [
  { kind: "text", name: "name", label: "Nombre", required: true },
  { kind: "number", name: "sort_order", label: "Orden", min: 0 },
];

export default function CategoryGroupsPage() {
  const qc = useQueryClient();
  const [showArchived, setShowArchived] = useState(false);
  const [editing, setEditing] = useState<CategoryGroup | null>(null);
  const [creating, setCreating] = useState(false);
  const [archiving, setArchiving] = useState<CategoryGroup | null>(null);

  const list = useQuery({
    queryKey: qk.categoryGroups(showArchived),
    queryFn: () => api.listCategoryGroups(showArchived),
  });

  const onErr = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error");
  const onOk = (msg: string) => {
    toast.success(msg);
    invalidate(qc, "categoryGroupWrite");
  };

  const create = useMutation({
    mutationFn: (v: FormValues) =>
      api.createCategoryGroup({ name: String(v.name), sort_order: (v.sort_order as number) ?? 0 }),
    onSuccess: () => { onOk("Grupo creado"); setCreating(false); },
    onError: onErr,
  });
  const update = useMutation({
    mutationFn: (v: FormValues) =>
      api.updateCategoryGroup(editing!.id, { name: String(v.name), sort_order: (v.sort_order as number) ?? 0 }),
    onSuccess: () => { onOk("Grupo actualizado"); setEditing(null); },
    onError: onErr,
  });
  const archive = useMutation({
    mutationFn: (id: number) => api.archiveCategoryGroup(id),
    onSuccess: () => { onOk("Grupo archivado"); setArchiving(null); },
    onError: onErr,
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Grupos de categorías"
        action={<Button onClick={() => setCreating(true)}>Nuevo</Button>}
      />

      <label className="flex items-center gap-2 text-sm" style={{ color: "var(--muted-foreground)" }}>
        <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
        Mostrar archivados
      </label>

      {list.isError && <ErrorState message="No se pudieron cargar los grupos" onRetry={() => list.refetch()} />}
      {list.data && list.data.length === 0 && <EmptyState message="Sin grupos" />}

      {list.data && list.data.length > 0 && (
        <div className="overflow-hidden rounded-lg border" style={{ borderColor: "var(--border)" }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ color: "var(--muted-foreground)" }}>
                <th className="px-3 py-2.5 text-left text-xs font-medium">Nombre</th>
                <th className="px-3 py-2.5 text-right text-xs font-medium">Orden</th>
                <th className="w-40 px-3 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {list.data.map((g) => (
                <tr key={g.id} className="border-t" style={{ borderColor: "var(--border)" }}>
                  <td className="px-3 py-2.5">
                    <span className="flex items-center gap-2">
                      {g.name} <StatusBadge kind="archived" value={g.archived} />
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{g.sort_order}</td>
                  <td className="px-3 py-2.5 text-right">
                    {!g.archived && (
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="sm" onClick={() => setEditing(g)}>Editar</Button>
                        <Button variant="ghost" size="sm" onClick={() => setArchiving(g)}>Archivar</Button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <EntityFormDialog
        open={creating}
        onOpenChange={setCreating}
        title="Nuevo grupo"
        fields={FIELDS}
        initialValues={{ name: "", sort_order: 0 }}
        pending={create.isPending}
        onSubmit={(v) => create.mutate(v)}
      />
      <EntityFormDialog
        open={editing !== null}
        onOpenChange={(o) => !o && setEditing(null)}
        title="Editar grupo"
        fields={FIELDS}
        initialValues={{ name: editing?.name ?? "", sort_order: editing?.sort_order ?? 0 }}
        pending={update.isPending}
        onSubmit={(v) => update.mutate(v)}
      />
      <ConfirmDialog
        open={archiving !== null}
        onOpenChange={(o) => !o && setArchiving(null)}
        title="Archivar grupo"
        description={`Se archivará "${archiving?.name}". No podrás reactivarlo desde la app (Fase 2).`}
        confirmLabel="Archivar"
        pending={archive.isPending}
        onConfirm={() => archiving && archive.mutate(archiving.id)}
      />
    </div>
  );
}
```

- [ ] **Step 2: Typecheck + lint** → PASS.

- [ ] **Step 3: Manual smoke**: load list · create a group · edit it · toggle "Mostrar archivados" · archive a group (confirm) → it disappears from the default list and appears when archived shown. Each action toasts and the list refreshes.

- [ ] **Step 4: Commit**

```bash
git add "frontend/app/(app)/category-groups/page.tsx"
git commit -m "feat(frontend): /category-groups master CRUD"
```

---

### Task 16: `/tags` page (hard delete, emphatic confirm)

**Files:**
- Create: `frontend/app/(app)/tags/page.tsx`

**Interfaces:**
- Consumes: `api.listTags`, `api.createTag`, `api.updateTag`, `api.deleteTag`; `qk.tags`; `invalidate(qc, "tagWrite")`; `EntityFormDialog`, `ConfirmDialog` (with `requireTextMatch`), `PageHeader`, `ErrorState`, `EmptyState`, `Button`.

- [ ] **Step 1: Create the page**

```tsx
"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError, type Tag } from "@/lib/api";
import { qk, invalidate } from "@/lib/query";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/error-state";
import { EmptyState } from "@/components/empty-state";
import { EntityFormDialog, type Field, type FormValues } from "@/components/entity-form-dialog";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Button } from "@/ui";

const FIELDS: Field[] = [{ kind: "text", name: "name", label: "Nombre", required: true }];

export default function TagsPage() {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<Tag | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<Tag | null>(null);

  const list = useQuery({ queryKey: qk.tags(), queryFn: () => api.listTags() });

  const onErr = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error");
  const done = (msg: string) => { toast.success(msg); invalidate(qc, "tagWrite"); };

  const create = useMutation({
    mutationFn: (v: FormValues) => api.createTag({ name: String(v.name) }),
    onSuccess: () => { done("Etiqueta creada"); setCreating(false); },
    onError: onErr,
  });
  const update = useMutation({
    mutationFn: (v: FormValues) => api.updateTag(editing!.id, { name: String(v.name) }),
    onSuccess: () => { done("Etiqueta actualizada"); setEditing(null); },
    onError: onErr,
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.deleteTag(id),
    onSuccess: () => { done("Etiqueta eliminada"); setDeleting(null); },
    onError: onErr,
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Etiquetas" action={<Button onClick={() => setCreating(true)}>Nueva</Button>} />

      {list.isError && <ErrorState message="No se pudieron cargar las etiquetas" onRetry={() => list.refetch()} />}
      {list.data && list.data.length === 0 && <EmptyState message="Sin etiquetas" />}

      {list.data && list.data.length > 0 && (
        <div className="overflow-hidden rounded-lg border" style={{ borderColor: "var(--border)" }}>
          <table className="w-full text-sm">
            <tbody>
              {list.data.map((t) => (
                <tr key={t.id} className="border-t first:border-t-0" style={{ borderColor: "var(--border)" }}>
                  <td className="px-3 py-2.5">{t.name}</td>
                  <td className="px-3 py-2.5 text-right">
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="sm" onClick={() => setEditing(t)}>Editar</Button>
                      <Button variant="ghost" size="sm" onClick={() => setDeleting(t)}>Eliminar</Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <EntityFormDialog
        open={creating}
        onOpenChange={setCreating}
        title="Nueva etiqueta"
        fields={FIELDS}
        initialValues={{ name: "" }}
        pending={create.isPending}
        onSubmit={(v) => create.mutate(v)}
      />
      <EntityFormDialog
        open={editing !== null}
        onOpenChange={(o) => !o && setEditing(null)}
        title="Editar etiqueta"
        fields={FIELDS}
        initialValues={{ name: editing?.name ?? "" }}
        pending={update.isPending}
        onSubmit={(v) => update.mutate(v)}
      />
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(o) => !o && setDeleting(null)}
        title="Eliminar etiqueta"
        description={
          <>
            Esto elimina la etiqueta <strong>{deleting?.name}</strong> y la quita de todas sus
            transacciones. Es permanente. Escribe el nombre para confirmar.
          </>
        }
        confirmLabel="Eliminar"
        destructive
        requireTextMatch={deleting?.name}
        pending={remove.isPending}
        onConfirm={() => deleting && remove.mutate(deleting.id)}
      />
    </div>
  );
}
```

- [ ] **Step 2: Typecheck + lint** → PASS.

- [ ] **Step 3: Manual smoke**: create a tag · edit it · delete one → the confirm requires typing the exact name before the button enables; deleting removes it. Toasts + refresh.

- [ ] **Step 4: Commit**

```bash
git add "frontend/app/(app)/tags/page.tsx"
git commit -m "feat(frontend): /tags master CRUD with emphatic delete"
```

---

### Task 17: `/accounts` page (create with opening balance; edit name/type only; archive)

**Files:**
- Create: `frontend/app/(app)/accounts/page.tsx`

**Interfaces:**
- Consumes: `api.listAccounts`, `api.createAccount`, `api.updateAccount`, `api.archiveAccount`; `qk.accounts`; `invalidate(qc, "accountWrite")`; `formatCents`; `EntityFormDialog` (create has a `money` field reading currency from the `currency` select; edit omits currency/balance), `ConfirmDialog`, `StatusBadge`, `PageHeader`, `ErrorState`, `EmptyState`, `Button`.
- Account types: `debit|credit|cash|savings`. Currencies: `COP|USD`.

- [ ] **Step 1: Create the page**

```tsx
"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError, type Account, type AccountType } from "@/lib/api";
import { qk, invalidate } from "@/lib/query";
import { formatCents } from "@/lib/money";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/error-state";
import { EmptyState } from "@/components/empty-state";
import { StatusBadge } from "@/components/status-badge";
import { EntityFormDialog, type Field, type FormValues } from "@/components/entity-form-dialog";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Button } from "@/ui";

const TYPE_OPTIONS = [
  { value: "debit", label: "Débito" },
  { value: "credit", label: "Crédito" },
  { value: "cash", label: "Efectivo" },
  { value: "savings", label: "Ahorros" },
];
const TYPE_LABEL: Record<string, string> = Object.fromEntries(TYPE_OPTIONS.map((o) => [o.value, o.label]));
const CURRENCY_OPTIONS = [
  { value: "COP", label: "COP" },
  { value: "USD", label: "USD" },
];

const CREATE_FIELDS: Field[] = [
  { kind: "text", name: "name", label: "Nombre", required: true },
  { kind: "select", name: "type", label: "Tipo", options: TYPE_OPTIONS, required: true },
  { kind: "select", name: "currency", label: "Moneda", options: CURRENCY_OPTIONS, required: true },
  { kind: "money", name: "balance", label: "Saldo inicial", currencyFrom: "currency" },
];
const EDIT_FIELDS: Field[] = [
  { kind: "text", name: "name", label: "Nombre", required: true },
  { kind: "select", name: "type", label: "Tipo", options: TYPE_OPTIONS, required: true },
];

export default function AccountsPage() {
  const qc = useQueryClient();
  const [showArchived, setShowArchived] = useState(false);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Account | null>(null);
  const [archiving, setArchiving] = useState<Account | null>(null);

  const list = useQuery({
    queryKey: qk.accounts(showArchived),
    queryFn: () => api.listAccounts(showArchived),
  });

  const onErr = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error");
  const done = (msg: string) => { toast.success(msg); invalidate(qc, "accountWrite"); };

  const create = useMutation({
    mutationFn: (v: FormValues) =>
      api.createAccount({
        name: String(v.name),
        type: v.type as AccountType,
        currency: String(v.currency),
        balance: (v.balance as number) ?? 0,
      }),
    onSuccess: () => { done("Cuenta creada"); setCreating(false); },
    onError: onErr,
  });
  const update = useMutation({
    mutationFn: (v: FormValues) =>
      api.updateAccount(editing!.id, { name: String(v.name), type: v.type as AccountType }),
    onSuccess: () => { done("Cuenta actualizada"); setEditing(null); },
    onError: onErr,
  });
  const archive = useMutation({
    mutationFn: (id: number) => api.archiveAccount(id),
    onSuccess: () => { done("Cuenta archivada"); setArchiving(null); },
    onError: onErr,
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Cuentas" action={<Button onClick={() => setCreating(true)}>Nueva</Button>} />

      <label className="flex items-center gap-2 text-sm" style={{ color: "var(--muted-foreground)" }}>
        <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
        Mostrar archivadas
      </label>

      {list.isError && <ErrorState message="No se pudieron cargar las cuentas" onRetry={() => list.refetch()} />}
      {list.data && list.data.length === 0 && <EmptyState message="Sin cuentas" />}

      {list.data && list.data.length > 0 && (
        <div className="overflow-hidden rounded-lg border" style={{ borderColor: "var(--border)" }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ color: "var(--muted-foreground)" }}>
                <th className="px-3 py-2.5 text-left text-xs font-medium">Nombre</th>
                <th className="px-3 py-2.5 text-left text-xs font-medium">Tipo</th>
                <th className="px-3 py-2.5 text-right text-xs font-medium">Saldo</th>
                <th className="w-40 px-3 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {list.data.map((a) => (
                <tr key={a.id} className="border-t" style={{ borderColor: "var(--border)" }}>
                  <td className="px-3 py-2.5">
                    <span className="flex items-center gap-2">
                      {a.name} <StatusBadge kind="archived" value={a.archived} />
                    </span>
                  </td>
                  <td className="px-3 py-2.5" style={{ color: "var(--muted-foreground)" }}>
                    {TYPE_LABEL[a.type] ?? a.type}
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{formatCents(a.balance, a.currency)}</td>
                  <td className="px-3 py-2.5 text-right">
                    {!a.archived && (
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="sm" onClick={() => setEditing(a)}>Editar</Button>
                        <Button variant="ghost" size="sm" onClick={() => setArchiving(a)}>Archivar</Button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <EntityFormDialog
        open={creating}
        onOpenChange={setCreating}
        title="Nueva cuenta"
        fields={CREATE_FIELDS}
        initialValues={{ name: "", type: "debit", currency: "COP", balance: null }}
        pending={create.isPending}
        onSubmit={(v) => create.mutate(v)}
      />
      <EntityFormDialog
        open={editing !== null}
        onOpenChange={(o) => !o && setEditing(null)}
        title="Editar cuenta"
        fields={EDIT_FIELDS}
        initialValues={{ name: editing?.name ?? "", type: editing?.type ?? "debit" }}
        pending={update.isPending}
        onSubmit={(v) => update.mutate(v)}
      />
      <ConfirmDialog
        open={archiving !== null}
        onOpenChange={(o) => !o && setArchiving(null)}
        title="Archivar cuenta"
        description={`Se archivará "${archiving?.name}". No podrás reactivarla desde la app (Fase 2).`}
        confirmLabel="Archivar"
        pending={archive.isPending}
        onConfirm={() => archiving && archive.mutate(archiving.id)}
      />
    </div>
  );
}
```

- [ ] **Step 2: Typecheck + lint** → PASS.

- [ ] **Step 3: Manual smoke**: create a COP account with opening balance (note the `$` prefix; balance shows formatted) · create a USD account (prefix `US$`, two decimals) · edit name/type (currency + balance not shown in edit) · archive · toggle "Mostrar archivadas". Balances must match what the dashboard shows.

- [ ] **Step 4: Commit**

```bash
git add "frontend/app/(app)/accounts/page.tsx"
git commit -m "feat(frontend): /accounts master CRUD with opening balance + archive"
```

---

### Task 18: `/categories` page (group via EntitySelect; three flags; archive)

**Files:**
- Create: `frontend/app/(app)/categories/page.tsx`

**Interfaces:**
- Consumes: `api.listCategories`, `api.createCategory`, `api.updateCategory`, `api.archiveCategory`, `api.listCategoryGroups` (for the group select + name display); `qk.categories`, `qk.categoryGroups`; `invalidate(qc, "categoryWrite")`; `EntityFormDialog` (with an `entity` field for the group + three `checkbox` fields), `ConfirmDialog`, `StatusBadge`, `PageHeader`, `ErrorState`, `EmptyState`, `Button`.

- [ ] **Step 1: Create the page**

```tsx
"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError, type Category } from "@/lib/api";
import { qk, invalidate } from "@/lib/query";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/error-state";
import { EmptyState } from "@/components/empty-state";
import { StatusBadge } from "@/components/status-badge";
import { EntityFormDialog, type Field, type FormValues } from "@/components/entity-form-dialog";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Button } from "@/ui";

const FIELDS: Field[] = [
  { kind: "text", name: "name", label: "Nombre", required: true },
  {
    kind: "entity",
    name: "group_id",
    label: "Grupo",
    queryKey: qk.categoryGroups(false),
    queryFn: () => api.listCategoryGroups(false),
    allowNullLabel: "Sin grupo",
  },
  { kind: "checkbox", name: "is_income", label: "Es ingreso" },
  { kind: "checkbox", name: "exclude_from_budget", label: "Excluir del presupuesto" },
  { kind: "checkbox", name: "exclude_from_totals", label: "Excluir de los totales" },
];

export default function CategoriesPage() {
  const qc = useQueryClient();
  const [showArchived, setShowArchived] = useState(false);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Category | null>(null);
  const [archiving, setArchiving] = useState<Category | null>(null);

  const list = useQuery({
    queryKey: qk.categories(showArchived),
    queryFn: () => api.listCategories(showArchived),
  });
  const groups = useQuery({
    queryKey: qk.categoryGroups(true),
    queryFn: () => api.listCategoryGroups(true),
  });
  const groupName = (id: number | null) =>
    id === null ? "—" : groups.data?.find((g) => g.id === id)?.name ?? "—";

  const onErr = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error");
  const done = (msg: string) => { toast.success(msg); invalidate(qc, "categoryWrite"); };

  const toBody = (v: FormValues) => ({
    name: String(v.name),
    group_id: (v.group_id as number | null) ?? null,
    is_income: Boolean(v.is_income),
    exclude_from_budget: Boolean(v.exclude_from_budget),
    exclude_from_totals: Boolean(v.exclude_from_totals),
  });

  const create = useMutation({
    mutationFn: (v: FormValues) => api.createCategory(toBody(v)),
    onSuccess: () => { done("Categoría creada"); setCreating(false); },
    onError: onErr,
  });
  const update = useMutation({
    mutationFn: (v: FormValues) => api.updateCategory(editing!.id, toBody(v)),
    onSuccess: () => { done("Categoría actualizada"); setEditing(null); },
    onError: onErr,
  });
  const archive = useMutation({
    mutationFn: (id: number) => api.archiveCategory(id),
    onSuccess: () => { done("Categoría archivada"); setArchiving(null); },
    onError: onErr,
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Categorías" action={<Button onClick={() => setCreating(true)}>Nueva</Button>} />

      <label className="flex items-center gap-2 text-sm" style={{ color: "var(--muted-foreground)" }}>
        <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
        Mostrar archivadas
      </label>

      {list.isError && <ErrorState message="No se pudieron cargar las categorías" onRetry={() => list.refetch()} />}
      {list.data && list.data.length === 0 && <EmptyState message="Sin categorías" />}

      {list.data && list.data.length > 0 && (
        <div className="overflow-hidden rounded-lg border" style={{ borderColor: "var(--border)" }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ color: "var(--muted-foreground)" }}>
                <th className="px-3 py-2.5 text-left text-xs font-medium">Nombre</th>
                <th className="px-3 py-2.5 text-left text-xs font-medium">Grupo</th>
                <th className="px-3 py-2.5 text-left text-xs font-medium">Flags</th>
                <th className="w-40 px-3 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {list.data.map((c) => (
                <tr key={c.id} className="border-t" style={{ borderColor: "var(--border)" }}>
                  <td className="px-3 py-2.5">
                    <span className="flex items-center gap-2">
                      {c.name} <StatusBadge kind="archived" value={c.archived} />
                    </span>
                  </td>
                  <td className="px-3 py-2.5" style={{ color: "var(--muted-foreground)" }}>{groupName(c.group_id)}</td>
                  <td className="px-3 py-2.5 text-xs" style={{ color: "var(--muted-foreground)" }}>
                    {[
                      c.is_income && "ingreso",
                      c.exclude_from_budget && "no-presup.",
                      c.exclude_from_totals && "no-totales",
                    ].filter(Boolean).join(" · ") || "—"}
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    {!c.archived && (
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="sm" onClick={() => setEditing(c)}>Editar</Button>
                        <Button variant="ghost" size="sm" onClick={() => setArchiving(c)}>Archivar</Button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <EntityFormDialog
        open={creating}
        onOpenChange={setCreating}
        title="Nueva categoría"
        fields={FIELDS}
        initialValues={{ name: "", group_id: null, is_income: false, exclude_from_budget: false, exclude_from_totals: false }}
        pending={create.isPending}
        onSubmit={(v) => create.mutate(v)}
      />
      <EntityFormDialog
        open={editing !== null}
        onOpenChange={(o) => !o && setEditing(null)}
        title="Editar categoría"
        fields={FIELDS}
        initialValues={{
          name: editing?.name ?? "",
          group_id: editing?.group_id ?? null,
          is_income: editing?.is_income ?? false,
          exclude_from_budget: editing?.exclude_from_budget ?? false,
          exclude_from_totals: editing?.exclude_from_totals ?? false,
        }}
        pending={update.isPending}
        onSubmit={(v) => update.mutate(v)}
      />
      <ConfirmDialog
        open={archiving !== null}
        onOpenChange={(o) => !o && setArchiving(null)}
        title="Archivar categoría"
        description={`Se archivará "${archiving?.name}". No podrás reactivarla desde la app (Fase 2).`}
        confirmLabel="Archivar"
        pending={archive.isPending}
        onConfirm={() => archiving && archive.mutate(archiving.id)}
      />
    </div>
  );
}
```

- [ ] **Step 2: Typecheck + lint** → PASS.

- [ ] **Step 3: Manual smoke**: create a category with a group + flags · the group column shows the group name · edit (group preselected, "Sin grupo" clears it) · toggle flags · archive · toggle "Mostrar archivadas".

- [ ] **Step 4: Commit**

```bash
git add "frontend/app/(app)/categories/page.tsx"
git commit -m "feat(frontend): /categories master CRUD with group + flags"
```

---

## Phase C — Movement (bespoke pages)

### Task 19: `/transactions` — filterable read table

**Files:**
- Create: `frontend/app/(app)/transactions/page.tsx`

**Interfaces:**
- Consumes: `api.listTransactions(filters)`, `api.listAccounts`, `api.listCategories`, `api.listTags`; `qk.transactions`, `qk.accounts`, `qk.categories`, `qk.tags`; `DataTable`, `EntitySelect`, `StatusBadge`, `MoneyAmount`, `Select`, `PageHeader`, `Button`.
- Produces: the transactions page shell (table + filter bar). Later tasks (20, 21) add the create/edit/delete dialogs to this same file.
- Filter state shape (kept in this task, reused by 20/21): `{ date_from, date_to, account_id, category_id, tag, type, status }`, all nullable.

- [ ] **Step 1: Read the Next.js App Router page guide** if you have not this session (`frontend/node_modules/next/dist/docs/01-app/`).

- [ ] **Step 2: Create `app/(app)/transactions/page.tsx`**

```tsx
"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  api,
  type Transaction,
  type TransactionFilters,
  type TxType,
  type TxStatus,
} from "@/lib/api";
import { qk } from "@/lib/query";
import { PageHeader } from "@/components/page-header";
import { MoneyAmount } from "@/components/money-amount";
import { StatusBadge } from "@/components/status-badge";
import { EntitySelect } from "@/components/entity-select";
import { DataTable, type Column } from "@/components/data-table";
import { Input, Select, Button } from "@/ui";

const TYPE_ITEMS = [
  { value: "expense", label: "Gasto" },
  { value: "income", label: "Ingreso" },
  { value: "transfer", label: "Transferencia" },
];
const STATUS_ITEMS = [
  { value: "planned", label: "Planeado" },
  { value: "posted", label: "Registrado" },
  { value: "skipped", label: "Omitido" },
];

export default function TransactionsPage() {
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [accountId, setAccountId] = useState<number | null>(null);
  const [categoryId, setCategoryId] = useState<number | null>(null);
  const [tag, setTag] = useState<number | null>(null);
  const [type, setType] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  const accounts = useQuery({ queryKey: qk.accounts(true), queryFn: () => api.listAccounts(true) });
  const categories = useQuery({ queryKey: qk.categories(true), queryFn: () => api.listCategories(true) });
  const tags = useQuery({ queryKey: qk.tags(), queryFn: () => api.listTags() });

  const accountName = (id: number | null) =>
    id === null ? "—" : accounts.data?.find((a) => a.id === id)?.name ?? `#${id}`;
  const categoryName = (id: number | null) =>
    id === null ? "—" : categories.data?.find((c) => c.id === id)?.name ?? `#${id}`;
  const tagName = (id: number | null) => tags.data?.find((t) => t.id === id)?.name;

  const filters: TransactionFilters = useMemo(() => {
    const f: TransactionFilters = {};
    if (dateFrom) f.date_from = dateFrom;
    if (dateTo) f.date_to = dateTo;
    if (accountId !== null) f.account_id = accountId;
    if (categoryId !== null) f.category_id = categoryId;
    if (tag !== null) f.tag = tagName(tag);
    if (type) f.type = type as TxType;
    if (status) f.status = status as TxStatus;
    return f;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dateFrom, dateTo, accountId, categoryId, tag, type, status, tags.data]);

  const list = useQuery({
    queryKey: qk.transactions(filters),
    queryFn: () => api.listTransactions(filters),
  });

  const columns: Column<Transaction>[] = [
    { key: "date", header: "Fecha", render: (t) => t.date },
    { key: "payee", header: "Beneficiario", render: (t) => <span className="font-medium">{t.payee || "—"}</span> },
    { key: "category", header: "Categoría", render: (t) => <span style={{ color: "var(--muted-foreground)" }}>{categoryName(t.category_id)}</span> },
    { key: "account", header: "Cuenta", render: (t) => <span style={{ color: "var(--muted-foreground)" }}>{accountName(t.account_id)}</span> },
    { key: "status", header: "Estado", render: (t) => <StatusBadge kind="tx" value={t.status} /> },
    {
      key: "amount",
      header: "Monto",
      align: "right",
      render: (t) => <MoneyAmount cents={t.amount} currency={t.currency} type={t.type} />,
    },
  ];

  const clear = () => {
    setDateFrom(""); setDateTo(""); setAccountId(null); setCategoryId(null);
    setTag(null); setType(null); setStatus(null);
  };

  const filterBar = (
    <div className="flex flex-wrap items-end gap-2">
      <div className="space-y-1">
        <label className="block text-xs" style={{ color: "var(--muted-foreground)" }}>Desde</label>
        <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="w-36" />
      </div>
      <div className="space-y-1">
        <label className="block text-xs" style={{ color: "var(--muted-foreground)" }}>Hasta</label>
        <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="w-36" />
      </div>
      <div className="w-40 space-y-1">
        <label className="block text-xs" style={{ color: "var(--muted-foreground)" }}>Cuenta</label>
        <EntitySelect
          value={accountId}
          onChange={setAccountId}
          queryKey={qk.accounts(true)}
          queryFn={() => api.listAccounts(true)}
          allowNullLabel="Todas"
        />
      </div>
      <div className="w-40 space-y-1">
        <label className="block text-xs" style={{ color: "var(--muted-foreground)" }}>Categoría</label>
        <EntitySelect
          value={categoryId}
          onChange={setCategoryId}
          queryKey={qk.categories(true)}
          queryFn={() => api.listCategories(true)}
          allowNullLabel="Todas"
        />
      </div>
      <div className="w-36 space-y-1">
        <label className="block text-xs" style={{ color: "var(--muted-foreground)" }}>Etiqueta</label>
        <EntitySelect
          value={tag}
          onChange={setTag}
          queryKey={qk.tags()}
          queryFn={() => api.listTags()}
          allowNullLabel="Todas"
        />
      </div>
      <div className="w-32 space-y-1">
        <label className="block text-xs" style={{ color: "var(--muted-foreground)" }}>Tipo</label>
        <Select value={type} onValueChange={setType} items={[{ value: "", label: "Todos" }, ...TYPE_ITEMS]} placeholder="Todos" />
      </div>
      <div className="w-32 space-y-1">
        <label className="block text-xs" style={{ color: "var(--muted-foreground)" }}>Estado</label>
        <Select value={status} onValueChange={setStatus} items={[{ value: "", label: "Todos" }, ...STATUS_ITEMS]} placeholder="Todos" />
      </div>
      <Button variant="ghost" size="sm" onClick={clear}>Limpiar</Button>
    </div>
  );

  return (
    <div className="space-y-6">
      <PageHeader title="Transacciones" />
      <DataTable
        rows={list.data}
        columns={columns}
        rowKey={(t) => t.id}
        filterBar={filterBar}
        isLoading={list.isLoading}
        isError={list.isError}
        onRetry={() => list.refetch()}
        emptyMessage="No hay transacciones para estos filtros"
      />
    </div>
  );
}
```

Note: the `Select` "Todos" option uses `value: ""`. `onValueChange` returns `""` → treated as falsy in the `filters` builder (`if (type)` is false for `""`), so it clears the filter. Confirm base-ui Select accepts an empty-string item value; if not, swap `""` for a sentinel like `"__all__"` and special-case it in the builder.

- [ ] **Step 3: Typecheck + lint** → PASS.

- [ ] **Step 4: Manual smoke**: table lists transactions; each filter narrows results (date range, account, category, tag, type, status); amounts are colored by type (expense red, income default/green per `MoneyAmount`); "Limpiar" resets; paging appears past `pageSize` rows.

- [ ] **Step 5: Commit**

```bash
git add "frontend/app/(app)/transactions/page.tsx"
git commit -m "feat(frontend): /transactions filterable read table"
```

---

### Task 20: `/transactions` — create (normal + transfer)

**Files:**
- Create: `frontend/components/transaction-create-dialog.tsx`
- Modify: `frontend/app/(app)/transactions/page.tsx` (wire the "Nueva" button + dialog)

**Interfaces:**
- Consumes: `api.createTransaction`, `api.createTransfer`, `api.listAccounts`, `invalidate(qc, "transactionWrite")`, `MoneyInput`, `EntitySelect`, `Select`, `Textarea`, `Dialog`, `Button`, `Tabs`.
- Produces: `TransactionCreateDialog({ open, onOpenChange })` — self-contained (owns its mutations + invalidation + toasts). Two modes via tabs: **Normal** (`POST /transactions`, `type` expense/income; currency derived from the chosen account) and **Transferencia** (`POST /transactions/transfer`). `type=transfer` is never sent to `POST /transactions` (routed to the transfer endpoint per the contract).
- Key rule: amount is cents from `MoneyInput`; `currency` equals the selected account's currency (the API rejects a mismatch). `fx_rate` is an optional decimal string, offered only when currency ≠ COP.

- [ ] **Step 1: Create `components/transaction-create-dialog.tsx`**

```tsx
"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError, type Account } from "@/lib/api";
import { qk, invalidate } from "@/lib/query";
import { MoneyInput } from "@/components/money-input";
import { EntitySelect } from "@/components/entity-select";
import {
  Dialog, DialogPopup, DialogTitle, Select, Textarea, Input, Label, Button,
  Tabs, TabsList, TabsTrigger, TabsContent,
} from "@/ui";

const TYPE_ITEMS = [
  { value: "expense", label: "Gasto" },
  { value: "income", label: "Ingreso" },
];

function currencyOf(accounts: Account[] | undefined, id: number | null): string {
  if (id === null) return "COP";
  return accounts?.find((a) => a.id === id)?.currency ?? "COP";
}

export function TransactionCreateDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const qc = useQueryClient();
  const accounts = useQuery({ queryKey: qk.accounts(false), queryFn: () => api.listAccounts(false) });

  // normal
  const [type, setType] = useState<string | null>("expense");
  const [accountId, setAccountId] = useState<number | null>(null);
  const [categoryId, setCategoryId] = useState<number | null>(null);
  const [amount, setAmount] = useState<number | null>(null);
  const [date, setDate] = useState("");
  const [payee, setPayee] = useState("");
  const [notes, setNotes] = useState("");
  const [fxRate, setFxRate] = useState("");

  // transfer
  const [fromId, setFromId] = useState<number | null>(null);
  const [toId, setToId] = useState<number | null>(null);
  const [tAmount, setTAmount] = useState<number | null>(null);
  const [tDate, setTDate] = useState("");
  const [tNotes, setTNotes] = useState("");
  const [tFxRate, setTFxRate] = useState("");

  const normalCurrency = currencyOf(accounts.data, accountId);
  const transferCurrency = currencyOf(accounts.data, fromId);

  const onErr = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error");
  const done = (msg: string) => {
    toast.success(msg);
    invalidate(qc, "transactionWrite");
    onOpenChange(false);
  };

  const createNormal = useMutation({
    mutationFn: () =>
      api.createTransaction({
        type: type as "expense" | "income",
        account_id: accountId!,
        amount: amount!,
        currency: normalCurrency,
        date,
        payee: payee || undefined,
        category_id: categoryId,
        notes: notes || undefined,
        fx_rate: normalCurrency !== "COP" && fxRate ? fxRate : undefined,
      }),
    onSuccess: () => done("Transacción creada"),
    onError: onErr,
  });

  const createTransfer = useMutation({
    mutationFn: () =>
      api.createTransfer({
        from_account_id: fromId!,
        to_account_id: toId!,
        amount: tAmount!,
        currency: transferCurrency,
        date: tDate,
        notes: tNotes || undefined,
        fx_rate: transferCurrency !== "COP" && tFxRate ? tFxRate : undefined,
      }),
    onSuccess: () => done("Transferencia creada"),
    onError: onErr,
  });

  const normalInvalid = !type || accountId === null || amount === null || !date;
  const transferInvalid = fromId === null || toId === null || tAmount === null || !tDate;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPopup className="max-w-lg">
        <DialogTitle>Nueva transacción</DialogTitle>
        <Tabs defaultValue="normal">
          <TabsList>
            <TabsTrigger value="normal">Normal</TabsTrigger>
            <TabsTrigger value="transfer">Transferencia</TabsTrigger>
          </TabsList>

          <TabsContent value="normal">
            <form
              onSubmit={(e) => { e.preventDefault(); if (!normalInvalid) createNormal.mutate(); }}
              className="space-y-4 pt-2"
            >
              <div className="space-y-1.5">
                <Label>Tipo *</Label>
                <Select value={type} onValueChange={setType} items={TYPE_ITEMS} />
              </div>
              <div className="space-y-1.5">
                <Label>Cuenta *</Label>
                <EntitySelect value={accountId} onChange={setAccountId} queryKey={qk.accounts(false)} queryFn={() => api.listAccounts(false)} />
              </div>
              <div className="space-y-1.5">
                <Label>Monto * ({normalCurrency})</Label>
                <MoneyInput currency={normalCurrency} value={amount} onChange={setAmount} />
              </div>
              <div className="space-y-1.5">
                <Label>Fecha *</Label>
                <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label>Beneficiario</Label>
                <Input value={payee} onChange={(e) => setPayee(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label>Categoría</Label>
                <EntitySelect value={categoryId} onChange={setCategoryId} queryKey={qk.categories(false)} queryFn={() => api.listCategories(false)} allowNullLabel="Sin categoría" />
              </div>
              {normalCurrency !== "COP" && (
                <div className="space-y-1.5">
                  <Label>Tasa USD→COP (opcional)</Label>
                  <Input value={fxRate} onChange={(e) => setFxRate(e.target.value)} placeholder="Se resuelve sola si la dejas vacía" />
                </div>
              )}
              <div className="space-y-1.5">
                <Label>Notas</Label>
                <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
              </div>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
                <Button type="submit" disabled={normalInvalid || createNormal.isPending}>
                  {createNormal.isPending ? "…" : "Crear"}
                </Button>
              </div>
            </form>
          </TabsContent>

          <TabsContent value="transfer">
            <form
              onSubmit={(e) => { e.preventDefault(); if (!transferInvalid) createTransfer.mutate(); }}
              className="space-y-4 pt-2"
            >
              <div className="space-y-1.5">
                <Label>Desde *</Label>
                <EntitySelect value={fromId} onChange={setFromId} queryKey={qk.accounts(false)} queryFn={() => api.listAccounts(false)} />
              </div>
              <div className="space-y-1.5">
                <Label>Hacia *</Label>
                <EntitySelect value={toId} onChange={setToId} queryKey={qk.accounts(false)} queryFn={() => api.listAccounts(false)} />
              </div>
              <div className="space-y-1.5">
                <Label>Monto * ({transferCurrency})</Label>
                <MoneyInput currency={transferCurrency} value={tAmount} onChange={setTAmount} />
              </div>
              <div className="space-y-1.5">
                <Label>Fecha *</Label>
                <Input type="date" value={tDate} onChange={(e) => setTDate(e.target.value)} />
              </div>
              {transferCurrency !== "COP" && (
                <div className="space-y-1.5">
                  <Label>Tasa USD→COP (opcional)</Label>
                  <Input value={tFxRate} onChange={(e) => setTFxRate(e.target.value)} />
                </div>
              )}
              <div className="space-y-1.5">
                <Label>Notas</Label>
                <Textarea value={tNotes} onChange={(e) => setTNotes(e.target.value)} />
              </div>
              <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
                Ambas cuentas deben tener la misma moneda.
              </p>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
                <Button type="submit" disabled={transferInvalid || createTransfer.isPending}>
                  {createTransfer.isPending ? "…" : "Crear"}
                </Button>
              </div>
            </form>
          </TabsContent>
        </Tabs>
      </DialogPopup>
    </Dialog>
  );
}
```

- [ ] **Step 2: Wire into `app/(app)/transactions/page.tsx`**

Add the import and a `creating` state, and pass an action to `PageHeader`:

```tsx
// add imports
import { useState } from "react"; // already imported alongside useMemo
import { TransactionCreateDialog } from "@/components/transaction-create-dialog";

// inside the component, add state:
const [creating, setCreating] = useState(false);

// change the PageHeader line to:
<PageHeader title="Transacciones" action={<Button onClick={() => setCreating(true)}>Nueva</Button>} />

// before the closing </div>, render the dialog:
<TransactionCreateDialog open={creating} onOpenChange={setCreating} />
```

- [ ] **Step 3: Typecheck + lint** → PASS.

- [ ] **Step 4: Manual smoke**: open "Nueva" → Normal tab: create an expense on a COP account (amount in pesos) → appears in the table and the dashboard balance drops. Create an income. On a USD account the amount shows `US$` and the fx-rate field appears (leave empty → backend resolves). Transfer tab: pick two same-currency accounts → creates two legs (`transfer_group_id` shared); both balances move. A transfer between different currencies should surface the backend error toast.

- [ ] **Step 5: Commit**

```bash
git add "frontend/components/transaction-create-dialog.tsx" "frontend/app/(app)/transactions/page.tsx"
git commit -m "feat(frontend): create transaction (normal + transfer)"
```

---

### Task 21: `/transactions` — limited edit + delete

**Files:**
- Create: `frontend/components/transaction-edit-dialog.tsx`
- Modify: `frontend/app/(app)/transactions/page.tsx` (row actions + dialogs)

**Interfaces:**
- Consumes: `api.updateTransaction`, `api.deleteTransaction`, `invalidate(qc, "transactionWrite")`, `formatCents`, `MoneyAmount`, `EntitySelect`, `Textarea`, `Dialog`, `Input`, `Button`, `ConfirmDialog`.
- Produces: `TransactionEditDialog({ tx, open, onOpenChange })` — PATCH only `payee/notes/category_id/date`; immutable fields (type, account, amount, currency) rendered disabled with the note "Para cambiar monto/cuenta, elimina y vuelve a crear." Delete is wired in the page (hard delete; transfers cannot be deleted → guarded with a toast instead of an API call).

- [ ] **Step 1: Create `components/transaction-edit-dialog.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError, type Transaction } from "@/lib/api";
import { qk, invalidate } from "@/lib/query";
import { formatCents } from "@/lib/money";
import { EntitySelect } from "@/components/entity-select";
import { Dialog, DialogPopup, DialogTitle, Input, Label, Textarea, Button } from "@/ui";

export function TransactionEditDialog({
  tx,
  open,
  onOpenChange,
}: {
  tx: Transaction | null;
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const qc = useQueryClient();
  const [payee, setPayee] = useState("");
  const [date, setDate] = useState("");
  const [categoryId, setCategoryId] = useState<number | null>(null);
  const [notes, setNotes] = useState("");

  useEffect(() => {
    if (tx) {
      setPayee(tx.payee ?? "");
      setDate(tx.date);
      setCategoryId(tx.category_id);
      setNotes(tx.notes ?? "");
    }
  }, [tx]);

  const update = useMutation({
    mutationFn: () =>
      api.updateTransaction(tx!.id, {
        payee,
        date,
        category_id: categoryId,
        notes: notes || null,
      }),
    onSuccess: () => {
      toast.success("Transacción actualizada");
      invalidate(qc, "transactionWrite");
      onOpenChange(false);
    },
    onError: (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error"),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPopup>
        <DialogTitle>Editar transacción</DialogTitle>
        {tx && (
          <form onSubmit={(e) => { e.preventDefault(); update.mutate(); }} className="space-y-4">
            <div className="rounded-lg border p-3 text-sm" style={{ borderColor: "var(--border)", color: "var(--muted-foreground)" }}>
              <p>{tx.type} · {formatCents(tx.amount, tx.currency)} · cuenta #{tx.account_id}</p>
              <p className="mt-1 text-xs">Para cambiar monto/cuenta, elimina y vuelve a crear.</p>
            </div>
            <div className="space-y-1.5">
              <Label>Beneficiario</Label>
              <Input value={payee} onChange={(e) => setPayee(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Fecha</Label>
              <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Categoría</Label>
              <EntitySelect
                value={categoryId}
                onChange={setCategoryId}
                queryKey={qk.categories(false)}
                queryFn={() => api.listCategories(false)}
                allowNullLabel="Sin categoría"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Notas</Label>
              <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
              <Button type="submit" disabled={update.isPending}>{update.isPending ? "…" : "Guardar"}</Button>
            </div>
          </form>
        )}
      </DialogPopup>
    </Dialog>
  );
}
```

- [ ] **Step 2: Wire row actions + delete into `app/(app)/transactions/page.tsx`**

Add imports and state:

```tsx
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ApiError } from "@/lib/api";
import { invalidate } from "@/lib/query";
import { TransactionEditDialog } from "@/components/transaction-edit-dialog";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { type RowAction } from "@/components/data-table";

// inside the component:
const qc = useQueryClient();
const [editing, setEditing] = useState<Transaction | null>(null);
const [deleting, setDeleting] = useState<Transaction | null>(null);

const del = useMutation({
  mutationFn: (id: number) => api.deleteTransaction(id),
  onSuccess: () => {
    toast.success("Transacción eliminada");
    invalidate(qc, "transactionWrite");
    setDeleting(null);
  },
  onError: (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error"),
});

const actions: RowAction<Transaction>[] = [
  { label: "Editar", onClick: (t) => setEditing(t) },
  {
    label: "Eliminar",
    variant: "destructive",
    onClick: (t) => {
      if (t.type === "transfer") {
        toast.error("Las transferencias no se pueden eliminar (Fase 1).");
        return;
      }
      setDeleting(t);
    },
  },
];
```

Pass `actions={actions}` to `<DataTable>`, and render after it:

```tsx
<TransactionEditDialog tx={editing} open={editing !== null} onOpenChange={(o) => !o && setEditing(null)} />
<ConfirmDialog
  open={deleting !== null}
  onOpenChange={(o) => !o && setDeleting(null)}
  title="Eliminar transacción"
  description={`Se eliminará "${deleting?.payee || "(sin beneficiario)"}". Es permanente.`}
  confirmLabel="Eliminar"
  destructive
  pending={del.isPending}
  onConfirm={() => deleting && del.mutate(deleting.id)}
/>
```

- [ ] **Step 3: Typecheck + lint** → PASS.

- [ ] **Step 4: Manual smoke**: row menu → "Editar" opens with immutable fields shown read-only; change payee/date/category/notes → saves and reflects in the table. "Eliminar" on a normal tx confirms then removes it (balance reverts if it was posted). "Eliminar" on a transfer toasts the guard and does not call the API.

- [ ] **Step 5: Commit**

```bash
git add "frontend/components/transaction-edit-dialog.tsx" "frontend/app/(app)/transactions/page.tsx"
git commit -m "feat(frontend): limited edit + delete for transactions"
```

---

### Task 22: `/to-pay` — planned queue (confirm / skip / plan one-off)

**Files:**
- Create: `frontend/app/(app)/to-pay/page.tsx`

**Interfaces:**
- Consumes: `api.toPay`, `api.confirmPayment`, `api.skipPlanned`, `api.planPayment`, `api.listAccounts`, `api.listCategories`; `qk.toPay`; `invalidate(qc, "plannedWrite")`; `date-fns` window helpers; `MoneyAmount`, `MoneyInput`, `EntitySelect`, `Dialog`, `Input`, `Textarea`, `Button`, `StatusBadge`, `formatCents`, `ErrorState`, `EmptyState`, `PageHeader`.
- Confirm body: `{ amount?, date? }` (prefilled from the item). Skip: no body. Plan one-off: `{ payee, amount, due_date, account_id, currency?, category_id?, notes? }`.

- [ ] **Step 1: Create `app/(app)/to-pay/page.tsx`**

```tsx
"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { startOfWeek, endOfWeek, startOfMonth, endOfMonth, format } from "date-fns";
import { toast } from "sonner";
import { api, ApiError, type Transaction } from "@/lib/api";
import { qk, invalidate } from "@/lib/query";
import { formatCents } from "@/lib/money";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/error-state";
import { EmptyState } from "@/components/empty-state";
import { MoneyAmount } from "@/components/money-amount";
import { MoneyInput } from "@/components/money-input";
import { EntitySelect } from "@/components/entity-select";
import { Dialog, DialogPopup, DialogTitle, Input, Label, Textarea, Button } from "@/ui";

type Scope = "week" | "month";

function windowFor(scope: Scope) {
  const now = new Date();
  const [since, until] =
    scope === "week"
      ? [startOfWeek(now, { weekStartsOn: 1 }), endOfWeek(now, { weekStartsOn: 1 })]
      : [startOfMonth(now), endOfMonth(now)];
  return { since: format(since, "yyyy-MM-dd"), until: format(until, "yyyy-MM-dd") };
}

export default function ToPayPage() {
  const qc = useQueryClient();
  const [scope, setScope] = useState<Scope>("week");
  const { since, until } = windowFor(scope);

  const [confirming, setConfirming] = useState<Transaction | null>(null);
  const [cAmount, setCAmount] = useState<number | null>(null);
  const [cDate, setCDate] = useState("");

  const [planning, setPlanning] = useState(false);
  const [pPayee, setPPayee] = useState("");
  const [pAmount, setPAmount] = useState<number | null>(null);
  const [pDue, setPDue] = useState("");
  const [pAccount, setPAccount] = useState<number | null>(null);
  const [pCategory, setPCategory] = useState<number | null>(null);
  const [pNotes, setPNotes] = useState("");

  const list = useQuery({ queryKey: qk.toPay(since, until), queryFn: () => api.toPay(since, until) });

  const onErr = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error");
  const done = (msg: string) => { toast.success(msg); invalidate(qc, "plannedWrite"); };

  const confirm = useMutation({
    mutationFn: () =>
      api.confirmPayment(confirming!.id, {
        amount: cAmount ?? undefined,
        date: cDate || undefined,
      }),
    onSuccess: () => { done("Pago confirmado"); setConfirming(null); },
    onError: onErr,
  });
  const skip = useMutation({
    mutationFn: (id: number) => api.skipPlanned(id),
    onSuccess: () => done("Pago omitido"),
    onError: onErr,
  });
  const plan = useMutation({
    mutationFn: () =>
      api.planPayment({
        payee: pPayee,
        amount: pAmount!,
        due_date: pDue,
        account_id: pAccount!,
        category_id: pCategory,
        notes: pNotes || undefined,
      }),
    onSuccess: () => {
      done("Pago planeado");
      setPlanning(false);
      setPPayee(""); setPAmount(null); setPDue(""); setPAccount(null); setPCategory(null); setPNotes("");
    },
    onError: onErr,
  });

  function openConfirm(item: Transaction) {
    setConfirming(item);
    setCAmount(item.amount);
    setCDate(item.date);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Por pagar"
        action={<Button onClick={() => setPlanning(true)}>Planear pago</Button>}
      />

      <div className="inline-flex items-center gap-1 rounded-md p-0.5" style={{ background: "var(--muted)" }}>
        {(["week", "month"] as Scope[]).map((s) => (
          <button
            key={s}
            onClick={() => setScope(s)}
            className="rounded px-2.5 py-1 text-xs transition-all"
            style={{
              background: scope === s ? "var(--card)" : "transparent",
              color: scope === s ? "var(--foreground)" : "var(--muted-foreground)",
              fontWeight: scope === s ? 500 : 400,
            }}
          >
            {s === "week" ? "Esta semana" : "Este mes"}
          </button>
        ))}
      </div>

      {list.isError && <ErrorState message="No se pudo cargar lo pendiente" onRetry={() => list.refetch()} />}

      {list.data && (
        <>
          <p className="text-3xl font-bold tabular-nums tracking-tight">{formatCents(list.data.total_base, "COP")}</p>
          {list.data.items.length === 0 ? (
            <EmptyState message="Nada pendiente en este periodo." />
          ) : (
            <ul className="divide-y" style={{ borderColor: "var(--border)" }}>
              {list.data.items.map((item) => (
                <li key={item.id} className="flex items-center justify-between gap-4 py-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{item.payee || "—"}</p>
                    <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>{item.date}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <MoneyAmount cents={item.amount} currency={item.currency} className="text-sm font-medium" />
                    <Button size="sm" onClick={() => openConfirm(item)}>Confirmar</Button>
                    <Button size="sm" variant="ghost" disabled={skip.isPending} onClick={() => skip.mutate(item.id)}>
                      Omitir
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      {/* Confirm dialog */}
      <Dialog open={confirming !== null} onOpenChange={(o) => !o && setConfirming(null)}>
        <DialogPopup className="max-w-sm">
          <DialogTitle>Confirmar pago</DialogTitle>
          {confirming && (
            <form onSubmit={(e) => { e.preventDefault(); confirm.mutate(); }} className="space-y-4">
              <div className="space-y-1.5">
                <Label>Monto real ({confirming.currency})</Label>
                <MoneyInput currency={confirming.currency} value={cAmount} onChange={setCAmount} />
              </div>
              <div className="space-y-1.5">
                <Label>Fecha</Label>
                <Input type="date" value={cDate} onChange={(e) => setCDate(e.target.value)} />
              </div>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => setConfirming(null)}>Cancelar</Button>
                <Button type="submit" disabled={confirm.isPending}>{confirm.isPending ? "…" : "Confirmar"}</Button>
              </div>
            </form>
          )}
        </DialogPopup>
      </Dialog>

      {/* Plan one-off dialog */}
      <Dialog open={planning} onOpenChange={setPlanning}>
        <DialogPopup>
          <DialogTitle>Planear pago</DialogTitle>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (pPayee && pAmount !== null && pDue && pAccount !== null) plan.mutate();
            }}
            className="space-y-4"
          >
            <div className="space-y-1.5">
              <Label>Beneficiario *</Label>
              <Input value={pPayee} onChange={(e) => setPPayee(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Cuenta *</Label>
              <EntitySelect value={pAccount} onChange={setPAccount} queryKey={qk.accounts(false)} queryFn={() => api.listAccounts(false)} />
            </div>
            <div className="space-y-1.5">
              <Label>Monto * (COP)</Label>
              <MoneyInput currency="COP" value={pAmount} onChange={setPAmount} />
            </div>
            <div className="space-y-1.5">
              <Label>Fecha de vencimiento *</Label>
              <Input type="date" value={pDue} onChange={(e) => setPDue(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Categoría</Label>
              <EntitySelect value={pCategory} onChange={setPCategory} queryKey={qk.categories(false)} queryFn={() => api.listCategories(false)} allowNullLabel="Sin categoría" />
            </div>
            <div className="space-y-1.5">
              <Label>Notas</Label>
              <Textarea value={pNotes} onChange={(e) => setPNotes(e.target.value)} />
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setPlanning(false)}>Cancelar</Button>
              <Button type="submit" disabled={plan.isPending || !pPayee || pAmount === null || !pDue || pAccount === null}>
                {plan.isPending ? "…" : "Planear"}
              </Button>
            </div>
          </form>
        </DialogPopup>
      </Dialog>
    </div>
  );
}
```

Note: the plan one-off form fixes currency to COP (the `planPayment` default; the API requires it to match the account currency). If the user needs a non-COP planned payment, that is a Phase-2 refinement — keep COP here to match the contract's default and the single-user common case.

- [ ] **Step 2: Typecheck + lint** → PASS.

- [ ] **Step 3: Manual smoke**: list shows planned items + `total_base`; week/month toggle changes the window. Confirm opens prefilled with the item's amount/date → confirming posts it (it leaves the list; dashboard/balances update). Omitir skips it. "Planear pago" creates a one-off that then appears in the queue (within the active window).

- [ ] **Step 4: Commit**

```bash
git add "frontend/app/(app)/to-pay/page.tsx"
git commit -m "feat(frontend): /to-pay confirm/skip/plan one-off"
```

---

### Task 23: `/recurring` — list + create + skip (Phase-2 banner)

**Files:**
- Create: `frontend/components/phase2-banner.tsx`
- Create: `frontend/app/(app)/recurring/page.tsx`

**Interfaces:**
- Produces: `Phase2Banner({ children })` — a small info banner (reused by `/goals`, `/budgets`).
- Consumes: `api.listRecurring`, `api.createRecurring`, `api.skipRecurring`, `api.listAccounts`; `qk.recurring`, `qk.accounts`; `invalidate(qc, "recurringWrite")`; `MoneyInput`, `MoneyAmount`, `EntitySelect`, `StatusBadge`, `Dialog`, `Select`, `Input`, `Button`, `formatCents`, `ErrorState`, `EmptyState`, `PageHeader`.
- Create body: `{ name, type, mode, amount, account_id, interval_unit, start_date, payee?, currency?, category_id?, interval_count?, end_date? }`. Skip body: `{ due_date }`.

- [ ] **Step 1: Create `components/phase2-banner.tsx`**

```tsx
export function Phase2Banner({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="rounded-lg border px-4 py-3 text-sm"
      style={{ borderColor: "var(--border)", background: "var(--muted)", color: "var(--muted-foreground)" }}
    >
      {children}
    </div>
  );
}
```

- [ ] **Step 2: Create `app/(app)/recurring/page.tsx`**

```tsx
"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  api, ApiError, type Recurring, type Account,
  type IntervalUnit, type RecurringMode, type RecurringType,
} from "@/lib/api";
import { qk, invalidate } from "@/lib/query";
import { formatCents } from "@/lib/money";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/error-state";
import { EmptyState } from "@/components/empty-state";
import { StatusBadge } from "@/components/status-badge";
import { Phase2Banner } from "@/components/phase2-banner";
import { MoneyInput } from "@/components/money-input";
import { MoneyAmount } from "@/components/money-amount";
import { EntitySelect } from "@/components/entity-select";
import { Dialog, DialogPopup, DialogTitle, Select, Input, Label, Button } from "@/ui";

const TYPE_ITEMS = [
  { value: "expense", label: "Gasto" },
  { value: "income", label: "Ingreso" },
];
const MODE_ITEMS = [
  { value: "auto", label: "Automático" },
  { value: "manual", label: "Manual" },
];
const UNIT_ITEMS = [
  { value: "day", label: "Día(s)" },
  { value: "week", label: "Semana(s)" },
  { value: "month", label: "Mes(es)" },
  { value: "year", label: "Año(s)" },
];

const UNIT_SINGULAR: Record<IntervalUnit, string> = { day: "día", week: "semana", month: "mes", year: "año" };
const UNIT_PLURAL: Record<IntervalUnit, string> = { day: "días", week: "semanas", month: "meses", year: "años" };

function intervalLabel(unit: IntervalUnit, count: number): string {
  if (count === 1) return `Cada ${UNIT_SINGULAR[unit]}`;
  return `Cada ${count} ${UNIT_PLURAL[unit]}`;
}

function currencyOf(accounts: Account[] | undefined, id: number | null): string {
  if (id === null) return "COP";
  return accounts?.find((a) => a.id === id)?.currency ?? "COP";
}

export default function RecurringPage() {
  const qc = useQueryClient();
  const accounts = useQuery({ queryKey: qk.accounts(false), queryFn: () => api.listAccounts(false) });
  const list = useQuery({ queryKey: qk.recurring(), queryFn: () => api.listRecurring() });

  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [type, setType] = useState<string | null>("expense");
  const [mode, setMode] = useState<string | null>("manual");
  const [accountId, setAccountId] = useState<number | null>(null);
  const [categoryId, setCategoryId] = useState<number | null>(null);
  const [amount, setAmount] = useState<number | null>(null);
  const [unit, setUnit] = useState<string | null>("month");
  const [count, setCount] = useState<number | null>(1);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [payee, setPayee] = useState("");

  const [skipping, setSkipping] = useState<Recurring | null>(null);
  const [skipDate, setSkipDate] = useState("");

  const currency = currencyOf(accounts.data, accountId);
  const onErr = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error");
  const done = (msg: string) => { toast.success(msg); invalidate(qc, "recurringWrite"); };

  const create = useMutation({
    mutationFn: () =>
      api.createRecurring({
        name,
        type: type as RecurringType,
        mode: mode as RecurringMode,
        amount: amount!,
        account_id: accountId!,
        interval_unit: unit as IntervalUnit,
        interval_count: count ?? 1,
        start_date: startDate,
        end_date: endDate || null,
        currency,
        category_id: categoryId,
        payee: payee || undefined,
      }),
    onSuccess: () => {
      done("Recurrente creado");
      setCreating(false);
      setName(""); setAmount(null); setStartDate(""); setEndDate(""); setPayee("");
      setAccountId(null); setCategoryId(null); setCount(1);
    },
    onError: onErr,
  });

  const skip = useMutation({
    mutationFn: () => api.skipRecurring(skipping!.id, skipDate),
    onSuccess: () => { done("Ocurrencia omitida"); setSkipping(null); setSkipDate(""); },
    onError: onErr,
  });

  const invalid = !name || amount === null || accountId === null || !unit || !startDate || !type || !mode;

  return (
    <div className="space-y-6">
      <PageHeader title="Recurrentes" action={<Button onClick={() => setCreating(true)}>Nuevo</Button>} />

      <Phase2Banner>Editar y eliminar recurrentes llega en la Fase 2 (requiere endpoints del backend).</Phase2Banner>

      {list.isError && <ErrorState message="No se pudieron cargar los recurrentes" onRetry={() => list.refetch()} />}
      {list.data && list.data.length === 0 && <EmptyState message="Sin recurrentes" />}

      {list.data && list.data.length > 0 && (
        <div className="overflow-hidden rounded-lg border" style={{ borderColor: "var(--border)" }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ color: "var(--muted-foreground)" }}>
                <th className="px-3 py-2.5 text-left text-xs font-medium">Nombre</th>
                <th className="px-3 py-2.5 text-left text-xs font-medium">Frecuencia</th>
                <th className="px-3 py-2.5 text-left text-xs font-medium">Modo</th>
                <th className="px-3 py-2.5 text-right text-xs font-medium">Monto</th>
                <th className="w-24 px-3 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {list.data.map((r) => (
                <tr key={r.id} className="border-t" style={{ borderColor: "var(--border)" }}>
                  <td className="px-3 py-2.5 font-medium">{r.name}</td>
                  <td className="px-3 py-2.5" style={{ color: "var(--muted-foreground)" }}>
                    {intervalLabel(r.interval_unit, r.interval_count)}
                  </td>
                  <td className="px-3 py-2.5"><StatusBadge kind="mode" value={r.mode} /></td>
                  <td className="px-3 py-2.5 text-right">
                    <MoneyAmount cents={r.amount} currency={r.currency} type={r.type} />
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    <Button variant="ghost" size="sm" onClick={() => setSkipping(r)}>Omitir</Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create dialog */}
      <Dialog open={creating} onOpenChange={setCreating}>
        <DialogPopup className="max-w-lg">
          <DialogTitle>Nuevo recurrente</DialogTitle>
          <form onSubmit={(e) => { e.preventDefault(); if (!invalid) create.mutate(); }} className="space-y-4">
            <div className="space-y-1.5"><Label>Nombre *</Label><Input value={name} onChange={(e) => setName(e.target.value)} /></div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5"><Label>Tipo *</Label><Select value={type} onValueChange={setType} items={TYPE_ITEMS} /></div>
              <div className="space-y-1.5"><Label>Modo *</Label><Select value={mode} onValueChange={setMode} items={MODE_ITEMS} /></div>
            </div>
            <div className="space-y-1.5">
              <Label>Cuenta *</Label>
              <EntitySelect value={accountId} onChange={setAccountId} queryKey={qk.accounts(false)} queryFn={() => api.listAccounts(false)} />
            </div>
            <div className="space-y-1.5"><Label>Monto * ({currency})</Label><MoneyInput currency={currency} value={amount} onChange={setAmount} /></div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5"><Label>Cada (cantidad) *</Label>
                <Input type="number" min={1} value={count === null ? "" : String(count)} onChange={(e) => setCount(e.target.value === "" ? null : Number(e.target.value))} />
              </div>
              <div className="space-y-1.5"><Label>Unidad *</Label><Select value={unit} onValueChange={setUnit} items={UNIT_ITEMS} /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5"><Label>Inicio *</Label><Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} /></div>
              <div className="space-y-1.5"><Label>Fin (opcional)</Label><Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} /></div>
            </div>
            <div className="space-y-1.5">
              <Label>Categoría</Label>
              <EntitySelect value={categoryId} onChange={setCategoryId} queryKey={qk.categories(false)} queryFn={() => api.listCategories(false)} allowNullLabel="Sin categoría" />
            </div>
            <div className="space-y-1.5"><Label>Beneficiario</Label><Input value={payee} onChange={(e) => setPayee(e.target.value)} /></div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setCreating(false)}>Cancelar</Button>
              <Button type="submit" disabled={invalid || create.isPending}>{create.isPending ? "…" : "Crear"}</Button>
            </div>
          </form>
        </DialogPopup>
      </Dialog>

      {/* Skip dialog */}
      <Dialog open={skipping !== null} onOpenChange={(o) => !o && setSkipping(null)}>
        <DialogPopup className="max-w-sm">
          <DialogTitle>Omitir ocurrencia</DialogTitle>
          {skipping && (
            <form onSubmit={(e) => { e.preventDefault(); if (skipDate) skip.mutate(); }} className="space-y-4">
              <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
                Indica la fecha de la ocurrencia de &quot;{skipping.name}&quot; que quieres omitir.
              </p>
              <div className="space-y-1.5"><Label>Fecha de la ocurrencia *</Label><Input type="date" value={skipDate} onChange={(e) => setSkipDate(e.target.value)} /></div>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => setSkipping(null)}>Cancelar</Button>
                <Button type="submit" disabled={!skipDate || skip.isPending}>{skip.isPending ? "…" : "Omitir"}</Button>
              </div>
            </form>
          )}
        </DialogPopup>
      </Dialog>
    </div>
  );
}
```

- [ ] **Step 3: Typecheck + lint** → PASS.

- [ ] **Step 4: Manual smoke**: list renders frequency human-readable ("Cada 2 semanas", "Mensual"→"Cada mes"), mode badge, amount colored by type. Create a recurring (e.g. monthly auto, every-2-weeks manual) → appears. "Omitir" with a due date → succeeds (skips that occurrence). Phase-2 banner is visible; no edit/delete actions exist.

- [ ] **Step 5: Commit**

```bash
git add "frontend/components/phase2-banner.tsx" "frontend/app/(app)/recurring/page.tsx"
git commit -m "feat(frontend): /recurring list + create + skip"
```

---

## Phase D — Planning (read-only) + Settings

### Task 24: `/goals` — read-only + Phase-2 banner

**Files:**
- Create: `frontend/app/(app)/goals/page.tsx`

**Interfaces:**
- Consumes: `api.goalsProgress`; `qk.goalsProgress`; `formatCents`; `StatusBadge` (`onTrack`), `Phase2Banner`, `PageHeader`, `ErrorState`, `EmptyState`. All numbers (`saved`, `target_amount`, `monthly_required`, `remaining`) arrive resolved (COP cents) — render only.

- [ ] **Step 1: Create `app/(app)/goals/page.tsx`**

```tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { qk } from "@/lib/query";
import { formatCents } from "@/lib/money";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/error-state";
import { EmptyState } from "@/components/empty-state";
import { StatusBadge } from "@/components/status-badge";
import { Phase2Banner } from "@/components/phase2-banner";

export default function GoalsPage() {
  const goals = useQuery({ queryKey: qk.goalsProgress(), queryFn: () => api.goalsProgress() });

  return (
    <div className="space-y-6">
      <PageHeader title="Metas" />
      <Phase2Banner>Crear y contribuir a metas llega en la Fase 2 (requiere endpoints del backend).</Phase2Banner>

      {goals.isError && <ErrorState message="No se pudieron cargar las metas" onRetry={() => goals.refetch()} />}
      {goals.data && goals.data.length === 0 && <EmptyState message="Sin metas activas" />}

      {goals.data && goals.data.length > 0 && (
        <div className="space-y-3">
          {goals.data.map((g) => {
            const pct = g.target_amount ? Math.min(100, Math.round((g.saved / g.target_amount) * 100)) : null;
            return (
              <div key={g.goal_id} className="space-y-3 rounded-lg border p-5" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium">{g.name}</span>
                  {g.on_track !== null && <StatusBadge kind="onTrack" value={g.on_track} />}
                </div>

                <div className="flex items-baseline justify-between gap-2 text-sm">
                  <span style={{ color: "var(--muted-foreground)" }}>
                    {formatCents(g.saved, "COP")}{g.target_amount !== null && ` / ${formatCents(g.target_amount, "COP")}`}
                  </span>
                  {pct !== null && <span className="tabular-nums">{pct}%</span>}
                </div>

                {pct !== null && (
                  <div className="h-1.5 overflow-hidden rounded-full" style={{ background: "var(--muted)" }}>
                    <div className="h-full rounded-full" style={{ width: `${pct}%`, background: "var(--foreground)" }} />
                  </div>
                )}

                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs" style={{ color: "var(--muted-foreground)" }}>
                  {g.monthly_required !== null && <span>Requerido/mes: {formatCents(g.monthly_required, "COP")}</span>}
                  {g.remaining !== null && <span>Restante: {formatCents(g.remaining, "COP")}</span>}
                  {g.eta && <span>ETA: {g.eta}</span>}
                  {g.deadline && <span>Fecha límite: {g.deadline}</span>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Typecheck + lint** → PASS.

- [ ] **Step 3: Manual smoke**: each active goal shows saved/target, %, progress bar, on-track badge, monthly-required/remaining/ETA when present. Banner visible; no write controls.

- [ ] **Step 4: Commit**

```bash
git add "frontend/app/(app)/goals/page.tsx"
git commit -m "feat(frontend): /goals read-only view"
```

---

### Task 25: `/budgets` — read-only (month selector + safe-to-spend + envelopes) + Phase-2 banner

**Files:**
- Create: `frontend/app/(app)/budgets/page.tsx`

**Interfaces:**
- Consumes: `api.safeToSpend(month)`, `api.report(month)` (for envelope status); `qk.safeToSpend`, `qk.report`; `formatCents`; `Phase2Banner`, `PageHeader`, `ErrorState`, `Input`. All figures arrive resolved — render only.

- [ ] **Step 1: Create `app/(app)/budgets/page.tsx`**

```tsx
"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { format } from "date-fns";
import { api } from "@/lib/api";
import { qk } from "@/lib/query";
import { formatCents } from "@/lib/money";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/error-state";
import { Phase2Banner } from "@/components/phase2-banner";
import { Input } from "@/ui";

function Row({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4 py-1.5">
      <span className="text-sm" style={{ color: strong ? "var(--foreground)" : "var(--muted-foreground)" }}>{label}</span>
      <span className={`tabular-nums ${strong ? "text-sm font-semibold" : "text-sm"}`}>{value}</span>
    </div>
  );
}

export default function BudgetsPage() {
  const [month, setMonth] = useState(format(new Date(), "yyyy-MM"));
  const sts = useQuery({ queryKey: qk.safeToSpend(month), queryFn: () => api.safeToSpend(month) });
  const report = useQuery({ queryKey: qk.report(month), queryFn: () => api.report(month) });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Presupuestos"
        subtitle={month}
        action={<Input type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="w-40" />}
      />
      <Phase2Banner>Asignar a sobres y manejar presupuestos llega en la Fase 2 (requiere endpoints del backend).</Phase2Banner>

      {sts.isError && <ErrorState message="No se pudo cargar disponible para gastar" onRetry={() => sts.refetch()} />}

      {sts.data && (
        <div className="space-y-4 rounded-lg border p-5" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
          <div>
            <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>Disponible para gastar</p>
            <p className="text-4xl font-bold tabular-nums tracking-tight">{formatCents(sts.data.free, "COP")}</p>
          </div>
          <hr style={{ borderColor: "var(--border)" }} />
          <div>
            <Row label="Ingreso previsto" value={formatCents(sts.data.income_forecast, "COP")} />
            <Row label="Comprometido" value={formatCents(sts.data.committed, "COP")} />
            <Row label="Asignado a sobres" value={formatCents(sts.data.assigned_envelopes, "COP")} />
            <Row label="Libre" value={formatCents(sts.data.free, "COP")} strong />
          </div>
          {sts.data.committed_breakdown.length > 0 && (
            <>
              <hr style={{ borderColor: "var(--border)" }} />
              <div className="space-y-1">
                <p className="text-xs font-medium uppercase tracking-wider" style={{ color: "var(--muted-foreground)" }}>Comprometido</p>
                {sts.data.committed_breakdown.map((c, i) => (
                  <Row key={`${c.name}-${c.date}-${i}`} label={`${c.name} · ${c.date}`} value={formatCents(c.amount, "COP")} />
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {report.data && report.data.envelopes.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-medium" style={{ color: "var(--muted-foreground)" }}>Sobres</h2>
          <div className="overflow-hidden rounded-lg border" style={{ borderColor: "var(--border)" }}>
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--muted-foreground)" }}>
                  <th className="px-3 py-2.5 text-left text-xs font-medium">Categoría</th>
                  <th className="px-3 py-2.5 text-right text-xs font-medium">Asignado</th>
                  <th className="px-3 py-2.5 text-right text-xs font-medium">Gastado</th>
                  <th className="px-3 py-2.5 text-right text-xs font-medium">Disponible</th>
                </tr>
              </thead>
              <tbody>
                {report.data.envelopes.map((e) => (
                  <tr key={e.category} className="border-t" style={{ borderColor: "var(--border)" }}>
                    <td className="px-3 py-2.5">{e.category}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums" style={{ color: "var(--muted-foreground)" }}>{formatCents(e.allocated, "COP")}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums" style={{ color: "var(--muted-foreground)" }}>{formatCents(e.spent, "COP")}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums font-medium" style={{ color: e.status === "over" ? "var(--expense)" : "var(--income)" }}>
                      {formatCents(e.available, "COP")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Typecheck + lint** → PASS.

- [ ] **Step 3: Manual smoke**: month selector changes the data; safe-to-spend breakdown (income/committed/assigned/free) renders; committed breakdown lists items; envelopes table shows allocated/spent/available with over-budget colored. Banner visible; no write controls.

- [ ] **Step 4: Commit**

```bash
git add "frontend/app/(app)/budgets/page.tsx"
git commit -m "feat(frontend): /budgets read-only view"
```

---

### Task 26: `/settings` — default source account + manual FX override

**Files:**
- Create: `frontend/app/(app)/settings/page.tsx`

**Interfaces:**
- Consumes: `api.getSettings`, `api.updateSettings`, `api.getFx`, `api.setFx`, `api.listAccounts`; `qk.settings`, `qk.fx`, `qk.accounts`; `invalidate(qc, "settingsWrite")` and `invalidate(qc, "fxWrite")`; `EntitySelect`, `Input`, `Label`, `Button`, `PageHeader`, `ErrorState`. `ApiError` with `code === "MissingRate"` (status 409) when no FX exists yet — render "Sin tasa registrada", not an error state.

- [ ] **Step 1: Create `app/(app)/settings/page.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import { qk, invalidate } from "@/lib/query";
import { PageHeader } from "@/components/page-header";
import { EntitySelect } from "@/components/entity-select";
import { Input, Label, Button } from "@/ui";

const TODAY = format(new Date(), "yyyy-MM-dd");

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <h2 className="text-sm font-medium" style={{ color: "var(--muted-foreground)" }}>{title}</h2>
      <div className="space-y-4 rounded-lg border p-5" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
        {children}
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const qc = useQueryClient();
  const settings = useQuery({ queryKey: qk.settings(), queryFn: () => api.getSettings() });
  const fx = useQuery({
    queryKey: qk.fx(),
    queryFn: () => api.getFx(),
    retry: false, // a 409 MissingRate is an expected "no rate yet" state, not a transient error
  });

  const [sourceId, setSourceId] = useState<number | null>(null);
  useEffect(() => {
    if (settings.data) setSourceId(settings.data.default_source_account_id);
  }, [settings.data]);

  const [fxDate, setFxDate] = useState(TODAY);
  const [usdCop, setUsdCop] = useState("");

  const onErr = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error");

  const saveSettings = useMutation({
    mutationFn: () => api.updateSettings({ default_source_account_id: sourceId }),
    onSuccess: () => { toast.success("Ajustes guardados"); invalidate(qc, "settingsWrite"); },
    onError: onErr,
  });

  const saveFx = useMutation({
    mutationFn: () => api.setFx({ date: fxDate, usd_cop: usdCop }),
    onSuccess: () => { toast.success("Tasa registrada"); invalidate(qc, "fxWrite"); setUsdCop(""); },
    onError: onErr,
  });

  const fxMissing = fx.isError && fx.error instanceof ApiError && fx.error.code === "MissingRate";

  return (
    <div className="space-y-6">
      <PageHeader title="Ajustes" />

      <Section title="Cuenta origen por defecto">
        <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
          Cuenta usada como origen de las contribuciones a metas y transferencias planeadas.
        </p>
        <div className="space-y-1.5">
          <Label>Cuenta origen</Label>
          <EntitySelect
            value={sourceId}
            onChange={setSourceId}
            queryKey={qk.accounts(false)}
            queryFn={() => api.listAccounts(false)}
            allowNullLabel="Ninguna"
          />
        </div>
        <div className="flex justify-end">
          <Button onClick={() => saveSettings.mutate()} disabled={saveSettings.isPending}>
            {saveSettings.isPending ? "…" : "Guardar"}
          </Button>
        </div>
      </Section>

      <Section title="Tasa USD→COP (override manual)">
        <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
          Tasa actual:{" "}
          {fx.isLoading
            ? "…"
            : fxMissing
            ? "Sin tasa registrada"
            : fx.data
            ? `${fx.data.usd_cop} (${fx.data.date})`
            : "—"}
        </p>
        <form
          onSubmit={(e) => { e.preventDefault(); if (usdCop) saveFx.mutate(); }}
          className="grid grid-cols-2 gap-3"
        >
          <div className="space-y-1.5">
            <Label>Fecha</Label>
            <Input type="date" value={fxDate} onChange={(e) => setFxDate(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label>USD→COP</Label>
            <Input inputMode="decimal" value={usdCop} onChange={(e) => setUsdCop(e.target.value)} placeholder="4000.00" />
          </div>
          <div className="col-span-2 flex justify-end">
            <Button type="submit" disabled={!usdCop || saveFx.isPending}>{saveFx.isPending ? "…" : "Registrar tasa"}</Button>
          </div>
        </form>
      </Section>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck + lint** → PASS.

- [ ] **Step 3: Manual smoke**: the default-source select preselects the saved value; change + Guardar persists (reload keeps it). FX section shows the latest rate (or "Sin tasa registrada"); registering a date + rate persists and the "Tasa actual" line refreshes. A non-COP transaction with no rate should then succeed (cross-check on `/transactions` create).

- [ ] **Step 4: Commit**

```bash
git add "frontend/app/(app)/settings/page.tsx"
git commit -m "feat(frontend): /settings default source account + FX override"
```

---

## Final verification

- [ ] **Run the full gate from `frontend/`:** `pnpm lint && pnpm exec tsc --noEmit && pnpm build`. All three pass.
- [ ] **Walk the Phase-1 "done" checklist (spec §"Testing and done criteria") against `pnpm dev` + a real backend:**
  1. Sidebar renders all 12 routes; active highlight; responsive drawer; logout clears.
  2. Transactions: filterable table; create (normal + transfer); limited edit; delete — each reflected in dashboard/balances.
  3. To-pay: list + confirm + skip + plan one-off.
  4. Recurring: list + create + skip; Phase-2 banner.
  5. Masters: accounts/categories/category-groups/tags CRUD with correct archive-vs-delete + filters.
  6. Planning: goals + budgets render read-only with Phase-2 banners.
  7. Settings: default source account + FX override persist.
  8. Thin-client purity: no business arithmetic in `lib/` or components (the only numeric transform is `MoneyInput` text↔cents).

---

## Self-Review (author's checklist — verified while writing)

**Spec coverage** — every spec screen/requirement maps to a task:
- `/transactions` full CRUD + transfer + filters → Tasks 19–21. `/to-pay` confirm/skip/plan → Task 22. `/recurring` create/list/skip + banner → Task 23.
- Masters `/accounts` `/categories` `/category-groups` `/tags` → Tasks 15–18 (archive-vs-delete semantics encoded per entity).
- Read-only `/goals` `/budgets` + banners → Tasks 24–25. `/settings` → Task 26.
- Generic scaffold (`EntityFormDialog` + simple list) for the 4 masters → Task 13 + Tasks 15–18. Bespoke pages for transactions/to-pay/recurring → Tasks 19–23.
- `ui/` primitives (dialog/select/checkbox/textarea/dropdown-menu) under the ADR-0002 boundary → Tasks 3–7. Shared components → Tasks 8–14. `lib/api.ts` ~35 methods + types → Task 1. `lib/query.ts` keys + invalidation map → Task 2. Sidebar nav → Task 14.
- Error handling (toast on mutation, ErrorState on load, 401 redirect, MissingRate) → Task 1 (`ApiError`, 401 hook), Task 2 (Providers), per-page mutations, Task 26 (MissingRate).
- Out of scope honored: no `/import`, no goals/budgets writes, no recurring edit/delete, no un-archive, no automated test runner, client-side paging only.

**Type consistency** — names are stable across tasks: `api.listAccounts/listCategories/listCategoryGroups/listTags`, `qk.<entity>(archived?)`, `invalidate(qc, "<group>Write")`, `Field`/`FormValues` (Task 13) consumed by Tasks 15–18, `Column`/`RowAction` (Task 12) consumed by Tasks 19/21, `Phase2Banner` (Task 23) reused in Tasks 24/25, `parseMoneyToCents`/`MoneyInput` (Task 8) consumed by forms.

**Known verification points for the implementer** (flagged inline): base-ui part/prop names (`Select.items`/`onValueChange`, `Checkbox.onCheckedChange`, `Menu` parts, `DialogPrimitive` parts, `MenuTrigger render`) should be confirmed against `frontend/node_modules/@base-ui/react/**/*.d.ts` on first use; the `Select` empty-string "Todos" sentinel (Task 19) may need a non-empty sentinel.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-20-P6-frontend-crud.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
