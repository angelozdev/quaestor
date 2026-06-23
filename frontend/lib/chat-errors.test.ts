import { describe, expect, it } from "vitest"
import { translateChatError } from "./chat-errors"

describe("translateChatError", () => {
  it("maps network failures to the offline copy", () => {
    expect(translateChatError(new Error("fetch failed"))).toBe(
      "No pudimos contactar al servidor",
    )
    expect(translateChatError(new TypeError("Failed to fetch"))).toBe(
      "No pudimos contactar al servidor",
    )
  })

  it("maps 413 / too-large messages to the length copy", () => {
    expect(translateChatError(new Error("message content exceeds 32 KB"))).toBe(
      "Tu mensaje es muy largo. Acórtalo e intenta de nuevo.",
    )
  })

  it("maps 422 validation errors to the reformulate copy", () => {
    const err = new Error("Unprocessable Entity")
    ;(err as Error & { status?: number }).status = 422
    expect(translateChatError(err)).toBe(
      "No pude procesar tu mensaje. Reformúlalo e intenta otra vez.",
    )
  })

  it("maps 429 rate-limit errors to the wait copy", () => {
    const err = new Error("Too Many Requests")
    ;(err as Error & { status?: number }).status = 429
    expect(translateChatError(err)).toBe(
      "Demasiadas solicitudes. Espera un momento e intenta de nuevo.",
    )
  })

  it("falls back to the generic copy on unknown errors", () => {
    expect(translateChatError(new Error("something exotic"))).toBe(
      "Algo salió mal. Vuelve a intentarlo en un momento.",
    )
  })
})
