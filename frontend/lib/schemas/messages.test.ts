import { describe, expect, it } from "vitest"
import { z } from "zod"
import { registerZodMessages } from "./messages"

describe("registerZodMessages", () => {
  it("overrides invalid_type for number with Solo números", () => {
    registerZodMessages()
    const schema = z.number({ invalid_type_error: "Solo números" })
    const result = schema.safeParse("abc")
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.issues[0].message).toBe("Solo números")
    }
  })
})

describe("registerZodMessages (global map)", () => {
  it("too_small on number fires 'Debe ser ≥ 1' via global map", () => {
    // Use a schema with NO chain-level message — the global map must fire.
    const result = z.number().min(1).safeParse(0)
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.issues[0].message).toBe("Debe ser ≥ 1")
    }
  })

  it("too_small on number ≥ 0 fires 'Debe ser ≥ 0' via global map", () => {
    const result = z.number().min(0).safeParse(-1)
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.issues[0].message).toBe("Debe ser ≥ 0")
    }
  })

  it("invalid_format fires 'Formato inválido'", () => {
    const result = z.string().email().safeParse("not-an-email")
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.issues[0].message).toBe("Formato inválido")
    }
  })

  it("too_big fires 'Valor demasiado grande'", () => {
    const result = z.number().max(10).safeParse(20)
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.issues[0].message).toBe("Valor demasiado grande")
    }
  })
})
