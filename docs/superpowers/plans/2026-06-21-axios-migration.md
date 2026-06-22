# Axios Migration + API Folder Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `frontend/lib/api.ts` with an axios-based client split into per-entity modules; update all 20 consumers to import per-entity named exports instead of `api.x()`.

**Architecture:** One new `frontend/lib/api/` folder. `client.ts` owns the axios instance, two response interceptors (success extracts `.data` and handles 204; error maps to `ApiError` and triggers `onUnauthorized` on 401), the `qs()` helper, and five typed helpers (`get`/`post`/`patch`/`put`/`del`). `types.ts` centralizes all interfaces and `ApiError`. One file per entity exposes named exports. `index.ts` is a barrel. The old `frontend/lib/api.ts` is deleted.

**Tech Stack:** axios, TypeScript, Next.js (App Router), TanStack Query, pnpm

## Global Constraints

- All code in English (ADR-0001).
- pnpm is the sole package manager for the frontend (ADR-0003).
- `setUnauthorizedHandler` must keep working — it is wired in `app/providers.tsx`.
- `ApiError` shape (`{ status, code, message }`) is part of the consumer contract; do not break it.

## File Structure

**Create:**
- `frontend/lib/api/client.ts` — axios instance, interceptors, helpers, `qs()`
- `frontend/lib/api/types.ts` — interfaces, `ApiError`, `setUnauthorizedHandler`
- `frontend/lib/api/auth.ts`, `transactions.ts`, `planned.ts`, `recurring.ts`, `accounts.ts`, `categories.ts`, `category-groups.ts`, `tags.ts`, `settings.ts`, `fx.ts`, `goals.ts`, `budgets.ts`, `reports.ts` — entity modules
- `frontend/lib/api/index.ts` — barrel

**Delete:**
- `frontend/lib/api.ts`

**Modify (20 consumer files):**
- `frontend/app/providers.tsx`
- `frontend/app/(app)/page.tsx`
- `frontend/app/(app)/settings/page.tsx`
- `frontend/app/(app)/to-pay/page.tsx`
- `frontend/app/(app)/category-groups/page.tsx`
- `frontend/app/(app)/goals/page.tsx`
- `frontend/app/(app)/tags/page.tsx`
- `frontend/app/(app)/transactions/page.tsx`
- `frontend/app/(app)/accounts/page.tsx`
- `frontend/app/(app)/budgets/page.tsx`
- `frontend/app/(app)/categories/page.tsx`
- `frontend/app/(app)/recurring/page.tsx`
- `frontend/app/(app)/reports/page.tsx`
- `frontend/app/(auth)/login/page.tsx`
- `frontend/lib/query.ts`
- `frontend/components/transaction-edit-dialog.tsx`
- `frontend/components/to-pay-widget.tsx`
- `frontend/components/money-amount.tsx`
- `frontend/components/transaction-create-dialog.tsx`
- `frontend/components/app-shell.tsx`

---

## Task 1: Install axios and create folder

**Files:**
- Modify: `frontend/package.json` (via `pnpm add`)
- Create: `frontend/lib/api/` (directory)

- [ ] **Step 1: Install axios**

Run from `frontend/`:
```bash
cd frontend && pnpm add axios
```

Expected: package.json shows `"axios"` in dependencies; `frontend/node_modules/axios/` exists.

- [ ] **Step 2: Create the api folder**

```bash
mkdir -p frontend/lib/api
```

- [ ] **Step 3: Verify**

```bash
ls frontend/lib/api && cat frontend/package.json | grep axios
```

Expected: empty directory listing; package.json has axios.

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/pnpm-lock.yaml
git commit -m "chore(frontend): add axios dependency"
```

---

## Task 2: Create types.ts

**Files:**
- Create: `frontend/lib/api/types.ts`

**Interfaces:** `ApiError`, `setUnauthorizedHandler`, `onUnauthorized` slot. All existing interfaces from `frontend/lib/api.ts` lines 1–378 — copied verbatim.

- [ ] **Step 1: Write types.ts**

Copy the full file content from `frontend/lib/api.ts` lines 1–396 (every `export interface`, `export type`, `ApiError` class, `setUnauthorizedHandler` function) into `frontend/lib/api/types.ts`. End the file with:

```ts
export let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null) {
  onUnauthorized = fn;
}
```

(The `onUnauthorized` slot moves out of `client.ts` so it can live next to its sibling `setUnauthorizedHandler` and stay co-located with the public types it sits beside. `client.ts` imports it from `./types`.)

- [ ] **Step 2: Verify no duplicates**

```bash
grep -c "export interface" frontend/lib/api/types.ts
```

Expected: ~40 (matches the count of `export interface` in old `api.ts`).

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/api/types.ts
git commit -m "feat(frontend/api): extract types and ApiError to types.ts"
```

---

## Task 3: Create client.ts with axios instance and helpers

**Files:**
- Create: `frontend/lib/api/client.ts`

- [ ] **Step 1: Write client.ts**

