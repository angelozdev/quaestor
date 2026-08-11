import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { AxiosError, type InternalAxiosRequestConfig } from "axios"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { http } from "@/lib/api/client"
import { makeTransaction, queryWrapper } from "@/tests/factories"
import { TransactionEditDialog } from "./transaction-edit-dialog"

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn() } }))
vi.mock("sonner", () => ({ toast }))

const ACCOUNTS = [
  { id: 1, name: "Bancolombia", type: "debit", currency: "COP", balance: 0, archived: false },
  { id: 2, name: "Nequi", type: "debit", currency: "COP", balance: 0, archived: false },
]

const READS: Record<string, unknown> = {
  "/accounts": ACCOUNTS,
  "/categories": [],
  "/transactions": [],
  "/metas": [],
  "/tags": [],
  "/fx": { usd_cop: "4000" },
}

function sessionExpiredOnWrites() {
  return vi.fn((config: InternalAxiosRequestConfig) => {
    const path = (config.url ?? "").split("?")[0]
    if ((config.method ?? "get").toLowerCase() === "get") {
      return Promise.resolve({
        data: READS[path] ?? [],
        status: 200,
        statusText: "OK",
        headers: {},
        config,
      })
    }
    return Promise.reject(
      new AxiosError("Request failed with status code 401", "ERR_BAD_REQUEST", config, null, {
        data: { error: "Unauthorized", detail: "credentials required or invalid" },
        status: 401,
        statusText: "Unauthorized",
        headers: {},
        config,
      }),
    )
  })
}

describe("TransactionEditDialog when the session expired", () => {
  const original = http.defaults.adapter

  beforeEach(() => {
    toast.success.mockClear()
    toast.error.mockClear()
    http.defaults.adapter = sessionExpiredOnWrites()
  })

  afterEach(() => {
    http.defaults.adapter = original
  })

  async function moveTheMovementAndSave(onOpenChange: () => void) {
    const user = userEvent.setup()
    render(<TransactionEditDialog tx={makeTransaction()} open onOpenChange={onOpenChange} />, {
      wrapper: queryWrapper,
    })
    await user.click(await screen.findByRole("combobox", { name: "Cuenta" }))
    await user.click(await screen.findByRole("option", { name: "Nequi" }))
    await user.click(screen.getByRole("button", { name: "Guardar" }))
  }

  const theSaveAnswered = () =>
    expect([...toast.success.mock.calls, ...toast.error.mock.calls]).toHaveLength(1)

  it("never claims the movement was updated, and keeps the dialog open", async () => {
    const onOpenChange = vi.fn()

    await moveTheMovementAndSave(onOpenChange)
    await waitFor(theSaveAnswered)

    expect(toast.success).not.toHaveBeenCalled()
    expect(onOpenChange).not.toHaveBeenCalled()
    expect(toast.error).toHaveBeenCalledTimes(1)
  })

  it("tells the owner in Spanish to sign in again", async () => {
    await moveTheMovementAndSave(vi.fn())

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        "Tu sesión expiró. Vuelve a iniciar sesión e inténtalo de nuevo.",
      ),
    )
  })
})
