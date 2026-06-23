import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { ChatBlinkingCursor } from "./chat-blinking-cursor"

describe("ChatBlinkingCursor", () => {
  it("renders an aria-hidden decorative glyph with the expected text", () => {
    render(<ChatBlinkingCursor />)
    const glyph = screen.getByTestId("chat-cursor")
    expect(glyph).toBeInTheDocument()
    expect(glyph).toHaveAttribute("aria-hidden", "true")
    expect(glyph.textContent).toBe("_")
  })

  it("uses the Bricolage heading font", () => {
    render(<ChatBlinkingCursor />)
    const glyph = screen.getByTestId("chat-cursor")
    // font-family must include the brand display font CSS var chain.
    const style = (glyph as HTMLElement).style.fontFamily
    expect(style).toContain("var(--font-heading)")
  })

  it("uses the mint primary color", () => {
    render(<ChatBlinkingCursor />)
    const glyph = screen.getByTestId("chat-cursor")
    const style = (glyph as HTMLElement).style.color
    expect(style).toContain("var(--primary)")
  })
})