```ts
import axios, { AxiosError } from "axios";
import { ApiError, onUnauthorized } from "./types";

export const http = axios.create({
  baseURL: "/api",
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

http.interceptors.response.use(
  (res) => (res.status === 204 ? undefined : res.data),
  (err: AxiosError) => {
    const url = err.config?.url ?? "";
    if (err.response?.status === 401 && !url.startsWith("/auth")) {
      onUnauthorized?.();
      return undefined as unknown;
    }
    const data = err.response?.data as { error?: string; detail?: string } | null;
    throw new ApiError(
      err.response?.status ?? 0,
      data?.error ?? "Error",
      data?.detail ?? `Request failed (${err.response?.status})`
    );
  }
);

export const get   = <T>(url: string)                 => http.get<T>(url)        as unknown as Promise<T>;
export const post  = <T>(url: string, data?: unknown) => http.post<T>(url, data) as unknown as Promise<T>;
export const patch = <T>(url: string, data?: unknown) => http.patch<T>(url, data) as unknown as Promise<T>;
export const put   = <T>(url: string, data?: unknown) => http.put<T>(url, data)  as unknown as Promise<T>;
export const del   = <T>(url: string)                 => http.delete<T>(url)     as unknown as Promise<T>;

export function qs(params: Record<string, string | number | boolean | undefined>): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") usp.set(k, String(v));
  }
  const s = usp.toString();
  return s ? `?${s}` : "";
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/lib/api/client.ts
git commit -m "feat(frontend/api): add axios client with interceptors and typed helpers"
```

---

## Task 4: Create auth module

**Files:**
- Create: `frontend/lib/api/auth.ts`

- [ ] **Step 1: Write auth.ts**

```ts
import { post, get } from "./client";

export const login  = (password: string) => post<{ ok: boolean }>("/auth/login", { password });
export const logout = ()                  => post<{ ok: boolean }>("/auth/logout");
export const me     = ()                  => get<{ authenticated: boolean }>("/auth/me");
```

- [ ] **Step 2: Commit**

```bash
git add frontend/lib/api/auth.ts
git commit -m "feat(frontend/api): add auth module"
```

---

## Task 5: Create transactions module

**Files:**
- Create: `frontend/lib/api/transactions.ts`

- [ ] **Step 1: Write transactions.ts**

```ts
import { get, post, patch, del, qs } from "./client";
import type {
  Transaction,
  TransactionFilters,
  TransactionCreate,
  TransactionUpdate,
  TransferCreate,
  TransferOut,
} from "./types";

export const listTransactions = (filters: TransactionFilters = {}) =>
  get<Transaction[]>(`/transactions${qs(filters as Record<string, string | number | boolean | undefined>)}`);

export const getTransaction = (id: number) => get<Transaction>(`/transactions/${id}`);

export const createTransaction = (body: TransactionCreate) =>
  post<Transaction>("/transactions", body);

export const createTransfer = (body: TransferCreate) =>
  post<TransferOut>("/transactions/transfer", body);

export const updateTransaction = (id: number, body: TransactionUpdate) =>
  patch<Transaction>(`/transactions/${id}`, body);

export const deleteTransaction = (id: number) => del<void>(`/transactions/${id}`);
```

- [ ] **Step 2: Commit**

```bash
git add frontend/lib/api/transactions.ts
git commit -m "feat(frontend/api): add transactions module"
```

---

## Task 6: Create planned module

**Files:**
- Create: `frontend/lib/api/planned.ts`

- [ ] **Step 1: Write planned.ts**

```ts
import { get, post, qs } from "./client";
import type { ToPay, Transaction, PlanPaymentCreate, ConfirmPaymentBody } from "./types";

export const toPay = (since: string, until: string) =>
  get<ToPay>(`/planned/to-pay${qs({ since, until })}`);

export const planPayment = (body: PlanPaymentCreate) =>
  post<Transaction>("/planned", body);

export const confirmPayment = (id: number, body: ConfirmPaymentBody = {}) =>
  post<Transaction>(`/planned/${id}/confirm`, body);

export const skipPlanned = (id: number) =>
  post<Transaction>(`/planned/${id}/skip`, {});
```

- [ ] **Step 2: Commit**

```bash
git add frontend/lib/api/planned.ts
git commit -m "feat(frontend/api): add planned module"
```

---

## Task 7: Create recurring module

**Files:**
- Create: `frontend/lib/api/recurring.ts`

- [ ] **Step 1: Write recurring.ts**

```ts
import { get, post, patch, del, qs } from "./client";
import type { Recurring, RecurringCreate, RecurringUpdate, Occurrence } from "./types";

export const listRecurring = (active?: boolean) =>
  get<Recurring[]>(`/recurring${qs({ active })}`);

export const createRecurring = (body: RecurringCreate) =>
  post<Recurring>("/recurring", body);

export const skipRecurring = (id: number, due_date: string) =>
  post<Occurrence>(`/recurring/${id}/skip`, { due_date });

export const updateRecurring = (id: number, body: RecurringUpdate) =>
  patch<Recurring>(`/recurring/${id}`, body);

export const deleteRecurring = (id: number) => del<void>(`/recurring/${id}`);

export const restoreRecurring = (id: number) =>
  post<Recurring>(`/recurring/${id}/restore`, {});
```

- [ ] **Step 2: Commit**

```bash
git add frontend/lib/api/recurring.ts
git commit -m "feat(frontend/api): add recurring module"
```

---

## Task 8: Create accounts module

**Files:**
- Create: `frontend/lib/api/accounts.ts`

- [ ] **Step 1: Write accounts.ts**

