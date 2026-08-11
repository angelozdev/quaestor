import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { fieldUnder, makeTransaction, openHelpPanel, queryWrapper } from "@/tests/factories"

const { toPay, listMetas, listAccounts, listCategories, planPayment, confirmPayment, getFx } =
  vi.hoisted(() => ({
    toPay: vi.fn(),
    listMetas: vi.fn(),
    listAccounts: vi.fn(),
    listCategories: vi.fn(),
    planPayment: vi.fn(),
    confirmPayment: vi.fn(),
    getFx: vi.fn(),
  }))

vi.mock("@/lib/api/planned", () => ({
  toPay,
  confirmPayment,
  skipPlanned: vi.fn(),
  planPayment,
}))
vi.mock("@/lib/api/accounts", () => ({ listAccounts }))
vi.mock("@/lib/api/categories", () => ({ listCategories }))
vi.mock("@/lib/api/fx", () => ({ getFx }))

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
const RAPPICARD = {
  id: 2,
  name: "RappiCard",
  type: "credit",
  currency: "COP",
  balance: 0,
  archived: false,
}
const DOLARAPP = {
  id: 3,
  name: "DolarApp",
  type: "debit",
  currency: "USD",
  balance: 0,
  archived: false,
}
const KOREA = { id: 9, name: "Korea", type: "debit", currency: "COP", balance: 0, archived: true }
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
  listAccounts.mockImplementation((includeArchived = false) =>
    Promise.resolve(
      includeArchived ? [ACCOUNT, RAPPICARD, DOLARAPP, KOREA] : [ACCOUNT, RAPPICARD, DOLARAPP],
    ),
  )
  getFx.mockResolvedValue({ usd_cop: "4000" })
  confirmPayment.mockResolvedValue(makeTransaction({ status: "posted" }))
  listCategories.mockResolvedValue([CATEGORY])
  planPayment.mockResolvedValue(makeTransaction({ status: "planned" }))
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

/**
 * A payment already waiting, so the confirmation has something to open onto.
 * The default `toPay` is empty on purpose — AC-10 above turns on that.
 */
function aWaitingPayment() {
  const tx = makeTransaction({
    id: 7,
    payee: "Hogaru",
    status: "planned",
    amount: 40_000_000,
    account_id: ACCOUNT.id,
    date: new Date().toISOString().slice(0, 10),
  })
  toPay.mockResolvedValue({ overdue: [tx], upcoming: [], total_base: tx.amount })
  return tx
}

async function openConfirmation() {
  const user = userEvent.setup()
  aWaitingPayment()
  render(<ToPayPage />, { wrapper: queryWrapper })
  await user.click(await screen.findByRole("button", { name: "Confirmar" }))
  await waitFor(() =>
    expect(screen.getByRole("combobox", { name: "Cuenta" })).toHaveTextContent(ACCOUNT.name),
  )
  return user
}

describe("012 — confirming a payment says which account it came out of", () => {
  it("The confirmation offers the account it was planned against", async () => {
    await openConfirmation()
    expect(screen.getByRole("combobox", { name: "Cuenta" })).toHaveTextContent(ACCOUNT.name)
  })

  it("The account is named, never numbered", async () => {
    await openConfirmation()
    expect(screen.getByRole("combobox", { name: "Cuenta" })).toHaveTextContent(ACCOUNT.name)
    expect(screen.queryByText(/cuenta #/)).not.toBeInTheDocument()
  })

  it("An account in another currency is on the list", async () => {
    const user = await openConfirmation()
    await user.click(screen.getByRole("combobox", { name: "Cuenta" }))
    expect(await screen.findByRole("option", { name: DOLARAPP.name })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: ACCOUNT.name })).toBeInTheDocument()
  })

  it("The converted figure arrives already filled in", async () => {
    const user = await openConfirmation()
    await user.click(screen.getByRole("combobox", { name: "Cuenta" }))
    await user.click(await screen.findByRole("option", { name: DOLARAPP.name }))
    expect(await screen.findByLabelText("Monto real (USD)")).toHaveValue("100")
  })

  it("The offered figure is a suggestion, not a decision", async () => {
    const user = await openConfirmation()
    await user.click(screen.getByRole("combobox", { name: "Cuenta" }))
    await user.click(await screen.findByRole("option", { name: DOLARAPP.name }))
    const amount = await screen.findByLabelText("Monto real (USD)")
    await user.clear(amount)
    await user.type(amount, "105")

    await user.click(screen.getByRole("button", { name: "Confirmar" }))
    await waitFor(() => expect(confirmPayment).toHaveBeenCalledTimes(1))
    expect(confirmPayment).toHaveBeenCalledWith(
      7,
      expect.objectContaining({ amount: 10_500, account_id: DOLARAPP.id }),
    )
  })

  it("A retired account is not on the list when confirming", async () => {
    const user = await openConfirmation()
    await user.click(screen.getByRole("combobox", { name: "Cuenta" }))
    await screen.findByRole("option", { name: DOLARAPP.name })
    expect(screen.queryByRole("option", { name: KOREA.name })).not.toBeInTheDocument()
  })

  it("The account offered when confirming is reachable by its label", async () => {
    await openConfirmation()
    expect(screen.getByLabelText("Cuenta")).toBeInTheDocument()
    expect(screen.getByLabelText("Monto real (COP)")).toBeInTheDocument()
    expect(screen.getByLabelText("Fecha")).toBeInTheDocument()
  })

  it("An account in the same currency leaves the amount box exactly as the owner left it", async () => {
    const user = await openConfirmation()
    await user.clear(screen.getByLabelText("Monto real (COP)"))
    await user.click(screen.getByRole("combobox", { name: "Cuenta" }))
    await user.click(await screen.findByRole("option", { name: RAPPICARD.name }))

    expect(screen.getByLabelText("Monto real (COP)")).toHaveValue("")
    await user.click(screen.getByRole("button", { name: "Confirmar" }))
    await waitFor(() => expect(confirmPayment).toHaveBeenCalledTimes(1))
    expect(confirmPayment).toHaveBeenCalledWith(
      7,
      expect.objectContaining({ account_id: RAPPICARD.id }),
    )
    expect(confirmPayment.mock.calls[0][1].amount).toBeUndefined()
  })
})

