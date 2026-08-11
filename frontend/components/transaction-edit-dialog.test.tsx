import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type { Transaction } from "@/lib/api/types"
import { makeTransaction, queryWrapper } from "@/tests/factories"
import { TransactionEditDialog } from "./transaction-edit-dialog"

const updateTransaction = vi.fn()
const listTransactions = vi.fn()
const correctTransaction = vi.fn()

vi.mock("@/lib/api/transactions", () => ({
  updateTransaction: (...a: unknown[]) => updateTransaction(...a),
  listTransactions: (...a: unknown[]) => listTransactions(...a),
  correctTransaction: (...a: unknown[]) => correctTransaction(...a),
}))
vi.mock("@/lib/api/fx", () => ({ getFx: () => Promise.resolve({ usd_cop: "4000" }) }))
vi.mock("@/lib/api/categories", () => ({ listCategories: vi.fn().mockResolvedValue([]) }))
vi.mock("@/lib/api/tags", () => ({
  listTags: vi.fn().mockResolvedValue([{ id: 1, name: "viaje" }]),
}))
vi.mock("@/lib/api/accounts", () => ({
  listAccounts: (includeArchived = false) =>
    Promise.resolve([
      { id: 1, name: "Bancolombia", type: "debit", currency: "COP", balance: 0, archived: false },
      { id: 2, name: "Nequi", type: "debit", currency: "COP", balance: 0, archived: false },
      { id: 3, name: "DolarApp", type: "debit", currency: "USD", balance: 0, archived: false },
      ...(includeArchived
        ? [{ id: 9, name: "Korea", type: "debit", currency: "COP", balance: 0, archived: true }]
        : []),
    ]),
}))
vi.mock("@/lib/api/metas", () => ({
  listMetas: vi.fn().mockResolvedValue([
    {
      meta_id: 4,
      name: "Televisor",
      year_month: "2026-07",
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
    },
  ]),
}))

function renderDialog(tx: Transaction) {
  return render(<TransactionEditDialog tx={tx} open onOpenChange={() => undefined} />, {
    wrapper: queryWrapper,
  })
}

describe("TransactionEditDialog tags", () => {
  beforeEach(() => {
    updateTransaction.mockReset().mockResolvedValue(makeTransaction())
    listTransactions.mockReset().mockResolvedValue([])
  })

  it("shows the transaction's tags as chips", () => {
    renderDialog(makeTransaction({ tags: ["viaje"] }))
    expect(screen.getByText("viaje")).toBeInTheDocument()
    expect(screen.getByLabelText("Etiquetas")).toBeInTheDocument()
  })

  it("sends the tag replace-set on save", async () => {
    const user = userEvent.setup()
    renderDialog(makeTransaction({ tags: ["viaje"] }))
    await user.click(screen.getByRole("button", { name: "Quitar etiqueta viaje" }))
    await user.click(screen.getByRole("button", { name: "Guardar" }))
    await waitFor(() => expect(updateTransaction).toHaveBeenCalledTimes(1))
    expect(updateTransaction).toHaveBeenCalledWith(1, expect.objectContaining({ tags: [] }))
  })
})

describe("AC-28 — the link can be removed or moved", () => {
  beforeEach(() => {
    updateTransaction.mockReset().mockResolvedValue(makeTransaction())
    listTransactions.mockReset().mockResolvedValue([])
  })

  it("gives the purchase back to its category by dropping the meta", async () => {
    const user = userEvent.setup()
    renderDialog(makeTransaction({ meta_id: 4 }))
    await user.click(await screen.findByRole("combobox", { name: /Es la compra de una meta/ }))
    await user.click(screen.getByRole("option", { name: "Ninguna" }))
    await user.click(screen.getByRole("button", { name: "Guardar" }))

    await waitFor(() => expect(updateTransaction).toHaveBeenCalledTimes(1))
    expect(updateTransaction).toHaveBeenCalledWith(1, expect.objectContaining({ meta_id: null }))
  })

  it("points the purchase at another meta", async () => {
    const user = userEvent.setup()
    renderDialog(makeTransaction())
    await user.click(await screen.findByRole("combobox", { name: /Es la compra de una meta/ }))
    await user.click(await screen.findByRole("option", { name: "Televisor" }))
    await user.click(screen.getByRole("button", { name: "Guardar" }))

    await waitFor(() => expect(updateTransaction).toHaveBeenCalledTimes(1))
    expect(updateTransaction).toHaveBeenCalledWith(1, expect.objectContaining({ meta_id: 4 }))
  })

  it("never asks a transfer which meta it is for", async () => {
    renderDialog(makeTransaction({ type: "transfer", transfer_group_id: null }))
    expect(await screen.findByRole("button", { name: "Guardar" })).toBeInTheDocument()
    expect(screen.queryByRole("combobox", { name: /Es la compra de una meta/ })).toBeNull()
  })
})

