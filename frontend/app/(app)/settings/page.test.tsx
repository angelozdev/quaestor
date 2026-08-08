import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { queryWrapper } from "@/tests/factories"

const { getSettings, updateSettings, getFx, setFx, listAccounts } = vi.hoisted(() => ({
  getSettings: vi.fn(),
  updateSettings: vi.fn(),
  getFx: vi.fn(),
  setFx: vi.fn(),
  listAccounts: vi.fn(),
}))

vi.mock("@/lib/api/settings", () => ({ getSettings, updateSettings }))
vi.mock("@/lib/api/fx", () => ({ getFx, setFx }))
vi.mock("@/lib/api/accounts", () => ({ listAccounts }))

import SettingsPage from "./page"

beforeEach(() => {
  vi.clearAllMocks()
  getSettings.mockResolvedValue({ base_currency: "COP", default_source_account_id: null })
  getFx.mockResolvedValue({ usd_cop: "4000.00" })
  listAccounts.mockResolvedValue([])
})

describe("AC-21 — one vocabulary, everywhere", () => {
  it("Ajustes no longer speaks of a feature that was removed", async () => {
    render(<SettingsPage />, { wrapper: queryWrapper })

    await screen.findByText("Ajustes")
    expect(document.body.textContent).not.toMatch(/metas/i)
    expect(screen.getByText(/Cuenta usada como origen de las transferencias/)).toBeInTheDocument()
  })
})
