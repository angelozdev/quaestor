// @vitest-environment node

import { NextRequest } from "next/server"
import { describe, expect, it } from "vitest"
import { forwardRequestHeaders } from "./request-headers"

function req(headers: Record<string, string>): NextRequest {
  return new NextRequest(new Request("http://localhost/api/x", { headers }))
}

describe("forwardRequestHeaders", () => {
  it("copies content-type when present", () => {
    const out = forwardRequestHeaders(req({ "content-type": "application/json" }))
    expect(out.get("content-type")).toBe("application/json")
  })

  it("copies cookie when present", () => {
    const out = forwardRequestHeaders(req({ cookie: "session=abc" }))
    expect(out.get("cookie")).toBe("session=abc")
  })

  it("copies x-csrf-token when present", () => {
    const out = forwardRequestHeaders(req({ "x-csrf-token": "tok" }))
    expect(out.get("x-csrf-token")).toBe("tok")
  })

  it("copies authorization when present", () => {
    const out = forwardRequestHeaders(req({ authorization: "Bearer app-token" }))
    expect(out.get("authorization")).toBe("Bearer app-token")
  })

  it("omits headers that are absent", () => {
    const out = forwardRequestHeaders(req({}))
    expect(out.has("content-type")).toBe(false)
    expect(out.has("cookie")).toBe(false)
    expect(out.has("x-csrf-token")).toBe(false)
    expect(out.has("authorization")).toBe(false)
  })

  it("does not forward unrelated headers like x-custom", () => {
    const out = forwardRequestHeaders(req({ "x-custom": "drop-me" }))
    expect(out.has("x-custom")).toBe(false)
  })
})
