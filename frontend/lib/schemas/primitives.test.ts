import { describe, expect, it } from "vitest"
import {
  fxRate,
  intervalCount,
  isoDate,
  nonNegativeCents,
  optionalString,
  positiveCents,
  requiredString,
} from "./primitives"

describe("nonNegativeCents", () => {
  it("rejects negative", () => {
    expect(nonNegativeCents.safeParse(-1).success).toBe(false)
  })
  it("accepts zero", () => {
    expect(nonNegativeCents.safeParse(0).success).toBe(true)
  })
  it("accepts large positive", () => {
    expect(nonNegativeCents.safeParse(10_000_000).success).toBe(true)
  })
  it("rejects NaN", () => {
    expect(nonNegativeCents.safeParse(Number.NaN).success).toBe(false)
  })
})

describe("positiveCents", () => {
  it("rejects zero", () => {
    expect(positiveCents.safeParse(0).success).toBe(false)
  })
  it("rejects negative", () => {
    expect(positiveCents.safeParse(-100).success).toBe(false)
  })
  it("accepts 1", () => {
    expect(positiveCents.safeParse(1).success).toBe(true)
  })
})

describe("intervalCount", () => {
  it("rejects 0", () => {
    expect(intervalCount.safeParse(0).success).toBe(false)
  })
  it("rejects 1.5", () => {
    expect(intervalCount.safeParse(1.5).success).toBe(false)
  })
  it("rejects > 1000", () => {
    expect(intervalCount.safeParse(1001).success).toBe(false)
  })
  it("accepts 2", () => {
    expect(intervalCount.safeParse(2).success).toBe(true)
  })
})

describe("fxRate", () => {
  it("rejects 0", () => {
    expect(fxRate.safeParse(0).success).toBe(false)
  })
  it("rejects > 100000", () => {
    expect(fxRate.safeParse(100_001).success).toBe(false)
  })
  it("accepts 4150.5", () => {
    expect(fxRate.safeParse(4150.5).success).toBe(true)
  })
})

describe("isoDate", () => {
  it("accepts YYYY-MM-DD", () => {
    expect(isoDate.safeParse("2026-06-21").success).toBe(true)
  })
  it("rejects DD/MM/YYYY", () => {
    expect(isoDate.safeParse("21/06/2026").success).toBe(false)
  })
  it("rejects empty", () => {
    expect(isoDate.safeParse("").success).toBe(false)
  })
})

describe("requiredString", () => {
  it("rejects empty", () => {
    expect(requiredString.safeParse("").success).toBe(false)
  })
  it("rejects whitespace-only", () => {
    expect(requiredString.safeParse("   ").success).toBe(false)
  })
  it("accepts non-empty", () => {
    expect(requiredString.safeParse("Hola").success).toBe(true)
  })
})

describe("optionalString", () => {
  it("accepts undefined", () => {
    expect(optionalString.safeParse(undefined).success).toBe(true)
  })
  it("accepts empty string", () => {
    expect(optionalString.safeParse("").success).toBe(true)
  })
  it("accepts long string", () => {
    expect(optionalString.safeParse("a".repeat(500)).success).toBe(true)
  })
})
