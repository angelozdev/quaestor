/**
 * Maps a raw `useChat` error to a small allowlist of es-CO user-facing
 * strings. The raw `error.message` is NEVER rendered verbatim — Pydantic
 * detail strings can leak schema internals (OWASP A02 information
 * disclosure). The raw error is still logged via `console.error` for
 * diagnostic purposes; the user only sees the translated copy.
 *
 * Errors carry `status` only when the transport layer attached it; many
 * fetch failures arrive as plain `Error` / `TypeError`, so message regex
 * is the primary discriminator.
 */
type WithStatus = { status?: number }

const NETWORK_RX = /fetch failed|Failed to fetch|NetworkError|ERR_NETWORK/i
const TOO_LARGE_RX = /exceeds.*KB|too large|413/i

export function translateChatError(error: Error): string {
  const status = (error as Error & WithStatus).status
  const msg = error.message ?? ""

  if (status === 413 || TOO_LARGE_RX.test(msg)) {
    return "Tu mensaje es muy largo. Acórtalo e intenta de nuevo."
  }
  if (status === 422) {
    return "No pude procesar tu mensaje. Reformúlalo e intenta otra vez."
  }
  if (status === 429) {
    return "Demasiadas solicitudes. Espera un momento e intenta de nuevo."
  }
  if (NETWORK_RX.test(msg)) {
    return "No pudimos contactar al servidor"
  }
  // Backend SSE error event surfaces as Error with errorText in message.
  if (msg.startsWith("errorText:") || /no pude completar/i.test(msg)) {
    return "No pude completar tu solicitud. Vuelve a intentarlo."
  }
  // Diagnostic log; never reaches the DOM.
  console.error("[chat] untranslated error:", error)
  return "Algo salió mal. Vuelve a intentarlo en un momento."
}
