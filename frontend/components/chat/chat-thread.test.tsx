import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import type { UIMessage } from "ai"
import { ChatThread } from "./chat-thread"

function msg(role: "user" | "assistant", text: string, id: string): UIMessage {
  return { id, role, parts: [{ type: "text", text, state: "done" }] }
}

describe("ChatThread", () => {
  it("renders each message in order", () => {
    render(
      <ChatThread
        messages={[msg("user", "hi", "u1"), msg("assistant", "hello", "a1")]}
        status="ready"
      />,
    )
    expect(screen.getByText("hi")).toBeInTheDocument()
    expect(screen.getByText("hello")).toBeInTheDocument()
  })

  it("applies aria-live=polite and aria-label for accessibility", () => {
    const { container } = render(<ChatThread messages={[]} status="ready" />)
    const region = container.querySelector("section")
    expect(region?.getAttribute("aria-live")).toBe("polite")
    expect(region?.getAttribute("aria-label")).toMatch(/Conversación con asistente/i)
  })

  it("renders the blinking cursor on the last assistant message while streaming", () => {
    render(
      <ChatThread
        messages={[
          msg("user", "hola", "u1"),
          { id: "a1", role: "assistant", parts: [{ type: "text", text: "partial", state: "streaming" }] },
        ]}
        status="streaming"
      />,
    )
    expect(screen.getByTestId("chat-cursor")).toBeInTheDocument()
  })

  it("does NOT render the cursor when status is ready", () => {
    render(
      <ChatThread
        messages={[msg("assistant", "done", "a1")]}
        status="ready"
      />,
    )
    expect(screen.queryByTestId("chat-cursor")).not.toBeInTheDocument()
  })

  it("uses a scrollable container with overflow-y:auto", () => {
    const { container } = render(<ChatThread messages={[]} status="ready" />)
    const scrollEl = container.querySelector('[data-testid="chat-scroll"]') as HTMLElement
    expect(scrollEl).not.toBeNull()
    expect(scrollEl.style.overflowY).toBe("auto")
  })
})
