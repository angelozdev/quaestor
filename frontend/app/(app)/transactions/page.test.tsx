import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type { Transaction } from "@/lib/api/types"
import { makeTransaction, queryWrapper } from "@/tests/factories"
import TransactionsPage from "./page"

const listTransactions = vi.fn()
const deleteTransaction = vi.fn()
const restorePlanned = vi.fn()
let currentParams = new URLSearchParams("")

vi.mock("next/navigation", () => ({
  useSearchParams: () => currentParams,
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/transactions",
}))
vi.mock("@/lib/api/transactions", () => ({
  listTransactions: (...a: unknown[]) => listTransactions(...a),
  deleteTransaction: (...a: unknown[]) => deleteTransaction(...a),
}))
vi.mock("@/lib/api/planned", () => ({
  restorePlanned: (...a: unknown[]) => restorePlanned(...a),
}))
vi.mock("@/lib/api/accounts", () => ({ listAccounts: vi.fn().mockResolvedValue([]) }))
vi.mock("@/lib/api/categories", () => ({ listCategories: vi.fn().mockResolvedValue([]) }))
vi.mock("@/lib/api/tags", () => ({ listTags: vi.fn().mockResolvedValue([]) }))

const makeTransferLeg = (): Transaction =>
  makeTransaction({
    id: 7,
    payee: "transfer",
    type: "transfer",
    amount: 10_000_000,
    cop_equivalent: 10_000_000,
    transfer_group_id: "g1",
    transfer_direction: "out",
  })

describe("TransactionsPage URL filters", () => {
  beforeEach(() => {
    listTransactions.mockReset().mockResolvedValue([])
    currentParams = new URLSearchParams("")
  })

  it("passes URL filters to listTransactions", async () => {
    currentParams = new URLSearchParams("type=expense&account_id=3")
    render(<TransactionsPage />, { wrapper: queryWrapper })
    await waitFor(() =>
      expect(listTransactions).toHaveBeenCalledWith({ type: "expense", account_id: 3 }),
    )
  })
})

describe("TransactionsPage transfer rows", () => {
  beforeEach(async () => {
    const { listAccounts } = await import("@/lib/api/accounts")
    vi.mocked(listAccounts).mockResolvedValue([
      { id: 1, name: "Bancolombia", type: "debit", currency: "COP", balance: 0, archived: false },
      { id: 2, name: "Nequi", type: "debit", currency: "COP", balance: 0, archived: false },
    ])
    listTransactions.mockReset().mockResolvedValue([
      makeTransferLeg(),
      {
        ...makeTransferLeg(),
        id: 8,
        account_id: 2,
        transfer_direction: "in",
      },
      {
        ...makeTransferLeg(),
        id: 9,
        type: "expense",
        payee: "Éxito",
        transfer_group_id: null,
        transfer_direction: null,
      },
    ])
    currentParams = new URLSearchParams("")
  })

  it("labels each transfer leg with its direction and counterpart account", async () => {
    render(<TransactionsPage />, { wrapper: queryWrapper })
    expect(await screen.findByText("Transferencia a Nequi")).toBeInTheDocument()
    expect(await screen.findByText("Transferencia desde Bancolombia")).toBeInTheDocument()
    expect(await screen.findByText("Éxito")).toBeInTheDocument()
  })
})

describe("TransactionsPage transfer deletion", () => {
  beforeEach(() => {
    listTransactions.mockReset().mockResolvedValue([makeTransferLeg()])
    deleteTransaction.mockReset().mockResolvedValue(undefined)
    currentParams = new URLSearchParams("")
  })

  it("deletes a transfer row after warning it removes both sides", async () => {
    const user = userEvent.setup()
    render(<TransactionsPage />, { wrapper: queryWrapper })
    await user.click(await screen.findByRole("button", { name: "Acciones" }))
    await user.click(await screen.findByText("Eliminar"))
    const dialog = await screen.findByRole("dialog")
    expect(within(dialog).getByText(/ambos lados de la transferencia/i)).toBeInTheDocument()
    expect(within(dialog).getByText(/Es permanente/)).toBeInTheDocument()
    await user.click(within(dialog).getByRole("button", { name: "Eliminar" }))
    await waitFor(() => expect(deleteTransaction).toHaveBeenCalledWith(7))
  })
})

