import { describe, expect, it } from "vitest"
import { formatCents, formatRate, impliedRate } from "./money"

describe("impliedRate", () => {
  it("is received over sent", () => {
    expect(impliedRate(10000, 40000000)).toBe(4000)
  })

  it("accepts any positive pair without judging the ratio", () => {
    expect(impliedRate(10000, 1)).toBe(0.0001)
  })

  it("is null while either amount is missing", () => {
    expect(impliedRate(null, 40000000)).toBeNull()
    expect(impliedRate(10000, null)).toBeNull()
    expect(impliedRate(Number.NaN, 40000000)).toBeNull()
  })

  it("is null for non-positive amounts", () => {
    expect(impliedRate(0, 40000000)).toBeNull()
    expect(impliedRate(10000, 0)).toBeNull()
    expect(impliedRate(-10000, 40000000)).toBeNull()
  })
})

describe("formatRate", () => {
  it("formats with two decimals in es-CO", () => {
    expect(formatRate(4000)).toBe("4.000,00")
  })
})

describe("formatCents", () => {
  it("formats COP without decimals", () => {
    expect(formatCents(4000000, "COP")).toBe("$ 40.000")
  })

  it("formats USD with two decimals", () => {
    expect(formatCents(1234, "USD")).toBe("US$ 12.34")
  })
})
