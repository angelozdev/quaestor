import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { ChatInput } from "./chat-input"

describe("ChatInput", () => {
  it("renders a textarea and a send button", () => {
    render(<ChatInput status="ready" onSend={vi.fn()} onStop={vi.fn()} />)
    expect(screen.getByRole("textbox")).toBeInTheDocument()
    expect(screen.getByRole("button")).toBeInTheDocument()
  })

  it("calls onSend with the typed text on Enter", async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<ChatInput status="ready" onSend={onSend} onStop={vi.fn()} />)
    const ta = screen.getByRole("textbox")
    await user.type(ta, "hola mundo")
    await user.keyboard("{Enter}")
    expect(onSend).toHaveBeenCalledWith("hola mundo")
  })

  it("does NOT call onSend on Shift+Enter (inserts newline)", async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<ChatInput status="ready" onSend={onSend} onStop={vi.fn()} />)
    const ta = screen.getByRole("textbox")
    await user.type(ta, "line1")
    await user.keyboard("{Shift>}{Enter}{/Shift}")
    await user.keyboard("line2")
    expect(onSend).not.toHaveBeenCalled()
  })

  it("disables the textarea and shows a stop button while streaming", () => {
    render(<ChatInput status="streaming" onSend={vi.fn()} onStop={vi.fn()} />)
    expect(screen.getByRole("textbox")).toBeDisabled()
    expect(screen.getByRole("button", { name: /detener|stop/i })).toBeInTheDocument()
  })

  it("calls onStop when Esc is pressed while streaming", async () => {
    const user = userEvent.setup()
    const onStop = vi.fn()
    render(<ChatInput status="streaming" onSend={vi.fn()} onStop={onStop} />)
    await user.click(screen.getByRole("textbox"))
    await user.keyboard("{Escape}")
    expect(onStop).toHaveBeenCalledTimes(1)
  })

  it("calls onStop when the stop button is clicked", async () => {
    const user = userEvent.setup()
    const onStop = vi.fn()
    render(<ChatInput status="submitted" onSend={vi.fn()} onStop={onStop} />)
    await user.click(screen.getByRole("button"))
    expect(onStop).toHaveBeenCalledTimes(1)
  })

  it("clears the textarea after a successful send", async () => {
    const user = userEvent.setup()
    render(<ChatInput status="ready" onSend={vi.fn()} onStop={vi.fn()} />)
    const ta = screen.getByRole("textbox") as HTMLTextAreaElement
    await user.type(ta, "pregunta")
    await user.keyboard("{Enter}")
    expect(ta.value).toBe("")
  })

  it("wraps the textarea in a div with the chat-input-underline class", () => {
    const { container } = render(
      <ChatInput status="ready" onSend={vi.fn()} onStop={vi.fn()} />,
    )
    expect(container.querySelector(".chat-input-underline")).not.toBeNull()
  })
})
