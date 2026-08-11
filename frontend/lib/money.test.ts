import { describe, expect, it } from "vitest"
import {
  amountForAccount,
  convertCents,
  currencyForAccount,
  currencyOf,
  formatCents,
  formatRate,
  impliedRate,
} from "./money"

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

describe("convertCents", () => {
  it("leaves a figure alone when the currency does not change", () => {
    expect(convertCents(40_000_000, "COP", "COP", null)).toBe(40_000_000)
  })

  it("restates pesos as dollars at the app's rate", () => {
    expect(convertCents(40_000_000, "COP", "USD", 4000)).toBe(10_000)
  })

  it("restates dollars as pesos at the app's rate", () => {
    expect(convertCents(10_000, "USD", "COP", 4000)).toBe(40_000_000)
  })

  it("offers nothing rather than a figure it invented when no rate is known", () => {
    expect(convertCents(40_000_000, "COP", "USD", null)).toBeNull()
    expect(convertCents(40_000_000, "COP", "USD", 0)).toBeNull()
    expect(convertCents(40_000_000, "COP", "USD", Number.NaN)).toBeNull()
  })

  it("offers nothing for a pair of currencies the single rate does not span", () => {
    expect(convertCents(100, "EUR", "COP", 4000)).toBeNull()
  })

  it("offers whole pesos, the only peso figure the app can hold", () => {
    expect(convertCents(155_604, "USD", "COP", 3142)).toBe(488_907_800)
  })

  it("keeps the cents of a dollar figure, which the app can hold", () => {
    expect(convertCents(27_500_000, "COP", "USD", 3142)).toBe(8_752)
  })
})

describe("amountForAccount", () => {
  it("keeps the figure when the account picked holds the same currency", () => {
    expect(amountForAccount({ cents: 42_000_000, currency: "COP" }, "COP", 4000)).toBe(42_000_000)
  })

  it("restates the figure in the currency the account picked holds", () => {
    expect(amountForAccount({ cents: 40_000_000, currency: "COP" }, "USD", 4000)).toBe(10_000)
  })

  it("has nothing to restate when no figure was written", () => {
    expect(amountForAccount({ cents: null, currency: "COP" }, "USD", 4000)).toBeNull()
  })

  it("hands back what was stated, however many currencies were passed through", () => {
    const tigo = { cents: 9_355_800, currency: "COP" }
    expect(amountForAccount(tigo, "USD", 4000)).toBe(2_339)
    expect(amountForAccount(tigo, "COP", 4000)).toBe(9_355_800)
  })
})

describe("currencyOf", () => {
  const accounts = [
    { id: 1, currency: "COP" },
    { id: 3, currency: "USD" },
  ]

  it("names the currency an account holds", () => {
    expect(currencyOf(accounts, 3)).toBe("USD")
  })

  it("falls back to pesos while the account is not known yet", () => {
    expect(currencyOf(undefined, 3)).toBe("COP")
    expect(currencyOf(accounts, null)).toBe("COP")
  })
})

describe("currencyForAccount", () => {
  const accounts = [
    { id: 1, currency: "COP" },
    { id: 3, currency: "USD" },
  ]
  const inDollars = { account_id: 3, currency: "USD" }

  it("reads the movement's own currency while it stays on its account", () => {
    expect(currencyForAccount(inDollars, undefined, 3)).toBe("USD")
  })

  it("reads the chosen account's currency once the movement moves", () => {
    expect(currencyForAccount(inDollars, accounts, 1)).toBe("COP")
  })

  it("has only the list to read when there is no movement yet", () => {
    expect(currencyForAccount(null, accounts, 3)).toBe("USD")
  })
})
