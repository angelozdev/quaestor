import { describe, expect, it } from "vitest"
import { BufferedResponsePolicy } from "./buffered-response-policy"
import { selectResponsePolicy } from "./select-response-policy"
import { StreamingResponsePolicy } from "./streaming-response-policy"

describe("selectResponsePolicy", () => {
  it("returns streaming for text/event-stream", () => {
    const u = new Response(null, { headers: { "content-type": "text/event-stream" } })
    expect(selectResponsePolicy(u)).toBeInstanceOf(StreamingResponsePolicy)
  })

  it("returns streaming for text/plain", () => {
    const u = new Response(null, { headers: { "content-type": "text/plain" } })
    expect(selectResponsePolicy(u)).toBeInstanceOf(StreamingResponsePolicy)
  })

  it("returns streaming for any text/* content-type", () => {
    const u = new Response(null, { headers: { "content-type": "text/html; charset=utf-8" } })
    expect(selectResponsePolicy(u)).toBeInstanceOf(StreamingResponsePolicy)
  })

  it("returns buffered for application/json", () => {
    const u = new Response(null, { headers: { "content-type": "application/json" } })
    expect(selectResponsePolicy(u)).toBeInstanceOf(BufferedResponsePolicy)
  })

  it("returns buffered when content-type is missing", () => {
    const u = new Response(null)
    expect(selectResponsePolicy(u)).toBeInstanceOf(BufferedResponsePolicy)
  })
})
