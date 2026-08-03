import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { Transaction } from "@/lib/api/types"

const CATEGORY_ID = 3

/** A movement as the API returns it. Expenses and incomes carry a category and
 * transfers carry none (ADR-0042), so the default follows `type` unless the
 * caller overrides it. */
export function makeTransaction(overrides: Partial<Transaction> = {}): Transaction {
  const type = overrides.type ?? "expense"
  return {
    id: 1,
    date: "2026-07-10",
    payee: "Exito",
    notes: null,
    type: "expense",
    status: "posted",
    amount: 5_000_000,
    currency: "COP",
    cop_equivalent: 5_000_000,
    account_id: 1,
    category_id: type === "transfer" ? null : CATEGORY_ID,
    transfer_group_id: null,
    transfer_direction: null,
    source: "manual",
    created_at: "2026-07-10T00:00:00Z",
    tags: [],
    ...overrides,
  }
}

export function queryWrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}
