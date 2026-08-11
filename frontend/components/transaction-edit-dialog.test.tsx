import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type { Transaction } from "@/lib/api/types"
import { makeTransaction, queryWrapper } from "@/tests/factories"
import { TransactionEditDialog } from "./transaction-edit-dialog"

const updateTransaction = vi.fn()
const listTransactions = vi.fn()
const correctTransaction = vi.fn()

const { listAccounts, toast } = vi.hoisted(() => ({
  listAccounts: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock("@/lib/api/transactions", () => ({
  updateTransaction: (...a: unknown[]) => updateTransaction(...a),
  listTransactions: (...a: unknown[]) => listTransactions(...a),
  correctTransaction: (...a: unknown[]) => correctTransaction(...a),
}))
vi.mock("sonner", () => ({ toast }))
vi.mock("@/lib/api/fx", () => ({ getFx: () => Promise.resolve({ usd_cop: "4000" }) }))
vi.mock("@/lib/api/categories", () => ({ listCategories: vi.fn().mockResolvedValue([]) }))
vi.mock("@/lib/api/tags", () => ({
  listTags: vi.fn().mockResolvedValue([{ id: 1, name: "viaje" }]),
}))
vi.mock("@/lib/api/accounts", () => ({ listAccounts }))

const ACCOUNTS = [
  { id: 1, name: "Bancolombia", type: "debit", currency: "COP", balance: 0, archived: false },
  { id: 2, name: "Nequi", type: "debit", currency: "COP", balance: 0, archived: false },
  { id: 3, name: "DolarApp", type: "debit", currency: "USD", balance: 0, archived: false },
]
const KOREA = { id: 9, name: "Korea", type: "debit", currency: "COP", balance: 0, archived: true }

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

beforeEach(() => {
  toast.success.mockClear()
  toast.error.mockClear()
  listAccounts.mockImplementation((includeArchived = false) =>
    Promise.resolve(includeArchived ? [...ACCOUNTS, KOREA] : ACCOUNTS),
  )
})

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
    expect(correctTransaction).toHaveBeenCalledWith(1, { account_id: 2 })
    expect(updateTransaction).toHaveBeenCalledTimes(1)
  })

  it("states only the amount when only the amount was rewritten", async () => {
    const user = userEvent.setup()
    renderDialog(makeTransaction())
    const amount = await screen.findByLabelText("Monto (COP)")
    await user.clear(amount)
    await user.type(amount, "95200")
    await user.click(screen.getByRole("button", { name: "Guardar" }))
    await waitFor(() => expect(correctTransaction).toHaveBeenCalledTimes(1))
    expect(correctTransaction).toHaveBeenCalledWith(1, { amount: 9_520_000 })
  })

  it("states the account and the amount together when both were changed in one currency", async () => {
    const user = userEvent.setup()
    renderDialog(makeTransaction())
    await user.click(await screen.findByRole("combobox", { name: "Cuenta" }))
    await user.click(screen.getByRole("option", { name: "Nequi" }))
    const amount = await screen.findByLabelText("Monto (COP)")
    await user.clear(amount)
    await user.type(amount, "420000")
    await user.click(screen.getByRole("button", { name: "Guardar" }))
    await waitFor(() => expect(correctTransaction).toHaveBeenCalledTimes(1))
    expect(correctTransaction).toHaveBeenCalledWith(1, { account_id: 2, amount: 42_000_000 })
  })

  it("states no correction at all when nothing was touched", async () => {
    const user = userEvent.setup()
    renderDialog(makeTransaction())
    await user.click(await screen.findByRole("button", { name: "Guardar" }))
    await waitFor(() => expect(updateTransaction).toHaveBeenCalledTimes(1))
    expect(correctTransaction).not.toHaveBeenCalled()
  })
})

describe("012 — a movement is read in the currency it was recorded in", () => {
  beforeEach(() => {
    updateTransaction.mockReset().mockResolvedValue(makeTransaction())
    listTransactions.mockReset().mockResolvedValue([])
    correctTransaction.mockReset().mockResolvedValue(makeTransaction())
    listAccounts.mockReturnValue(new Promise(() => undefined))
  })

  const inDollars = () =>
    makeTransaction({ account_id: 3, amount: 10_000, currency: "USD", cop_equivalent: 40_000_000 })

  it("A movement in another currency is read in its own currency", async () => {
    renderDialog(inDollars())
    expect(await screen.findByLabelText("Monto (USD)")).toHaveValue("100")
  })

  it("A figure written before the list of accounts arrives keeps its cents", async () => {
    const user = userEvent.setup()
    renderDialog(inDollars())
    const amount = await screen.findByLabelText("Monto (USD)")
    await user.clear(amount)
    await user.type(amount, "87.52")
    expect(amount).toHaveValue("87.52")

    await user.click(screen.getByRole("button", { name: "Guardar" }))
    await waitFor(() => expect(correctTransaction).toHaveBeenCalledTimes(1))
    expect(correctTransaction).toHaveBeenCalledWith(1, { amount: 8_752 })
  })
})