describe("TransactionEditDialog transfer pair", () => {
  beforeEach(() => {
    updateTransaction.mockReset().mockResolvedValue(makeTransaction())
    listTransactions.mockReset().mockResolvedValue([
      makeTransaction({ id: 10, type: "transfer", transfer_group_id: "g1", account_id: 1 }),
      makeTransaction({
        id: 11,
        type: "transfer",
        transfer_group_id: "g1",
        account_id: 2,
        amount: 4_000_000,
      }),
    ])
  })

  it("identifies a transfer leg and its counterpart", async () => {
    renderDialog(
      makeTransaction({
        id: 10,
        type: "transfer",
        transfer_group_id: "g1",
        transfer_direction: "out",
      }),
    )
    expect(await screen.findByText("Parte de una transferencia")).toBeInTheDocument()
    expect(await screen.findByText(/Enviada a/)).toBeInTheDocument()
    expect(await screen.findByText(/Nequi/)).toBeInTheDocument()
    expect(await screen.findByText(/40\.000/)).toBeInTheDocument()
  })

  it("shows no transfer badge for a regular expense", () => {
    renderDialog(makeTransaction())
    expect(screen.queryByText("Parte de una transferencia")).not.toBeInTheDocument()
  })
})

describe("012 — a movement is corrected, not deleted", () => {
  beforeEach(() => {
    updateTransaction.mockReset().mockResolvedValue(makeTransaction())
    listTransactions.mockReset().mockResolvedValue([])
    correctTransaction.mockReset().mockResolvedValue(makeTransaction())
  })

  it("The instruction to delete and recreate is gone", () => {
    renderDialog(makeTransaction())
    expect(screen.queryByText(/elimina y vuelve a crear/i)).not.toBeInTheDocument()
  })

  it("The account is offered rather than described", async () => {
    renderDialog(makeTransaction())
    await waitFor(() =>
      expect(screen.getByRole("combobox", { name: "Cuenta" })).toHaveTextContent("Bancolombia"),
    )
    expect(screen.queryByText(/cuenta #/)).not.toBeInTheDocument()
  })

  it("The amount is offered rather than described", async () => {
    renderDialog(makeTransaction({ amount: 10_000_000 }))
    expect(await screen.findByLabelText("Monto (COP)")).toHaveValue("100000")
  })

  it("A retired account is not on the list when correcting", async () => {
    const user = userEvent.setup()
    renderDialog(makeTransaction())
    await user.click(await screen.findByRole("combobox", { name: "Cuenta" }))
    expect(screen.queryByRole("option", { name: "Korea" })).not.toBeInTheDocument()
    expect(screen.getByRole("option", { name: "Nequi" })).toBeInTheDocument()
  })

  it("The account offered when correcting is reachable by its label", async () => {
    renderDialog(makeTransaction())
    expect(await screen.findByLabelText("Cuenta")).toBeInTheDocument()
    expect(screen.getByLabelText("Monto (COP)")).toBeInTheDocument()
  })

  it("The converted figure arrives filled in, exactly as when confirming", async () => {
    const user = userEvent.setup()
    renderDialog(
      makeTransaction({
        type: "transfer",
        transfer_group_id: "g1",
        transfer_direction: "in",
        amount: 40_000_000,
        currency: "COP",
        category_id: null,
      }),
    )
    await user.click(await screen.findByRole("combobox", { name: "Cuenta" }))
    await user.click(screen.getByRole("option", { name: "DolarApp" }))
    expect(await screen.findByLabelText("Monto (USD)")).toHaveValue("100")
  })

  it("sends the correction and the edit as two acts of one save", async () => {
    const user = userEvent.setup()
    renderDialog(makeTransaction())
    await user.click(await screen.findByRole("combobox", { name: "Cuenta" }))
    await user.click(screen.getByRole("option", { name: "Nequi" }))
    await user.click(screen.getByRole("button", { name: "Guardar" }))
    await waitFor(() => expect(correctTransaction).toHaveBeenCalledTimes(1))
    expect(correctTransaction).toHaveBeenCalledWith(1, { account_id: 2, amount: 5_000_000 })
    expect(updateTransaction).toHaveBeenCalledTimes(1)
  })
})
