import { zodResolver } from "@hookform/resolvers/zod"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useForm } from "react-hook-form"
import { describe, expect, it } from "vitest"
import { z } from "zod"
import { FormField } from "./form-field"

function Harness() {
  const schema = z.object({ name: z.string().min(1, "Requerido") })
  const { control, handleSubmit } = useForm<{ name: string }>({
    resolver: zodResolver(schema),
    defaultValues: { name: "" },
  })
  return (
    <form onSubmit={handleSubmit(() => {})}>
      <FormField control={control} name="name" label="Nombre" />
      <button type="submit">Enviar</button>
    </form>
  )
}

describe("FormField", () => {
  it("shows label", () => {
    render(<Harness />)
    expect(screen.getByText("Nombre")).toBeInTheDocument()
  })

  it("shows error after invalid submit", async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(screen.getByRole("button", { name: "Enviar" }))
    expect(await screen.findByText("Requerido")).toBeInTheDocument()
  })

  it("clears error when user types", async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(screen.getByRole("button", { name: "Enviar" }))
    await user.type(screen.getByLabelText("Nombre *"), "Ana")
    expect(screen.queryByText("Requerido")).not.toBeInTheDocument()
  })
})
