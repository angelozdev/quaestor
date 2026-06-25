import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { Markdown } from "./markdown"

describe("Markdown", () => {
  it("renders bold text as a <strong> element", () => {
    render(<Markdown>{"**hola**"}</Markdown>)
    const strong = screen.getByText("hola")
    expect(strong.tagName).toBe("STRONG")
  })
})