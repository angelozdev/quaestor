/**
 * Client-side CSRF support (QUA-A01-01).
 *
 * The backend's `CSRFMiddleware` requires the value of the non-HttpOnly
 * `quaestor_csrf` cookie to be echoed in the `X-CSRF-Token` request header
 * on every state-changing request. Because the cookie is non-HttpOnly, the
 * browser exposes it via `document.cookie`, and JavaScript can mirror it
 * into the header. The browser will not let a cross-origin attacker read
 * the cookie, so the header cannot be forged from another origin.
 *
 * Keep this module dependency-free so it can be imported from both the
 * axios client (browser) and the AI SDK chat transport (browser) without
 * pulling in React or any framework.
 */
export const CSRF_COOKIE_NAME = "quaestor_csrf"
export const CSRF_HEADER_NAME = "X-CSRF-Token"

export function getCsrfToken(): string {
  if (typeof document === "undefined") return ""
  for (const part of document.cookie.split(";")) {
    const [rawName, ...rest] = part.split("=")
    if (rawName && rawName.trim() === CSRF_COOKIE_NAME) {
      return decodeURIComponent(rest.join("=").trim())
    }
  }
  return ""
}

export function csrfHeaders(): Record<string, string> {
  const token = getCsrfToken()
  return token ? { [CSRF_HEADER_NAME]: token } : {}
}
