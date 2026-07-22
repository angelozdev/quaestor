import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("@/lib/api/budgets", () => ({
  safeToSpend: vi.fn(),
  listBudgets: vi.fn(),
  assignBudget: vi.fn(),
}))

import { listBudgets, safeToSpend } from "@/lib/api/budgets"
import BudgetsPage from "./page"

const STS = {
  year_month: "2026-07",
  income_forecast: 0,
  committed: 0,
  assigned_envelopes: 0,
  free: 0,
  committed_breakdown: [],
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <BudgetsPage />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe("BudgetsPage async states", () => {
  it("shows a skeleton while loading (after the anti-flash delay)", async () => {
    vi.mocked(safeToSpend).mockReturnValue(new Promise(() => {})) // never resolves
    vi.mocked(listBudgets).mockReturnValue(new Promise(() => {}))
    const { container } = renderPage()
    await waitFor(() =>
      expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0),
    )
  })

  it("shows the error state with retry when safe-to-spend fails", async () => {
    vi.mocked(safeToSpend).mockRejectedValue(new Error("boom"))
    vi.mocked(listBudgets).mockResolvedValue([])
    renderPage()
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /reintentar/i })).toBeInTheDocument(),
    )
  })

  it("shows an empty state when there are no envelopes", async () => {
    vi.mocked(safeToSpend).mockResolvedValue(STS)
    vi.mocked(listBudgets).mockResolvedValue([])
    renderPage()
    await waitFor(() => expect(screen.getByText("Aún no hay sobres este mes")).toBeInTheDocument())
  })
})
