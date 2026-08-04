import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

const { createFund, previewFund, moneyAvailable, deleteFund, listCategories } = vi.hoisted(() => ({
  createFund: vi.fn(),
  previewFund: vi.fn(),
  moneyAvailable: vi.fn(),
  deleteFund: vi.fn(),
  listCategories: vi.fn(),
}))

vi.mock("@/lib/api/funds", () => ({ createFund, previewFund, moneyAvailable, deleteFund }))
vi.mock("@/lib/api/categories", () => ({ listCategories }))

import FundsPage from "./page"

const RESTAURANTES = { id: 7, name: "Restaurantes", is_income: false }

const EMPTY_MONTH = {
  year_month: "2026-11",
  income: 0,
  funds: [],
  uncovered: 0,
  free: 0,
}

const A_FUND = {
  fund_id: 3,
  category_id: 7,
  name: "Restaurantes",
  year_month: "2026-11",
  rule: "fixed",
  asks: 20_000_000,
  holds: 5_000_000,
  accumulates: true,
  accumulation_is_implied: false,
  on_track: true,
  averaged_over: null,
  spreads_over: null,
  whole_by: null,
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <FundsPage />
    </QueryClientProvider>,
  )
}

async function openTheForm(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "Nuevo fondo" }))
  await user.click(screen.getByRole("combobox", { name: "Categoría *" }))
  await user.click(await screen.findByRole("option", { name: "Restaurantes" }))
}

async function chooseRule(user: ReturnType<typeof userEvent.setup>, label: string) {
  await user.click(screen.getByRole("combobox", { name: "Regla *" }))
  await user.click(await screen.findByRole("option", { name: label }))
}

beforeEach(() => {
  vi.clearAllMocks()
  moneyAvailable.mockResolvedValue(EMPTY_MONTH)
  listCategories.mockResolvedValue([RESTAURANTES])
  previewFund.mockResolvedValue({ category_id: 7, would_ask: 0, warning: null })
  createFund.mockResolvedValue({ id: 3 })
  deleteFund.mockResolvedValue(undefined)
})

describe("FundsPage creating a fund with each rule", () => {
  it("creates one asking a fixed amount each month", async () => {
    const user = userEvent.setup()
    renderPage()
    await openTheForm(user)
    await user.type(screen.getByLabelText("Monto mensual * (COP)"), "200000")
    await user.click(screen.getByRole("button", { name: "Crear" }))

    await waitFor(() => expect(createFund).toHaveBeenCalledTimes(1))
    expect(createFund).toHaveBeenCalledWith(
      expect.objectContaining({ category_id: 7, rule: "fixed", amount: 20_000_000 }),
    )
  })

  it("creates one averaging the last months", async () => {
    const user = userEvent.setup()
    renderPage()
    await openTheForm(user)
    await chooseRule(user, "Promedio de los últimos meses")
    await user.type(screen.getByLabelText("Meses a promediar *"), "3")
    await user.click(screen.getByRole("button", { name: "Crear" }))

    await waitFor(() => expect(createFund).toHaveBeenCalledTimes(1))
    expect(createFund).toHaveBeenCalledWith(
      expect.objectContaining({ rule: "average", window_months: 3 }),
    )
  })

  it("creates one funded from its obligations", async () => {
    const user = userEvent.setup()
    renderPage()
    await openTheForm(user)
    await chooseRule(user, "Lo que piden sus obligaciones")
    await user.click(screen.getByRole("button", { name: "Crear" }))

    await waitFor(() => expect(createFund).toHaveBeenCalledTimes(1))
    expect(createFund).toHaveBeenCalledWith(expect.objectContaining({ rule: "from-recurring" }))
  })

  it("creates one saving toward a dated target", async () => {
    const user = userEvent.setup()
    renderPage()
    await openTheForm(user)
    await chooseRule(user, "Meta con fecha")
    await user.type(screen.getByLabelText("Objetivo * (COP)"), "3000000")
    await user.type(screen.getByLabelText("Mes objetivo *"), "2027-06")
    await user.click(screen.getByRole("button", { name: "Crear" }))

    await waitFor(() => expect(createFund).toHaveBeenCalledTimes(1))
    expect(createFund).toHaveBeenCalledWith(
      expect.objectContaining({
        rule: "target-by-date",
        target_amount: 300_000_000,
        target_month: "2027-06",
      }),
    )
  })
})

describe("FundsPage warns before creating (AC-24)", () => {
  it("shows the warning and creates nothing until the owner insists", async () => {
    previewFund.mockResolvedValue({
      category_id: 7,
      would_ask: 300_000_000,
      warning: "2026-11 no deja ningún mes para ahorrar: pediría 3.000.000 de una vez",
    })
    const user = userEvent.setup()
    renderPage()
    await openTheForm(user)
    await chooseRule(user, "Meta con fecha")
    await user.type(screen.getByLabelText("Objetivo * (COP)"), "3000000")
    await user.type(screen.getByLabelText("Mes objetivo *"), "2026-11")
    await user.click(screen.getByRole("button", { name: "Crear" }))

    expect(await screen.findByRole("alert")).toHaveTextContent(/no deja ningún mes para ahorrar/)
    expect(createFund).not.toHaveBeenCalled()

    await user.click(screen.getByRole("button", { name: "Crear de todos modos" }))
    await waitFor(() => expect(createFund).toHaveBeenCalledTimes(1))
  })
})

describe("FundsPage accumulation toggle", () => {
  it("is offered for a fixed fund and for an average one", async () => {
    const user = userEvent.setup()
    renderPage()
    await openTheForm(user)
    expect(
      screen.getByRole("checkbox", { name: "Acumula lo que sobra cada mes" }),
    ).toBeInTheDocument()

    await chooseRule(user, "Promedio de los últimos meses")
    expect(
      screen.getByRole("checkbox", { name: "Acumula lo que sobra cada mes" }),
    ).toBeInTheDocument()
  })

  it("is not offered for a fund saving toward a date, which always accumulates", async () => {
    const user = userEvent.setup()
    renderPage()
    await openTheForm(user)

    await chooseRule(user, "Meta con fecha")
    expect(
      screen.queryByRole("checkbox", { name: "Acumula lo que sobra cada mes" }),
    ).not.toBeInTheDocument()

    await chooseRule(user, "Lo que piden sus obligaciones")
    expect(
      screen.queryByRole("checkbox", { name: "Acumula lo que sobra cada mes" }),
    ).not.toBeInTheDocument()
  })
})

describe("FundsPage listing", () => {
  it("shows what each fund asks and holds this month", async () => {
    moneyAvailable.mockResolvedValue({ ...EMPTY_MONTH, funds: [A_FUND] })
    renderPage()
    expect(await screen.findByText("Restaurantes")).toBeInTheDocument()
    expect(screen.getByText("$ 200.000")).toBeInTheDocument()
    expect(screen.getByText("$ 50.000")).toBeInTheDocument()
    expect(screen.getByText("En camino")).toBeInTheDocument()
  })

  it("says there are no funds yet when the month has none", async () => {
    renderPage()
    expect(await screen.findByText("Aún no hay fondos")).toBeInTheDocument()
  })

  it("deletes a fund once the owner confirms", async () => {
    moneyAvailable.mockResolvedValue({ ...EMPTY_MONTH, funds: [A_FUND] })
    const user = userEvent.setup()
    renderPage()
    await user.click(
      await screen.findByRole("button", { name: "Eliminar el fondo de Restaurantes" }),
    )
    await user.click(await screen.findByRole("button", { name: "Eliminar" }))
    await waitFor(() => expect(deleteFund).toHaveBeenCalledWith(3))
  })
})
