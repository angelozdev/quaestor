import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { openHelpPanel } from "@/tests/factories"

const { listCategoryGroups } = vi.hoisted(() => ({ listCategoryGroups: vi.fn() }))

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(""),
  useRouter: () => ({ replace: vi.fn() }),
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

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <CategoryGroupsPage />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  listCategoryGroups.mockResolvedValue([])
})

describe("AC-7 — every screen carries the same control", () => {
  it("Grupos offers to explain itself", async () => {
    renderPage()

    expect(await openHelpPanel("Grupos")).toHaveTextContent(
      "Un grupo junta categorías que van juntas",
    )
  })
})

describe("AC-10 — an empty screen teaches and offers the way in", () => {
  it("An empty Grupos screen teaches and offers the way in", async () => {
    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByText(/Un grupo junta categorías que van juntas/)).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Crear el primero" }))

    expect(screen.getByText("Nuevo grupo")).toBeInTheDocument()
  })
})
