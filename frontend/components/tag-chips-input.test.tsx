import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { TagChipsInput } from "./tag-chips-input"

function renderChips(overrides: Partial<Parameters<typeof TagChipsInput>[0]> = {}) {
  const onChange = vi.fn()
  const utils = render(
    <TagChipsInput
      value={["viaje"]}
      onChange={onChange}
      suggestions={["viaje", "comida", "trabajo"]}
      {...overrides}
    />,
  )
  return { onChange, ...utils }
}

describe("TagChipsInput", () => {
  it("renders the current tags as chips", () => {
    renderChips()
    expect(screen.getByText("viaje")).toBeInTheDocument()
    expect(screen.getByLabelText("Etiquetas")).toBeInTheDocument()
  })

  it("adds a typed tag on Enter", async () => {
    const user = userEvent.setup()
    const { onChange } = renderChips()
    await user.type(screen.getByLabelText("Etiquetas"), "reembolso{Enter}")
    expect(onChange).toHaveBeenCalledWith(["viaje", "reembolso"])
  })

  it("never duplicates an already selected tag", async () => {
    const user = userEvent.setup()
    const { onChange } = renderChips()
    await user.type(screen.getByLabelText("Etiquetas"), "viaje{Enter}")
    expect(onChange).not.toHaveBeenCalled()
    expect(screen.getByLabelText("Etiquetas")).toHaveValue("")
  })

  it("ignores blank input on Enter", async () => {
    const user = userEvent.setup()
    const { onChange } = renderChips()
    await user.type(screen.getByLabelText("Etiquetas"), "   {Enter}")
    expect(onChange).not.toHaveBeenCalled()
  })

  it("removes a chip from its button", async () => {
    const user = userEvent.setup()
    const { onChange } = renderChips()
    await user.click(screen.getByRole("button", { name: "Quitar etiqueta viaje" }))
    expect(onChange).toHaveBeenCalledWith([])
  })

  it("suggests matching existing tags, excluding selected ones", async () => {
    const user = userEvent.setup()
    const { onChange } = renderChips()
    await user.type(screen.getByLabelText("Etiquetas"), "a")
    expect(screen.getByRole("button", { name: "comida" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "trabajo" })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "viaje" })).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "comida" }))
    expect(onChange).toHaveBeenCalledWith(["viaje", "comida"])
  })

  it("shows no suggestions while the input is empty", () => {
    renderChips()
    expect(screen.queryByRole("button", { name: "comida" })).not.toBeInTheDocument()
  })
})
