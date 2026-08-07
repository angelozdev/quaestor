import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

const { listCategories, listCategoryGroups } = vi.hoisted(() => ({
  listCategories: vi.fn(),
  listCategoryGroups: vi.fn(),
}))

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(""),
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/categories",
}))
vi.mock("@/lib/api/categories", () => ({
  listCategories,
  createCategory: vi.fn(),
  updateCategory: vi.fn(),
  archiveCategory: vi.fn(),
  restoreCategory: vi.fn(),
}))
vi.mock("@/lib/api/category-groups", () => ({ listCategoryGroups }))

import CategoriesPage from "./page"

const RESTAURANTES = {
  id: 7,
  name: "Restaurantes",
  group_id: null,
  is_income: false,
  exclude_from_budget: true,
  exclude_from_totals: false,
  archived: false,
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <CategoriesPage />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  listCategories.mockResolvedValue([RESTAURANTES])
  listCategoryGroups.mockResolvedValue([])
})

describe("AC-21 — one vocabulary, everywhere", () => {
  it("The dead setting that used the word is gone from Categorías", async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole("button", { name: "Editar" }))

    expect(await screen.findByText("Editar categoría")).toBeInTheDocument()
    expect(
      screen.queryByRole("checkbox", { name: "Excluir del presupuesto" }),
    ).not.toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/presupuesto/i)
  })

  it("The badge for the dead setting is gone from the category list", async () => {
    renderPage()

    await screen.findByText("Restaurantes")
    expect(screen.queryByText(/no-presup/)).not.toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/presupuesto/i)
  })

  it("The setting that does work keeps working and keeps its name", async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole("button", { name: "Editar" }))

    expect(
      await screen.findByRole("checkbox", { name: "Excluir de los totales" }),
    ).toBeInTheDocument()
  })
})