/**
 * The confirmation of a dollar payment opened while the list of accounts is
 * still in flight. The query never settles, so the only currency on screen is
 * the one the payment itself carries.
 */
async function openConfirmationOfADollarPayment() {
  const user = userEvent.setup()
  const tx = makeTransaction({
    id: 7,
    payee: "Hogaru",
    status: "planned",
    amount: 10_000,
    currency: "USD",
    account_id: DOLARAPP.id,
    date: new Date().toISOString().slice(0, 10),
  })
  toPay.mockResolvedValue({ overdue: [tx], upcoming: [], total_base: tx.amount })
  listAccounts.mockReturnValue(new Promise(() => undefined))
  render(<ToPayPage />, { wrapper: queryWrapper })
  await user.click(await screen.findByRole("button", { name: "Confirmar" }))
  return user
}

describe("012 — the confirmation reads the payment, not the list of accounts", () => {
  it("The confirmation reads the payment's own currency before the list of accounts arrives", async () => {
    await openConfirmationOfADollarPayment()
    expect(await screen.findByLabelText("Monto real (USD)")).toHaveValue("100")
  })

  it("A figure written into the confirmation before the list arrives keeps its cents", async () => {
    const user = await openConfirmationOfADollarPayment()
    const amount = await screen.findByLabelText("Monto real (USD)")
    await user.clear(amount)
    await user.type(amount, "87.52")
    expect(amount).toHaveValue("87.52")

    await user.click(screen.getByRole("button", { name: "Confirmar" }))
    await waitFor(() => expect(confirmPayment).toHaveBeenCalledTimes(1))
    expect(confirmPayment).toHaveBeenCalledWith(7, expect.objectContaining({ amount: 8_752 }))
  })
})

/** A payment of $93.558 waiting on a peso account, as Tigo's is in production. */
async function openConfirmationOfATigoBill() {
  const user = userEvent.setup()
  const tx = makeTransaction({
    id: 7,
    payee: "Tigo",
    status: "planned",
    amount: 9_355_800,
    account_id: ACCOUNT.id,
    date: new Date().toISOString().slice(0, 10),
  })
  toPay.mockResolvedValue({ overdue: [tx], upcoming: [], total_base: tx.amount })
  render(<ToPayPage />, { wrapper: queryWrapper })
  await user.click(await screen.findByRole("button", { name: "Confirmar" }))
  await waitFor(() =>
    expect(screen.getByRole("combobox", { name: "Cuenta" })).toHaveTextContent(ACCOUNT.name),
  )
  return user
}

async function goToDollarsAndBack(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("combobox", { name: "Cuenta" }))
  await user.click(await screen.findByRole("option", { name: DOLARAPP.name }))
  expect(await screen.findByLabelText("Monto real (USD)")).toHaveValue("23.39")
  await user.click(screen.getByRole("combobox", { name: "Cuenta" }))
  await user.click(await screen.findByRole("option", { name: ACCOUNT.name }))
}

