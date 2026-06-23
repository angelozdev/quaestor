import { DefaultChatTransport } from "ai"

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
 */
export function createChatTransport() {
  return new DefaultChatTransport({ api: "/api/chat" })
}
