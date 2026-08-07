import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ replace: vi.fn(), refresh: vi.fn() }),
}))
vi.mock("next-themes", () => ({ useTheme: () => ({ resolvedTheme: "dark", setTheme: vi.fn() }) }))

import { AppShell } from "./app-shell"

function renderShell() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <AppShell>
        <p>contenido</p>
      </AppShell>
    </QueryClientProvider>,
  )
}

describe("AC-1 — the menu carries both words", () => {
  it("The navigation names both shapes", () => {
    renderShell()

    const entries = screen.getAllByRole("link", { name: "Fondos y presupuestos" })
    expect(entries.length).toBeGreaterThan(0)
    expect(entries[0]).toHaveAttribute("href", "/funds")
    expect(screen.queryByRole("link", { name: "Fondos" })).not.toBeInTheDocument()
  })
})
