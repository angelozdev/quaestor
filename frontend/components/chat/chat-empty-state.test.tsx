import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { ChatEmptyState } from "./chat-empty-state"

describe("ChatEmptyState", () => {
  it("renders the title and subtitle copy", () => {
    render(<ChatEmptyState onPick={vi.fn()} />)
    expect(screen.getByText("Pregúntale a tu asistente")).toBeInTheDocument()
    expect(screen.getByText(/Puede leer tus cuentas, transacciones y fondos\./)).toBeInTheDocument()
  })

  it("renders exactly 3 suggested-prompt buttons", () => {
    render(<ChatEmptyState onPick={vi.fn()} />)
    const buttons = screen.getAllByRole("button")
    expect(buttons).toHaveLength(3)
  })

  it("calls onPick with the chip text when clicked", async () => {
    const user = userEvent.setup()
    const onPick = vi.fn()
    render(<ChatEmptyState onPick={onPick} />)
    await user.click(screen.getByRole("button", { name: /¿Cuánto puedo gastar este mes\?/ }))
    expect(onPick).toHaveBeenCalledWith("¿Cuánto puedo gastar este mes?")
  })

  it("uses the brand mint accent for the chip border", () => {
    const { container } = render(<ChatEmptyState onPick={vi.fn()} />)
    const firstChip = container.querySelector("button")
    const style = (firstChip as HTMLElement).style.borderColor
    expect(style).toContain("var(--primary)")
  })
})
