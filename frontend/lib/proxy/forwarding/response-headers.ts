/**
 * Build the header set forwarded from the upstream backend to the outgoing
 * browser response. Copies content-type and every set-cookie value
 * (preserving multiplicity — Headers.getSetCookie returns the full array).
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
