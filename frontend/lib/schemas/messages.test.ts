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
