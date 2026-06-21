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
