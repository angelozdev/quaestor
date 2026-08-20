import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { openHelpPanel, queryWrapper } from "@/tests/factories"

const { listCategoryGroups, mockPush } = vi.hoisted(() => ({
  listCategoryGroups: vi.fn(),
  mockPush: vi.fn(),
}))

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(""),
  useRouter: () => ({ replace: vi.fn(), push: mockPush }),
  usePathname: () => "/category-groups",
}))
vi.mock("@/lib/api/category-groups", () => ({
  listCategoryGroups,
  createCategoryGroup: vi.fn(),
  updateCategoryGroup: vi.fn(),
  archiveCategoryGroup: vi.fn(),
  restoreCategoryGroup: vi.fn(),
}))

import CategoryGroupsPage from "./page"

beforeEach(() => {
  vi.clearAllMocks()
  listCategoryGroups.mockResolvedValue([])
})

describe("AC-7 — every screen carries the same control", () => {
  it("Grupos offers to explain itself", async () => {
    render(<CategoryGroupsPage />, { wrapper: queryWrapper })

    expect(await openHelpPanel("Grupos")).toHaveTextContent(
      "Un grupo junta categorías que van juntas",
    )
  })
})

describe("AC-10 — an empty screen teaches and offers the way in", () => {
  it("An empty Grupos screen teaches and offers the way in", async () => {
    const user = userEvent.setup()
    render(<CategoryGroupsPage />, { wrapper: queryWrapper })

    expect(await screen.findByText(/Un grupo junta categorías que van juntas/)).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Crear el primero" }))

    expect(screen.getByText("Nuevo grupo")).toBeInTheDocument()
  })
})

describe("AC-5 — Ver movimientos drills down into the filtered list", () => {
  it("Opening Ver movimientos from a group lands on its filtered list", async () => {
    listCategoryGroups.mockResolvedValue([
      { id: 4, name: "Finanzas", sort_order: 0, archived: false },
    ])
    const user = userEvent.setup()
    render(<CategoryGroupsPage />, { wrapper: queryWrapper })
    await user.click(await screen.findByRole("button", { name: "Ver movimientos" }))

    expect(mockPush).toHaveBeenCalledWith("/transactions?group_id=4")
  })
})
