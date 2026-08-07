import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { PageHeader } from "./page-header"

describe("PageHeader", () => {
  it("shows the title by default", () => {
    render(<PageHeader title="Cuentas" />)
    expect(screen.getByRole("heading", { name: "Cuentas", level: 1 })).toBeVisible()
  })

  it("keeps a hidden title for a screen reader and off the screen", () => {
    render(<PageHeader title="Dashboard" titleHidden />)
    const heading = screen.getByRole("heading", { name: "Dashboard", level: 1 })
    expect(heading).toBeInTheDocument()
    expect(heading).toHaveClass("sr-only")
  })

  it("keeps the help control in the row when the title is hidden", () => {
    render(<PageHeader title="Dashboard" titleHidden help={<button type="button">Ayuda</button>} />)
    expect(screen.getByRole("button", { name: "Ayuda" })).toBeInTheDocument()
  })
})
