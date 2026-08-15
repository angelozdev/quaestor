import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { fieldUnder } from "@/tests/factories"
import { TransactionCreateDialog } from "./transaction-create-dialog"

const { createTransaction, createTransfer, listAccounts, listCategories, listMetas, chargeMarks } =
  vi.hoisted(() => ({
    createTransaction: vi.fn(),
    createTransfer: vi.fn(),
    listAccounts: vi.fn().mockResolvedValue([]),
    listCategories: vi.fn().mockResolvedValue([]),
    listMetas: vi.fn().mockResolvedValue([]),
    chargeMarks: vi.fn().mockResolvedValue([]),
  }))
vi.mock("@/lib/api/transactions", () => ({ createTransaction, createTransfer }))
vi.mock("@/lib/api/accounts", () => ({ listAccounts }))
vi.mock("@/lib/api/categories", () => ({ listCategories }))
vi.mock("@/lib/api/metas", () => ({ listMetas }))
vi.mock("@/lib/api/funds", () => ({ chargeMarks }))

const ACCOUNT = {
  id: 1,
  name: "Bancolombia",
  type: "debit",
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
const EXPENSE_CATEGORY = { id: 1, name: "Restaurantes", is_income: false }
const INCOME_CATEGORY = { id: 2, name: "Salario", is_income: true }
vi.mock("@/lib/api/tags", () => ({
  listTags: vi.fn().mockResolvedValue([{ id: 1, name: "viaje" }]),
}))

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe("TransactionCreateDialog tags", () => {
  it("offers a tags chips field on the normal tab", () => {
    render(<TransactionCreateDialog open onOpenChange={() => undefined} />, { wrapper })
    expect(screen.getByLabelText("Etiquetas")).toBeInTheDocument()
  })

  it("adds a typed tag as a chip", async () => {
    const user = userEvent.setup()
    render(<TransactionCreateDialog open onOpenChange={() => undefined} />, { wrapper })
    await user.type(screen.getByLabelText("Etiquetas"), "comida{Enter}")
    expect(screen.getByText("comida")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Quitar etiqueta comida" })).toBeInTheDocument()
  })

  it("suggests existing tags while typing", async () => {
    const user = userEvent.setup()
    render(<TransactionCreateDialog open onOpenChange={() => undefined} />, { wrapper })
    await user.type(screen.getByLabelText("Etiquetas"), "via")
    expect(await screen.findByRole("button", { name: "viaje" })).toBeInTheDocument()
  })
})

describe("TransactionCreateDialog category", () => {
  beforeEach(() => {
    listCategories
      .mockReset()
      .mockImplementation((_archived: boolean, isIncome?: boolean) =>
        Promise.resolve(isIncome ? [INCOME_CATEGORY] : [EXPENSE_CATEGORY]),
      )
    listAccounts.mockReset().mockResolvedValue([ACCOUNT])
    createTransaction.mockReset().mockResolvedValue(undefined)
  })

  it("does not offer to record without a category", async () => {
    render(<TransactionCreateDialog open onOpenChange={() => undefined} />, { wrapper })
    await waitFor(() => expect(listCategories).toHaveBeenCalled())
    expect(screen.queryByText("Sin categoría")).not.toBeInTheDocument()
  })

  it("offers only expense categories for a gasto, and only income ones for an ingreso", async () => {
    const user = userEvent.setup()
    render(<TransactionCreateDialog open onOpenChange={() => undefined} />, { wrapper })
    await waitFor(() => expect(listCategories).toHaveBeenCalledWith(false, false))

    await user.click(screen.getByRole("combobox", { name: "Tipo *" }))
    await user.click(screen.getByRole("option", { name: "Ingreso" }))

    await waitFor(() => expect(listCategories).toHaveBeenCalledWith(false, true))
  })

  it("sends the typed name as new_category so the movement saves in one action", async () => {
    const user = userEvent.setup()
    render(<TransactionCreateDialog open onOpenChange={() => undefined} />, { wrapper })
    await waitFor(() => expect(listCategories).toHaveBeenCalled())

    await user.click(screen.getByRole("button", { name: "Crear categoría" }))
    await user.type(screen.getByPlaceholderText("Nombre de la categoría de gasto"), "4x1000")
    await user.click(screen.getByRole("combobox", { name: "Cuenta *" }))
    await user.click(screen.getByRole("option", { name: "Bancolombia" }))
    await user.type(screen.getByLabelText("Monto * (COP)"), "12000")
    await user.type(screen.getByLabelText(/Beneficiario/), "Banco")
    await user.click(screen.getByRole("button", { name: "Crear" }))

    await waitFor(() => expect(createTransaction).toHaveBeenCalledTimes(1))
    expect(createTransaction).toHaveBeenCalledWith(
      expect.objectContaining({ new_category: "4x1000", category_id: null, payee: "Banco" }),
    )
  })
})

/**
 * The metas the month has, as the server hands them over.
 *
 * `listMetas` answers with the month's living metas and with no other — a
 * cancelled meta is absent from the answer, not marked inside it. The fake
 * keeps that contract so the screen is tested against the list it will really
 * be given, and a picker that built its options from any other source would
 * show "Celular" and fail here.
 */
const THIS_MONTH = new Date().toISOString().slice(0, 7)

const META_STORE = [
  { meta_id: 4, name: "Televisor", archived: false },
  { meta_id: 5, name: "Celular", archived: true },
]

function livingMetas() {
  return META_STORE.filter((meta) => !meta.archived).map((meta) => ({
    meta_id: meta.meta_id,
    name: meta.name,
    year_month: THIS_MONTH,
    amount: 500_000_000,
    currency: "COP",
    target_month: "2026-12",
    asks: 100_000_000,
    asks_cop: 100_000_000,
    holds: 100_000_000,
    progress: 20,
    complete: false,
    closed: false,
    waiting: false,
    cancelled: false,
    released: 0,
  }))
}

describe("AC-29 — a meta is archived and restored, never destroyed", () => {
  beforeEach(() => {
    listCategories
      .mockReset()
      .mockImplementation((_archived: boolean, isIncome?: boolean) =>
        Promise.resolve(isIncome ? [INCOME_CATEGORY] : [EXPENSE_CATEGORY]),
      )
    listAccounts.mockReset().mockResolvedValue([ACCOUNT])
    listMetas.mockReset().mockImplementation(() => Promise.resolve(livingMetas()))
    createTransaction.mockReset().mockResolvedValue(undefined)
  })

  it("An archived meta is not offered when an expense is recorded", async () => {
    const user = userEvent.setup()
    render(<TransactionCreateDialog open onOpenChange={() => undefined} />, { wrapper })
    await waitFor(() => expect(listMetas).toHaveBeenCalledWith(THIS_MONTH))

    await user.click(screen.getByRole("combobox", { name: /Es la compra de una meta/ }))
    expect(await screen.findByRole("option", { name: "Televisor" })).toBeInTheDocument()
    expect(screen.queryByRole("option", { name: "Celular" })).not.toBeInTheDocument()
  })
})

describe("TransactionCreateDialog meta link", () => {
  beforeEach(() => {
    listCategories
      .mockReset()
      .mockImplementation((_archived: boolean, isIncome?: boolean) =>
        Promise.resolve(isIncome ? [INCOME_CATEGORY] : [EXPENSE_CATEGORY]),
      )
    listAccounts.mockReset().mockResolvedValue([ACCOUNT])
    listMetas.mockReset().mockImplementation(() => Promise.resolve(livingMetas()))
    createTransaction.mockReset().mockResolvedValue(undefined)
  })

  it("sends the chosen meta with the purchase", async () => {
    const user = userEvent.setup()
    render(<TransactionCreateDialog open onOpenChange={() => undefined} />, { wrapper })
    await waitFor(() => expect(listMetas).toHaveBeenCalled())

    await user.click(screen.getByRole("combobox", { name: "Cuenta *" }))
    await user.click(screen.getByRole("option", { name: "Bancolombia" }))
    await user.type(screen.getByLabelText("Monto * (COP)"), "5000000")
    await user.click(screen.getByRole("combobox", { name: "Categoría *" }))
    await user.click(screen.getByRole("option", { name: "Restaurantes" }))
    await user.click(screen.getByRole("combobox", { name: /Es la compra de una meta/ }))
    await user.click(await screen.findByRole("option", { name: "Televisor" }))
    await user.click(screen.getByRole("button", { name: "Crear" }))

    await waitFor(() => expect(createTransaction).toHaveBeenCalledTimes(1))
    expect(createTransaction).toHaveBeenCalledWith(expect.objectContaining({ meta_id: 4 }))
  })

  it("never asks money coming in which meta it is for", async () => {
    const user = userEvent.setup()
    render(<TransactionCreateDialog open onOpenChange={() => undefined} />, { wrapper })
    expect(await screen.findByRole("combobox", { name: /Es la compra de una meta/ })).toBeVisible()

    await user.click(screen.getByRole("combobox", { name: "Tipo *" }))
    await user.click(screen.getByRole("option", { name: "Ingreso" }))

    expect(screen.queryByRole("combobox", { name: /Es la compra de una meta/ })).toBeNull()
  })
})

/**
 * AC-5 — the offer to name the charge a payment settled belongs to the screen
 * that saves the payment, which is where the owner is when they know.
 */
describe("AC-5 — a hand-typed payment may name the charge it settled", () => {
  const CARRO = { id: 7, name: "Carro", is_income: false }
  const marked = (over: Record<string, unknown> = {}) => ({
    recurring_id: 42,
    category_id: CARRO.id,
    name: "Seguro",
    currency: "COP",
    can_be_marked: false,
    why_not: null,
    fund_id: 7,
    ...over,
  })

  beforeEach(() => {
    listCategories
      .mockReset()
      .mockImplementation((_archived: boolean, isIncome?: boolean) =>
        Promise.resolve(isIncome ? [INCOME_CATEGORY] : [CARRO]),
      )
    listAccounts.mockReset().mockResolvedValue([ACCOUNT])
    listMetas.mockReset().mockResolvedValue([])
    createTransaction.mockReset().mockResolvedValue(undefined)
    chargeMarks.mockReset().mockResolvedValue([])
  })

  async function chooseCarro(user: ReturnType<typeof userEvent.setup>) {
    render(<TransactionCreateDialog open onOpenChange={() => undefined} />, { wrapper })
    await user.click(await screen.findByRole("combobox", { name: "Categoría *" }))
    await user.click(await screen.findByRole("option", { name: "Carro" }))
  }

  it("Saving an expense offers the marked charges of its category", async () => {
    chargeMarks.mockResolvedValue([
      marked(),
      marked({ recurring_id: 43, name: "SOAT", fund_id: 8 }),
    ])
    const user = userEvent.setup()
    await chooseCarro(user)

    await user.click(await screen.findByRole("combobox", { name: /salda un cobro/ }))

    expect(await screen.findByRole("option", { name: "Seguro" })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: "SOAT" })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: "Ninguno, es un gasto aparte" })).toBeInTheDocument()
  })

  it("A category with no marked charge offers nothing to settle", async () => {
    chargeMarks.mockResolvedValue([marked({ category_id: 99 })])
    const user = userEvent.setup()
    await chooseCarro(user)

    await waitFor(() => expect(chargeMarks).toHaveBeenCalled())

    expect(screen.queryByRole("combobox", { name: /salda un cobro/ })).toBeNull()
  })

  it("sends the chosen charge with the payment", async () => {
    chargeMarks.mockResolvedValue([marked()])
    const user = userEvent.setup()
    await chooseCarro(user)

    await user.click(screen.getByRole("combobox", { name: "Cuenta *" }))
    await user.click(screen.getByRole("option", { name: "Bancolombia" }))
    await user.type(screen.getByLabelText("Monto * (COP)"), "110000")
    await user.click(await screen.findByRole("combobox", { name: /salda un cobro/ }))
    await user.click(await screen.findByRole("option", { name: "Seguro" }))
    await user.click(screen.getByRole("button", { name: "Crear" }))

    await waitFor(() => expect(createTransaction).toHaveBeenCalledTimes(1))
    expect(createTransaction).toHaveBeenCalledWith(expect.objectContaining({ recurring_id: 42 }))
  })

  it("never asks money coming in which charge it settled", async () => {
    chargeMarks.mockResolvedValue([marked()])
    const user = userEvent.setup()
    await chooseCarro(user)
    expect(await screen.findByRole("combobox", { name: /salda un cobro/ })).toBeVisible()

    await user.click(screen.getByRole("combobox", { name: "Tipo *" }))
    await user.click(screen.getByRole("option", { name: "Ingreso" }))

    expect(screen.queryByRole("combobox", { name: /salda un cobro/ })).toBeNull()
  })
})

