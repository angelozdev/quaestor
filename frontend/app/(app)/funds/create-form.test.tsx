import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type { FundPreview } from "@/lib/api/types"
import { CreateFundForm } from "./create-form"

const { createFund, previewFund, listCategories, toast } = vi.hoisted(() => ({
  createFund: vi.fn(),
  previewFund: vi.fn(),
  listCategories: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock("@/lib/api/funds", () => ({ createFund, previewFund }))
vi.mock("@/lib/api/categories", () => ({ listCategories }))
vi.mock("sonner", () => ({ toast }))

const TECNOLOGIA = { id: 8, name: "Tecnologia", is_income: false }

function renderForm() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <CreateFundForm
        shape="fondo"
        month="2026-01"
        heldBy={new Map()}
        onDone={() => undefined}
        onCancel={() => undefined}
      />
    </QueryClientProvider>,
  )
}

async function fillTheRequiredFields(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("combobox", { name: "Categoría *" }))
  await user.click(await screen.findByRole("option", { name: "Tecnologia" }))
  await user.type(screen.getByLabelText("Monto mensual * (COP)"), "200000")
}

describe("AC-1, AC-6 — declaring the saved balance from the create-fund screen, or leaving it blank", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listCategories.mockResolvedValue([TECNOLOGIA])
    previewFund.mockResolvedValue({
      category_id: TECNOLOGIA.id,
      would_ask: 0,
      warning: null,
      crowded: [],
      has_something_to_spread: false,
    } satisfies FundPreview)
    createFund.mockResolvedValue({ id: 1 })
  })

  it("The create-fund form lets the owner say what it already holds", async () => {
    const user = userEvent.setup()
    renderForm()

    await fillTheRequiredFields(user)
    await user.type(screen.getByLabelText("Ya tiene ahorrado (opcional)"), "500000")
    await user.click(screen.getByRole("button", { name: "Crear" }))

    await waitFor(() =>
      expect(createFund).toHaveBeenCalledWith(
        expect.objectContaining({
          category_id: TECNOLOGIA.id,
          amount: 20_000_000,
          opening_balance: 50_000_000,
        }),
      ),
    )
  })

  it("leaves opening_balance out of the request when the owner never states one", async () => {
    const user = userEvent.setup()
    renderForm()

    await fillTheRequiredFields(user)
    await user.click(screen.getByRole("button", { name: "Crear" }))

    await waitFor(() => expect(createFund).toHaveBeenCalled())
    expect(createFund.mock.calls[0][0]).not.toHaveProperty("opening_balance")
  })
})
