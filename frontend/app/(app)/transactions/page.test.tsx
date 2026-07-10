import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import TransactionsPage from "./page"

const listTransactions = vi.fn()
let currentParams = new URLSearchParams("")

vi.mock("next/navigation", () => ({
  useSearchParams: () => currentParams,
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/transactions",
}))
vi.mock("@/lib/api/transactions", () => ({
  listTransactions: (...a: unknown[]) => listTransactions(...a),
  deleteTransaction: vi.fn(),
}))
vi.mock("@/lib/api/accounts", () => ({ listAccounts: vi.fn().mockResolvedValue([]) }))
vi.mock("@/lib/api/categories", () => ({ listCategories: vi.fn().mockResolvedValue([]) }))
vi.mock("@/lib/api/tags", () => ({ listTags: vi.fn().mockResolvedValue([]) }))

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe("TransactionsPage URL filters", () => {
  beforeEach(() => {
    listTransactions.mockReset().mockResolvedValue([])
    currentParams = new URLSearchParams("")
  })

  it("passes URL filters to listTransactions", async () => {
    currentParams = new URLSearchParams("type=expense&account_id=3")
    render(<TransactionsPage />, { wrapper })
    await waitFor(() =>
      expect(listTransactions).toHaveBeenCalledWith({ type: "expense", account_id: 3 }),
    )
  })
})
