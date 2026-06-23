import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import type { UIMessage } from "ai"
import { ChatMessage } from "./chat-message"

function userMessage(text: string): UIMessage {
  return {
    id: "u1",
    role: "user",
    parts: [{ type: "text", text }],
  }
}

function assistantMessage(text: string, id = "a1"): UIMessage {
  return {
    id,
    role: "assistant",
    parts: [{ type: "text", text, state: "done" }],
  }
}

describe("ChatMessage", () => {
  it("renders a user message right-aligned with secondary background", () => {
    const { container } = render(<ChatMessage message={userMessage("hola")} showCursor={false} />)
    const wrapper = container.firstChild as HTMLElement
    expect(wrapper.className).toMatch(/self-end|justify-end/)
    expect(wrapper.style.backgroundColor).toContain("var(--secondary)")
    expect(screen.getByText("hola")).toBeInTheDocument()
  })

  it("renders an assistant message left-aligned, plain text, no bubble background", () => {
    const { container } = render(
      <ChatMessage message={assistantMessage("respuesta")} showCursor={false} />,
    )
    const wrapper = container.firstChild as HTMLElement
    expect(wrapper.style.backgroundColor).not.toContain("var(--secondary)")
    expect(screen.getByText("respuesta")).toBeInTheDocument()
  })

  it("shows the blinking cursor when showCursor is true and no tool parts present", () => {
    render(<ChatMessage message={assistantMessage("partial")} showCursor={true} />)
    expect(screen.getByTestId("chat-cursor")).toBeInTheDocument()
  })

  it("hides the blinking cursor when showCursor is false", () => {
    render(<ChatMessage message={assistantMessage("done")} showCursor={false} />)
    expect(screen.queryByTestId("chat-cursor")).not.toBeInTheDocument()
  })

  it("renders a tool chip for dynamic-tool parts", () => {
    const msg: UIMessage = {
      id: "a2",
      role: "assistant",
      parts: [
        {
          type: "dynamic-tool",
          toolName: "list_accounts",
          toolCallId: "c1",
          state: "output-available",
          input: {},
          output: "7 accounts",
        },
      ],
    }
    const { container } = render(<ChatMessage message={msg} showCursor={false} />)
    expect(screen.getByText("list_accounts")).toBeInTheDocument()
    // No <p> wrapping a plain text node should appear (no text part).
    expect(container.querySelectorAll("p").length).toBe(0)
  })

  it("renders both text and tool parts in order", () => {
    const msg: UIMessage = {
      id: "a3",
      role: "assistant",
      parts: [
        { type: "text", text: "Resultados:", state: "done" },
        {
          type: "dynamic-tool",
          toolName: "list_accounts",
          toolCallId: "c2",
          state: "output-available",
          input: {},
          output: "ok",
        },
        { type: "text", text: "Listo.", state: "done" },
      ],
    }
    render(<ChatMessage message={msg} showCursor={false} />)
    expect(screen.getByText("Resultados:")).toBeInTheDocument()
    expect(screen.getByText("list_accounts")).toBeInTheDocument()
    expect(screen.getByText("Listo.")).toBeInTheDocument()
  })

  it("returns null for system messages", () => {
    const { container } = render(
      <ChatMessage
        message={{
          id: "s1",
          role: "system",
          parts: [{ type: "text", text: "you are a helpful assistant" }],
        }}
        showCursor={false}
      />,
    )
    expect(container.firstChild).toBeNull()
  })
})
