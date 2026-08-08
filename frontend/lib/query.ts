import type { QueryClient } from "@tanstack/react-query"
import type { FundCreate, MetaCreate, TransactionFilters } from "@/lib/api/types"

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
  funds: "funds",
  reports: "reports",
  metas: "metas",
} as const

const DETAIL = "detail" as const

// Query-key factory. First element is the entity root used for broad invalidation.
export const qk = {
  transactions: (filters: TransactionFilters = {}) => [ROOTS.transactions, filters] as const,
  transaction: (id: number) => [ROOTS.transactions, DETAIL, id] as const,
  toPay: (since: string, until: string) => [ROOTS.planned, "to-pay", since, until] as const,
  recurring: (active?: boolean) => [ROOTS.recurring, active ?? "all"] as const,
  pendingDates: (id: number) => [ROOTS.recurring, "pending-dates", id] as const,
  accounts: (archived = false) => [ROOTS.accounts, archived] as const,
  account: (id: number) => [ROOTS.accounts, DETAIL, id] as const,
  categories: (archived = false, isIncome?: boolean) =>
    [ROOTS.categories, archived, isIncome ?? "all"] as const,
  categoryGroups: (archived = false) => [ROOTS.categoryGroups, archived] as const,
  tags: () => [ROOTS.tags] as const,
  settings: () => [ROOTS.settings] as const,
  fx: () => [ROOTS.fx, "latest"] as const,
  moneyAvailable: (month: string) => [ROOTS.funds, "available", month] as const,
  moneyRates: (month: string) => [ROOTS.funds, "rates", month] as const,
  funds: () => [ROOTS.funds, "list"] as const,
  metas: (month: string) => [ROOTS.metas, "list", month] as const,
  metaSplit: (month: string) => [ROOTS.metas, "split", month] as const,
  metaPreview: (body: MetaCreate | null) => [ROOTS.metas, "preview", body] as const,
  fundPreview: (rule: string, body: FundCreate | null) =>
    [ROOTS.funds, "preview", rule, body] as const,
  report: (month: string) => [ROOTS.reports, month] as const,
}

// Each mutation declares the entity roots it must invalidate so derived numbers
// (balances, dashboard, reports) refresh instantly. Roots reference ROOTS so a
// rename forces tsc to flag every invalidation group that needs updating.
export const INVALIDATION = {
  // `categories` is in all three because a movement can create the category it
  // is filed under, in the same request (ADR-0042) — a list that still holds
  // the old set renders the new one as a bare id.
  transactionWrite: [
    [ROOTS.transactions],
    [ROOTS.reports],
    [ROOTS.accounts],
    [ROOTS.funds],
    [ROOTS.planned],
    [ROOTS.categories],
  ],
  plannedWrite: [
    [ROOTS.planned],
    [ROOTS.reports],
    [ROOTS.accounts],
    [ROOTS.funds],
    [ROOTS.categories],
  ],
  recurringWrite: [
    [ROOTS.recurring],
    [ROOTS.planned],
    [ROOTS.reports],
    [ROOTS.funds],
    [ROOTS.transactions],
    [ROOTS.accounts],
    [ROOTS.categories],
  ],
  accountWrite: [[ROOTS.accounts], [ROOTS.settings], [ROOTS.reports], [ROOTS.funds]],
  categoryWrite: [[ROOTS.categories], [ROOTS.reports], [ROOTS.funds]],
  categoryGroupWrite: [[ROOTS.categoryGroups], [ROOTS.categories], [ROOTS.reports]],
  tagWrite: [[ROOTS.tags], [ROOTS.transactions]],
  settingsWrite: [[ROOTS.settings]],
  fxWrite: [
    [ROOTS.fx],
    [ROOTS.reports],
    [ROOTS.funds],
    [ROOTS.accounts],
    [ROOTS.transactions],
    [ROOTS.planned],
  ],
  fundWrite: [[ROOTS.funds], [ROOTS.reports]],
  metaWrite: [[ROOTS.metas], [ROOTS.funds], [ROOTS.reports]],
  // Scoped invalidation triggered by ChatSection's `useChat` onFinish. The
  // MCP tools can mutate any of these entity roots; settings/categories/tags
  // are intentionally excluded (no chat tool mutates them in v1). Never call
  // `qc.invalidateQueries()` without args — that wipes unrelated cards.
  chatAssistantTurn: [
    [ROOTS.transactions],
    [ROOTS.planned],
    [ROOTS.accounts],
    [ROOTS.funds],
    [ROOTS.reports],
    [ROOTS.recurring],
  ],
} as const

export type InvalidationGroup = keyof typeof INVALIDATION

export function invalidate(qc: QueryClient, group: InvalidationGroup) {
  for (const key of INVALIDATION[group]) {
    qc.invalidateQueries({ queryKey: key })
  }
}
