// @vitest-environment node
import { describe, expect, it } from "vitest"
import { BufferedResponsePolicy } from "./buffered-response-policy"

describe("BufferedResponsePolicy", () => {
  it("awaits upstream text and returns it as body", async () => {
    const upstream = new Response('{"ok":true}', {
      status: 200,
      headers: { "content-type": "application/json" },
    })
    const policy = new BufferedResponsePolicy()
    const out = await policy.build(upstream)
    expect(out.status).toBe(200)
    expect(out.headers.get("content-type")).toBe("application/json")
    expect(await out.text()).toBe('{"ok":true}')
  })

  it("returns null body for 204", async () => {
    const upstream = new Response(null, { status: 204 })
    const policy = new BufferedResponsePolicy()
    const out = await policy.build(upstream)
    expect(out.status).toBe(204)
    expect(out.body).toBeNull()
  })

  it("returns null body for 304", async () => {
    const upstream = new Response(null, { status: 304 })
    const policy = new BufferedResponsePolicy()
    const out = await policy.build(upstream)
    expect(out.status).toBe(304)
    expect(out.body).toBeNull()
  })

  it("returns null body for 205", async () => {
    const upstream = new Response(null, { status: 205 })
    const policy = new BufferedResponsePolicy()
    const out = await policy.build(upstream)
    expect(out.status).toBe(205)
    expect(out.body).toBeNull()
  })

  it("forwards set-cookie headers", async () => {
    const upstream = new Response("body", {
      headers: [["set-cookie", "quaestor_csrf=tok; Path=/"]],
    })
    const policy = new BufferedResponsePolicy()
    const out = await policy.build(upstream)
    expect(out.headers.getSetCookie()).toEqual(["quaestor_csrf=tok; Path=/"])
  })
})
