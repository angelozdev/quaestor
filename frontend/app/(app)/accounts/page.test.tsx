import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { openHelpPanel } from "@/tests/factories"
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

describe("AC-7 — every screen carries the same control", () => {
  beforeEach(() => {
    listAccounts.mockReset().mockResolvedValue([])
    currentParams = new URLSearchParams("")
  })

  it("Cuentas offers to explain itself", async () => {
    render(<AccountsPage />, { wrapper })

    expect(await openHelpPanel("Cuentas")).toHaveTextContent("Una cuenta es donde está la plata")
  })
})

describe("AC-10 — an empty screen teaches and offers the way in", () => {
  beforeEach(() => {
    listAccounts.mockReset().mockResolvedValue([])
    currentParams = new URLSearchParams("")
  })

  it("An empty Cuentas screen teaches and offers the way in", async () => {
    const user = userEvent.setup()
    render(<AccountsPage />, { wrapper })

    expect(await screen.findByText(/Una cuenta es donde está la plata/)).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Crear la primera" }))

    expect(screen.getByText("Nueva cuenta")).toBeInTheDocument()
  })
})
