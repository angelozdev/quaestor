import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useState } from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { type CategoryChoice, CategoryField, NO_CATEGORY } from "./category-field"

const { listCategories } = vi.hoisted(() => ({ listCategories: vi.fn() }))
vi.mock("@/lib/api/categories", () => ({ listCategories }))

const EXPENSE = { id: 1, name: "Restaurantes", is_income: false }
const INCOME = { id: 2, name: "Salario", is_income: true }

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

function renderField(isIncome: boolean, onChange = vi.fn(), value: CategoryChoice = NO_CATEGORY) {
  render(<CategoryField value={value} onChange={onChange} isIncome={isIncome} />, { wrapper })
  return onChange
}

describe("CategoryField", () => {
  beforeEach(() => {
    listCategories
      .mockReset()
      .mockImplementation((_archived: boolean, isIncome?: boolean) =>
        Promise.resolve(isIncome ? [INCOME] : [EXPENSE]),
      )
  })

  it("never offers to leave the movement uncategorised", async () => {
    renderField(false)
    await waitFor(() => expect(listCategories).toHaveBeenCalled())
    expect(screen.queryByText("Sin categoría")).not.toBeInTheDocument()
  })

  it("asks the API only for categories of the movement's direction", async () => {
    renderField(true)
    await waitFor(() => expect(listCategories).toHaveBeenCalledWith(false, true))
    expect(listCategories).not.toHaveBeenCalledWith(false, false)
  })

  it("swaps the select for a name input when the user creates one", async () => {
    const user = userEvent.setup()
    let chosen: CategoryChoice = NO_CATEGORY

    function Harness() {
      const [value, setValue] = useState<CategoryChoice>(NO_CATEGORY)
      chosen = value
      return <CategoryField value={value} onChange={setValue} isIncome={false} />
    }
    render(<Harness />, { wrapper })

    await user.click(screen.getByRole("button", { name: "Crear categoría" }))
    await user.type(screen.getByPlaceholderText("Nombre de la categoría de gasto"), "4x1000")

    expect(chosen).toEqual({ categoryId: null, newCategory: "4x1000" })
  })

  it("clears what was chosen when the user switches between the two ways", async () => {
    const user = userEvent.setup()
    const onChange = renderField(false, vi.fn(), { categoryId: 1, newCategory: "" })

    await user.click(screen.getByRole("button", { name: "Crear categoría" }))

    expect(onChange).toHaveBeenCalledWith(NO_CATEGORY)
  })

  it("shows the refusal the form hands it", () => {
    render(
      <CategoryField value={NO_CATEGORY} onChange={vi.fn()} isIncome={false} error="Requerido" />,
      { wrapper },
    )
    expect(screen.getByText("Requerido")).toBeInTheDocument()
  })
})
