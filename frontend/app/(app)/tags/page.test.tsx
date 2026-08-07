import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { openHelpPanel, queryWrapper } from "@/tests/factories"

const { listTags } = vi.hoisted(() => ({ listTags: vi.fn() }))

vi.mock("@/lib/api/tags", () => ({
  listTags,
  createTag: vi.fn(),
  updateTag: vi.fn(),
  deleteTag: vi.fn(),
}))

import TagsPage from "./page"

beforeEach(() => {
  vi.clearAllMocks()
  listTags.mockResolvedValue([])
})

describe("AC-7 — every screen carries the same control", () => {
  it("Etiquetas offers to explain itself", async () => {
    render(<TagsPage />, { wrapper: queryWrapper })

    expect(await openHelpPanel("Etiquetas")).toHaveTextContent(
      "Una etiqueta marca movimientos que van juntos aunque estén en categorías distintas",
    )
  })
})

describe("AC-10 — an empty screen teaches and offers the way in", () => {
  it("An empty Etiquetas screen teaches and offers the way in", async () => {
    const user = userEvent.setup()
    render(<TagsPage />, { wrapper: queryWrapper })

    expect(
      await screen.findByText(/Una etiqueta marca movimientos que van juntos/),
    ).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Crear la primera" }))

    expect(screen.getByText("Nueva etiqueta")).toBeInTheDocument()
  })
})
