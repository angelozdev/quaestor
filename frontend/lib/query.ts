import type { QueryClient } from "@tanstack/react-query"
import type { TransactionFilters } from "@/lib/api/types"

// Entity roots: single source of truth for query keys + invalidation groups.
// `as const` keeps literal types so downstream key matching stays narrow.
const ROOTS = {
  transactions: "transactions",
  planned: "planned",
  recurring: "recurring",
  accounts: "accounts",
  categories: "categories",
  categoryGroups: "category-groups",
  tags: "tags",
  settings: "settings",
  fx: "fx",
  goals: "goals",
  budgets: "budgets",
  reports: "reports",
} as const

const DETAIL = "detail" as const

// Query-key factory. First element is the entity root used for broad invalidation.
export const qk = {
  transactions: (filters: TransactionFilters = {}) => [ROOTS.transactions, filters] as const,
  transaction: (id: number) => [ROOTS.transactions, DETAIL, id] as const,
  toPay: (since: string, until: string) => [ROOTS.planned, "to-pay", since, until] as const,
  recurring: (active?: boolean) => [ROOTS.recurring, active ?? "all"] as const,
  accounts: (archived = false) => [ROOTS.accounts, archived] as const,
  account: (id: number) => [ROOTS.accounts, DETAIL, id] as const,
  categories: (archived = false) => [ROOTS.categories, archived] as const,
  categoryGroups: (archived = false) => [ROOTS.categoryGroups, archived] as const,
  tags: () => [ROOTS.tags] as const,
  settings: () => [ROOTS.settings] as const,
  fx: (date?: string) => [ROOTS.fx, date ?? "latest"] as const,
  safeToSpend: (month: string) => [ROOTS.budgets, "safe-to-spend", month] as const,
  goalsProgress: () => [ROOTS.goals, "progress"] as const,
  goals: () => [ROOTS.goals, "list"] as const,
  budgets: (month: string) => [ROOTS.budgets, "lines", month] as const,
  report: (month: string) => [ROOTS.reports, month] as const,
}

// Each mutation declares the entity roots it must invalidate so derived numbers
// (balances, dashboard, reports) refresh instantly. Roots reference ROOTS so a
// rename forces tsc to flag every invalidation group that needs updating.
export const INVALIDATION = {
  transactionWrite: [
    [ROOTS.transactions],
    [ROOTS.reports],
    [ROOTS.accounts],
    [ROOTS.budgets],
    [ROOTS.planned],
  ],
  plannedWrite: [[ROOTS.planned], [ROOTS.reports], [ROOTS.accounts], [ROOTS.budgets]],
  recurringWrite: [[ROOTS.recurring], [ROOTS.planned], [ROOTS.reports], [ROOTS.budgets]],
  accountWrite: [[ROOTS.accounts], [ROOTS.settings], [ROOTS.reports], [ROOTS.budgets]],
  categoryWrite: [[ROOTS.categories], [ROOTS.reports], [ROOTS.budgets]],
  categoryGroupWrite: [[ROOTS.categoryGroups], [ROOTS.categories], [ROOTS.reports]],
  tagWrite: [[ROOTS.tags], [ROOTS.transactions]],
  settingsWrite: [[ROOTS.settings]],
  fxWrite: [[ROOTS.fx], [ROOTS.reports], [ROOTS.budgets], [ROOTS.accounts]],
  goalWrite: [[ROOTS.goals], [ROOTS.accounts], [ROOTS.transactions], [ROOTS.reports]],
  budgetWrite: [[ROOTS.budgets], [ROOTS.reports]],
} as const

export type InvalidationGroup = keyof typeof INVALIDATION

export function invalidate(qc: QueryClient, group: InvalidationGroup) {
  for (const key of INVALIDATION[group]) {
    qc.invalidateQueries({ queryKey: key })
  }
}
