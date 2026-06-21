import { describe, expect, it, vi } from "vitest"
import { ApiError, applyApiErrorsToForm } from "./types"

describe("applyApiErrorsToForm", () => {
  it("calls setFieldMeta for each entry in ApiError.fields", () => {
    const setFieldMeta = vi.fn()
    const err = new ApiError(422, "ValidationError", "invalid", {
      amount: "must be > 0",
      interval_count: "must be > 0",
    })
    applyApiErrorsToForm({ setFieldMeta }, err)
    expect(setFieldMeta).toHaveBeenCalledTimes(2)
    expect(setFieldMeta).toHaveBeenCalledWith("amount", { error: "must be > 0" })
    expect(setFieldMeta).toHaveBeenCalledWith("interval_count", { error: "must be > 0" })
  })

  it("is a no-op when err is not an ApiError", () => {
    const setFieldMeta = vi.fn()
    applyApiErrorsToForm({ setFieldMeta }, new Error("boom"))
    applyApiErrorsToForm({ setFieldMeta }, "string error")
    applyApiErrorsToForm({ setFieldMeta }, null)
    applyApiErrorsToForm({ setFieldMeta }, undefined)
    expect(setFieldMeta).not.toHaveBeenCalled()
  })

  it("is a no-op when ApiError.fields is empty", () => {
    const setFieldMeta = vi.fn()
    const err = new ApiError(500, "Internal", "boom")
    applyApiErrorsToForm({ setFieldMeta }, err)
    expect(setFieldMeta).not.toHaveBeenCalled()
  })
})
