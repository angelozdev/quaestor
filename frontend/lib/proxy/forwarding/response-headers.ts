/**
 * Build the header set forwarded from the upstream backend to the outgoing
 * browser response. Copies content-type and every set-cookie value
 * (preserving multiplicity — Headers.getSetCookie returns the full array).
 *
 * Intentionally NOT forwarded:
 *  - `content-encoding`: undici has already decoded the upstream body,
 *    so the bytes handed to `Response` are plain. Forwarding the header
 *    would tell the browser the body is still compressed.
 *  - `content-length`: same reason — the byte count changes after
 *    decoding. `Response` sets the correct length itself.
 *  - `transfer-encoding`: same reason. Next/undici set this for chunked
 *    streaming when appropriate.
 */
export function forwardResponseHeaders(upstream: Response): Headers {
  const out = new Headers()
  const contentType = upstream.headers.get("content-type")
  if (contentType) out.set("content-type", contentType)
  for (const cookie of upstream.headers.getSetCookie()) {
    out.append("set-cookie", cookie)
  }
  return out
}
