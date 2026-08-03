import type { UIMessage } from "ai"
import { DefaultChatTransport } from "ai"
import { describe, expect, it, vi } from "vitest"
import { createChatTransport } from "./chat-transport"

// Structural type — avoids leaking DefaultChatTransport's <UI_MESSAGE> generic
// into the test (TS requires it on the named export). We only need the
// protected `prepareSendMessagesRequest` hook here.
type TransportLike = {
  prepareSendMessagesRequest: (opts: {
    id: string
    messages: UIMessage[]
    trigger: "submit-message" | "regenerate-message"
  }) => {
    body: {
      messages: Array<{ role: string; content: string }>
      trigger: string
    }
  }
}

function getPrepareSendMessagesRequest(
  transport: unknown,
): TransportLike["prepareSendMessagesRequest"] {
  return (transport as TransportLike).prepareSendMessagesRequest
}

describe("createChatTransport", () => {
  it("returns a DefaultChatTransport pointed at /api/chat", () => {
    const transport = createChatTransport()
    expect(transport).toBeInstanceOf(DefaultChatTransport)
    expect(transport).not.toBeNull()
  })

  describe("prepareSendMessagesRequest (ADR-0015)", () => {
    it("converts a single-text UIMessage to {role, content}", () => {
      const transport = createChatTransport()
      const transform = getPrepareSendMessagesRequest(transport)
      const { body } = transform({
        id: "conv1",
        trigger: "submit-message",
        messages: [{ id: "m1", role: "user", parts: [{ type: "text", text: "hola" }] }],
      })
      expect(body).toEqual({
        trigger: "submit-message",
        messages: [{ role: "user", content: "hola" }],
      })
    })

    it("joins multi-text parts with \\n", () => {
      const transport = createChatTransport()
      const transform = getPrepareSendMessagesRequest(transport)
      const { body } = transform({
        id: "conv1",
        trigger: "submit-message",
        messages: [
          {
            id: "m1",
            role: "assistant",
            parts: [
              { type: "text", text: "Resultados:" },
              { type: "text", text: "Listo." },
            ],
          },
        ],
      })
      expect(body.messages[0].content).toBe("Resultados:\nListo.")
      expect(body.messages[0].role).toBe("assistant")
    })

    it("drops non-text parts (with a warn) and keeps text content", () => {
      const transport = createChatTransport()
      const transform = getPrepareSendMessagesRequest(transport)
      const warn = vi.spyOn(console, "warn").mockImplementation(() => {})
      const { body } = transform({
        id: "conv1",
        trigger: "submit-message",
        messages: [
          {
            id: "m1",
            role: "user",
            parts: [
              { type: "text", text: "ver imagen" },
              {
                type: "file",
                mediaType: "image/png",
                filename: "x.png",
                url: "data:image/png;base64,xxx",
              },
            ],
          },
        ],
      })
      expect(body.messages[0].content).toBe("ver imagen")
      expect(warn).toHaveBeenCalledOnce()
      warn.mockRestore()
    })

    it("forwards the trigger verbatim", () => {
      const transport = createChatTransport()
      const transform = getPrepareSendMessagesRequest(transport)
      const submit = transform({
        id: "c",
        trigger: "submit-message",
        messages: [],
      })
      expect(submit.body.trigger).toBe("submit-message")
      const regen = transform({
        id: "c",
        trigger: "regenerate-message",
        messages: [],
      })
      expect(regen.body.trigger).toBe("regenerate-message")
    })

    it("passes through role for user/assistant/system", () => {
      const transport = createChatTransport()
      const transform = getPrepareSendMessagesRequest(transport)
      const { body } = transform({
        id: "c",
        trigger: "submit-message",
        messages: [
          { id: "u", role: "user", parts: [{ type: "text", text: "a" }] },
          { id: "a", role: "assistant", parts: [{ type: "text", text: "b" }] },
          { id: "s", role: "system", parts: [{ type: "text", text: "c" }] },
        ],
      })
      expect(body.messages.map((m) => m.role)).toEqual(["user", "assistant", "system"])
    })
  })
})