```ts
import { get, post, patch, del, qs } from "./client";
import type { Account, AccountCreate, AccountUpdate } from "./types";

export const listAccounts = (archived = false) =>
  get<Account[]>(`/accounts${qs({ archived })}`);

export const getAccount = (id: number) => get<Account>(`/accounts/${id}`);

export const createAccount = (body: AccountCreate) =>
  post<Account>("/accounts", body);

export const updateAccount = (id: number, body: AccountUpdate) =>
  patch<Account>(`/accounts/${id}`, body);

export const archiveAccount = (id: number) => del<void>(`/accounts/${id}`);

export const restoreAccount = (id: number) =>
  post<Account>(`/accounts/${id}/restore`, {});
```

- [ ] **Step 2: Commit**

```bash
git add frontend/lib/api/accounts.ts
git commit -m "feat(frontend/api): add accounts module"
```

---

## Task 9: Create categories module

**Files:**
- Create: `frontend/lib/api/categories.ts`

- [ ] **Step 1: Write categories.ts**

```ts
import { get, post, patch, del, qs } from "./client";
import type { Category, CategoryCreate, CategoryUpdate } from "./types";

export const listCategories = (archived = false) =>
  get<Category[]>(`/categories${qs({ archived })}`);

export const createCategory = (body: CategoryCreate) =>
  post<Category>("/categories", body);

export const updateCategory = (id: number, body: CategoryUpdate) =>
  patch<Category>(`/categories/${id}`, body);

export const archiveCategory = (id: number) => del<void>(`/categories/${id}`);

export const restoreCategory = (id: number) =>
  post<Category>(`/categories/${id}/restore`, {});
```

- [ ] **Step 2: Commit**

```bash
git add frontend/lib/api/categories.ts
git commit -m "feat(frontend/api): add categories module"
```

---

## Task 10: Create category-groups module

**Files:**
- Create: `frontend/lib/api/category-groups.ts`

- [ ] **Step 1: Write category-groups.ts**

```ts
import { get, post, patch, del, qs } from "./client";
import type { CategoryGroup, CategoryGroupCreate, CategoryGroupUpdate } from "./types";

export const listCategoryGroups = (archived = false) =>
  get<CategoryGroup[]>(`/category-groups${qs({ archived })}`);

export const createCategoryGroup = (body: CategoryGroupCreate) =>
  post<CategoryGroup>("/category-groups", body);

export const updateCategoryGroup = (id: number, body: CategoryGroupUpdate) =>
  patch<CategoryGroup>(`/category-groups/${id}`, body);

export const archiveCategoryGroup = (id: number) =>
  del<void>(`/category-groups/${id}`);

export const restoreCategoryGroup = (id: number) =>
  post<CategoryGroup>(`/category-groups/${id}/restore`, {});
```

- [ ] **Step 2: Commit**

```bash
git add frontend/lib/api/category-groups.ts
git commit -m "feat(frontend/api): add category-groups module"
```

---

## Task 11: Create tags module

**Files:**
- Create: `frontend/lib/api/tags.ts`

- [ ] **Step 1: Write tags.ts**

```ts
import { get, post, patch, del } from "./client";
import type { Tag, TagCreate, TagUpdate } from "./types";

export const listTags    = ()                  => get<Tag[]>("/tags");
export const createTag   = (body: TagCreate)   => post<Tag>("/tags", body);
export const updateTag   = (id: number, body: TagUpdate) => patch<Tag>(`/tags/${id}`, body);
export const deleteTag   = (id: number)        => del<void>(`/tags/${id}`);
```

- [ ] **Step 2: Commit**

```bash
git add frontend/lib/api/tags.ts
git commit -m "feat(frontend/api): add tags module"
```

---

## Task 12: Create settings module

**Files:**
- Create: `frontend/lib/api/settings.ts`

- [ ] **Step 1: Write settings.ts**

```ts
import { get, patch } from "./client";
import type { Settings, SettingsUpdate } from "./types";

export const getSettings    = ()                          => get<Settings>("/settings");
export const updateSettings = (body: SettingsUpdate)       => patch<Settings>("/settings", body);
```

- [ ] **Step 2: Commit**

```bash
git add frontend/lib/api/settings.ts
git commit -m "feat(frontend/api): add settings module"
```

---

## Task 13: Create fx module

**Files:**
- Create: `frontend/lib/api/fx.ts`

- [ ] **Step 1: Write fx.ts**

```ts
import { get, post, qs } from "./client";
import type { Fx, FxCreate } from "./types";

export const getFx = (date?: string) => get<Fx>(`/fx${qs({ date })}`);
export const setFx = (body: FxCreate) => post<Fx>("/fx", body);
```

- [ ] **Step 2: Commit**

```bash
git add frontend/lib/api/fx.ts
git commit -m "feat(frontend/api): add fx module"
```

---

## Task 14: Create goals module

**Files:**
- Create: `frontend/lib/api/goals.ts`

- [ ] **Step 1: Write goals.ts**

```ts
import { get, post, patch, del } from "./client";
import type {
  Goal,
  GoalCreate,
  GoalUpdate,
  GoalContributeBody,
  GoalContribution,
  GoalProgress,
} from "./types";

export const listGoals      = ()                                  => get<Goal[]>("/goals");
export const createGoal     = (body: GoalCreate)                  => post<Goal>("/goals", body);
export const updateGoal     = (id: number, body: GoalUpdate)      => patch<Goal>(`/goals/${id}`, body);
export const pauseGoal      = (id: number)                        => del<void>(`/goals/${id}`);
export const restoreGoal    = (id: number)                        => post<Goal>(`/goals/${id}/restore`, {});
export const contributeGoal = (id: number, body: GoalContributeBody) =>
  post<GoalContribution>(`/goals/${id}/contribute`, body);
export const goalsProgress  = ()                                  => get<GoalProgress[]>("/goals/progress");
```

