import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { openHelpPanel, queryWrapper } from "@/tests/factories"

const { toPay } = vi.hoisted(() => ({ toPay: vi.fn() }))

vi.mock("@/lib/api/planned", () => ({
  toPay,
  confirmPayment: vi.fn(),
  skipPlanned: vi.fn(),
  planPayment: vi.fn(),
}))
vi.mock("@/lib/api/accounts", () => ({ listAccounts: vi.fn().mockResolvedValue([]) }))
vi.mock("@/lib/api/categories", () => ({ listCategories: vi.fn().mockResolvedValue([]) }))

vi.mock("@/lib/api/metas", () => ({ listMetas: vi.fn().mockResolvedValue([]) }))

import ToPayPage from "./page"

beforeEach(() => {
  vi.clearAllMocks()
  toPay.mockResolvedValue({ overdue: [], upcoming: [], total_base: 0 })
})

describe("AC-7 — every screen carries the same control", () => {
  it("Por pagar offers to explain itself", async () => {
    render(<ToPayPage />, { wrapper: queryWrapper })

    expect(await openHelpPanel("Por pagar")).toHaveTextContent(
      "cobros que ya vencieron o vencen dentro del periodo y todavía no has pagado",
    )
  })
})

describe("AC-10 — an empty screen teaches and offers the way in", () => {
  it("An empty Por pagar screen teaches what it would show", async () => {
    render(<ToPayPage />, { wrapper: queryWrapper })

    expect(await screen.findByText("Nada pendiente en este periodo.")).toBeInTheDocument()
    expect(
      screen.getByText(
        /Aquí aparecen los cobros que ya vencieron o vencen dentro del periodo y todavía no has pagado/,
      ),
    ).toBeInTheDocument()
  })
})

describe("AC-43 — a debt can be pointed at a meta when it is written down", () => {
  it("The plan form offers the metas of the month the payment is due", async () => {
    const user = userEvent.setup()
    render(<ToPayPage />, { wrapper: queryWrapper })
    await user.click(await screen.findByRole("button", { name: /Planear/ }))

    expect(await screen.findByLabelText("¿Es la compra de una meta?")).toBeInTheDocument()
  })
})
