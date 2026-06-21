import { useForm } from "@tanstack/react-form"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import { z } from "zod"
import { messages } from "@/lib/schemas/messages"
import { FormField } from "./form-field"

function Harness() {
  const form = useForm({
    defaultValues: { name: "" },
    validators: {
      // Zod v4 implements StandardSchemaV1; TanStack accepts it directly.
      onChange: z.object({ name: z.string().min(1, messages.required) }),
    },
  })
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        form.handleSubmit()
      }}
    >
      <form.Field name="name">{(field) => <FormField field={field} label="Nombre" />}</form.Field>
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
    expect(await screen.findByText(messages.required)).toBeInTheDocument()
  })

  it("clears error when user types", async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(screen.getByRole("button", { name: "Enviar" }))
    await user.type(screen.getByLabelText("Nombre *"), "Ana")
    expect(screen.queryByText(messages.required)).not.toBeInTheDocument()
  })
})
