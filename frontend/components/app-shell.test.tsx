import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { queryWrapper } from "@/tests/factories"

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ replace: vi.fn(), refresh: vi.fn() }),
}))
vi.mock("next-themes", () => ({ useTheme: () => ({ resolvedTheme: "dark", setTheme: vi.fn() }) }))

import { AppShell } from "./app-shell"

function renderShell() {
  return render(
    <AppShell>
      <p>contenido</p>
    </AppShell>,
    { wrapper: queryWrapper },
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
