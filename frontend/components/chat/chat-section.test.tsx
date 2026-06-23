import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import type { ReactNode } from "react"

type Msg = {
  id: string
  role: "user" | "assistant" | "system"
  parts: Array<{ type: string; text?: string }>
}

// --- Mock @ai-sdk/react (hoisted) ----------------------------------------
const mocks = vi.hoisted(() => {
  const sendMessage = vi.fn()
  const stop = vi.fn()
  const regenerate = vi.fn()
  return {
    sendMessage,
    stop,
    regenerate,
    mockStatus: { current: "ready" as "submitted" | "streaming" | "ready" | "error" },
    mockMessages: { current: [] as Msg[] },
    mockError: { current: undefined as Error | undefined },
  }
})

vi.mock("@ai-sdk/react", () => ({
  useChat: () => ({
    messages: mocks.mockMessages.current,
    sendMessage: mocks.sendMessage,
    stop: mocks.stop,
    regenerate: mocks.regenerate,
    status: mocks.mockStatus.current,
    error: mocks.mockError.current,
  }),
}))

import { ChatSection } from "./chat-section"

function withQueryClient(node: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{node}</QueryClientProvider>
}

function resetMocks() {
  mocks.sendMessage.mockClear()
  mocks.stop.mockClear()
  mocks.regenerate.mockClear()
  mocks.mockStatus.current = "ready"
  mocks.mockMessages.current = []
  mocks.mockError.current = undefined
}

describe("ChatSection", () => {
  it("renders the empty state with 3 chips when no messages and status ready", () => {
    resetMocks()
    render(withQueryClient(<ChatSection />))
    expect(screen.getByText("Pregúntale a tu asistente")).toBeInTheDocument()
    const buttons = screen.getAllByRole("button")
    // 3 suggestion chips.
    expect(buttons.length).toBeGreaterThanOrEqual(3)
  })

  it("clicking a suggestion chip calls sendMessage with that text", async () => {
    const user = userEvent.setup()
    resetMocks()
    render(withQueryClient(<ChatSection />))
    await user.click(screen.getByRole("button", { name: /Lista mis cuentas y sus saldos/ }))
    expect(mocks.sendMessage).toHaveBeenCalledWith({ text: "Lista mis cuentas y sus saldos" })
  })

  it("renders ChatThread when messages exist", () => {
    resetMocks()
    mocks.mockMessages.current = [
      { id: "u1", role: "user", parts: [{ type: "text", text: "hola" }] },
      { id: "a1", role: "assistant", parts: [{ type: "text", text: "buenos días" }] },
    ]
    render(withQueryClient(<ChatSection />))
    expect(screen.getByText("hola")).toBeInTheDocument()
    expect(screen.getByText("buenos días")).toBeInTheDocument()
  })

  it("renders the error banner when status is error", () => {
    resetMocks()
    mocks.mockStatus.current = "error"
    mocks.mockError.current = new Error("message content exceeds 32 KB")
    render(withQueryClient(<ChatSection />))
    const banner = screen.getByRole("alert")
    // The raw message is NEVER rendered — translateChatError replaces it.
    expect(banner).not.toHaveTextContent(/message content exceeds 32 KB/)
    expect(screen.getByRole("button", { name: /Reintentar/i })).toBeInTheDocument()
  })

  it("regenerate button calls the regenerate hook", async () => {
    const user = userEvent.setup()
    resetMocks()
    mocks.mockStatus.current = "error"
    mocks.mockError.current = new Error("boom")
    render(withQueryClient(<ChatSection />))
    await user.click(screen.getByRole("button", { name: /Reintentar/i }))
    expect(mocks.regenerate).toHaveBeenCalledTimes(1)
  })

  it("renders the es-CO translated copy, NOT the raw error.message", () => {
    resetMocks()
    mocks.mockStatus.current = "error"
    mocks.mockError.current = new Error("message content exceeds 32 KB")
    render(withQueryClient(<ChatSection />))
    const banner = screen.getByRole("alert")
    expect(banner).toHaveTextContent(/Tu mensaje es muy largo\. Acórtalo e intenta de nuevo\./)
  })

  it("close × button dismisses the banner", async () => {
    const user = userEvent.setup()
    resetMocks()
    mocks.mockStatus.current = "error"
    mocks.mockError.current = new Error("boom")
    render(withQueryClient(<ChatSection />))
    expect(screen.getByRole("alert")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: /Cerrar mensaje de error/i }))
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })

  it("a new error message re-shows the banner after dismissal", async () => {
    const user = userEvent.setup()
    resetMocks()
    mocks.mockStatus.current = "error"
    mocks.mockError.current = new Error("boom")
    const { rerender } = render(withQueryClient(<ChatSection />))
    await user.click(screen.getByRole("button", { name: /Cerrar mensaje de error/i }))
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
    // Simulate a fresh error arriving.
    mocks.mockError.current = new Error("fetch failed")
    rerender(withQueryClient(<ChatSection />))
    expect(screen.getByRole("alert")).toBeInTheDocument()
  })
})
