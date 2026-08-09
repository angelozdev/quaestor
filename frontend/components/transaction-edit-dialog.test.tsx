import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type { Transaction } from "@/lib/api/types"
import { makeTransaction, queryWrapper } from "@/tests/factories"
import { TransactionEditDialog } from "./transaction-edit-dialog"

const updateTransaction = vi.fn()
const listTransactions = vi.fn()

vi.mock("@/lib/api/transactions", () => ({
  updateTransaction: (...a: unknown[]) => updateTransaction(...a),
  listTransactions: (...a: unknown[]) => listTransactions(...a),
}))
vi.mock("@/lib/api/categories", () => ({ listCategories: vi.fn().mockResolvedValue([]) }))
vi.mock("@/lib/api/tags", () => ({
  listTags: vi.fn().mockResolvedValue([{ id: 1, name: "viaje" }]),
}))
vi.mock("@/lib/api/accounts", () => ({
  listAccounts: vi.fn().mockResolvedValue([
    { id: 1, name: "Bancolombia", type: "debit", currency: "COP", balance: 0, archived: false },
    { id: 2, name: "Nequi", type: "debit", currency: "COP", balance: 0, archived: false },
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
