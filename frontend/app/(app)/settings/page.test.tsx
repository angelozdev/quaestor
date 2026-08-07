import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

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

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <SettingsPage />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  getSettings.mockResolvedValue({ base_currency: "COP", default_source_account_id: null })
  getFx.mockResolvedValue({ usd_cop: "4000.00" })
  listAccounts.mockResolvedValue([])
})

describe("AC-21 — one vocabulary, everywhere", () => {
  it("Ajustes no longer speaks of a feature that was removed", async () => {
    renderPage()

    await screen.findByText("Ajustes")
    expect(document.body.textContent).not.toMatch(/metas/i)
    expect(screen.getByText(/Cuenta usada como origen de las transferencias/)).toBeInTheDocument()
  })
})
