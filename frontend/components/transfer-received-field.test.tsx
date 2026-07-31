import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { TransferReceivedField } from "./transfer-received-field"

function renderField(overrides: Partial<Parameters<typeof TransferReceivedField>[0]> = {}) {
  return render(
    <TransferReceivedField
      active
      sentCurrency="USD"
      receivedCurrency="COP"
      sentCents={10000}
      receivedCents={40000000}
      onChange={vi.fn()}
      {...overrides}
    />,
  )
}

describe("TransferReceivedField", () => {
  it("renders the received amount input when currencies differ", () => {
    renderField()
    expect(screen.getByText(/monto recibido \* \(cop\)/i)).toBeInTheDocument()
    expect(screen.getByRole("textbox")).toBeInTheDocument()
  })

  it("renders nothing for same-currency transfers", () => {
    const { container } = renderField({ sentCurrency: "COP", receivedCurrency: "COP" })
    expect(container).toBeEmptyDOMElement()
  })

  it("renders nothing until both accounts are chosen", () => {
    const { container } = renderField({ active: false })
    expect(container).toBeEmptyDOMElement()
  })

  it("shows the implied rate as information only", () => {
    renderField()
    expect(screen.getByText(/tasa implícita: 4\.000,00 \(solo informativa\)/i)).toBeInTheDocument()
  })

  it("updates the implied rate with the amounts", () => {
    renderField({ sentCents: 10000, receivedCents: 1 })
    expect(screen.getByText(/tasa implícita: 0,00/i)).toBeInTheDocument()
  })

  it("hides the implied rate while an amount is missing", () => {
    renderField({ receivedCents: null })
    expect(screen.queryByText(/tasa implícita/i)).not.toBeInTheDocument()
  })

  it("shows a validation message when given one", () => {
    renderField({ errorMessage: "Debe ser positivo" })
    expect(screen.getByText("Debe ser positivo")).toBeInTheDocument()
  })
})
