import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { EmptyState } from "./empty-state"

describe("EmptyState", () => {
  it("renders the message", () => {
    render(<EmptyState message="Sin datos" />)
    expect(screen.getByText("Sin datos")).toBeInTheDocument()
  })

  it("renders an action button that fires onClick", async () => {
    const onClick = vi.fn()
    render(<EmptyState message="Nada aún" action={{ label: "Crear", onClick }} />)
    screen.getByRole("button", { name: "Crear" }).click()
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it("renders an action link when href is given", () => {
    render(<EmptyState message="Nada aún" action={{ label: "Ir", href: "/x" }} />)
    expect(screen.getByRole("link", { name: "Ir" })).toHaveAttribute("href", "/x")
  })

  it("renders one way in per action when a screen holds more than one kind of thing", () => {
    const first = vi.fn()
    const second = vi.fn()
    render(
      <EmptyState
        message="Nada aún"
        description={<p>lo que cada uno hace</p>}
        action={[
          { label: "Crear el primero", onClick: first },
          { label: "Crear el otro", onClick: second },
        ]}
      />,
    )

    expect(screen.getByText("lo que cada uno hace")).toBeInTheDocument()
    screen.getByRole("button", { name: "Crear el otro" }).click()
    expect(first).not.toHaveBeenCalled()
    expect(second).toHaveBeenCalledTimes(1)
  })
})