describe("012 — a currency passed through charges nothing", () => {
  it("The figure comes back as the payment holds it after a trip through dollars", async () => {
    const user = await openConfirmationOfATigoBill()
    await goToDollarsAndBack(user)

    expect(await screen.findByLabelText("Monto real (COP)")).toHaveValue("93558")
  })

  it("Confirming after that trip charges the figure the payment already held", async () => {
    const user = await openConfirmationOfATigoBill()
    await goToDollarsAndBack(user)
    await screen.findByLabelText("Monto real (COP)")
    await user.click(screen.getByRole("button", { name: "Confirmar" }))

    await waitFor(() => expect(confirmPayment).toHaveBeenCalledTimes(1))
    expect(confirmPayment).toHaveBeenCalledWith(
      7,
      expect.objectContaining({ amount: 9_355_800, account_id: ACCOUNT.id }),
    )
  })
})

/** A dollar payment waiting on DolarApp, with every account already on the list. */
async function openConfirmationOfAHogaruBillInDollars() {
  const user = userEvent.setup()
  const tx = makeTransaction({
    id: 7,
    payee: "Hogaru",
    status: "planned",
    amount: 10_000,
    currency: "USD",
    account_id: DOLARAPP.id,
    date: new Date().toISOString().slice(0, 10),
  })
  toPay.mockResolvedValue({ overdue: [tx], upcoming: [], total_base: tx.amount })
  render(<ToPayPage />, { wrapper: queryWrapper })
  await user.click(await screen.findByRole("button", { name: "Confirmar" }))
  await waitFor(() =>
    expect(screen.getByRole("combobox", { name: "Cuenta" })).toHaveTextContent(DOLARAPP.name),
  )
  return user
}

async function emptyTheBoxOnPesosAndGoBackToDollars(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("combobox", { name: "Cuenta" }))
  await user.click(await screen.findByRole("option", { name: ACCOUNT.name }))
  expect(await screen.findByLabelText("Monto real (COP)")).toHaveValue("400000")
  await user.clear(screen.getByLabelText("Monto real (COP)"))
  await user.click(screen.getByRole("combobox", { name: "Cuenta" }))
  await user.click(await screen.findByRole("option", { name: DOLARAPP.name }))
}

/**
 * A payment planned against an account that holds dollars.
 *
 * The account is chosen before the figure is typed, as the owner does it: the
 * amount box must already be asking for dollars by then, or a figure with cents
 * loses its decimal point to peso parsing and the payment is planned in a
 * currency the account does not hold.
 */
describe("a payment is planned in the currency the account holds", () => {
  async function planADollarPayment(user: ReturnType<typeof userEvent.setup>) {
    render(<ToPayPage />, { wrapper: queryWrapper })
    await user.click(await screen.findByRole("button", { name: /Planear/ }))
    await screen.findByLabelText("¿Es la compra de una meta?")

    await user.type(screen.getByLabelText(/Beneficiario/), "Hogaru")
    await user.click(within(fieldUnder("Cuenta *")).getByRole("combobox"))
    await user.click(await screen.findByRole("option", { name: DOLARAPP.name }))
    await user.type(within(fieldUnder(/^Monto \*/)).getByRole("textbox"), "1556.04")
    await user.type(screen.getByLabelText(/Fecha de vencimiento/), "2027-03-15")
    await user.click(screen.getByRole("combobox", { name: "Categoría *" }))
    await user.click(await screen.findByRole("option", { name: CATEGORY.name }))
  }

  it("The amount box asks for dollars as soon as a dollar account is chosen", async () => {
    const user = userEvent.setup()
    await planADollarPayment(user)

    expect(screen.getByText("Monto * (USD)")).toBeInTheDocument()
  })

  it("The payment is planned in dollars, cents and all", async () => {
    const user = userEvent.setup()
    await planADollarPayment(user)
    await user.click(screen.getByRole("button", { name: "Planear" }))

    await waitFor(() => expect(planPayment).toHaveBeenCalledTimes(1))
    expect(planPayment).toHaveBeenCalledWith(
      expect.objectContaining({
        currency: "USD",
        amount: 155_604,
        account_id: DOLARAPP.id,
      }),
    )
  })
})

describe("012 — an emptied box stays empty on the confirmation", () => {
  it("A box the owner emptied is still empty when he picks another account", async () => {
    const user = await openConfirmationOfAHogaruBillInDollars()
    await emptyTheBoxOnPesosAndGoBackToDollars(user)

    expect(await screen.findByLabelText("Monto real (USD)")).toHaveValue("")
  })

  it("Confirming an empty box charges no figure the owner never wrote", async () => {
    const user = await openConfirmationOfAHogaruBillInDollars()
    await emptyTheBoxOnPesosAndGoBackToDollars(user)
    await screen.findByLabelText("Monto real (USD)")
    await user.click(screen.getByRole("button", { name: "Confirmar" }))

    await waitFor(() => expect(confirmPayment).toHaveBeenCalledTimes(1))
    expect(confirmPayment.mock.calls[0][1].amount).toBeUndefined()
  })
})