describe("TransactionsPage restore action", () => {
  const openRowActions = async (status: Transaction["status"]) => {
    const user = userEvent.setup()
    listTransactions.mockReset().mockResolvedValue([makeTransaction({ id: 42, status })])
    render(<TransactionsPage />, { wrapper: queryWrapper })
    await user.click(await screen.findByRole("button", { name: "Acciones" }))
    return user
  }

  beforeEach(() => {
    restorePlanned.mockReset().mockResolvedValue(undefined)
    currentParams = new URLSearchParams("")
  })

  it("offers Restaurar on a skipped row and restores it", async () => {
    const user = await openRowActions("skipped")
    await user.click(await screen.findByText("Restaurar"))
    await waitFor(() => expect(restorePlanned).toHaveBeenCalledWith(42))
  })

  it("does not offer Restaurar on a planned row", async () => {
    await openRowActions("planned")
    expect(await screen.findByText("Editar")).toBeInTheDocument()
    expect(screen.queryByText("Restaurar")).not.toBeInTheDocument()
  })

  it("does not offer Restaurar on a posted row", async () => {
    await openRowActions("posted")
    expect(await screen.findByText("Editar")).toBeInTheDocument()
    expect(screen.queryByText("Restaurar")).not.toBeInTheDocument()
  })
})

describe("TransactionsPage single-leg transfer deletion", () => {
  beforeEach(() => {
    listTransactions.mockReset().mockResolvedValue([
      {
        ...makeTransferLeg(),
        id: 11,
        payee: "Goal: Korea",
        status: "planned",
        transfer_group_id: null,
        transfer_direction: null,
      },
    ])
    deleteTransaction.mockReset().mockResolvedValue(undefined)
    currentParams = new URLSearchParams("")
  })

  it("warns that only this movement is removed when there is no counterpart", async () => {
    const user = userEvent.setup()
    render(<TransactionsPage />, { wrapper: queryWrapper })
    await user.click(await screen.findByRole("button", { name: "Acciones" }))
    await user.click(await screen.findByText("Eliminar"))
    const dialog = await screen.findByRole("dialog")
    expect(within(dialog).queryByText(/ambos lados de la transferencia/i)).not.toBeInTheDocument()
    expect(within(dialog).getByText(/solo este movimiento/i)).toBeInTheDocument()
    await user.click(within(dialog).getByRole("button", { name: "Eliminar" }))
    await waitFor(() => expect(deleteTransaction).toHaveBeenCalledWith(11))
  })
})

describe("TransactionsPage engine provenance", () => {
  beforeEach(() => {
    deleteTransaction.mockReset()
    currentParams = new URLSearchParams("")
  })

  it("marks a movement the recurring engine made", async () => {
    listTransactions
      .mockReset()
      .mockResolvedValue([makeTransaction({ id: 21, payee: "Netflix", source: "recurring" })])
    render(<TransactionsPage />, { wrapper: queryWrapper })
    const row = (await screen.findByText("Netflix")).closest("tr") as HTMLElement
    expect(within(row).getByText("Recurrente")).toBeInTheDocument()
  })

  it("leaves a hand-entered movement unmarked", async () => {
    listTransactions
      .mockReset()
      .mockResolvedValue([makeTransaction({ id: 22, payee: "Tienda", source: "manual" })])
    render(<TransactionsPage />, { wrapper: queryWrapper })
    const row = (await screen.findByText("Tienda")).closest("tr") as HTMLElement
    expect(within(row).queryByText("Recurrente")).not.toBeInTheDocument()
  })
})