/** Both halves of a transfer, as the group query hands them over. */
function aTransferPair(overrides: { received?: Partial<Transaction> } = {}) {
  const sent = makeTransaction({
    id: 10,
    type: "transfer",
    transfer_group_id: "g1",
    transfer_direction: "out",
    account_id: 2,
    amount: 20_000_000,
    currency: "COP",
  })
  const received = makeTransaction({
    id: 11,
    type: "transfer",
    transfer_group_id: "g1",
    transfer_direction: "in",
    account_id: 1,
    amount: 20_000_000,
    currency: "COP",
    ...overrides.received,
  })
  listTransactions.mockResolvedValue([sent, received])
  return { sent, received }
}

describe("012 — a transfer is restated on both of its sides", () => {
  beforeEach(() => {
    updateTransaction.mockReset().mockResolvedValue(makeTransaction())
    listTransactions.mockReset().mockResolvedValue([])
    correctTransaction.mockReset().mockResolvedValue(makeTransaction())
  })

  it("A transfer in one currency shows the half being corrected what it is worth", async () => {
    const { sent } = aTransferPair()
    renderDialog(sent)
    expect(await screen.findByLabelText("Monto (COP)")).toHaveValue("200000")
  })

  it("Restating one half on the screen restates both halves", async () => {
    const user = userEvent.setup()
    const { sent } = aTransferPair()
    renderDialog(sent)
    const amount = await screen.findByLabelText("Monto (COP)")
    await user.clear(amount)
    await user.type(amount, "250000")
    await user.click(screen.getByRole("button", { name: "Guardar" }))
    await waitFor(() => expect(correctTransaction).toHaveBeenCalledTimes(1))
    expect(correctTransaction).toHaveBeenCalledWith(10, { sent: 25_000_000, received: 25_000_000 })
  })

  it("asks what left and what arrived when the two halves are in different currencies", async () => {
    const user = userEvent.setup()
    const { sent } = aTransferPair({
      received: { account_id: 3, amount: 5_000, currency: "USD" },
    })
    renderDialog(sent)
    expect(await screen.findByLabelText("Monto enviado (COP)")).toHaveValue("200000")
    expect(screen.getByLabelText("Monto recibido (USD)")).toHaveValue("50")

    const received = screen.getByLabelText("Monto recibido (USD)")
    await user.clear(received)
    await user.type(received, "52")
    await user.click(screen.getByRole("button", { name: "Guardar" }))
    await waitFor(() => expect(correctTransaction).toHaveBeenCalledTimes(1))
    expect(correctTransaction).toHaveBeenCalledWith(10, { sent: 20_000_000, received: 5_200 })
  })
})

describe("012 — a correction that states nothing writes nothing", () => {
  beforeEach(() => {
    updateTransaction.mockReset().mockResolvedValue(makeTransaction())
    listTransactions.mockReset().mockResolvedValue([])
    correctTransaction.mockReset().mockResolvedValue(makeTransaction())
  })

  it("An emptied amount is not saved as a correction", async () => {
    const user = userEvent.setup()
    renderDialog(makeTransaction())
    const amount = await screen.findByLabelText("Monto (COP)")
    await user.clear(amount)
    await user.click(screen.getByRole("button", { name: "Guardar" }))

    await waitFor(() => expect(toast.error).toHaveBeenCalledTimes(1))
    expect(correctTransaction).not.toHaveBeenCalled()
    expect(updateTransaction).not.toHaveBeenCalled()
    expect(toast.success).not.toHaveBeenCalled()
  })
})

describe("012 — the money moves after the edit is safe", () => {
  beforeEach(() => {
    listTransactions.mockReset().mockResolvedValue([])
  })

  it("saves the edit before it moves any balance", async () => {
    const user = userEvent.setup()
    const order: string[] = []
    updateTransaction.mockReset().mockImplementation(async () => {
      order.push("edit")
      return makeTransaction()
    })
    correctTransaction.mockReset().mockImplementation(async () => {
      order.push("correction")
      return makeTransaction()
    })
    renderDialog(makeTransaction())
    await user.click(await screen.findByRole("combobox", { name: "Cuenta" }))
    await user.click(screen.getByRole("option", { name: "Nequi" }))
    await user.click(screen.getByRole("button", { name: "Guardar" }))

    await waitFor(() => expect(correctTransaction).toHaveBeenCalledTimes(1))
    expect(order).toEqual(["edit", "correction"])
  })

  it("says the edit was saved when the correction is refused", async () => {
    const user = userEvent.setup()
    updateTransaction.mockReset().mockResolvedValue(makeTransaction())
    correctTransaction.mockReset().mockRejectedValue(new Error("nope"))
    renderDialog(makeTransaction())
    await user.click(await screen.findByRole("combobox", { name: "Cuenta" }))
    await user.click(screen.getByRole("option", { name: "Nequi" }))
    await user.click(screen.getByRole("button", { name: "Guardar" }))

    await waitFor(() => expect(toast.error).toHaveBeenCalledTimes(1))
    expect(toast.error).toHaveBeenCalledWith(
      expect.stringContaining("Se guardaron los datos, pero el monto y la cuenta"),
    )
    expect(toast.success).not.toHaveBeenCalled()
  })
})