- [ ] **Step 2: Commit**

```bash
git add frontend/lib/api/goals.ts
git commit -m "feat(frontend/api): add goals module"
```

---

## Task 15: Create budgets module

**Files:**
- Create: `frontend/lib/api/budgets.ts`

- [ ] **Step 1: Write budgets.ts**

```ts
import { get, put, qs } from "./client";
import type { BudgetLine, BudgetAssign, SafeToSpend } from "./types";

export const listBudgets  = (month: string) => get<BudgetLine[]>(`/budgets${qs({ month })}`);
export const assignBudget = (body: BudgetAssign) => put<BudgetLine>("/budgets", body);
export const safeToSpend  = (month: string) => get<SafeToSpend>(`/budgets/safe-to-spend${qs({ month })}`);
```

- [ ] **Step 2: Commit**

```bash
git add frontend/lib/api/budgets.ts
git commit -m "feat(frontend/api): add budgets module"
```

---

## Task 16: Create reports module

**Files:**
- Create: `frontend/lib/api/reports.ts`

- [ ] **Step 1: Write reports.ts**

```ts
import { get, qs } from "./client";
import type { MonthlyReport } from "./types";

export const report = (month: string) => get<MonthlyReport>(`/reports${qs({ month })}`);
```

- [ ] **Step 2: Commit**

```bash
git add frontend/lib/api/reports.ts
git commit -m "feat(frontend/api): add reports module"
```

---

## Task 17: Create index.ts barrel

**Files:**
- Create: `frontend/lib/api/index.ts`

- [ ] **Step 1: Write index.ts**

```ts
export * from "./auth";
export * from "./transactions";
export * from "./planned";
export * from "./recurring";
export * from "./accounts";
export * from "./categories";
export * from "./category-groups";
export * from "./tags";
export * from "./settings";
export * from "./fx";
export * from "./goals";
export * from "./budgets";
export * from "./reports";

export { ApiError, setUnauthorizedHandler, onUnauthorized } from "./types";
export type * from "./types";
```

- [ ] **Step 2: Verify build works before deleting the old file**

Run from `frontend/`:
```bash
cd frontend && pnpm tsc --noEmit
```

