import { forwardResponseHeaders } from "../forwarding/response-headers"
import type { ResponsePolicy } from "./response-policy"

const NO_BODY_STATUSES = new Set([204, 205, 304])

/**
 * Buffered strategy for discrete payloads (JSON, HTML, plain text). Reads
 * the full upstream body and returns it as a string. Status codes that
 * forbid a response body (204, 205, 304) are short-circuited to `null`.
 */
export class BufferedResponsePolicy implements ResponsePolicy {
  async build(upstream: Response): Promise<Response> {
    if (NO_BODY_STATUSES.has(upstream.status)) {
      return new Response(null, {
        status: upstream.status,
        headers: forwardResponseHeaders(upstream),
      })
    }
    const text = await upstream.text()
    return new Response(text, {
      status: upstream.status,
      headers: forwardResponseHeaders(upstream),
    })
  }
}
