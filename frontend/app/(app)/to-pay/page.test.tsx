import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { makeTransaction, openHelpPanel, queryWrapper } from "@/tests/factories"

const { toPay, listMetas, listAccounts, listCategories, planPayment } = vi.hoisted(() => ({
  toPay: vi.fn(),
  listMetas: vi.fn(),
  listAccounts: vi.fn(),
  listCategories: vi.fn(),
  planPayment: vi.fn(),
}))

vi.mock("@/lib/api/planned", () => ({
  toPay,
  confirmPayment: vi.fn(),
  skipPlanned: vi.fn(),
  planPayment,
}))
vi.mock("@/lib/api/accounts", () => ({ listAccounts }))
vi.mock("@/lib/api/categories", () => ({ listCategories }))

vi.mock("@/lib/api/metas", () => ({ listMetas }))

import ToPayPage from "./page"

const ACCOUNT = {
  id: 1,
  name: "Nu Débito",
  type: "debit",
  currency: "COP",
  balance: 0,
  archived: false,
}
const CATEGORY = { id: 3, name: "Tecnología", is_income: false }
const TELEVISOR = 4

/**
 * The metas of whichever month is asked for, as the server hands them over.
 *
 * The month is echoed back into `year_month` so a picker reading the wrong
 * month would be offering a list this fake never built for it.
 */
function metasOf(month: string) {
  return [
    {
      meta_id: TELEVISOR,
      name: "Televisor",
      year_month: month,
      amount: 500_000_000,
      currency: "COP",
      target_month: "2027-06",
      asks: 100_000_000,
      asks_cop: 100_000_000,
      holds: 0,
      progress: 0,
      complete: false,
      closed: false,
      waiting: false,
      cancelled: false,
      released: 0,
    },
  ]
}

beforeEach(() => {
  vi.clearAllMocks()
  toPay.mockResolvedValue({ overdue: [], upcoming: [], total_base: 0 })
  listMetas.mockResolvedValue([])
  listAccounts.mockResolvedValue([ACCOUNT])
  listCategories.mockResolvedValue([CATEGORY])
  planPayment.mockResolvedValue(makeTransaction({ status: "planned" }))
})

/**
 * The control under a label that names it in text only.
 *
 * The account and amount fields of this dialog carry a `Label` with no
 * `htmlFor`, so `getByLabelText` cannot reach them; the surrounding field is
 * the nearest thing the test can name without asserting on class names.
 */
function fieldUnder(label: string) {
  const field = screen.getByText(label).parentElement
  if (!field) throw new Error(`the label "${label}" stands outside a field`)
  return field
}

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

  it("A due date in another month offers that month's metas", async () => {
    const user = userEvent.setup()
    render(<ToPayPage />, { wrapper: queryWrapper })
    await user.click(await screen.findByRole("button", { name: /Planear/ }))
    await screen.findByLabelText("¿Es la compra de una meta?")

    await user.type(screen.getByLabelText(/Fecha de vencimiento/), "2027-03-15")

    await waitFor(() => expect(listMetas).toHaveBeenCalledWith("2027-03"))
  })

  /**
   * Offering the right metas and sending the one that was chosen are two
   * different promises, and only the first was pinned. The screen may show
   * "Televisor", the owner may pick it, and the request may still go out
   * naming no meta at all — the debt would then be written down as an
   * ordinary payment and the meta it belonged to would never see it.
   */
  async function fillThePlanForm(user: ReturnType<typeof userEvent.setup>) {
    render(<ToPayPage />, { wrapper: queryWrapper })
    await user.click(await screen.findByRole("button", { name: /Planear/ }))
    await screen.findByLabelText("¿Es la compra de una meta?")

    await user.type(screen.getByLabelText(/Beneficiario/), "Falabella")
    await user.click(within(fieldUnder("Cuenta *")).getByRole("combobox"))
    await user.click(await screen.findByRole("option", { name: ACCOUNT.name }))
    await user.type(within(fieldUnder("Monto * (COP)")).getByRole("textbox"), "1200000")
    await user.type(screen.getByLabelText(/Fecha de vencimiento/), "2027-03-15")
    await user.click(screen.getByRole("combobox", { name: "Categoría *" }))
    await user.click(await screen.findByRole("option", { name: CATEGORY.name }))
  }

  it("The meta the owner picked is the meta the planned payment is written down with", async () => {
    const user = userEvent.setup()
    listMetas.mockImplementation((month: string) => Promise.resolve(metasOf(month)))
    await fillThePlanForm(user)

    await user.click(screen.getByRole("combobox", { name: /Es la compra de una meta/ }))
    await user.click(await screen.findByRole("option", { name: "Televisor" }))
    await user.click(screen.getByRole("button", { name: "Planear" }))

    await waitFor(() => expect(planPayment).toHaveBeenCalledTimes(1))
    expect(planPayment).toHaveBeenCalledWith(
      expect.objectContaining({
        meta_id: TELEVISOR,
        due_date: "2027-03-15",
        payee: "Falabella",
        amount: 120_000_000,
        account_id: ACCOUNT.id,
        category_id: CATEGORY.id,
      }),
    )
  })

  it("A debt that belongs to no meta says so, rather than saying nothing", async () => {
    const user = userEvent.setup()
    listMetas.mockImplementation((month: string) => Promise.resolve(metasOf(month)))
    await fillThePlanForm(user)

    await user.click(screen.getByRole("button", { name: "Planear" }))

    await waitFor(() => expect(planPayment).toHaveBeenCalledTimes(1))
    expect(planPayment.mock.calls[0][0]).toHaveProperty("meta_id", null)
  })
})
