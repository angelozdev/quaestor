import { forwardResponseHeaders } from "../forwarding/response-headers"
import type { ResponsePolicy } from "./response-policy"

/**
 * Pass-through strategy for streaming responses (SSE, text/*). Hands the
 * upstream `ReadableStream` directly to the outgoing `Response` so bytes
 * flow to the browser as the LLM emits them. Zero buffering. Status and
 * headers are forwarded via the response-headers module.
 */
export class StreamingResponsePolicy implements ResponsePolicy {
  async build(upstream: Response): Promise<Response> {
    return new Response(upstream.body, {
      status: upstream.status,
      headers: forwardResponseHeaders(upstream),
    })
  }
}
