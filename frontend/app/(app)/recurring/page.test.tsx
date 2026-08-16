import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { HELP_LABEL } from "@/components/screen-help"
import { ApiError, type Recurring } from "@/lib/api/types"
import { fieldUnder, openHelpPanel, queryWrapper } from "@/tests/factories"

const {
  listRecurring,
  createRecurring,
  updateRecurring,
  listAccounts,
  listCategories,
  getFx,
  toast,
  chargeMarks,
  markCharge,
  unmarkCharge,
  chargeEditCost,
} = vi.hoisted(() => ({
  listRecurring: vi.fn(),
  createRecurring: vi.fn(),
  updateRecurring: vi.fn(),
  listAccounts: vi.fn(),
  listCategories: vi.fn(),
  getFx: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn() },
  chargeMarks: vi.fn(),
  markCharge: vi.fn(),
  unmarkCharge: vi.fn(),
  chargeEditCost: vi.fn(),
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
vi.mock("@/lib/api/funds", () => ({
  chargeMarks,
  markCharge,
  unmarkCharge,
  chargeEditCost,
  openTurns: vi.fn().mockResolvedValue([]),
}))
vi.mock("sonner", () => ({ toast }))

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
  chargeMarks.mockResolvedValue([])
  chargeEditCost.mockResolvedValue({ would_lose_its_fund: false })
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

/**
 * Feature 013 — an obligation holds the merchant's price and its account decides
 * what is debited (ADR-0053), so a row has two figures to carry: the price, and
 * what it comes to in the account that pays it.
 *
 * Hevy Pro is priced at 400.000 pesos and paid from a dollar account, which is
 * exactly the shape ADR-0052 refused to store and this feature exists to allow.
 */
describe("013 — the repeating obligations show the price and what it comes to", () => {
  const HEVY: Recurring = {
    ...NETFLIX,
    id: 11,
    name: "Hevy Pro",
    payee: "Hevy",
    mode: "manual",
    amount: 40_000_000,
    currency: "COP",
    account_id: DOLARAPP.id,
  }
  const OPAL: Recurring = {
    ...NETFLIX,
    id: 12,
    name: "Opal",
    payee: "Opal",
    mode: "manual",
    amount: 4_000,
    currency: "USD",
    account_id: DOLARAPP.id,
  }

  function rowFor(name: string) {
    const cell = screen.getByText(name).closest("tr")
    if (!cell) throw new Error(`no row for ${name}`)
    return cell
  }

  beforeEach(() => {
    listAccounts.mockResolvedValue([NU, DOLARAPP])
  })

  it("The row carries both figures", async () => {
    listRecurring.mockResolvedValue([HEVY])
    render(<RecurringPage />, { wrapper: queryWrapper })
    await screen.findByText("Hevy Pro")

    await waitFor(() => expect(rowFor("Hevy Pro")).toHaveTextContent("$ 400.000"))
    expect(rowFor("Hevy Pro")).toHaveTextContent("≈ US$ 100.00")
  })

  it("A rule that agrees with its account shows one figure only", async () => {
    listRecurring.mockResolvedValue([OPAL])
    render(<RecurringPage />, { wrapper: queryWrapper })
    await screen.findByText("Opal")

    await waitFor(() => expect(rowFor("Opal")).toHaveTextContent("US$ 40.00"))
    expect(rowFor("Opal")).not.toHaveTextContent("≈")
  })

  it("The converted figure disappears, the price stays", async () => {
    getFx.mockRejectedValue(new Error("no TRM has been set"))
    listRecurring.mockResolvedValue([HEVY])
    render(<RecurringPage />, { wrapper: queryWrapper })
    await screen.findByText("Hevy Pro")

    await waitFor(() => expect(rowFor("Hevy Pro")).toHaveTextContent("$ 400.000"))
    expect(rowFor("Hevy Pro")).not.toHaveTextContent("≈")
    expect(screen.queryByText(/No se pudo/)).not.toBeInTheDocument()
  })

  it("The move offers a figure in the new account's currency", async () => {
    const user = userEvent.setup()
    listRecurring.mockResolvedValue([OPAL])
    listCategories.mockResolvedValue([SUSCRIPCIONES])
    render(<RecurringPage />, { wrapper: queryWrapper })
    await screen.findByText("Opal")
    await user.click(screen.getByRole("button", { name: "Editar" }))

    await user.click(within(fieldUnder("Cuenta *")).getByRole("combobox"))
    await user.click(await screen.findByRole("option", { name: NU.name }))

    expect(screen.getByText("Monto * (COP)")).toBeInTheDocument()
    await waitFor(() =>
      expect(within(fieldUnder(/^Monto \*/)).getByRole("textbox")).toHaveValue("160000"),
    )
  })
})

/**
 * The create dialog is not mounted on anything, so it survives being closed.
 *
 * Every other money box in the app hangs off a keyed child and starts fresh
 * with it; this one is state on the screen, so what the owner stated last time
 * outlives the charge it belonged to unless the reset reaches it too.
 */
describe("013 — a saved charge leaves nothing behind in the next one", () => {
  it("The amount box is empty again when the dialog is reopened", async () => {
    const user = userEvent.setup()
    listAccounts.mockResolvedValue([NU, DOLARAPP])
    listCategories.mockResolvedValue([SUSCRIPCIONES])
    createRecurring.mockResolvedValue({ ...NETFLIX, id: 99 })
    render(<RecurringPage />, { wrapper: queryWrapper })

    await user.click(await screen.findByRole("button", { name: "Nuevo" }))
    await user.type(screen.getByLabelText(/Nombre/), "Hevy Pro")
    await user.click(within(fieldUnder("Cuenta *")).getByRole("combobox"))
    await user.click(await screen.findByRole("option", { name: NU.name }))
    await user.type(within(fieldUnder(/^Monto \*/)).getByRole("textbox"), "99900")
    await user.click(screen.getByRole("combobox", { name: "Categoría *" }))
    await user.click(await screen.findByRole("option", { name: SUSCRIPCIONES.name }))
    await user.click(screen.getByRole("button", { name: "Crear" }))
    await waitFor(() => expect(createRecurring).toHaveBeenCalledTimes(1))

    await user.click(screen.getByRole("button", { name: "Nuevo" }))
    await user.click(within(fieldUnder("Cuenta *")).getByRole("combobox"))
    await user.click(await screen.findByRole("option", { name: DOLARAPP.name }))

    expect(within(fieldUnder(/^Monto \*/)).getByRole("textbox")).toHaveValue("")
  })
})

/**
 * Saying the price is in another currency relabels the figure; it never converts
 * it.
 *
 * The number the owner typed is the merchant's price, and the app has no
 * business restating it because he corrected which currency he meant. Converting
 * here would be the money hole in its quietest form: an obligation that pays
 * itself would go on charging the converted figure every period.
 */
describe("013 — naming the price's currency does not restate the price", () => {
  const OPAL: Recurring = {
    ...NETFLIX,
    id: 12,
    name: "Opal",
    payee: "Opal",
    mode: "manual",
    amount: 4_000,
    currency: "USD",
    account_id: DOLARAPP.id,
  }

  async function openOpalAndSayPesos(user: ReturnType<typeof userEvent.setup>) {
    listRecurring.mockResolvedValue([OPAL])
    listAccounts.mockResolvedValue([NU, DOLARAPP])
    listCategories.mockResolvedValue([SUSCRIPCIONES])
    render(<RecurringPage />, { wrapper: queryWrapper })
    await screen.findByText("Opal")
    await user.click(screen.getByRole("button", { name: "Editar" }))
    await user.click(screen.getByRole("combobox", { name: "Moneda del precio *" }))
    await user.click(await screen.findByRole("option", { name: "Pesos (COP)" }))
  }

  it("The figure stays exactly as the owner typed it", async () => {
    const user = userEvent.setup()
    await openOpalAndSayPesos(user)

    expect(screen.getByText("Monto * (COP)")).toBeInTheDocument()
    expect(within(fieldUnder(/^Monto \*/)).getByRole("textbox")).toHaveValue("40")
  })

  it("The price that reaches the charge is the one on screen", async () => {
    const user = userEvent.setup()
    await openOpalAndSayPesos(user)

    await user.click(screen.getByRole("button", { name: "Guardar" }))

    await waitFor(() => expect(updateRecurring).toHaveBeenCalledTimes(1))
    expect(updateRecurring).toHaveBeenCalledWith(
      OPAL.id,
      expect.objectContaining({ currency: "COP", amount: 4_000 }),
    )
  })
})

/**
 * Marking a charge is what creates its fund — no form, nothing to confirm
 * afterwards. Where the box cannot be ticked the row says why in the same
 * breath, because an inert box and no reason is worse than no box at all.
 */
describe("015 — a fund may hang off the charge it fills", () => {
  const SEGURO: Recurring = {
    ...NETFLIX,
    id: 42,
    name: "Seguro",
    interval_unit: "year",
    interval_count: 1,
    start_date: "2027-07-05",
  }

  const markOf = (over: Record<string, unknown> = {}) => ({
    recurring_id: SEGURO.id,
    category_id: SEGURO.category_id,
    name: SEGURO.name,
    currency: "COP",
    can_be_marked: true,
    why_not: null,
    fund_id: null,
    ...over,
  })

  beforeEach(() => {
    listAccounts.mockResolvedValue([NU])
    listCategories.mockResolvedValue([SUSCRIPCIONES])
  })

  it("The charge is marked from the list, with nothing left to confirm", async () => {
    listRecurring.mockResolvedValue([SEGURO])
    chargeMarks.mockResolvedValue([markOf()])
    markCharge.mockResolvedValue({ id: 1 })
    const user = userEvent.setup()
    render(<RecurringPage />, { wrapper: queryWrapper })
    await screen.findByText(SEGURO.name)

    await user.click(await screen.findByRole("checkbox", { name: "Juntar mes a mes" }))

    await waitFor(() => expect(markCharge).toHaveBeenCalledWith(SEGURO.id, expect.any(String)))
    expect(screen.queryByRole("dialog")).toBeNull()
    expect(await screen.findByText(SEGURO.name)).toBeInTheDocument()
  })

  it("The list says why a charge cannot be marked", async () => {
    listRecurring.mockResolvedValue([NETFLIX])
    chargeMarks.mockResolvedValue([
      markOf({
        recurring_id: NETFLIX.id,
        name: NETFLIX.name,
        can_be_marked: false,
        why_not: "it comes back before a whole month has passed, so saving for it would ask …",
      }),
    ])
    render(<RecurringPage />, { wrapper: queryWrapper })

    const row = (await screen.findByText(NETFLIX.name)).closest("tr") as HTMLElement

    expect(within(row).queryByRole("checkbox", { name: "Juntar mes a mes" })).toBeNull()
    expect(row.textContent).toContain("Vuelve cada mes")
  })

  it("A refused marking says why on the screen, and leaves the charge alone", async () => {
    listRecurring.mockResolvedValue([SEGURO])
    chargeMarks.mockResolvedValue([markOf()])
    markCharge.mockRejectedValue(
      new ApiError(400, "validation_error", "'Seguro' cannot be saved for: it charges this month"),
    )
    const user = userEvent.setup()
    render(<RecurringPage />, { wrapper: queryWrapper })
    await screen.findByText(SEGURO.name)

    await user.click(await screen.findByRole("checkbox", { name: "Juntar mes a mes" }))

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(expect.stringContaining("cannot be saved for")),
    )
    expect(screen.getByRole("checkbox", { name: "Juntar mes a mes" })).not.toBeChecked()
  })

  it("Making a charge monthly says first that its fund goes with it", async () => {
    listRecurring.mockResolvedValue([SEGURO])
    chargeMarks.mockResolvedValue([markOf({ fund_id: 7 })])
    chargeEditCost.mockResolvedValue({ would_lose_its_fund: true })
    const user = userEvent.setup()
    render(<RecurringPage />, { wrapper: queryWrapper })

    await user.click(await screen.findByRole("button", { name: "Editar" }))
    await user.click(await screen.findByRole("button", { name: "Guardar" }))

    expect(await screen.findByText(/su fondo se va a borrar/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Guardar y borrar el fondo" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Cancelar" })).toBeInTheDocument()
    expect(updateRecurring).not.toHaveBeenCalled()
  })

  it("The question carries every field that could cost the fund, not only the cadence", async () => {
    listRecurring.mockResolvedValue([SEGURO])
    chargeMarks.mockResolvedValue([markOf({ fund_id: 7 })])
    chargeEditCost.mockResolvedValue({ would_lose_its_fund: false })
    const user = userEvent.setup()
    render(<RecurringPage />, { wrapper: queryWrapper })

    await user.click(await screen.findByRole("button", { name: "Editar" }))
    await user.click(await screen.findByRole("button", { name: "Guardar" }))

    await waitFor(() => expect(chargeEditCost).toHaveBeenCalled())
    expect(chargeEditCost).toHaveBeenCalledWith(
      SEGURO.id,
      expect.objectContaining({
        interval_unit: SEGURO.interval_unit,
        interval_count: SEGURO.interval_count,
        start_date: SEGURO.start_date,
        end_date: SEGURO.end_date ?? null,
      }),
    )
  })

  it("Cancelling that warning leaves the charge and its fund alone", async () => {
    listRecurring.mockResolvedValue([SEGURO])
    chargeMarks.mockResolvedValue([markOf({ fund_id: 7 })])
    chargeEditCost.mockResolvedValue({ would_lose_its_fund: true })
    const user = userEvent.setup()
    render(<RecurringPage />, { wrapper: queryWrapper })

    await user.click(await screen.findByRole("button", { name: "Editar" }))
    await user.click(await screen.findByRole("button", { name: "Guardar" }))
    await user.click(await screen.findByRole("button", { name: "Cancelar" }))

    expect(updateRecurring).not.toHaveBeenCalled()
    expect(unmarkCharge).not.toHaveBeenCalled()
    expect(await screen.findByLabelText(/Nombre/)).toHaveValue(SEGURO.name)
  })
})
