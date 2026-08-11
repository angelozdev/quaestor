import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { HELP_LABEL } from "@/components/screen-help"
import type { Recurring } from "@/lib/api/types"
import { fieldUnder, openHelpPanel, queryWrapper } from "@/tests/factories"

const { listRecurring, createRecurring, updateRecurring, listAccounts, listCategories, getFx } =
  vi.hoisted(() => ({
    listRecurring: vi.fn(),
    createRecurring: vi.fn(),
    updateRecurring: vi.fn(),
    listAccounts: vi.fn(),
    listCategories: vi.fn(),
    getFx: vi.fn(),
  }))

vi.mock("@/lib/api/recurring", () => ({
  listRecurring,
  createRecurring,
  updateRecurring,
  deleteRecurring: vi.fn(),
  restoreRecurring: vi.fn(),
  skipRecurring: vi.fn(),
}))
vi.mock("@/lib/api/accounts", () => ({ listAccounts }))
vi.mock("@/lib/api/categories", () => ({ listCategories }))
vi.mock("@/lib/api/fx", () => ({ getFx }))

import RecurringPage from "./page"

const NETFLIX: Recurring = {
  id: 3,
  name: "Netflix",
  payee: "Netflix",
  type: "expense",
  mode: "auto",
  amount: 3_500_000,
  currency: "COP",
  category_id: 9,
  account_id: 1,
  interval_unit: "month",
  interval_count: 1,
  start_date: "2026-08-01",
  end_date: null,
  active: true,
}

const NU = { id: 1, name: "Nu Débito", type: "debit", currency: "COP", balance: 0, archived: false }
const DOLARAPP = {
  id: 3,
  name: "DolarApp",
  type: "debit",
  currency: "USD",
  balance: 0,
  archived: false,
}
const SUSCRIPCIONES = { id: 9, name: "Suscripciones", is_income: false }

const openHelp = () => openHelpPanel("Recurrentes")

beforeEach(() => {
  vi.clearAllMocks()
  listRecurring.mockResolvedValue([])
  listAccounts.mockResolvedValue([])
  listCategories.mockResolvedValue([])
  getFx.mockResolvedValue({ usd_cop: "4000" })
})

describe("AC-7 — every screen carries the same control", () => {
  it("Recurrentes offers to explain itself", async () => {
    render(<RecurringPage />, { wrapper: queryWrapper })

    expect(await screen.findByRole("button", { name: HELP_LABEL })).toBeInTheDocument()
    expect(await openHelp()).toHaveTextContent("Un cobro recurrente es uno que vuelve solo")
  })
})

describe("AC-8 — the panel explains the screen using the owner's own figures", () => {
  it("Every screen's panel speaks about what that screen holds", async () => {
    listRecurring.mockResolvedValue([NETFLIX])
    render(<RecurringPage />, { wrapper: queryWrapper })
    await screen.findByText("Netflix")

    const panel = await openHelp()

    expect(panel).toHaveTextContent("Netflix")
    expect(panel).toHaveTextContent("Netflix — cobra $ 35.000 cada mes.")
  })
})

describe("AC-10 — an empty screen teaches and offers the way in", () => {
  it("An empty Recurrentes screen teaches and offers the way in", async () => {
    const user = userEvent.setup()
    render(<RecurringPage />, { wrapper: queryWrapper })

    expect(
      await screen.findByText(/Un cobro recurrente es uno que vuelve solo/),
    ).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Crear el primero" }))

    expect(screen.getByText("Nuevo recurrente")).toBeInTheDocument()
  })
})

/**
 * Editing a charge starts from the charge, not from a blank sheet.
 *
 * Nothing on the screen can restate a figure in the right currency while the
 * dialog does not carry the charge it was asked about, so this is the ground the
 * currency stands on.
 */
describe("the edit dialog opens on the charge it was asked about", () => {
  it("The boxes carry what the charge already says", async () => {
    const user = userEvent.setup()
    listRecurring.mockResolvedValue([NETFLIX])
    listAccounts.mockResolvedValue([NU, DOLARAPP])
    listCategories.mockResolvedValue([SUSCRIPCIONES])
    render(<RecurringPage />, { wrapper: queryWrapper })
    await screen.findByText("Netflix")

    await user.click(screen.getByRole("button", { name: "Editar" }))

    expect(screen.getByLabelText(/Nombre/)).toHaveValue("Netflix")
    expect(screen.getByLabelText(/Inicio/)).toHaveValue(NETFLIX.start_date)
    expect(within(fieldUnder(/^Monto \*/)).getByRole("textbox")).toHaveValue("35000")
  })
})

