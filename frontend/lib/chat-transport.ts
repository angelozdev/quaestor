import { DefaultChatTransport, isTextUIPart } from "ai"
import { csrfHeaders } from "@/lib/csrf"

/**
 * Factory for the chat transport used by `useChat` in `ChatSection`.
 *
 * Returns a fresh `DefaultChatTransport` instance pointed at the backend
 * `POST /api/chat` SSE endpoint. The Next rewrite at `/api/[...path]/route.ts`
 * forwards the request to the FastAPI process with the session cookie
 * attached, so no auth header needs to be set here.
 *
 * Consumers MUST memoize the result (`useMemo(() => createChatTransport(), [])`)
 * to avoid recreating the transport on every render.
 *
 * Request body shape: the backend `ChatRequest` model
 * (backend/src/quaestor/api/chat.py) consumes
 * `{ messages: [{ role, content: string }], trigger }` — the OpenAI /
 * LiteLLM chat-completion shape. `useChat`'s default envelope is the
 * UIMessage shape `{ messages: [{ role, parts: [{ type, text }] }] }`,
 * which Pydantic would parse with `content=""`. We rewrite the body via
 * `prepareSendMessagesRequest` so the LLM actually sees the user's text.
 * See ADR-0015 for the rationale.
 */
export function createChatTransport() {
  return new DefaultChatTransport({
    api: "/api/chat",
    prepareSendMessagesRequest: ({ messages, trigger }) => ({
      body: {
        trigger,
        messages: messages.map((m) => {
          const textParts = m.parts.filter(isTextUIPart)
          if (textParts.length !== m.parts.length) {
            console.warn(
              "[chat] dropping non-text part(s) on outgoing request:",
              m.parts.filter((p) => !isTextUIPart(p)).map((p) => p.type),
            )
          }
          return {
            role: m.role,
            content: textParts.map((p) => p.text).join("\n"),
          }
        }),
      },
      headers: csrfHeaders(),
    }),
  })
}