/**
 * A movement written down against an account that holds dollars.
 *
 * The account is chosen before the figure is typed, as the owner does it: the
 * amount box must already be asking for dollars by then, or a figure with cents
 * loses its decimal point to peso parsing and the request states the movement in
 * a currency the account does not hold.
 */
describe("a movement is stated in the currency the chosen account holds", () => {
  beforeEach(() => {
    listCategories
      .mockReset()
      .mockImplementation((_archived: boolean, isIncome?: boolean) =>
        Promise.resolve(isIncome ? [INCOME_CATEGORY] : [EXPENSE_CATEGORY]),
      )
    listAccounts.mockReset().mockResolvedValue([ACCOUNT, DOLARAPP])
    listMetas.mockReset().mockResolvedValue([])
    createTransaction.mockReset().mockResolvedValue(undefined)
  })

  async function writeADollarPurchase(user: ReturnType<typeof userEvent.setup>) {
    render(<TransactionCreateDialog open onOpenChange={() => undefined} />, { wrapper })
    await waitFor(() => expect(listCategories).toHaveBeenCalled())

    await user.click(screen.getByRole("combobox", { name: "Cuenta *" }))
    await user.click(await screen.findByRole("option", { name: DOLARAPP.name }))
    await user.type(screen.getByLabelText(/^Monto \*/), "1556.04")
    await user.click(screen.getByRole("combobox", { name: "Categoría *" }))
    await user.click(await screen.findByRole("option", { name: EXPENSE_CATEGORY.name }))
  }

  it("The amount box asks for dollars as soon as a dollar account is chosen", async () => {
    const user = userEvent.setup()
    await writeADollarPurchase(user)

    expect(screen.getByLabelText("Monto * (USD)")).toBeInTheDocument()
  })

  it("The first press states the movement in dollars, cents and all", async () => {
    const user = userEvent.setup()
    await writeADollarPurchase(user)
    await user.click(screen.getByRole("button", { name: "Crear" }))

    await waitFor(() => expect(createTransaction).toHaveBeenCalledTimes(1))
    expect(createTransaction).toHaveBeenCalledWith(
      expect.objectContaining({ currency: "USD", amount: 155_604, account_id: DOLARAPP.id }),
    )
  })

  it("Dollars leaving for a peso account are asked for as two figures, and sent as dollars", async () => {
    const user = userEvent.setup()
    render(<TransactionCreateDialog open onOpenChange={() => undefined} />, { wrapper })
    await user.click(screen.getByRole("tab", { name: "Transferencia" }))

    await user.click(within(fieldUnder("Desde *")).getByRole("combobox"))
    await user.click(await screen.findByRole("option", { name: DOLARAPP.name }))
    await user.click(within(fieldUnder("Hacia *")).getByRole("combobox"))
    await user.click(await screen.findByRole("option", { name: ACCOUNT.name }))

    await user.type(within(fieldUnder("Monto enviado * (USD)")).getByRole("textbox"), "1556.04")
    await user.type(within(fieldUnder("Monto recibido * (COP)")).getByRole("textbox"), "6200000")
    await user.click(screen.getByRole("button", { name: "Crear" }))

    await waitFor(() => expect(createTransfer).toHaveBeenCalledTimes(1))
    expect(createTransfer).toHaveBeenCalledWith(
      expect.objectContaining({
        currency: "USD",
        amount: 155_604,
        amount_received: 620_000_000,
        from_account_id: DOLARAPP.id,
        to_account_id: ACCOUNT.id,
      }),
    )
  })
})

describe("TransactionCreateDialog category direction", () => {
  beforeEach(() => {
    listCategories
      .mockReset()
      .mockImplementation((_archived: boolean, isIncome?: boolean) =>
        Promise.resolve(isIncome ? [INCOME_CATEGORY] : [EXPENSE_CATEGORY]),
      )
    listAccounts.mockReset().mockResolvedValue([ACCOUNT])
    createTransaction.mockReset().mockResolvedValue(undefined)
  })

  it("drops the chosen category when the direction changes under it", async () => {
    const user = userEvent.setup()
    render(<TransactionCreateDialog open onOpenChange={() => undefined} />, { wrapper })
    await waitFor(() => expect(listCategories).toHaveBeenCalledWith(false, false))

    await user.click(screen.getByRole("combobox", { name: "Categoría *" }))
    await user.click(screen.getByRole("option", { name: "Restaurantes" }))
    await user.click(screen.getByRole("combobox", { name: "Tipo *" }))
    await user.click(screen.getByRole("option", { name: "Ingreso" }))

    expect(screen.queryByText("Restaurantes")).not.toBeInTheDocument()
  })
})
