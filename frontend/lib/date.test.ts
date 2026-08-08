import { describe, expect, it } from "vitest"
import { formatDate, hasEnded, isOverdue, monthNameOf, nextYearMonth } from "./date"

const NOON = new Date("2026-08-02T12:00:00")

describe("formatDate", () => {
  it("renders the wire date in the app-wide human format", () => {
    expect(formatDate("2026-05-10")).toBe("Sun, 10 May 2026")
  })
})

describe("isOverdue", () => {
  it("is false for today", () => {
    expect(isOverdue("2026-08-02", NOON)).toBe(false)
  })

  it("is true for yesterday", () => {
    expect(isOverdue("2026-08-01", NOON)).toBe(true)
  })
})

describe("hasEnded", () => {
  it("is false for an obligation with no end date", () => {
    expect(hasEnded(null, NOON)).toBe(false)
  })

  it("is false on the end date itself — it is a due date too", () => {
    expect(hasEnded("2026-08-02", NOON)).toBe(false)
  })

  it("is true the day after the end date", () => {
    expect(hasEnded("2026-08-01", NOON)).toBe(true)
  })
})

describe("nextYearMonth", () => {
  it("advances one month", () => {
    expect(nextYearMonth("2026-08")).toBe("2026-09")
  })

  it("rolls into the next year", () => {
    expect(nextYearMonth("2026-12")).toBe("2027-01")
  })
})

describe("monthNameOf", () => {
  it("names the month in Spanish, capitalized", () => {
    expect(monthNameOf("2026-09")).toBe("Septiembre")
  })

  it("names January of the following year", () => {
    expect(monthNameOf("2027-01")).toBe("Enero")
  })
})
