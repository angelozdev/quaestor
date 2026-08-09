import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { openHelpPanel, queryWrapper } from "@/tests/factories"

const { listCategories, listCategoryGroups, createCategory, updateCategory } = vi.hoisted(() => ({
  listCategories: vi.fn(),
  listCategoryGroups: vi.fn(),
  createCategory: vi.fn(),
  updateCategory: vi.fn(),
}))

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(""),
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/categories",
}))
vi.mock("@/lib/api/categories", () => ({
  listCategories,
  createCategory,
  updateCategory,
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
  counts_as_saving: false,
  archived: false,
}

beforeEach(() => {
  vi.clearAllMocks()
  listCategories.mockResolvedValue([RESTAURANTES])
  listCategoryGroups.mockResolvedValue([])
})

describe("AC-21 — one vocabulary, everywhere", () => {
  it("The dead setting that used the word is gone from Categorías", async () => {
    const user = userEvent.setup()
    render(<CategoriesPage />, { wrapper: queryWrapper })
    await user.click(await screen.findByRole("button", { name: "Editar" }))

    expect(await screen.findByText("Editar categoría")).toBeInTheDocument()
    expect(
      screen.queryByRole("checkbox", { name: "Excluir del presupuesto" }),
    ).not.toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/presupuesto/i)
  })

  it("The badge for the dead setting is gone from the category list", async () => {
    render(<CategoriesPage />, { wrapper: queryWrapper })

    await screen.findByText("Restaurantes")
    expect(screen.queryByText(/no-presup/)).not.toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/presupuesto/i)
  })

  it("The setting that does work keeps working and keeps its name", async () => {
    const user = userEvent.setup()
    render(<CategoriesPage />, { wrapper: queryWrapper })
    await user.click(await screen.findByRole("button", { name: "Editar" }))

    expect(
      await screen.findByRole("checkbox", { name: "Excluir de los totales" }),
    ).toBeInTheDocument()
  })
})

describe("AC-7 — every screen carries the same control", () => {
  it("Categorías offers to explain itself", async () => {
    render(<CategoriesPage />, { wrapper: queryWrapper })

    expect(await openHelpPanel("Categorías")).toHaveTextContent(
      "Una categoría dice para qué fue un movimiento",
    )
  })
})

describe("AC-10 — an empty screen teaches and offers the way in", () => {
  it("An empty Categorías screen teaches and offers the way in", async () => {
    listCategories.mockResolvedValue([])
    const user = userEvent.setup()
    render(<CategoriesPage />, { wrapper: queryWrapper })

    expect(
      await screen.findByText(/Una categoría dice para qué fue un movimiento/),
    ).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Crear la primera" }))

    expect(screen.getByText("Nueva categoría")).toBeInTheDocument()
  })
})

describe("AC-41 — a category can say that spending in it is saving", () => {
  it("The mark can be put on a new category", async () => {
    const user = userEvent.setup()
    createCategory.mockResolvedValue({ ...RESTAURANTES, id: 9, name: "Inversión" })
    render(<CategoriesPage />, { wrapper: queryWrapper })
    await user.click(await screen.findByRole("button", { name: "Nueva" }))

    await user.type(await screen.findByLabelText(/^Nombre/), "Inversión")
    await user.click(screen.getByRole("checkbox", { name: "Gastar aquí es ahorrar" }))
    await user.click(screen.getByRole("button", { name: "Guardar" }))

    expect(createCategory).toHaveBeenCalledWith(
      expect.objectContaining({ name: "Inversión", counts_as_saving: true }),
    )
  })

  it("The mark can be put on a category that already exists", async () => {
    const user = userEvent.setup()
    updateCategory.mockResolvedValue({ ...RESTAURANTES, counts_as_saving: true })
    render(<CategoriesPage />, { wrapper: queryWrapper })
    await user.click(await screen.findByRole("button", { name: "Editar" }))

    await user.click(await screen.findByRole("checkbox", { name: "Gastar aquí es ahorrar" }))
    await user.click(screen.getByRole("button", { name: "Guardar" }))

    expect(updateCategory).toHaveBeenCalledWith(
      7,
      expect.objectContaining({ counts_as_saving: true }),
    )
  })

  it("A category that is saving says so in the list", async () => {
    listCategories.mockResolvedValue([{ ...RESTAURANTES, counts_as_saving: true }])
    render(<CategoriesPage />, { wrapper: queryWrapper })

    expect(await screen.findByText("ahorro")).toBeInTheDocument()
  })

  it("The mark is off unless the owner puts it on", async () => {
    render(<CategoriesPage />, { wrapper: queryWrapper })

    await screen.findByText("Restaurantes")
    expect(screen.queryByText("ahorro")).not.toBeInTheDocument()
  })
})
