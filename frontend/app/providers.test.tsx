import { describe, expect, it } from "vitest"
import { ApiError } from "@/lib/api"
import { worthAskingAgain } from "./providers"

describe("a failed read is asked again only when asking again could help", () => {
  it("A refusal is the server's answer, so it is not asked again", () => {
    const refused = new ApiError(
      422,
      "ValidationError",
      "a meta cannot already hold more than it costs",
    )

    expect(worthAskingAgain(0, refused)).toBe(false)
  })

  it("Every 4xx that is a decision is treated the same way", () => {
    for (const status of [400, 401, 403, 404, 409, 422]) {
      expect(worthAskingAgain(0, new ApiError(status, "E", "no"))).toBe(false)
    }
  })

  it("A timeout and a rate limit do get better on their own", () => {
    expect(worthAskingAgain(0, new ApiError(408, "Timeout", "slow"))).toBe(true)
    expect(worthAskingAgain(0, new ApiError(429, "TooMany", "wait"))).toBe(true)
  })

  it("A server error is worth one more try", () => {
    expect(worthAskingAgain(0, new ApiError(500, "Error", "boom"))).toBe(true)
    expect(worthAskingAgain(1, new ApiError(500, "Error", "boom"))).toBe(false)
  })

  it("Something that is not an answer at all — a dropped connection — is worth one more try", () => {
    expect(worthAskingAgain(0, new Error("Network Error"))).toBe(true)
    expect(worthAskingAgain(1, new Error("Network Error"))).toBe(false)
  })
})
