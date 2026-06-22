# Axios Migration + API Folder Split

- **Date:** 2026-06-21
- **Status:** approved
- **Deciders:** Angelo

## Goal

Replace the monolithic `frontend/lib/api.ts` with an axios-based client split into
per-entity modules. Eliminates manual `JSON.stringify` and explicit `method:` strings
from every API call, and enforces single-responsibility per file.

## Architecture

### Folder structure

```
frontend/lib/api/
  client.ts          — axios instance, interceptors, typed helpers (get/post/patch/put/del), qs()
  types.ts           — all TypeScript interfaces/types, ApiError class, setUnauthorizedHandler
  auth.ts            — login, logout, me
  transactions.ts    — listTransactions, getTransaction, createTransaction, updateTransaction,
                       deleteTransaction, createTransfer
  planned.ts         — toPay, planPayment, confirmPayment, skipPlanned
  recurring.ts       — listRecurring, createRecurring, updateRecurring, skipRecurring,
                       deleteRecurring, restoreRecurring
  accounts.ts        — listAccounts, getAccount, createAccount, updateAccount,
                       archiveAccount, restoreAccount
  categories.ts      — listCategories, createCategory, updateCategory,
                       archiveCategory, restoreCategory
  category-groups.ts — listCategoryGroups, createCategoryGroup, updateCategoryGroup,
                       archiveCategoryGroup, restoreCategoryGroup
  tags.ts            — listTags, createTag, updateTag, deleteTag
  settings.ts        — getSettings, updateSettings
  fx.ts              — getFx, setFx
  goals.ts           — listGoals, createGoal, updateGoal, pauseGoal, restoreGoal,
                       contributeGoal, goalsProgress
  budgets.ts         — listBudgets, assignBudget, safeToSpend
  reports.ts         — report
  index.ts           — barrel: re-exports all named exports + types
```

The old `frontend/lib/api.ts` is deleted.

### client.ts

Creates an axios instance with:
- `baseURL: '/api'`
- `withCredentials: true`
- `headers: { 'Content-Type': 'application/json' }`

**Success interceptor:** returns `response.data`; returns `undefined` when status is 204.

**Error interceptor:**
- 401 on a non-`/auth` URL → calls `onUnauthorized?.()`, returns `undefined`
- All other errors → throws `ApiError(status, data.error, data.detail)`

**Typed helpers** (exported for entity modules):

```ts
export const get   = <T>(url: string)                 => http.get<T>(url)        as unknown as Promise<T>
export const post  = <T>(url: string, data?: unknown) => http.post<T>(url, data) as unknown as Promise<T>
export const patch = <T>(url: string, data?: unknown) => http.patch<T>(url, data) as unknown as Promise<T>
export const put   = <T>(url: string, data?: unknown) => http.put<T>(url, data)  as unknown as Promise<T>
export const del   = <T>(url: string)                 => http.delete<T>(url)     as unknown as Promise<T>
```

The `as unknown as Promise<T>` cast is required because the interceptor transforms
`AxiosResponse<T>` → `T` at runtime but TypeScript's type system does not track that.

**`qs()` helper** is preserved in `client.ts` unchanged — it filters `undefined`/empty
values before building query strings.

### types.ts

Contains all existing interfaces verbatim plus `ApiError` and `setUnauthorizedHandler`.
Entity modules import their types from here.

### Entity modules

Each file imports `{ get, post, patch, put, del, qs }` from `./client` and its types
from `./types`. Each function is a named export.

Example (`goals.ts`):

```ts
import { get, post, patch, del } from './client'
import type { Goal, GoalCreate, GoalUpdate, GoalContributeBody, GoalContribution, GoalProgress } from './types'

export const listGoals      = ()                                   => get<Goal[]>('/goals')
export const createGoal     = (body: GoalCreate)                   => post<Goal>('/goals', body)
export const updateGoal     = (id: number, body: GoalUpdate)       => patch<Goal>(`/goals/${id}`, body)
export const pauseGoal      = (id: number)                         => del<void>(`/goals/${id}`)
export const restoreGoal    = (id: number)                         => post<Goal>(`/goals/${id}/restore`)
export const contributeGoal = (id: number, b: GoalContributeBody)  => post<GoalContribution>(`/goals/${id}/contribute`, b)
export const goalsProgress  = ()                                   => get<GoalProgress[]>('/goals/progress')
```

### index.ts (barrel)

Re-exports everything so consumers can do either:

```ts
import { listGoals } from '@/lib/api/goals'   // preferred — explicit
import { listGoals } from '@/lib/api'          // also valid via barrel
```

## Consumer updates

All pages and hooks under `frontend/app/` that currently do:

```ts
import { api } from '@/lib/api'
api.listGoals()
```

must be updated to:

```ts
import { listGoals } from '@/lib/api/goals'
listGoals()
```

Type imports (`Goal`, `ApiError`, etc.) move to `@/lib/api/types` or `@/lib/api`.

## What does not change

- `ApiError` class shape and throw behavior
- `setUnauthorizedHandler` / `onUnauthorized` pattern
- `qs()` logic
- All TypeScript interface definitions
- All component and hook logic beyond the import lines

## Dependencies

- Add `axios` to `frontend/` (`pnpm add axios` inside `frontend/`)
- No other new dependencies

## Error handling

`ApiError` is thrown from the axios error interceptor. Consumers catch it the same
way as today — no changes needed beyond the import path.

## Testing

No dedicated unit tests exist for `lib/api.ts` today. After migration, smoke-test
each page manually to confirm requests succeed and errors (401, non-2xx) still
surface correctly.
