import type { NextRequest } from "next/server"

/**
 * Build the header set forwarded from the incoming request to the upstream
 * backend. Centralized here so the cross-proxy policy is a single source
 * of truth: cookie (session auth), x-csrf-token (CSRF double-submit
 * cookie, ADR-0020), authorization (APP_TOKEN fallback), content-type.
 * Other headers do not cross the boundary.
 *
 * `content-type` is forwarded for every method (including GET/HEAD) by
 * design — the orchestrator decides whether to send a request body. Some
 * clients attach `content-type` on GET for legacy reasons; FastAPI
 * ignores it. If you ever add `accept`/`accept-encoding` to this list,
 * note that the orchestrator does not negotiate compression upstream,
 * so `accept-encoding` from the client must NOT cross the boundary
 * (let undici negotiate directly).
 */
export function forwardRequestHeaders(req: NextRequest): Headers {
  const out = new Headers()
  const contentType = req.headers.get("content-type")
  if (contentType) out.set("content-type", contentType)
  const cookie = req.headers.get("cookie")
  if (cookie) out.set("cookie", cookie)
  const csrf = req.headers.get("x-csrf-token")
  if (csrf) out.set("x-csrf-token", csrf)
  const auth = req.headers.get("authorization")
  if (auth) out.set("authorization", auth)
  return out
}
