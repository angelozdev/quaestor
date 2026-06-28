// @vitest-environment node
import { describe, expect, it } from "vitest"
import { forwardResponseHeaders } from "./response-headers"

describe("forwardResponseHeaders", () => {
  it("copies content-type from upstream", () => {
    const upstream = new Response("body", { headers: { "content-type": "application/json" } })
    const out = forwardResponseHeaders(upstream)
    expect(out.get("content-type")).toBe("application/json")
  })

  it("preserves every set-cookie value as separate header", () => {
    const upstream = new Response(null, {
      headers: [
        ["set-cookie", "quaestor_csrf=abc; Path=/"],
        ["set-cookie", "session=xyz; HttpOnly"],
      ],
    })
    const out = forwardResponseHeaders(upstream)
    const cookies = out.getSetCookie()
    expect(cookies).toEqual(["quaestor_csrf=abc; Path=/", "session=xyz; HttpOnly"])
  })

  it("returns empty Headers when upstream has no relevant headers", () => {
    // Use null body so Node's Response constructor doesn't auto-inject content-type: text/plain;charset=UTF-8 for string bodies.
    const upstream = new Response(null)
    const out = forwardResponseHeaders(upstream)
    expect(out.has("content-type")).toBe(false)
    expect(out.getSetCookie()).toEqual([])
  })
})
