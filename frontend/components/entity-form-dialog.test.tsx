import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { z } from "zod"
import { messages } from "@/lib/schemas/messages"
import { EntityFormDialog, type Field } from "./entity-form-dialog"

// Three-kind smoke test (per Task 43 / Finding 3): text, money, select.
const FIELDS: Field[] = [
  { kind: "text", name: "name", label: "Nombre", required: true },
  {
    kind: "select",
    name: "type",
    label: "Tipo",
    required: true,
    options: [
      { value: "expense", label: "Gasto" },
      { value: "income", label: "Ingreso" },
    ],
  },
  {
    kind: "money",
    name: "balance",
    label: "Balance",
    currencyFrom: "currency",
  },
]

const SCHEMA = z.object({
  name: z.string().trim().min(1, messages.required),
  type: z.string().min(1, messages.required),
  balance: z.number().int().nullable(),
  currency: z.string(),
})

type Values = z.infer<typeof SCHEMA>

const INITIAL: Values = { name: "", type: "expense", balance: null, currency: "COP" }

function renderDialog(props: Partial<React.ComponentProps<typeof EntityFormDialog<Values>>> = {}) {
  const onSubmit = vi.fn()
  const utils = render(
    <EntityFormDialog<Values>
      open
      onOpenChange={() => undefined}
      title="Test"
      fields={FIELDS}
      initialValues={INITIAL}
      onSubmit={onSubmit}
      schema={SCHEMA}
      {...props}
    />,
  )
  return { onSubmit, ...utils }
}

describe("EntityFormDialog", () => {
  it("renders all three field kinds", () => {
    renderDialog()
    // text field — input with id matches the field name
    expect(screen.getByLabelText("Nombre *")).toBeInTheDocument()
    // select — base-ui renders a trigger with the accessible label we set via <Label htmlFor>
    expect(screen.getByLabelText("Tipo *")).toBeInTheDocument()
    // money — MoneyInput renders a span with the currency prefix
    expect(screen.getByText("$")).toBeInTheDocument()
    expect(screen.getByLabelText("Balance")).toBeInTheDocument()
  })

  it("calls onSubmit with parsed values when all required fields are filled", async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderDialog()

    await user.type(screen.getByLabelText("Nombre *"), "Comida")
    // Type into the money input
    await user.type(screen.getByLabelText("Balance"), "15000")
    await user.click(screen.getByRole("button", { name: "Guardar" }))

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1)
    })
    const submitted = onSubmit.mock.calls[0]?.[0] as Values
    expect(submitted.name).toBe("Comida")
    // 15000 COP -> 1500000 cents
    expect(submitted.balance).toBe(1_500_000)
    // currency default from initialValues
    expect(submitted.currency).toBe("COP")
    // Select unchanged from defaults
    expect(submitted.type).toBe("expense")
  })

  it("shows validation error when a required field is empty", async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderDialog()

    // Submit with the required `name` field empty (zod min(1) should reject).
    await user.click(screen.getByRole("button", { name: "Guardar" }))

    expect(await screen.findByText(messages.required)).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it("clears validation error after the user types", async () => {
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole("button", { name: "Guardar" }))
    expect(await screen.findByText(messages.required)).toBeInTheDocument()

    await user.type(screen.getByLabelText("Nombre *"), "X")
    await waitFor(() => {
      expect(screen.queryByText(messages.required)).not.toBeInTheDocument()
    })
  })
})
