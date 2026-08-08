import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { HELP_LABEL } from "@/components/screen-help"
import type { Recurring } from "@/lib/api/types"
import { openHelpPanel, queryWrapper } from "@/tests/factories"

const { listRecurring } = vi.hoisted(() => ({ listRecurring: vi.fn() }))

vi.mock("@/lib/api/recurring", () => ({
  listRecurring,
  createRecurring: vi.fn(),
  updateRecurring: vi.fn(),
  deleteRecurring: vi.fn(),
  restoreRecurring: vi.fn(),
  skipRecurring: vi.fn(),
}))
vi.mock("@/lib/api/accounts", () => ({ listAccounts: vi.fn().mockResolvedValue([]) }))
vi.mock("@/lib/api/categories", () => ({ listCategories: vi.fn().mockResolvedValue([]) }))

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

const openHelp = () => openHelpPanel("Recurrentes")

beforeEach(() => {
  vi.clearAllMocks()
  listRecurring.mockResolvedValue([])
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