Expected: no errors. (The old `frontend/lib/api.ts` is still present and is the only file exporting `api`/`ApiError`. The new folder is also importable. If tsc complains about duplicate exports, it means `types.ts` and the old `api.ts` both export `ApiError` — that's fine, they are at different paths, but `app/providers.tsx` etc. still import the old one.)

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/api/index.ts
git commit -m "feat(frontend/api): add barrel index"
```

---

## Task 18: Delete old api.ts

**Files:**
- Delete: `frontend/lib/api.ts`

- [ ] **Step 1: Remove the old file**

```bash
rm frontend/lib/api.ts
```

- [ ] **Step 2: Verify**

```bash
ls frontend/lib/api* 2>/dev/null
```

Expected: only `frontend/lib/api/` (folder) is listed; `frontend/lib/api.ts` is gone.

- [ ] **Step 3: Commit**

```bash
git add -u frontend/lib/api.ts
git commit -m "refactor(frontend): remove old monolithic api.ts"
```

---

## Task 19: Update providers.tsx

**Files:**
- Modify: `frontend/app/providers.tsx`

- [ ] **Step 1: Update the import**

Replace:
```ts
import { setUnauthorizedHandler } from "@/lib/api";
```
with:
```ts
import { setUnauthorizedHandler } from "@/lib/api";
```

(Wait — that import path still resolves because of the new barrel `frontend/lib/api/index.ts`. Verified: path `@/lib/api` resolves to `frontend/lib/api/index.ts` if `frontend/lib/api.ts` no longer exists. The barrel re-exports `setUnauthorizedHandler` from `types.ts`. No code change needed; just confirm it still works after Task 18.)

- [ ] **Step 2: Verify**

```bash
cd frontend && pnpm tsc --noEmit 2>&1 | head -30
```

Expected: no errors mentioning `setUnauthorizedHandler` or `app/providers.tsx`.

- [ ] **Step 3: Commit only if a change was made**

```bash
git diff --quiet frontend/app/providers.tsx || (git add frontend/app/providers.tsx && git commit -m "chore(frontend): import setUnauthorizedHandler from api barrel")
```

(If `git diff` is empty, skip the commit.)

---

## Task 20: Update login page

**Files:**
- Modify: `frontend/app/(auth)/login/page.tsx`

- [ ] **Step 1: Replace the import and call**

Replace the import line:
```ts
import { api, ApiError } from "@/lib/api";
```
with:
```ts
import { login } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/types";
```

Replace:
```ts
await api.login(password);
```
with:
```ts
await login(password);
```

- [ ] **Step 2: Verify**

```bash
cd frontend && pnpm tsc --noEmit 2>&1 | grep "login/page" | head
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(auth\)/login/page.tsx
git commit -m "refactor(frontend): use login from api/auth module"
```

---

## Task 21: Update app-shell

**Files:**
- Modify: `frontend/components/app-shell.tsx`

- [ ] **Step 1: Replace the import and call**

Replace:
```ts
import { api } from "@/lib/api";
```
with:
```ts
import { logout } from "@/lib/api/auth";
```

Replace:
```ts
await api.logout();
```
with:
```ts
await logout();
```

- [ ] **Step 2: Verify**

```bash
cd frontend && pnpm tsc --noEmit 2>&1 | grep "app-shell" | head
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/app-shell.tsx
git commit -m "refactor(frontend): use logout from api/auth module"
```

---

## Task 22: Update to-pay-widget

**Files:**
- Modify: `frontend/components/to-pay-widget.tsx`

- [ ] **Step 1: Replace the import and calls**

Replace:
```ts
import { api } from "@/lib/api";
```
with:
```ts
import { toPay, confirmPayment } from "@/lib/api/planned";
```

Replace:
```ts
queryFn: () => api.toPay(since, until),
```
with:
```ts
queryFn: () => toPay(since, until),
```

Replace:
```ts
mutationFn: (id: number) => api.confirmPayment(id),
```
with:
```ts
mutationFn: (id: number) => confirmPayment(id),
```

- [ ] **Step 2: Verify**

```bash
cd frontend && pnpm tsc --noEmit 2>&1 | grep "to-pay-widget" | head
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/to-pay-widget.tsx
git commit -m "refactor(frontend): use planned module in to-pay-widget"
```

---

## Task 23: Update money-amount

**Files:**
- Modify: `frontend/components/money-amount.tsx`

- [ ] **Step 1: Update the import**

Replace:
```ts
import type { TxType } from "@/lib/api";
```
with:
```ts
import type { TxType } from "@/lib/api/types";
```

(Or leave as `@/lib/api` — the barrel re-exports types. Pick the explicit form for consistency.)

- [ ] **Step 2: Verify**

```bash
cd frontend && pnpm tsc --noEmit 2>&1 | grep "money-amount" | head
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/money-amount.tsx
git commit -m "refactor(frontend): import TxType from api/types"
```

---

## Task 24: Update lib/query.ts

**Files:**
- Modify: `frontend/lib/query.ts`

- [ ] **Step 1: Update the type import**

Replace:
```ts
import type { TransactionFilters } from "@/lib/api";
```
with:
```ts
import type { TransactionFilters } from "@/lib/api/types";
```

- [ ] **Step 2: Verify**

```bash
cd frontend && pnpm tsc --noEmit 2>&1 | grep "lib/query" | head
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/query.ts
git commit -m "refactor(frontend): import TransactionFilters from api/types"
```

---

## Task 25: Update dashboard page (app/(app)/page.tsx)

**Files:**
- Modify: `frontend/app/(app)/page.tsx`

- [ ] **Step 1: Replace import and calls**

Replace:
```ts
import { api } from "@/lib/api";
```
with:
```ts
import { safeToSpend } from "@/lib/api/budgets";
import { report } from "@/lib/api/reports";
import { goalsProgress } from "@/lib/api/goals";
import { listAccounts } from "@/lib/api/accounts";
```

Replace each `api.x()` call inside the file (lines 49–52):
- `api.safeToSpend(MONTH)` → `safeToSpend(MONTH)`
- `api.report(MONTH)` → `report(MONTH)`
- `api.goalsProgress()` → `goalsProgress()`
- `api.listAccounts()` → `listAccounts()`

- [ ] **Step 2: Verify**

```bash
cd frontend && pnpm tsc --noEmit 2>&1 | grep "(app)/page" | head
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(app\)/page.tsx
git commit -m "refactor(frontend): use entity modules in dashboard"
```

---

## Task 26: Update settings page

**Files:**
- Modify: `frontend/app/(app)/settings/page.tsx`

- [ ] **Step 1: Replace import and calls**

Replace:
```ts
import { api, ApiError } from "@/lib/api";
```
with:
```ts
import { getSettings, updateSettings } from "@/lib/api/settings";
import { getFx, setFx } from "@/lib/api/fx";
import { listAccounts } from "@/lib/api/accounts";
import { ApiError } from "@/lib/api/types";
```

Replace each `api.x()` call (lines 28, 31, 47, 53, 74):
- `api.getSettings()` → `getSettings()`
- `api.getFx()` → `getFx()`
- `api.updateSettings(...)` → `updateSettings(...)`
- `api.setFx(...)` → `setFx(...)`
- `api.listAccounts(false)` → `listAccounts(false)`

- [ ] **Step 2: Verify**

```bash
cd frontend && pnpm tsc --noEmit 2>&1 | grep "settings/page" | head
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(app\)/settings/page.tsx
git commit -m "refactor(frontend): use entity modules in settings page"
```

---

## Task 27: Update to-pay page

**Files:**
- Modify: `frontend/app/(app)/to-pay/page.tsx`

- [ ] **Step 1: Replace import and calls**

Replace:
```ts
import { api, ApiError, type Account, type Transaction } from "@/lib/api";
```
with:
```ts
import { toPay, planPayment, confirmPayment, skipPlanned } from "@/lib/api/planned";
import { listAccounts } from "@/lib/api/accounts";
import { listCategories } from "@/lib/api/categories";
import { ApiError, type Account, type Transaction } from "@/lib/api/types";
```

Replace each `api.x()` call (lines 50, 51, 60, 68, 74, 189, 201):
- `api.toPay(since, until)` → `toPay(since, until)`
- `api.listAccounts(false)` → `listAccounts(false)` (3 occurrences)
- `api.confirmPayment(confirming!.id, ...)` → `confirmPayment(confirming!.id, ...)`
- `api.skipPlanned(id)` → `skipPlanned(id)`
- `api.planPayment(...)` → `planPayment(...)`
- `api.listCategories(false)` → `listCategories(false)`

- [ ] **Step 2: Verify**

```bash
cd frontend && pnpm tsc --noEmit 2>&1 | grep "to-pay/page" | head
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(app\)/to-pay/page.tsx
git commit -m "refactor(frontend): use entity modules in to-pay page"
```

---

## Task 28: Update category-groups page

**Files:**
- Modify: `frontend/app/(app)/category-groups/page.tsx`

- [ ] **Step 1: Replace import and calls**

Replace:
```ts
import { api, ApiError, type CategoryGroup } from "@/lib/api";
```
with:
```ts
import { listCategoryGroups, createCategoryGroup, updateCategoryGroup, archiveCategoryGroup, restoreCategoryGroup } from "@/lib/api/category-groups";
import { ApiError, type CategoryGroup } from "@/lib/api/types";
```

Replace each `api.x()` call (lines 30, 41, 47, 52, 57):
- `api.listCategoryGroups(showArchived)` → `listCategoryGroups(showArchived)`
- `api.createCategoryGroup(...)` → `createCategoryGroup(...)`
- `api.updateCategoryGroup(...)` → `updateCategoryGroup(...)`
- `api.archiveCategoryGroup(id)` → `archiveCategoryGroup(id)`
- `api.restoreCategoryGroup(id)` → `restoreCategoryGroup(id)`

- [ ] **Step 2: Verify**

```bash
cd frontend && pnpm tsc --noEmit 2>&1 | grep "category-groups/page" | head
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(app\)/category-groups/page.tsx
git commit -m "refactor(frontend): use category-groups module in page"
```

---

## Task 29: Update goals page

**Files:**
- Modify: `frontend/app/(app)/goals/page.tsx`

- [ ] **Step 1: Replace import and calls**

Replace:
```ts
import { api, ApiError, type Goal } from "@/lib/api";
```
with:
```ts
import { listGoals, createGoal, updateGoal, pauseGoal, restoreGoal, contributeGoal, goalsProgress } from "@/lib/api/goals";
import { listAccounts } from "@/lib/api/accounts";
import { ApiError, type Goal } from "@/lib/api/types";
```

Replace each `api.x()` call (lines 20, 21, 41, 49, 57, 62, 67, 139):
- `api.listGoals()` → `listGoals()`
- `api.goalsProgress()` → `goalsProgress()`
- `api.createGoal(...)` → `createGoal(...)`
- `api.updateGoal(...)` → `updateGoal(...)`
- `api.pauseGoal(pausing!.id)` → `pauseGoal(pausing!.id)`
- `api.restoreGoal(g.id)` → `restoreGoal(g.id)`
- `api.contributeGoal(...)` → `contributeGoal(...)`
- `api.listAccounts(false)` → `listAccounts(false)`

- [ ] **Step 2: Verify**

```bash
cd frontend && pnpm tsc --noEmit 2>&1 | grep "goals/page" | head
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(app\)/goals/page.tsx
git commit -m "refactor(frontend): use goals + accounts modules in goals page"
```

---

## Task 30: Update tags page

**Files:**
- Modify: `frontend/app/(app)/tags/page.tsx`

- [ ] **Step 1: Replace import and calls**

Replace:
```ts
import { api, ApiError, type Tag } from "@/lib/api";
```
with:
```ts
import { listTags, createTag, updateTag, deleteTag } from "@/lib/api/tags";
import { ApiError, type Tag } from "@/lib/api/types";
```

Replace each `api.x()` call (lines 23, 29, 34, 39):
- `api.listTags()` → `listTags()`
- `api.createTag(...)` → `createTag(...)`
- `api.updateTag(...)` → `updateTag(...)`
- `api.deleteTag(id)` → `deleteTag(id)`

- [ ] **Step 2: Verify**

```bash
cd frontend && pnpm tsc --noEmit 2>&1 | grep "tags/page" | head
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(app\)/tags/page.tsx
git commit -m "refactor(frontend): use tags module in tags page"
```

---

## Task 31: Update transactions page

**Files:**
- Modify: `frontend/app/(app)/transactions/page.tsx`

- [ ] **Step 1: Replace import and calls**

Replace:
```ts
import {
  api,
  ApiError,
  type Transaction,
  type TransactionFilters,
  type TxType,
  type TxStatus,
} from "@/lib/api";
```
with:
```ts
import { listTransactions, deleteTransaction } from "@/lib/api/transactions";
import { listAccounts } from "@/lib/api/accounts";
import { listCategories } from "@/lib/api/categories";
import { listTags } from "@/lib/api/tags";
import {
  ApiError,
  type Transaction,
  type TransactionFilters,
  type TxType,
  type TxStatus,
} from "@/lib/api/types";
```

Replace each `api.x()` call (lines 48, 66, 70, 74, 103, 214, 229, 244):
- `api.deleteTransaction(id)` → `deleteTransaction(id)`
- `api.listAccounts(true)` → `listAccounts(true)` (2 occurrences)
- `api.listCategories(true)` → `listCategories(true)` (2 occurrences)
- `api.listTags()` → `listTags()` (2 occurrences)
- `api.listTransactions(filters)` → `listTransactions(filters)`

- [ ] **Step 2: Verify**

```bash
cd frontend && pnpm tsc --noEmit 2>&1 | grep "transactions/page" | head
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(app\)/transactions/page.tsx
git commit -m "refactor(frontend): use entity modules in transactions page"
```

---

## Task 32: Update accounts page

**Files:**
- Modify: `frontend/app/(app)/accounts/page.tsx`

- [ ] **Step 1: Replace import and calls**

Replace:
```ts
import { api, ApiError, type Account, type AccountType } from "@/lib/api";
```
with:
```ts
import { listAccounts, createAccount, updateAccount, archiveAccount, restoreAccount } from "@/lib/api/accounts";
import { ApiError, type Account, type AccountType } from "@/lib/api/types";
```

Replace each `api.x()` call (lines 49, 57, 68, 73, 78):
- `api.listAccounts(showArchived)` → `listAccounts(showArchived)`
- `api.createAccount(...)` → `createAccount(...)`
- `api.updateAccount(...)` → `updateAccount(...)`
- `api.archiveAccount(id)` → `archiveAccount(id)`
- `api.restoreAccount(id)` → `restoreAccount(id)`

- [ ] **Step 2: Verify**

```bash
cd frontend && pnpm tsc --noEmit 2>&1 | grep "accounts/page" | head
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(app\)/accounts/page.tsx
git commit -m "refactor(frontend): use accounts module in accounts page"
```

---

## Task 33: Update budgets page

**Files:**
- Modify: `frontend/app/(app)/budgets/page.tsx`

- [ ] **Step 1: Replace import and calls**

Replace:
```ts
import { api } from "@/lib/api";
import { ApiError } from "@/lib/api";
```
with:
```ts
import { listBudgets, assignBudget, safeToSpend } from "@/lib/api/budgets";
import { ApiError } from "@/lib/api/types";
```

Replace each `api.x()` call (lines 29, 30, 36):
- `api.safeToSpend(month)` → `safeToSpend(month)`
- `api.listBudgets(month)` → `listBudgets(month)`
- `api.assignBudget(...)` → `assignBudget(...)`

- [ ] **Step 2: Verify**

```bash
cd frontend && pnpm tsc --noEmit 2>&1 | grep "budgets/page" | head
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(app\)/budgets/page.tsx
git commit -m "refactor(frontend): use budgets module in budgets page"
```

---

## Task 34: Update categories page

**Files:**
- Modify: `frontend/app/(app)/categories/page.tsx`

- [ ] **Step 1: Replace import and calls**

Replace:
```ts
import { api, ApiError, type Category } from "@/lib/api";
```
with:
```ts
import { listCategories, createCategory, updateCategory, archiveCategory, restoreCategory } from "@/lib/api/categories";
import { listCategoryGroups } from "@/lib/api/category-groups";
import { ApiError, type Category } from "@/lib/api/types";
```

Replace each `api.x()` call (lines 23, 40, 44, 61, 66, 71, 76):
- `api.listCategoryGroups(false)` → `listCategoryGroups(false)`
- `api.listCategories(showArchived)` → `listCategories(showArchived)`
- `api.listCategoryGroups(true)` → `listCategoryGroups(true)`
- `api.createCategory(...)` → `createCategory(...)`
- `api.updateCategory(...)` → `updateCategory(...)`
- `api.archiveCategory(id)` → `archiveCategory(id)`
- `api.restoreCategory(id)` → `restoreCategory(id)`

- [ ] **Step 2: Verify**

```bash
cd frontend && pnpm tsc --noEmit 2>&1 | grep "categories/page" | head
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(app\)/categories/page.tsx
git commit -m "refactor(frontend): use categories + category-groups modules"
```

---

## Task 35: Update recurring page

**Files:**
- Modify: `frontend/app/(app)/recurring/page.tsx`

- [ ] **Step 1: Replace import and calls**

Replace:
```ts
import {
  api, ApiError, type Recurring, type Account,
  type IntervalUnit, type RecurringMode, type RecurringType,
} from "@/lib/api";
```
with:
```ts
import { listRecurring, createRecurring, updateRecurring, deleteRecurring, restoreRecurring, skipRecurring } from "@/lib/api/recurring";
import { listAccounts } from "@/lib/api/accounts";
import { listCategories } from "@/lib/api/categories";
import {
  ApiError, type Recurring, type Account,
  type IntervalUnit, type RecurringMode, type RecurringType,
} from "@/lib/api/types";
```

Replace each `api.x()` call (lines 51, 56, 83, 108, 120, 126, 132, 212, 227, 250, 265):
- `api.listAccounts(false)` → `listAccounts(false)` (3 occurrences)
- `api.listRecurring(...)` → `listRecurring(...)`
- `api.createRecurring(...)` → `createRecurring(...)`
- `api.updateRecurring(...)` → `updateRecurring(...)`
- `api.deleteRecurring(...)` → `deleteRecurring(...)`
- `api.restoreRecurring(r.id)` → `restoreRecurring(r.id)`
- `api.skipRecurring(...)` → `skipRecurring(...)`
- `api.listCategories(false)` → `listCategories(false)` (2 occurrences)

- [ ] **Step 2: Verify**

```bash
cd frontend && pnpm tsc --noEmit 2>&1 | grep "recurring/page" | head
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(app\)/recurring/page.tsx
git commit -m "refactor(frontend): use recurring + accounts + categories modules"
```

---

## Task 36: Update reports page

**Files:**
- Modify: `frontend/app/(app)/reports/page.tsx`

- [ ] **Step 1: Replace import and calls**

Replace:
```ts
import { api } from "@/lib/api";
```
with:
```ts
import { report } from "@/lib/api/reports";
```

Replace:
```ts
queryFn: () => api.report(month),
```
with:
```ts
queryFn: () => report(month),
```

- [ ] **Step 2: Verify**

```bash
cd frontend && pnpm tsc --noEmit 2>&1 | grep "reports/page" | head
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(app\)/reports/page.tsx
git commit -m "refactor(frontend): use reports module in reports page"
```

---

## Task 37: Update transaction-edit-dialog

**Files:**
- Modify: `frontend/components/transaction-edit-dialog.tsx`

- [ ] **Step 1: Replace import and calls**

Replace:
```ts
import { api, ApiError, type Transaction } from "@/lib/api";
```
with:
```ts
import { updateTransaction } from "@/lib/api/transactions";
import { listCategories } from "@/lib/api/categories";
import { ApiError, type Transaction } from "@/lib/api/types";
```

Replace each `api.x()` call (lines 39, 77):
- `api.updateTransaction(...)` → `updateTransaction(...)`
- `api.listCategories(false)` → `listCategories(false)`

- [ ] **Step 2: Verify**

```bash
cd frontend && pnpm tsc --noEmit 2>&1 | grep "transaction-edit-dialog" | head
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/transaction-edit-dialog.tsx
git commit -m "refactor(frontend): use transactions + categories modules in edit dialog"
```

---

## Task 38: Update transaction-create-dialog

**Files:**
- Modify: `frontend/components/transaction-create-dialog.tsx`

- [ ] **Step 1: Replace import and calls**

Replace:
```ts
import { api, ApiError, type Account } from "@/lib/api";
```
with:
```ts
import { createTransaction, createTransfer } from "@/lib/api/transactions";
import { listAccounts } from "@/lib/api/accounts";
import { listCategories } from "@/lib/api/categories";
import { ApiError, type Account } from "@/lib/api/types";
```

Replace each `api.x()` call (lines 45, 97, 114, 159, 191, 244, 253):
- `api.listAccounts(false)` → `listAccounts(false)` (4 occurrences)
- `api.createTransaction(...)` → `createTransaction(...)`
- `api.createTransfer(...)` → `createTransfer(...)`
- `api.listCategories(false)` → `listCategories(false)`

- [ ] **Step 2: Verify**

```bash
cd frontend && pnpm tsc --noEmit 2>&1 | grep "transaction-create-dialog" | head
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/transaction-create-dialog.tsx
git commit -m "refactor(frontend): use transactions + accounts + categories in create dialog"
```

---

## Task 39: Final verification

- [ ] **Step 1: Type check the whole project**

```bash
cd frontend && pnpm tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 2: Lint**

```bash
cd frontend && pnpm lint
```

Expected: zero errors (warnings ok).

- [ ] **Step 3: Confirm no `api.` calls remain**

```bash
grep -rn "api\." frontend/app frontend/components frontend/lib --include="*.ts" --include="*.tsx" | grep -v "lib/api/" | grep -E "api\.(login|logout|me|list|get|create|update|delete|archive|restore|pause|contribute|plan|confirm|skip|assign|safeToSpend|goalsProgress|report|setFx|setUnauthorizedHandler)" | head
```

Expected: no output — every call uses a named import.

- [ ] **Step 4: Confirm no old import path remains**

```bash
grep -rn 'from "@/lib/api"' frontend/app frontend/components frontend/lib --include="*.ts" --include="*.tsx" | grep -v "lib/api/" | head
```

Expected: no output (or only `from "@/lib/api/types"` and `from "@/lib/api/<entity>"` style imports).

- [ ] **Step 5: Smoke test**

Run:
```bash
cd frontend && pnpm dev
```

Open the dashboard, accounts, transactions, and goals pages in the browser. Confirm requests succeed and 401 (after session expiry) still triggers the redirect to `/login`.

- [ ] **Step 6: Commit any remaining changes**

```bash
git status
```

If only clean, no commit needed. If anything is unstaged, commit with an appropriate conventional message.

---

## Self-Review Notes

- **Spec coverage:** client + types + 13 entity modules + barrel + delete old + 20 consumer updates + verification = all sections of the spec covered.
- **No placeholders:** every step has explicit code or commands.
- **Type consistency:** `onUnauthorized` lives in `types.ts`; `client.ts` imports it. `ApiError` is in `types.ts`; both `client.ts` and consumers import it from `@/lib/api/types`. Helper signatures (`get<T>`, `post<T>`, etc.) are identical across all 13 entity modules.
- **Cast note:** The `as unknown as Promise<T>` cast on each helper is the only unavoidable type concession. The interceptor returns `T`, not `AxiosResponse<T>`, so the helper return type must be cast to match.
- **Barrel caveat:** `index.ts` re-exports `onUnauthorized` and `ApiError` from `./types` so existing `from "@/lib/api"` import paths keep working. This is intentional — see Task 19.
