import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import AccountsPage from "./page"

const listAccounts = vi.fn()
let currentParams = new URLSearchParams("")

vi.mock("next/navigation", () => ({
  useSearchParams: () => currentParams,
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/accounts",
}))
vi.mock("@/lib/api/accounts", () => ({
  listAccounts: (...a: unknown[]) => listAccounts(...a),
  createAccount: vi.fn(),
  updateAccount: vi.fn(),
  archiveAccount: vi.fn(),
  restoreAccount: vi.fn(),
}))

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe("AccountsPage URL archived filter", () => {
  beforeEach(() => {
    listAccounts.mockReset().mockResolvedValue([])
    currentParams = new URLSearchParams("")
  })

  it("reads archived=true from the URL", async () => {
    currentParams = new URLSearchParams("archived=true")
    render(<AccountsPage />, { wrapper })
    await waitFor(() => expect(listAccounts).toHaveBeenCalledWith(true))
  })

  it("defaults to archived=false when absent", async () => {
    render(<AccountsPage />, { wrapper })
    await waitFor(() => expect(listAccounts).toHaveBeenCalledWith(false))
  })
})
