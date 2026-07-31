import { describe, expect, it } from "vitest"
import { setTrmSchema } from "./settings.schema"

describe("setTrmSchema", () => {
  it("accepts a single positive TRM value with no date", () => {
    const parsed = setTrmSchema.safeParse({ usdCop: 4150.5 })
    expect(parsed.success).toBe(true)
  })

  it("has no date field anymore", () => {
    expect(Object.keys(setTrmSchema.shape)).toEqual(["usdCop"])
  })

  it("rejects zero and negative values", () => {
    expect(setTrmSchema.safeParse({ usdCop: 0 }).success).toBe(false)
    expect(setTrmSchema.safeParse({ usdCop: -100 }).success).toBe(false)
  })
})
