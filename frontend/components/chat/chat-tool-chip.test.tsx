import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import type { DynamicToolUIPart, ToolUIPart } from "ai"
import { ChatToolChip } from "./chat-tool-chip"

function dynamicPart(overrides: Partial<DynamicToolUIPart> = {}): DynamicToolUIPart {
  return {
    type: "dynamic-tool",
    toolName: "list_accounts",
    toolCallId: "call_123",
    state: "input-available",
    input: { filter: "active" },
    ...overrides,
  } as DynamicToolUIPart
}

function typedPart(overrides: Partial<ToolUIPart> = {}): ToolUIPart {
  return {
    type: "tool-list_accounts",
    toolCallId: "call_456",
    state: "input-available",
    input: {},
    ...overrides,
  } as ToolUIPart
}

describe("ChatToolChip", () => {
  it("renders the tool name from a dynamic-tool part", () => {
    render(<ChatToolChip part={dynamicPart()} />)
    expect(screen.getByText("list_accounts")).toBeInTheDocument()
  })

  it("renders the tool name from a typed tool-{name} part", () => {
    render(<ChatToolChip part={typedPart()} />)
    expect(screen.getByText("list_accounts")).toBeInTheDocument()
  })

  it("starts collapsed with aria-expanded=false", () => {
    render(<ChatToolChip part={dynamicPart({ state: "output-available", output: "ok" })} />)
    const toggle = screen.getByRole("button", { name: /list_accounts/i })
    expect(toggle).toHaveAttribute("aria-expanded", "false")
  })

  it("expands on click and reveals input + output", async () => {
    const user = userEvent.setup()
    render(
      <ChatToolChip
        part={dynamicPart({
          state: "output-available",
          input: { filter: "active" },
          output: "7 accounts",
        })}
      />,
    )
    const toggle = screen.getByRole("button", { name: /list_accounts/i })
    await user.click(toggle)
    expect(toggle).toHaveAttribute("aria-expanded", "true")
    // JSON-stringified input appears inside a <pre>
    expect(screen.getByText(/"filter": "active"/)).toBeInTheDocument()
    expect(screen.getByText("7 accounts")).toBeInTheDocument()
  })

  it("applies destructive styling when state is output-error", () => {
    render(
      <ChatToolChip
        part={dynamicPart({ state: "output-error", errorText: "tool blew up" })}
      />,
    )
    expect(screen.getByText("tool blew up")).toBeInTheDocument()
    // The output region exists and carries role=region for screen readers.
    // We assert the destructive color is applied via the dot's inline style.
    const dot = screen.getByTestId("chat-tool-dot")
    expect((dot as HTMLElement).style.backgroundColor).toContain("var(--destructive)")
  })

  it("hides input block when input is undefined", async () => {
    const user = userEvent.setup()
    render(
      <ChatToolChip
        part={dynamicPart({ state: "output-available", input: undefined, output: "ok" })}
      />,
    )
    await user.click(screen.getByRole("button", { name: /list_accounts/i }))
    // No JSON-looking <pre> exists; output block still does.
    expect(screen.queryByText(/[{}]/)).not.toBeInTheDocument()
    expect(screen.getByText("ok")).toBeInTheDocument()
  })

  it("marks expanded JSON <pre> blocks with data-sensitive='true'", async () => {
    const user = userEvent.setup()
    const { container } = render(
      <ChatToolChip
        part={dynamicPart({
          state: "output-available",
          input: { secret: "hunter2" },
          output: "7 accounts",
        })}
      />,
    )
    await user.click(screen.getByRole("button", { name: /list_accounts/i }))
    const pres = container.querySelectorAll("pre[data-sensitive]")
    expect(pres.length).toBeGreaterThanOrEqual(2)
    pres.forEach((el) => {
      expect(el.getAttribute("data-sensitive")).toBe("true")
    })
  })
})
