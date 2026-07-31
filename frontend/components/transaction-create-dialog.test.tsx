import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { TransactionCreateDialog } from "./transaction-create-dialog"

vi.mock("@/lib/api/transactions", () => ({
  createTransaction: vi.fn(),
  createTransfer: vi.fn(),
}))
vi.mock("@/lib/api/accounts", () => ({ listAccounts: vi.fn().mockResolvedValue([]) }))
vi.mock("@/lib/api/categories", () => ({ listCategories: vi.fn().mockResolvedValue([]) }))
vi.mock("@/lib/api/tags", () => ({
  listTags: vi.fn().mockResolvedValue([{ id: 1, name: "viaje" }]),
}))

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe("TransactionCreateDialog tags", () => {
  it("offers a tags chips field on the normal tab", () => {
    render(<TransactionCreateDialog open onOpenChange={() => undefined} />, { wrapper })
    expect(screen.getByLabelText("Etiquetas")).toBeInTheDocument()
  })

  it("adds a typed tag as a chip", async () => {
    const user = userEvent.setup()
    render(<TransactionCreateDialog open onOpenChange={() => undefined} />, { wrapper })
    await user.type(screen.getByLabelText("Etiquetas"), "comida{Enter}")
    expect(screen.getByText("comida")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Quitar etiqueta comida" })).toBeInTheDocument()
  })

  it("suggests existing tags while typing", async () => {
    const user = userEvent.setup()
    render(<TransactionCreateDialog open onOpenChange={() => undefined} />, { wrapper })
    await user.type(screen.getByLabelText("Etiquetas"), "via")
    expect(await screen.findByRole("button", { name: "viaje" })).toBeInTheDocument()
  })
})
