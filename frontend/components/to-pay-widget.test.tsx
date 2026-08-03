import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { ToPayWidget } from "./to-pay-widget"

const mockToPay = vi.fn()

vi.mock("@/lib/api/planned", () => ({
  toPay: (...args: unknown[]) => mockToPay(...args),
  confirmPayment: vi.fn(),
}))

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe("ToPayWidget", () => {
  beforeEach(() => {
    mockToPay.mockReset()
  })

  it("renders the overdue section when overdue items are present", async () => {
    mockToPay.mockResolvedValue({
      overdue: [
        {
          id: 1,
          payee: "Tigo",
          date: "2026-06-28",
          amount: 85000_00,
          currency: "COP",
        } as never,
      ],
      upcoming: [],
      total_base: 85000_00,
    })
    render(<ToPayWidget />, { wrapper })
    await waitFor(() => expect(screen.getByText("Tigo")).toBeInTheDocument())
    expect(screen.getByText(/vencidos/i)).toBeInTheDocument()
  })

  it("renders the upcoming section when upcoming items are present", async () => {
    mockToPay.mockResolvedValue({
      overdue: [],
      upcoming: [
        {
          id: 2,
          payee: "Rent",
          date: "2026-07-15",
          amount: 500000_00,
          currency: "COP",
        } as never,
      ],
      total_base: 500000_00,
    })
    render(<ToPayWidget />, { wrapper })
    await waitFor(() => expect(screen.getByText("Rent")).toBeInTheDocument())
    expect(screen.getByRole("heading", { name: /esta semana/i })).toBeInTheDocument()
  })

  it("does not render the overdue section when overdue is empty", async () => {
    mockToPay.mockResolvedValue({
      overdue: [],
      upcoming: [{ id: 3, payee: "Foo", date: "2026-07-15", amount: 1, currency: "COP" } as never],
      total_base: 1,
    })
    render(<ToPayWidget />, { wrapper })
    await waitFor(() => expect(screen.getByText("Foo")).toBeInTheDocument())
    expect(screen.queryByText(/vencidos/i)).not.toBeInTheDocument()
  })

  it("shows the total base from the sum of both buckets", async () => {
    mockToPay.mockResolvedValue({
      overdue: [
        { id: 1, payee: "A", date: "2026-06-28", amount: 100_00, currency: "COP" } as never,
      ],
      upcoming: [
        { id: 2, payee: "B", date: "2026-07-15", amount: 200_00, currency: "COP" } as never,
      ],
      total_base: 300_00,
    })
    render(<ToPayWidget />, { wrapper })
    await waitFor(() => expect(screen.getByText("A")).toBeInTheDocument())
    expect(screen.getByText(/300/)).toBeInTheDocument()
  })

  it("shows the empty state when both buckets are empty", async () => {
    mockToPay.mockResolvedValue({ overdue: [], upcoming: [], total_base: 0 })
    render(<ToPayWidget />, { wrapper })
    await waitFor(() => expect(screen.getByText(/nada pendiente/i)).toBeInTheDocument())
  })
})
