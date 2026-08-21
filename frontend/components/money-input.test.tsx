import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useState } from "react"
import { describe, expect, it, vi } from "vitest"
import { MoneyInput } from "./money-input"

describe("MoneyInput", () => {
  it("Typing a peso amount shows the thousand separator live", async () => {
    const user = userEvent.setup()
    render(<MoneyInput currency="COP" value={null} onChange={vi.fn()} />)

    await user.type(screen.getByRole("textbox"), "1000000")

    expect(screen.getByRole("textbox")).toHaveValue("1.000.000")
  })

  it("Typing a dollar amount shows the thousand separator without touching the decimal point", async () => {
    const user = userEvent.setup()
    render(<MoneyInput currency="USD" value={null} onChange={vi.fn()} />)

    await user.type(screen.getByRole("textbox"), "1000.5")

    expect(screen.getByRole("textbox")).toHaveValue("1,000.5")
  })

  it("Typing a second decimal point after typed cents does not misreport what was kept", async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<MoneyInput currency="USD" value={null} onChange={onChange} />)
    const input = screen.getByRole("textbox") as HTMLInputElement

    await user.type(input, "1000.5")
    expect(input).toHaveValue("1,000.5")
    expect(onChange).toHaveBeenLastCalledWith(100_050)

    await user.type(input, ".", { initialSelectionStart: 5, initialSelectionEnd: 5 })

    expect(input).toHaveValue("1,000.5")
    expect(onChange).toHaveBeenLastCalledWith(100_050)
  })

  it("Editing a digit in the middle of a long amount keeps the cursor next to it", async () => {
    const user = userEvent.setup()
    render(<MoneyInput currency="COP" value={150_000_000} onChange={vi.fn()} />)
    const input = screen.getByRole("textbox") as HTMLInputElement
    expect(input).toHaveValue("1.500.000")

    await user.type(input, "9", { initialSelectionStart: 3, initialSelectionEnd: 3 })

    expect(input).toHaveValue("15.900.000")
    expect(input.selectionStart).toBe(4)
    expect(input.selectionEnd).toBe(4)
  })

  it("A small amount shows no separator", async () => {
    const user = userEvent.setup()
    render(<MoneyInput currency="COP" value={null} onChange={vi.fn()} />)

    await user.type(screen.getByRole("textbox"), "500")

    expect(screen.getByRole("textbox")).toHaveValue("500")
  })

  it("Pasting an already-formatted amount reads the same as pasting the bare digits", async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<MoneyInput currency="COP" value={null} onChange={onChange} />)
    const input = screen.getByRole("textbox")

    await user.click(input)
    await user.paste("1.000.000")

    expect(input).toHaveValue("1.000.000")
    expect(onChange).toHaveBeenLastCalledWith(100_000_000)
  })

  it("Typing letters mixed with digits ignores the letters", async () => {
    const user = userEvent.setup()
    render(<MoneyInput currency="COP" value={null} onChange={vi.fn()} />)

    await user.type(screen.getByRole("textbox"), "abc1000abc")

    expect(screen.getByRole("textbox")).toHaveValue("1.000")
  })

  it("The saved amount survives a round trip through the formatted display", async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    const { unmount } = render(<MoneyInput currency="COP" value={null} onChange={onChange} />)

    await user.type(screen.getByRole("textbox"), "1500000")
    expect(onChange).toHaveBeenLastCalledWith(150_000_000)
    unmount()

    render(<MoneyInput currency="COP" value={150_000_000} onChange={vi.fn()} />)

    expect(screen.getByRole("textbox")).toHaveValue("1.500.000")
  })

  it("A field wired the way every real screen wires it does not drop a decimal digit already typed", async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()

    function Harness() {
      const [cents, setCents] = useState<number | null>(null)
      return (
        <MoneyInput
          currency="USD"
          value={cents}
          onChange={(c) => {
            onChange(c)
            setCents(c)
          }}
        />
      )
    }
    render(<Harness />)
    const input = screen.getByRole("textbox")

    await user.type(input, "1000.")
    expect(input).toHaveValue("1,000.")

    await user.type(input, "5")
    expect(input).toHaveValue("1,000.5")
    expect(onChange).toHaveBeenLastCalledWith(100_050)
  })

  it("An account balance in the hundreds of millions of pesos groups every separator", async () => {
    const user = userEvent.setup()
    render(<MoneyInput currency="COP" value={null} onChange={vi.fn()} />)

    await user.type(screen.getByRole("textbox"), "123456789")

    expect(screen.getByRole("textbox")).toHaveValue("123.456.789")
  })

  it("Switching currency from outside does not replay the change back and still lets the user keep typing", async () => {
    const onChange = vi.fn()

    function Harness() {
      const [currency, setCurrency] = useState("COP")
      const [cents, setCents] = useState<number | null>(null)
      return (
        <div>
          <button
            type="button"
            onClick={() => {
              setCurrency("USD")
              setCents(2000)
            }}
          >
            switch to dollars
          </button>
          <MoneyInput
            currency={currency}
            value={cents}
            onChange={(c) => {
              onChange(c)
              setCents(c)
            }}
          />
        </div>
      )
    }
    const user = userEvent.setup()
    render(<Harness />)
    const input = screen.getByRole("textbox")

    await user.click(screen.getByRole("button", { name: "switch to dollars" }))

    expect(input).toHaveValue("20")
    expect(onChange).not.toHaveBeenCalled()

    await user.type(input, "5")
    expect(onChange).toHaveBeenCalled()
  })
})