/**
 * A subscription charged in dollars — Opal, Hevy Pro, DolarApp Premium — declared
 * against the account that actually pays it.
 *
 * The account is chosen before the figure is typed, as the owner does it: the
 * amount box must already be asking for dollars by then, or US$ 29,35 is read as
 * 29.350 pesos and the charge is stated in a currency the account does not hold.
 */
describe("a recurring charge is stated in the currency its account holds", () => {
  beforeEach(() => {
    listAccounts.mockResolvedValue([NU, DOLARAPP])
    listCategories.mockResolvedValue([SUSCRIPCIONES])
    createRecurring.mockResolvedValue(NETFLIX)
    updateRecurring.mockResolvedValue(NETFLIX)
  })

  async function declareOpalOnDolarApp(user: ReturnType<typeof userEvent.setup>) {
    render(<RecurringPage />, { wrapper: queryWrapper })
    await user.click(await screen.findByRole("button", { name: "Nuevo" }))

    await user.type(screen.getByLabelText(/Nombre/), "Opal")
    await user.click(within(fieldUnder("Cuenta *")).getByRole("combobox"))
    await user.click(await screen.findByRole("option", { name: DOLARAPP.name }))
    await user.type(within(fieldUnder(/^Monto \*/)).getByRole("textbox"), "29.35")
    await user.click(screen.getByRole("combobox", { name: "Categoría *" }))
    await user.click(await screen.findByRole("option", { name: SUSCRIPCIONES.name }))
  }

  async function moveNetflixToDolarApp(user: ReturnType<typeof userEvent.setup>) {
    listRecurring.mockResolvedValue([NETFLIX])
    render(<RecurringPage />, { wrapper: queryWrapper })
    await screen.findByText("Netflix")
    await user.click(screen.getByRole("button", { name: "Editar" }))

    await user.click(within(fieldUnder("Cuenta *")).getByRole("combobox"))
    await user.click(await screen.findByRole("option", { name: DOLARAPP.name }))
  }

  it("The amount box asks for dollars as soon as a dollar account is chosen", async () => {
    const user = userEvent.setup()
    await declareOpalOnDolarApp(user)

    expect(screen.getByText("Monto * (USD)")).toBeInTheDocument()
  })

  it("The charge is created in dollars, cents and all", async () => {
    const user = userEvent.setup()
    await declareOpalOnDolarApp(user)
    await user.click(screen.getByRole("button", { name: "Crear" }))

    await waitFor(() => expect(createRecurring).toHaveBeenCalledTimes(1))
    expect(createRecurring).toHaveBeenCalledWith(
      expect.objectContaining({ currency: "USD", amount: 2935, account_id: DOLARAPP.id }),
    )
  })

  it("Moving a charge to a dollar account restates the amount box in dollars", async () => {
    const user = userEvent.setup()
    await moveNetflixToDolarApp(user)

    expect(screen.getByText("Monto * (USD)")).toBeInTheDocument()
  })

  it("The box offers the charge converted at the app's rate, not its old cents", async () => {
    const user = userEvent.setup()
    await moveNetflixToDolarApp(user)

    await waitFor(() =>
      expect(within(fieldUnder(/^Monto \*/)).getByRole("textbox")).toHaveValue("8.75"),
    )
  })

  it("The figure the box offers is the one that reaches the charge", async () => {
    const user = userEvent.setup()
    await moveNetflixToDolarApp(user)
    await waitFor(() =>
      expect(within(fieldUnder(/^Monto \*/)).getByRole("textbox")).toHaveValue("8.75"),
    )

    await user.click(screen.getByRole("button", { name: "Guardar" }))

    await waitFor(() => expect(updateRecurring).toHaveBeenCalledTimes(1))
    expect(updateRecurring).toHaveBeenCalledWith(
      NETFLIX.id,
      expect.objectContaining({ amount: 875, account_id: DOLARAPP.id }),
    )
  })

  it("A charge moved to a dollar account is restated in dollars, cents and all", async () => {
    const user = userEvent.setup()
    await moveNetflixToDolarApp(user)

    const amount = within(fieldUnder(/^Monto \*/)).getByRole("textbox")
    await user.clear(amount)
    await user.type(amount, "29.35")
    await user.click(screen.getByRole("button", { name: "Guardar" }))

    await waitFor(() => expect(updateRecurring).toHaveBeenCalledTimes(1))
    expect(updateRecurring).toHaveBeenCalledWith(
      NETFLIX.id,
      expect.objectContaining({ amount: 2935, account_id: DOLARAPP.id }),
    )
  })
})
