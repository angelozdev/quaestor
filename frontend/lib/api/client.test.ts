import { describe, expect, it } from "vitest"
import { ApiError } from "./types"

describe("ApiError", () => {
  it("exposes fields when constructed with a fields map", () => {
    const err = new ApiError(422, "ValidationError", "invalid", {
      amount: "must be > 0",
    })
    expect(err.status).toBe(422)
    expect(err.code).toBe("ValidationError")
    expect(err.message).toBe("invalid")
    expect(err.fields).toEqual({ amount: "must be > 0" })
  })

  it("defaults fields to an empty object when omitted", () => {
    const err = new ApiError(500, "Internal", "boom")
    expect(err.fields).toEqual({})
  })

  it("matches the shape produced by the 422 backend response", () => {
    const err = new ApiError(
      422,
      "ValidationError",
      "amount: must be greater than 0; interval_count: must be greater than 0",
      {
        amount: "must be greater than 0",
        interval_count: "must be greater than 0",
      },
    )
    expect(err.fields.amount).toBe("must be greater than 0")
    expect(err.fields.interval_count).toBe("must be greater than 0")
  })
})
