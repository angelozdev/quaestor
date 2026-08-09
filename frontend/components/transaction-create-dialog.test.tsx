import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { TransactionCreateDialog } from "./transaction-create-dialog"

const { createTransaction, listAccounts, listCategories, listMetas } = vi.hoisted(() => ({
  createTransaction: vi.fn(),
  listAccounts: vi.fn().mockResolvedValue([]),
  listCategories: vi.fn().mockResolvedValue([]),
  listMetas: vi.fn().mockResolvedValue([]),
}))
vi.mock("@/lib/api/transactions", () => ({ createTransaction, createTransfer: vi.fn() }))
vi.mock("@/lib/api/accounts", () => ({ listAccounts }))
vi.mock("@/lib/api/categories", () => ({ listCategories }))
vi.mock("@/lib/api/metas", () => ({ listMetas }))

const ACCOUNT = {
  id: 1,
  name: "Bancolombia",
  type: "debit",
  currency: "COP",
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
