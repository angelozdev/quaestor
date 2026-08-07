import { fireEvent, render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import { HELP_LABEL, ScreenHelp } from "./screen-help"

function aScreenCalled(name: string) {
  return (
    <div>
      <button type="button">Algo más en la pantalla</button>
      <ScreenHelp screen={name}>
        <p>Lo que hace {name}.</p>
      </ScreenHelp>
    </div>
  )
}

const panel = () => screen.getByRole("dialog")

const overlay = () => document.querySelector('[data-slot="screen-help-backdrop"]') as HTMLElement

describe("AC-9 — the panel never opens by itself", () => {
  it("A panel that was closed does not come back on the next visit", async () => {
    const user = userEvent.setup()

    const fondos = render(aScreenCalled("Fondos y presupuestos"))
    await user.click(screen.getByRole("button", { name: HELP_LABEL }))
    expect(panel()).toBeInTheDocument()
    await user.click(within(panel()).getByRole("button", { name: "Cerrar" }))
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    fondos.unmount()

    const recurrentes = render(aScreenCalled("Recurrentes"))
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    recurrentes.unmount()

    render(aScreenCalled("Fondos y presupuestos"))
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: HELP_LABEL })).toBeInTheDocument()
  })
})

describe("ScreenHelp mechanics", () => {
  it("renders whatever content the screen gives it, under that screen's name", async () => {
    const user = userEvent.setup()
    render(aScreenCalled("Etiquetas"))

    await user.click(screen.getByRole("button", { name: HELP_LABEL }))

    expect(screen.getByRole("dialog", { name: "¿Cómo funciona Etiquetas?" })).toHaveTextContent(
      "Lo que hace Etiquetas.",
    )
  })

  it("puts the keyboard inside the panel the moment it opens", async () => {
    const user = userEvent.setup()
    render(aScreenCalled("Cuentas"))

    await user.click(screen.getByRole("button", { name: HELP_LABEL }))

    expect(panel()).toContainElement(document.activeElement as HTMLElement)
  })

  it("keeps Tab inside the panel instead of letting it walk onto the screen behind", async () => {
    const user = userEvent.setup()
    render(aScreenCalled("Cuentas"))
    await user.click(screen.getByRole("button", { name: HELP_LABEL }))

    const behind = screen.getByRole("button", { name: "Algo más en la pantalla" })
    for (let step = 0; step < 5; step += 1) {
      await user.tab()
      expect(panel()).toContainElement(document.activeElement as HTMLElement)
      expect(document.activeElement).not.toBe(behind)
    }
  })

  it("walks backwards inside the panel too", async () => {
    const user = userEvent.setup()
    render(aScreenCalled("Cuentas"))
    await user.click(screen.getByRole("button", { name: HELP_LABEL }))

    await user.tab({ shift: true })

    expect(panel()).toContainElement(document.activeElement as HTMLElement)
  })

  it("stops listening for an outside press once it is closed", async () => {
    const user = userEvent.setup()
    render(aScreenCalled("Cuentas"))
    await user.click(screen.getByRole("button", { name: HELP_LABEL }))
    const dismissed = overlay()
    await user.click(dismissed)

    fireEvent.mouseDown(document.body)
    fireEvent.mouseUp(document.body)

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    expect(dismissed).not.toBeInTheDocument()
  })

  it("gives the reader their place back however the panel is closed", async () => {
    const user = userEvent.setup()
    render(aScreenCalled("Grupos"))
    const trigger = screen.getByRole("button", { name: HELP_LABEL })

    await user.click(trigger)
    await user.click(within(panel()).getByRole("button", { name: "Entendido" }))

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
  })
})
